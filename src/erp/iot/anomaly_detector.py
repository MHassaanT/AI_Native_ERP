"""IoT Sensor Degradation and Anomaly Detection Engine (PRD §Equipment Maintenance)."""

import logging
from collections import deque
from datetime import datetime

from pydantic import BaseModel, Field

from erp.iot.telemetry_stream import WorkstationTelemetryFrame

logger = logging.getLogger(__name__)


class AnomalyEvaluationResult(BaseModel):
    workstation_code: str
    is_anomaly: bool
    failure_probability: float = Field(..., ge=0.0, le=1.0)
    vibration_rms: float
    bearing_temp_c: float
    temp_rate_c_per_hr: float
    is_catastrophic: bool = False
    alarm_reasons: list[str] = Field(default_factory=list)


class TelemetryAnomalyDetector:
    """Detects component degradation using vibration thresholds and thermal rise rates."""

    VIBRATION_WARNING_THRESHOLD = 4.5  # mm/s
    VIBRATION_CATASTROPHIC_THRESHOLD = 6.5  # mm/s
    TEMP_RISE_THRESHOLD_PER_HOUR = 2.0  # C / hour

    def __init__(self):
        # Rolling historical window per workstation: deque of (timestamp, temp)
        self._temp_history: dict[str, deque[tuple[datetime, float]]] = {}

    def evaluate_telemetry(self, frame: WorkstationTelemetryFrame) -> AnomalyEvaluationResult:
        """Evaluates vibration RMS and 6-hour thermal drift against statutory machine safety limits."""
        alarms = []
        prob = 0.05  # Base probability of failure under nominal conditions

        # 1. Vibration Analysis
        if frame.vibration_rms_mm_s >= self.VIBRATION_CATASTROPHIC_THRESHOLD:
            alarms.append(
                f"CATASTROPHIC_VIBRATION: {frame.vibration_rms_mm_s:.2f} mm/s exceeds limit {self.VIBRATION_CATASTROPHIC_THRESHOLD} mm/s"
            )
            prob = 0.99
        elif frame.vibration_rms_mm_s >= self.VIBRATION_WARNING_THRESHOLD:
            alarms.append(
                f"DEGRADATION_VIBRATION: {frame.vibration_rms_mm_s:.2f} mm/s exceeds threshold {self.VIBRATION_WARNING_THRESHOLD} mm/s"
            )
            prob = max(prob, 0.88)

        # 2. Thermal Drift Analysis (rate of temperature change)
        hist = self._temp_history.setdefault(frame.workstation_code, deque(maxlen=360))
        hist.append((frame.timestamp, frame.bearing_temp_c))

        temp_rate = 0.0
        if len(hist) > 1:
            t0, temp0 = hist[0]
            elapsed_hours = (frame.timestamp - t0).total_seconds() / 3600.0
            if elapsed_hours > 0.01:
                temp_rate = (frame.bearing_temp_c - temp0) / elapsed_hours
                if temp_rate >= self.TEMP_RISE_THRESHOLD_PER_HOUR:
                    alarms.append(
                        f"THERMAL_OVERLOAD: Bearing temp rise rate {temp_rate:.2f} C/hr exceeds {self.TEMP_RISE_THRESHOLD_PER_HOUR} C/hr"
                    )
                    prob = max(prob, 0.90)

        is_catastrophic = frame.vibration_rms_mm_s >= self.VIBRATION_CATASTROPHIC_THRESHOLD
        is_anomaly = len(alarms) > 0

        return AnomalyEvaluationResult(
            workstation_code=frame.workstation_code,
            is_anomaly=is_anomaly,
            failure_probability=round(prob, 2),
            vibration_rms=frame.vibration_rms_mm_s,
            bearing_temp_c=frame.bearing_temp_c,
            temp_rate_c_per_hr=round(temp_rate, 2),
            is_catastrophic=is_catastrophic,
            alarm_reasons=alarms,
        )


anomaly_detector = TelemetryAnomalyDetector()
