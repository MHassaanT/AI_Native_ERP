"""Stock Ledger Lot Quarantine and Upstation Workstation Pause (PRD §Quality Control)."""

import logging
import uuid
from collections import deque
from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from erp.db.models.manufacturing import Workstation
from erp.events.outbox import OutboxManager
from erp.quality.defect_evaluator import DefectClassification

logger = logging.getLogger(__name__)


class LotQuarantineResult(BaseModel):
    lot_number: str
    is_quarantined: bool
    rolling_defect_rate_percent: float
    upstream_workstation_paused: bool
    quarantine_reason: str


class LotQuarantineManager:
    """Manages inventory lot quarantines and asserts workstation pauses when defect rate > 3.0%."""

    DEFECT_RATE_PAUSE_THRESHOLD = 3.0  # 3.0% rolling window defect rate

    def __init__(self):
        # Workstation rolling window: list of (timestamp, is_defective)
        self._inspection_history: dict[str, deque[tuple[datetime, bool]]] = {}
        self.quarantined_lots: set[str] = set()

    async def record_inspection_and_evaluate_quarantine(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        classification: DefectClassification,
    ) -> LotQuarantineResult:
        """Records inspection, flags lot as QUARANTINED if defective, and halts machine if defect rate > 3%."""
        hist = self._inspection_history.setdefault(
            classification.workstation_code, deque(maxlen=1000)
        )
        hist.append((classification.timestamp, classification.is_defective))

        # Calculate rolling defect rate
        defects = sum(1 for _, is_def in hist if is_def)
        rate = (defects / len(hist)) * 100.0 if hist else 0.0

        quarantine_triggered = False
        pause_machine = False

        if classification.trigger_plc_scrap_trip:
            self.quarantined_lots.add(classification.lot_number)
            quarantine_triggered = True

            # Enqueue outbox event for Stock Ledger Lot Quarantine and update StockLevel in DB
            if session is not None:
                from erp.db.models.inventory import StockLevel

                stk_stmt = select(StockLevel).where(
                    StockLevel.tenant_id == tenant_id,
                    StockLevel.lot_number == classification.lot_number,
                )
                matching_stks = (await session.execute(stk_stmt)).scalars().all()
                for s in matching_stks:
                    s.is_quarantined = True

                await OutboxManager.enqueue_event(
                    session=session,
                    tenant_id=tenant_id,
                    aggregate_type="INVENTORY_LOT",
                    aggregate_id=classification.lot_number,
                    event_type="erp.inventory.lot_quarantined",
                    payload={
                        "lot_number": classification.lot_number,
                        "item_code": classification.item_code,
                        "workstation_code": classification.workstation_code,
                        "defect_type": classification.defect_type,
                        "confidence": classification.confidence_score,
                    },
                )
            logger.warning(
                "Lot %s QUARANTINED in Stock Ledger due to %s",
                classification.lot_number,
                classification.defect_type,
            )


        # Check 1-hour rolling defect rate threshold (3.0%)
        if rate > self.DEFECT_RATE_PAUSE_THRESHOLD and len(hist) >= 20:
            pause_machine = True
            # Update workstation status in DB if session provided
            if session is not None:
                ws_stmt = select(Workstation).where(
                    Workstation.tenant_id == tenant_id,
                    Workstation.workstation_code == classification.workstation_code,
                )
                ws = (await session.execute(ws_stmt)).scalar_one_or_none()
                if ws:
                    ws.status = "PAUSED_QUALITY_HOLD"

            logger.critical(
                "Workstation %s PAUSED: Rolling defect rate %.2f%% exceeded 3.0%% threshold!",
                classification.workstation_code,
                rate,
            )

        return LotQuarantineResult(
            lot_number=classification.lot_number,
            is_quarantined=quarantine_triggered
            or classification.lot_number in self.quarantined_lots,
            rolling_defect_rate_percent=round(rate, 2),
            upstream_workstation_paused=pause_machine,
            quarantine_reason=f"Defect {classification.defect_type} (Confidence: {classification.confidence_score:.2f})",
        )


lot_quarantine_manager = LotQuarantineManager()
