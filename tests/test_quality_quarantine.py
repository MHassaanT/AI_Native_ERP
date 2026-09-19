"""Unit Tests for Edge Vision Quality Classification and Lot Quarantine."""

import uuid

import pytest

from erp.quality.defect_evaluator import quality_evaluator
from erp.quality.lot_quarantine import lot_quarantine_manager


class TestQualityAndQuarantine:
    """Tests edge defect classification and automated stock ledger lot quarantine."""

    def test_defect_confidence_over_98_triggers_plc_trip(self):
        eval_res = quality_evaluator.evaluate_inspection(
            inspection_id="INSP-001",
            item_code="FG-ENCLOSURE-IP67",
            lot_number="LOT-2026-A100",
            workstation_code="WS-QA-01",
            defect_type="SURFACE_CRACK",
            confidence_score=0.992,  # > 0.98
        )

        assert eval_res.is_defective is True
        assert eval_res.trigger_plc_scrap_trip is True

    def test_defect_confidence_under_98_does_not_trip_hardware(self):
        eval_res = quality_evaluator.evaluate_inspection(
            inspection_id="INSP-002",
            item_code="FG-ENCLOSURE-IP67",
            lot_number="LOT-2026-A101",
            workstation_code="WS-QA-01",
            defect_type="DIMENSIONAL_VARIANCE",
            confidence_score=0.88,  # < 0.98
        )

        assert eval_res.is_defective is True
        assert eval_res.trigger_plc_scrap_trip is False

    @pytest.mark.asyncio
    async def test_lot_quarantine_and_rolling_defect_pause(self):
        ws_code = "WS-QA-LINE-05"
        lot_no = "LOT-2026-CRITICAL-09"

        # Simulate 25 inspections with 2 defects (2/25 = 8% > 3% threshold)
        for i in range(23):
            clean = quality_evaluator.evaluate_inspection(
                inspection_id=f"INSP-{i}",
                item_code="FG-ENCLOSURE-IP67",
                lot_number=lot_no,
                workstation_code=ws_code,
                defect_type="NONE",
                confidence_score=0.0,
            )
            await lot_quarantine_manager.record_inspection_and_evaluate_quarantine(
                session=None,
                tenant_id=uuid.uuid4(),
                classification=clean,
            )

        # Inject 2 defective inspections with confidence > 0.98
        def1 = quality_evaluator.evaluate_inspection(
            inspection_id="INSP-DEF-1",
            item_code="FG-ENCLOSURE-IP67",
            lot_number=lot_no,
            workstation_code=ws_code,
            defect_type="SURFACE_CRACK",
            confidence_score=0.99,
        )
        res1 = await lot_quarantine_manager.record_inspection_and_evaluate_quarantine(
            session=None,
            tenant_id=uuid.uuid4(),
            classification=def1,
        )
        assert res1.is_quarantined is True

        def2 = quality_evaluator.evaluate_inspection(
            inspection_id="INSP-DEF-2",
            item_code="FG-ENCLOSURE-IP67",
            lot_number=lot_no,
            workstation_code=ws_code,
            defect_type="VOID",
            confidence_score=0.99,
        )
        res2 = await lot_quarantine_manager.record_inspection_and_evaluate_quarantine(
            session=None,
            tenant_id=uuid.uuid4(),
            classification=def2,
        )

        # Defect rate: 2 / 25 = 8.00% > 3.00% -> must pause machine!
        assert res2.rolling_defect_rate_percent >= 3.00
        assert res2.upstream_workstation_paused is True
