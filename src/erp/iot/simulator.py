"""Synthetic IoT Sensor Stream Generator."""

import math
import random
from datetime import UTC, datetime

from erp.iot.telemetry_stream import WorkstationTelemetryFrame


class SyntheticTelemetrySimulator:
    """Generates realistic vibration, thermal, and motor power telemetry frames."""

    def __init__(self):
        self._step = 0

    def generate_frame(
        self,
        workstation_code: str = "WS-INJECTION-01",
        inject_anomaly: bool = False,
        inject_catastrophic: bool = False,
    ) -> WorkstationTelemetryFrame:
        """Generates a telemetry frame with sinusoidal variation and optional anomaly injection."""
        self._step += 1

        # Base nominal vibration ~ 1.8 mm/s + small noise
        base_vib = 1.8 + (0.4 * math.sin(self._step * 0.1)) + random.uniform(-0.1, 0.1)

        # Base nominal temperature ~ 52.0 C
        base_temp = 52.0 + (2.0 * math.sin(self._step * 0.05)) + random.uniform(-0.2, 0.2)

        # Base nominal power ~ 14.5 kW
        base_power = 14.5 + random.uniform(-0.5, 0.5)

        if inject_catastrophic:
            # Spike vibration above catastrophic limit 6.5 mm/s
            vibration = 7.2 + random.uniform(0.1, 0.5)
            temp = base_temp + 18.0
            power = base_power + 8.0
        elif inject_anomaly:
            # Degraded vibration above warning limit 4.5 mm/s
            vibration = 4.8 + random.uniform(0.1, 0.4)
            temp = base_temp + 8.5
            power = base_power + 3.0
        else:
            vibration = max(0.5, base_vib)
            temp = base_temp
            power = base_power

        return WorkstationTelemetryFrame(
            workstation_code=workstation_code,
            timestamp=datetime.now(UTC),
            vibration_rms_mm_s=round(vibration, 3),
            bearing_temp_c=round(temp, 2),
            motor_power_kw=round(power, 2),
            rpm=1800.0,
        )


telemetry_simulator = SyntheticTelemetrySimulator()
