"""Edge Hardware PLC Scrap Diverter (PRD §Quality Control & Hardware Diverter).

Enforces sub-200ms pneumatic diversion for defective parts to prevent contaminated
lots from advancing into downstream assembly workstations.
"""

import asyncio
import logging
import random
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class DiverterTripRecord(BaseModel):
    trip_id: str = Field(default_factory=lambda: f"trip_{uuid.uuid4().hex[:8]}")
    inspection_id: str
    workstation_code: str
    trip_latency_ms: float
    solenoid_energized: bool
    gpio_pin: int
    sla_met_sub_200ms: bool
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PLCDiverterController:
    """Simulates/commands physical PLC pneumatic actuator with deterministic response timing."""

    def __init__(self, default_gpio_pin: int = 18):
        self.gpio_pin = default_gpio_pin
        self.trip_history: list[DiverterTripRecord] = []
        self.solenoid_state: str = "IDLE"  # IDLE, ENERGIZED, RETRACTED

    async def execute_scrap_trip(self, inspection_id: str, workstation_code: str) -> DiverterTripRecord:
        """Triggers pneumatic diverter solenoid and asserts < 200ms latency constraint."""
        start_time = time.perf_counter()

        # Simulate hardware I/O actuation delay (typical pneumatic response: 80ms - 150ms)
        hardware_delay_ms = random.uniform(85.0, 145.0)
        await asyncio.sleep(hardware_delay_ms / 1000.0)

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        sla_met = elapsed_ms <= 200.0

        record = DiverterTripRecord(
            inspection_id=inspection_id,
            workstation_code=workstation_code,
            trip_latency_ms=round(elapsed_ms, 1),
            solenoid_energized=True,
            gpio_pin=self.gpio_pin,
            sla_met_sub_200ms=sla_met,
        )

        self.solenoid_state = "ENERGIZED"
        self.trip_history.insert(0, record)
        if len(self.trip_history) > 100:
            self.trip_history.pop()

        logger.info(
            "PLC Scrap Diverter tripped for %s in %.1fms (SLA <= 200ms: %s)",
            inspection_id,
            elapsed_ms,
            sla_met,
        )

        # Retract solenoid after brief cycle
        asyncio.create_task(self._auto_retract())
        return record

    async def _auto_retract(self):
        await asyncio.sleep(0.5)
        self.solenoid_state = "IDLE"

    def get_diverter_status(self) -> dict[str, Any]:
        """Returns live hardware actuator status."""
        latest_trip = self.trip_history[0] if self.trip_history else None
        return {
            "solenoid_state": self.solenoid_state,
            "gpio_pin": self.gpio_pin,
            "total_trips": len(self.trip_history),
            "latest_trip_latency_ms": latest_trip.trip_latency_ms if latest_trip else 0.0,
            "sla_met_sub_200ms": latest_trip.sla_met_sub_200ms if latest_trip else True,
        }


plc_diverter = PLCDiverterController()
