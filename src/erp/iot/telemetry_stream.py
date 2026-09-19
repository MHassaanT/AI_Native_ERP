"""IoT Sensor Telemetry Frame Ingestion (PRD §Equipment Maintenance)."""

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class WorkstationTelemetryFrame(BaseModel):
    workstation_code: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    vibration_rms_mm_s: float = Field(
        ..., description="Root Mean Square vibration velocity in mm/s"
    )
    bearing_temp_c: float = Field(..., description="Bearing surface temperature in Celsius")
    motor_power_kw: float = Field(..., description="Electrical power consumption in kW")
    rpm: float = Field(default=1800.0, description="Spindle or motor rotation speed")
