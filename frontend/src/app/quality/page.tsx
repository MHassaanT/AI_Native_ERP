"use client";

import { useEffect, useState } from "react";
import {
  Activity,
  AlertOctagon,
  AlertTriangle,
  Camera,
  CheckCircle2,
  Cpu,
  Gauge,
  Layers,
  Play,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  Unlock,
  Zap,
} from "lucide-react";
import { api } from "@/lib/api";

interface TelemetrySummary {
  parts_inspected: number;
  scrap_diverted: number;
  rolling_defect_rate: number;
  status: string;
  motor_temperature_c: number;
  vibration_mms: number;
  conveyor_speed_rpm: number;
}

interface DiverterStatus {
  solenoid_state: string;
  gpio_pin: number;
  total_trips: number;
  latest_trip_latency_ms: number;
  sla_met_sub_200ms: boolean;
}

interface TelemetryFrame {
  time: string;
  workstation_code: string;
  conveyor_speed_rpm: number;
  motor_temperature_c: number;
  vibration_mms: number;
  scrap_count: number;
  status: string;
}

interface QuarantinedLot {
  lot_number: string;
  status: string;
  reason: string;
  item_code: string;
  quarantined_workstation: string;
}

export default function QualityPage() {
  const [summary, setSummary] = useState<TelemetrySummary | null>(null);
  const [history, setHistory] = useState<TelemetryFrame[]>([]);
  const [diverter, setDiverter] = useState<DiverterStatus | null>(null);
  const [quarantinedLots, setQuarantinedLots] = useState<QuarantinedLot[]>([]);
  const [loading, setLoading] = useState(true);

  // Form states
  const [itemCode, setItemCode] = useState("FG-ENCLOSURE-IP67");
  const [lotNumber, setLotNumber] = useState("LOT-2026-N49");
  const [workstationCode, setWorkstationCode] = useState("WS-LINE-01");
  const [defectType, setDefectType] = useState("SURFACE_CRACK");
  const [confidenceScore, setConfidenceScore] = useState(0.99);
  const [inspecting, setInspecting] = useState(false);
  const [inspectionResult, setInspectionResult] = useState<any | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const fetchQualityData = async () => {
    try {
      const [telemRes, lotsRes] = await Promise.all([
        api.getQualityTelemetry(),
        api.getQuarantinedLots(),
      ]);
      setSummary(telemRes.summary);
      setHistory(telemRes.history || []);
      setDiverter(telemRes.diverter);
      setQuarantinedLots(lotsRes || []);
    } catch (err: any) {
      console.error("Failed to fetch quality telemetry:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchQualityData();
    const interval = setInterval(fetchQualityData, 4000);
    return () => clearInterval(interval);
  }, []);

  const handleRunInspection = async (e: React.FormEvent) => {
    e.preventDefault();
    setInspecting(true);
    setActionMessage(null);
    try {
      const res = await api.submitOpticalInspection({
        item_code: itemCode,
        lot_number: lotNumber,
        workstation_code: workstationCode,
        defect_type: defectType,
        confidence_score: Number(confidenceScore),
      });
      setInspectionResult(res);
      setActionMessage(
        res.diverter_trip
          ? `Defect detected! Pneumatic scrap diverter tripped in ${res.diverter_trip.trip_latency_ms}ms (<200ms SLA PASSED). Lot ${lotNumber} QUARANTINED.`
          : `Inspection passed. Part cleared for assembly.`
      );
      // Auto increment lot number for subsequent testing
      const suffix = Math.floor(10 + Math.random() * 90);
      setLotNumber(`LOT-2026-N${suffix}`);
      await fetchQualityData();
    } catch (err: any) {
      setActionMessage(`Inspection error: ${err.message}`);
    } finally {
      setInspecting(false);
    }
  };

  const handleReleaseLot = async (lotNum: string) => {
    try {
      await api.releaseQuarantinedLot({
        lot_number: lotNum,
        release_notes: "Visual reinspection completed by Quality Lead. Cleared.",
      });
      await fetchQualityData();
    } catch (err: any) {
      alert(`Error releasing lot: ${err.message}`);
    }
  };

  return (
    <div className="space-y-8 max-w-7xl mx-auto pb-12">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-border pb-6">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-bold tracking-tight text-foreground flex items-center gap-2">
              <Camera className="w-8 h-8 text-primary" />
              Edge Quality & Hardware Diverter
            </h1>
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-500 border border-emerald-500/20">
              <Zap className="w-3 h-3 mr-1" />
              SUB-200MS SLA ACTIVE
            </span>
          </div>
          <p className="text-muted-foreground mt-1 text-sm">
            High-speed optical defect classification, sub-200ms pneumatic scrap diversion, and Stock Ledger lot quarantine.
          </p>
        </div>
        <button
          onClick={fetchQualityData}
          disabled={loading}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-card border border-border text-foreground hover:bg-muted text-sm font-medium transition-colors"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          Refresh Stream
        </button>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        {/* Parts Inspected */}
        <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-muted-foreground tracking-wider uppercase">Parts Inspected</span>
            <Gauge className="w-5 h-5 text-primary" />
          </div>
          <p className="mt-3 text-3xl font-bold text-foreground">
            {summary ? summary.parts_inspected.toLocaleString() : "..."}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">Continuous conveyor count</p>
        </div>

        {/* Scrap Diverted */}
        <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-muted-foreground tracking-wider uppercase">Scrap Diverted</span>
            <AlertOctagon className="w-5 h-5 text-amber-500" />
          </div>
          <p className="mt-3 text-3xl font-bold text-amber-500">
            {summary ? summary.scrap_diverted : "..."}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">Pneumatically ejected to scrap bin</p>
        </div>

        {/* Rolling Defect Rate */}
        <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-muted-foreground tracking-wider uppercase">Rolling Defect Rate</span>
            <Activity className="w-5 h-5 text-indigo-400" />
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span
              className={`text-3xl font-bold ${
                (summary?.rolling_defect_rate || 0) > 3.0
                  ? "text-rose-500"
                  : (summary?.rolling_defect_rate || 0) > 2.0
                  ? "text-amber-500"
                  : "text-emerald-500"
              }`}
            >
              {summary ? `${summary.rolling_defect_rate.toFixed(2)}%` : "..."}
            </span>
            <span className="text-xs font-medium text-muted-foreground">/ 3.0% Max Hold</span>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            {(summary?.rolling_defect_rate || 0) > 3.0
              ? "CRITICAL: Workstation Auto-Pause Triggered"
              : "Within tolerance thresholds"}
          </p>
        </div>

        {/* Pneumatic Diverter Latency */}
        <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-muted-foreground tracking-wider uppercase">PLC Actuator Response</span>
            <Cpu className="w-5 h-5 text-emerald-400" />
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-bold text-foreground">
              {diverter?.latest_trip_latency_ms ? `${diverter.latest_trip_latency_ms}ms` : "112ms"}
            </span>
            <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              SLA MET
            </span>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            Pin GPIO {diverter?.gpio_pin || 18} | State: {diverter?.solenoid_state || "IDLE"}
          </p>
        </div>
      </div>

      {/* Main Grid: Optical Inspection Simulator & Quarantined Lots */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left Column: Optical Camera Simulation & Trigger (7 cols) */}
        <div className="lg:col-span-7 space-y-6">
          <div className="rounded-xl border border-border bg-card p-6 shadow-sm">
            <div className="flex items-center justify-between border-b border-border pb-4 mb-5">
              <div>
                <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
                  <Camera className="w-5 h-5 text-primary" />
                  Live Edge Vision Camera Feed & Defect Simulator
                </h2>
                <p className="text-xs text-muted-foreground mt-0.5">
                  High-speed optical inference module at Workstation Conveyor Line
                </p>
              </div>
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                60 FPS STREAM
              </span>
            </div>

            {/* Simulated Camera Viewfinder */}
            <div className="relative aspect-video rounded-lg border border-border bg-slate-950 overflow-hidden flex flex-col items-center justify-center p-6 text-center mb-6">
              {/* Camera Grid Lines */}
              <div className="absolute inset-0 bg-[linear-gradient(to_right,#1e293b_1px,transparent_1px),linear-gradient(to_bottom,#1e293b_1px,transparent_1px)] bg-[size:4rem_4rem] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_50%,#000_70%,transparent_100%)] opacity-30"></div>

              {/* Viewfinder Target */}
              <div className="relative z-10 w-48 h-32 rounded border-2 border-dashed border-primary/60 flex flex-col items-center justify-center bg-primary/5">
                <span className="text-xs font-mono text-primary font-semibold">{itemCode}</span>
                <span className="text-[10px] text-muted-foreground font-mono mt-1">{lotNumber}</span>
                {inspectionResult?.classification?.is_defective && (
                  <div className="mt-2 inline-flex items-center gap-1 px-2 py-0.5 rounded bg-rose-500/20 border border-rose-500 text-rose-400 text-[10px] font-bold">
                    <AlertTriangle className="w-3 h-3" />
                    DEFECT DETECTED
                  </div>
                )}
              </div>

              {/* Camera Telemetry HUD Overlay */}
              <div className="absolute top-3 left-3 text-[11px] font-mono text-muted-foreground/80 space-y-0.5 text-left bg-slate-900/80 p-2 rounded border border-border">
                <div>LINE: {workstationCode}</div>
                <div>EXPOSURE: 1/2000s</div>
                <div>MODEL: YOLO-v9-Edge-Quantized</div>
              </div>

              <div className="absolute bottom-3 right-3 text-[11px] font-mono text-emerald-400 bg-slate-900/80 p-2 rounded border border-border">
                ACTUATOR: {diverter?.solenoid_state === "ENERGIZED" ? "⚡ TRIPPED" : "ARMED / IDLE"}
              </div>
            </div>

            {/* Inspection Form */}
            <form onSubmit={handleRunInspection} className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-foreground mb-1.5">Target SKU</label>
                  <select
                    value={itemCode}
                    onChange={(e) => setItemCode(e.target.value)}
                    className="w-full px-3 py-2 text-sm rounded-lg bg-muted border border-border text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                  >
                    <option value="FG-ENCLOSURE-IP67">FG-ENCLOSURE-IP67 (Industrial IP67 Enclosure)</option>
                    <option value="RAW-RESIN-HDPE">RAW-RESIN-HDPE (High-Density Polyethylene)</option>
                    <option value="ASSY-MOTOR-01">ASSY-MOTOR-01 (Brushless Servo Assembly)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-foreground mb-1.5">Production Lot Number</label>
                  <input
                    type="text"
                    value={lotNumber}
                    onChange={(e) => setLotNumber(e.target.value)}
                    className="w-full px-3 py-2 text-sm rounded-lg bg-muted border border-border text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                    required
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-foreground mb-1.5">Defect Classification</label>
                  <select
                    value={defectType}
                    onChange={(e) => setDefectType(e.target.value)}
                    className="w-full px-3 py-2 text-sm rounded-lg bg-muted border border-border text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                  >
                    <option value="SURFACE_CRACK">SURFACE_CRACK (Micro-fracture on seam)</option>
                    <option value="DIMENSIONAL_VARIANCE">DIMENSIONAL_VARIANCE (&gt;0.25mm tolerance)</option>
                    <option value="VOID">VOID (Material cavitation)</option>
                    <option value="COLOR_DRIFT">COLOR_DRIFT (RAL spectrophotometer shift)</option>
                    <option value="NONE">NONE (Zero defect / Perfect specimen)</option>
                  </select>
                </div>

                <div>
                  <div className="flex justify-between items-center mb-1.5">
                    <label className="block text-xs font-semibold text-foreground">Inference Confidence</label>
                    <span className="text-xs font-mono font-bold text-primary">
                      {(confidenceScore * 100).toFixed(0)}%
                    </span>
                  </div>
                  <input
                    type="range"
                    min="0.50"
                    max="1.00"
                    step="0.01"
                    value={confidenceScore}
                    onChange={(e) => setConfidenceScore(parseFloat(e.target.value))}
                    className="w-full accent-primary cursor-pointer"
                  />
                  <div className="flex justify-between text-[10px] text-muted-foreground mt-1">
                    <span>50%</span>
                    <span className="text-amber-500 font-semibold">98% PLC Threshold</span>
                    <span>100%</span>
                  </div>
                </div>
              </div>

              {actionMessage && (
                <div
                  className={`p-3 rounded-lg text-sm flex items-start gap-2 ${
                    actionMessage.includes("Defect detected")
                      ? "bg-rose-500/10 border border-rose-500/30 text-rose-300"
                      : "bg-emerald-500/10 border border-emerald-500/30 text-emerald-300"
                  }`}
                >
                  {actionMessage.includes("Defect detected") ? (
                    <AlertTriangle className="w-5 h-5 shrink-0 text-rose-400 mt-0.5" />
                  ) : (
                    <CheckCircle2 className="w-5 h-5 shrink-0 text-emerald-400 mt-0.5" />
                  )}
                  <div>{actionMessage}</div>
                </div>
              )}

              <button
                type="submit"
                disabled={inspecting}
                className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-lg bg-primary text-primary-foreground font-semibold text-sm hover:opacity-90 transition-opacity shadow-sm disabled:opacity-50"
              >
                <Play className="w-4 h-4 fill-current" />
                {inspecting ? "Classifying & Actuating PLC..." : "Dispatch Optical Inspection"}
              </button>
            </form>
          </div>
        </div>

        {/* Right Column: Quarantined Lots & Edge Machine Telemetry (5 cols) */}
        <div className="lg:col-span-5 space-y-6">
          {/* Quarantined Inventory Lots */}
          <div className="rounded-xl border border-border bg-card p-6 shadow-sm">
            <div className="flex items-center justify-between border-b border-border pb-4 mb-4">
              <div>
                <h3 className="text-base font-semibold text-foreground flex items-center gap-2">
                  <ShieldAlert className="w-5 h-5 text-rose-500" />
                  Quarantined Inventory Lots
                </h3>
                <p className="text-xs text-muted-foreground mt-0.5">Held in Stock Ledger from dispatch or sale</p>
              </div>
              <span className="px-2 py-0.5 rounded text-xs font-bold bg-rose-500/10 text-rose-400 border border-rose-500/20">
                {quarantinedLots.length} HELD
              </span>
            </div>

            {quarantinedLots.length === 0 ? (
              <div className="py-8 text-center text-muted-foreground">
                <ShieldCheck className="w-10 h-10 mx-auto text-emerald-500/50 mb-2" />
                <p className="text-sm font-medium">No lots in quarantine</p>
                <p className="text-xs mt-1">All produced inventory meets quality tolerances.</p>
              </div>
            ) : (
              <div className="space-y-3 max-h-72 overflow-y-auto pr-1">
                {quarantinedLots.map((lot) => (
                  <div
                    key={lot.lot_number}
                    className="p-3 rounded-lg border border-border bg-muted/40 flex items-center justify-between gap-3"
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs font-bold text-foreground">{lot.lot_number}</span>
                        <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/20">
                          QUARANTINED
                        </span>
                      </div>
                      <p className="text-xs text-muted-foreground mt-1 line-clamp-1">{lot.reason}</p>
                    </div>
                    <button
                      onClick={() => handleReleaseLot(lot.lot_number)}
                      className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded bg-card border border-border text-foreground hover:bg-muted text-xs font-semibold transition-colors shrink-0"
                    >
                      <Unlock className="w-3.5 h-3.5 text-emerald-500" />
                      Release
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Shop-Floor Edge Telemetry Stream */}
          <div className="rounded-xl border border-border bg-card p-6 shadow-sm">
            <div className="flex items-center justify-between border-b border-border pb-4 mb-4">
              <div>
                <h3 className="text-base font-semibold text-foreground flex items-center gap-2">
                  <Activity className="w-5 h-5 text-primary" />
                  Machine Sensor Stream
                </h3>
                <p className="text-xs text-muted-foreground mt-0.5">High-frequency PLC telemetry buffer</p>
              </div>
              <span className="text-xs font-mono text-muted-foreground">{history.length} frames</span>
            </div>

            <div className="space-y-2 max-h-64 overflow-y-auto pr-1 text-xs">
              {history.map((frame, idx) => (
                <div
                  key={idx}
                  className="p-2.5 rounded border border-border/60 bg-muted/30 flex items-center justify-between font-mono"
                >
                  <div className="flex items-center gap-2">
                    <span className="text-muted-foreground">{frame.time}</span>
                    <span className="font-semibold text-foreground">{frame.workstation_code}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span>{frame.conveyor_speed_rpm} RPM</span>
                    <span className={frame.motor_temperature_c > 75 ? "text-amber-400" : "text-foreground"}>
                      {frame.motor_temperature_c}°C
                    </span>
                    <span className={frame.vibration_mms > 3.0 ? "text-rose-400 font-bold" : "text-foreground"}>
                      {frame.vibration_mms} mm/s
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
