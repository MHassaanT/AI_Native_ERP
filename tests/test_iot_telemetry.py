"""Unit Tests for IoT Sensor Telemetry and Degradation Anomaly Detection."""

from datetime import UTC, datetime, timedelta

from erp.iot.anomaly_detector import anomaly_detector
from erp.iot.simulator import telemetry_simulator
from erp.iot.telemetry_stream import WorkstationTelemetryFrame


class TestIoTTelemetryAndAnomalies:
    """Tests sensor degradation rules and thermal drift tracking."""

    def test_nominal_telemetry_produces_no_alarms(self):
        frame = WorkstationTelemetryFrame(
            workstation_code="WS-TEST-01",
            vibration_rms_mm_s=1.85,
            bearing_temp_c=52.4,
            motor_power_kw=14.2,
        )
        res = anomaly_detector.evaluate_telemetry(frame)

        assert res.is_anomaly is False
        assert res.failure_probability < 0.20
        assert res.is_catastrophic is False
        assert len(res.alarm_reasons) == 0

    def test_vibration_above_threshold_triggers_degradation_alarm(self):
        # Vibration 5.1 mm/s exceeds warning limit 4.5 mm/s
        frame = WorkstationTelemetryFrame(
            workstation_code="WS-TEST-02",
            vibration_rms_mm_s=5.10,
            bearing_temp_c=56.0,
            motor_power_kw=16.0,
        )
        res = anomaly_detector.evaluate_telemetry(frame)

        assert res.is_anomaly is True
        assert res.failure_probability >= 0.85  # PRD horizon threshold
        assert any("DEGRADATION_VIBRATION" in a for a in res.alarm_reasons)

    def test_catastrophic_vibration_triggers_emergency_lockout(self):
        # Vibration 7.2 mm/s exceeds catastrophic limit 6.5 mm/s
        frame = WorkstationTelemetryFrame(
            workstation_code="WS-TEST-03",
            vibration_rms_mm_s=7.20,
            bearing_temp_c=68.0,
            motor_power_kw=22.0,
        )
        res = anomaly_detector.evaluate_telemetry(frame)

        assert res.is_anomaly is True
        assert res.is_catastrophic is True
        assert res.failure_probability >= 0.98
        assert any("CATASTROPHIC_VIBRATION" in a for a in res.alarm_reasons)

    def test_thermal_overload_drift_detection(self):
        ws_code = "WS-TEST-THERMAL"
        t0 = datetime.now(UTC) - timedelta(hours=2)
        frame_past = WorkstationTelemetryFrame(
            workstation_code=ws_code,
            timestamp=t0,
            vibration_rms_mm_s=2.0,
            bearing_temp_c=50.0,
            motor_power_kw=14.0,
        )
        anomaly_detector.evaluate_telemetry(frame_past)

        # 2 hours later, temp increased from 50.0 to 57.0 (+7.0 C over 2 hrs = 3.5 C/hr > 2.0 C/hr)
        t_now = datetime.now(UTC)
        frame_now = WorkstationTelemetryFrame(
            workstation_code=ws_code,
            timestamp=t_now,
            vibration_rms_mm_s=2.0,
            bearing_temp_c=57.0,
            motor_power_kw=15.0,
        )
        res = anomaly_detector.evaluate_telemetry(frame_now)

        assert res.is_anomaly is True
        assert res.temp_rate_c_per_hr >= 2.0
        assert any("THERMAL_OVERLOAD" in a for a in res.alarm_reasons)

    def test_telemetry_simulator_generates_valid_frames(self):
        frame = telemetry_simulator.generate_frame(
            workstation_code="WS-INJECTION-01",
            inject_anomaly=False,
        )
        assert frame.workstation_code == "WS-INJECTION-01"
        assert 0.0 < frame.vibration_rms_mm_s < 4.5
        assert 40.0 < frame.bearing_temp_c < 70.0
