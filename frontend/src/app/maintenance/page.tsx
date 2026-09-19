"use client";

import { useEffect, useState } from "react";
import { ShieldCheck, Plus, RefreshCw, AlertCircle, CheckCircle2, Wrench, Radio, ArrowRight } from "lucide-react";
import { api } from "@/lib/api";

export default function MaintenancePage() {
  const [tickets, setTickets] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Telemetry Simulation State
  const [workstationCode, setWorkstationCode] = useState("WS-INJECTION-01");
  const [injectAnomaly, setInjectAnomaly] = useState(true);
  const [simulating, setSimulating] = useState(false);
  const [telemetryResult, setTelemetryResult] = useState<any | null>(null);

  // Manual Ticket Modal
  const [showModal, setShowModal] = useState(false);
  const [ticketNumber, setTicketNumber] = useState("");
  const [wsTarget, setWsTarget] = useState("WS-CNC-01");
  const [faultCode, setFaultCode] = useState("VIB-BEARING-DEGRADE");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState("HIGH");
  const [creating, setCreating] = useState(false);

  const loadTickets = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getTickets();
      setTickets(data);
    } catch (err: any) {
      setError(err.message || "Failed to load maintenance tickets from database.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTickets();
  }, []);

  const handleSimulateAndIngest = async () => {
    setSimulating(true);
    setError(null);
    try {
      // 1. Simulate reading
      const frame = await api.simulateTelemetry({
        workstation_code: workstationCode,
        inject_anomaly: injectAnomaly,
      });

      // 2. Ingest through predictive maintenance pipeline
      const plan = await api.ingestTelemetry(frame);
      setTelemetryResult({ frame, plan });
      await loadTickets();
    } catch (err: any) {
      setError(err.message || "IoT telemetry ingestion failed.");
    } finally {
      setSimulating(false);
    }
  };

  const handleUpdateStatus = async (ticketId: string, newStatus: string) => {
    try {
      await api.updateTicketStatus(ticketId, newStatus);
      await loadTickets();
    } catch (err: any) {
      setError(err.message || "Failed to update ticket status.");
    }
  };

  const handleCreateTicket = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreating(true);
    try {
      await api.createTicket({
        ticket_number: ticketNumber.trim(),
        workstation_code: wsTarget,
        trigger_type: "MANUAL",
        fault_code: faultCode,
        description: description.trim(),
        priority,
      });
      setShowModal(false);
      setTicketNumber("");
      setDescription("");
      await loadTickets();
    } catch (err: any) {
      setError(err.message || "Failed to create maintenance ticket.");
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between border-b border-cream-300 pb-5">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-cream-900">
            IoT Edge Telemetry & Predictive Maintenance
          </h1>
          <p className="text-xs text-cream-700 mt-1">
            Sensor telemetry stream (vibration RMS, bearing thermals) and automated corrective dispatch.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={loadTickets}
            disabled={loading}
            className="flex items-center gap-1.5 rounded-md border border-cream-300 bg-cream-100 px-3 py-1.5 text-xs font-medium text-cream-800 hover:bg-cream-200 transition-colors"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
            <span>Refresh</span>
          </button>
          <button
            onClick={() => setShowModal(true)}
            className="flex items-center gap-1.5 rounded-md border border-cream-300 bg-cream-100 px-3 py-1.5 text-xs font-medium text-cream-800 hover:bg-cream-200 transition-colors"
          >
            <Plus className="h-3.5 w-3.5" />
            <span>Log Maintenance Ticket</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-terracotta-50 border border-terracotta-500/30 text-terracotta-700 text-xs">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* IoT Simulation Panel */}
      <div className="rounded-xl border border-cream-300 bg-cream-100 p-5 shadow-xs space-y-4">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 border-b border-cream-300 pb-3">
          <div className="flex items-center gap-2">
            <Radio className="h-4 w-4 text-cream-800" />
            <h2 className="text-xs font-semibold text-cream-900">Edge Telemetry Signal Generator & Anomaly Detection</h2>
          </div>
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-1.5 text-xs text-cream-800 cursor-pointer">
              <input
                type="checkbox"
                checked={injectAnomaly}
                onChange={(e) => setInjectAnomaly(e.target.checked)}
                className="rounded border-cream-300 text-cream-900"
              />
              <span>Inject Bearing Degradation Anomaly (&ge;0.85 prob)</span>
            </label>
            <button
              onClick={handleSimulateAndIngest}
              disabled={simulating}
              className="rounded-md border border-cream-400 bg-cream-900 px-3 py-1.5 text-xs font-medium text-cream-50 hover:bg-cream-800 transition-colors disabled:opacity-50"
            >
              {simulating ? "Transmitting & Evaluating..." : "Stream Telemetry Frame"}
            </button>
          </div>
        </div>

        {telemetryResult && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono">
            <div className="rounded-lg border border-cream-300 bg-cream-50 p-3 space-y-1">
              <span className="font-semibold text-cream-900">Ingested Frame Telemetry:</span>
              <div>Vibration RMS: {telemetryResult.frame.vibration_rms_g}g</div>
              <div>Bearing Temp: {telemetryResult.frame.bearing_temperature_c}&deg;C</div>
              <div>Motor Power: {telemetryResult.frame.motor_current_amperes}A</div>
            </div>
            <div className={`rounded-lg border p-3 space-y-1 ${
              telemetryResult.plan.work_order_created
                ? "border-terracotta-500/30 bg-terracotta-50 text-terracotta-900"
                : "border-sage-500/30 bg-sage-50 text-sage-900"
            }`}>
              <span className="font-semibold">Action Plan Outcome:</span>
              <div>Failure Probability: {(telemetryResult.plan.failure_probability * 100).toFixed(1)}%</div>
              <div>Status: {telemetryResult.plan.alarm_summary}</div>
              {telemetryResult.plan.ticket_number && (
                <div className="font-bold">Maintenance Ticket Generated: {telemetryResult.plan.ticket_number}</div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Tickets List */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-cream-900">Maintenance Tickets (PostgreSQL)</h2>
          <span className="text-xs text-cream-600 font-mono">{tickets.length} tickets</span>
        </div>

        {tickets.length === 0 ? (
          <div className="rounded-xl border border-cream-300 bg-cream-100 p-8 text-center text-xs text-cream-600">
            No open or resolved maintenance tickets. Stream an anomaly frame above to trigger a ticket.
          </div>
        ) : (
          <div className="rounded-xl border border-cream-300 bg-cream-100 overflow-hidden shadow-xs">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-cream-300 bg-cream-200/60 text-cream-800 font-medium text-[11px]">
                  <th className="py-2.5 px-4">Ticket #</th>
                  <th className="py-2.5 px-4">Machine</th>
                  <th className="py-2.5 px-4">Trigger</th>
                  <th className="py-2.5 px-4">Fault Code</th>
                  <th className="py-2.5 px-4">Priority</th>
                  <th className="py-2.5 px-4">Status</th>
                  <th className="py-2.5 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-cream-200">
                {tickets.map((t) => (
                  <tr key={t.ticket_id} className="hover:bg-cream-50/50 transition-colors">
                    <td className="py-3 px-4 font-mono font-medium text-cream-900">{t.ticket_number}</td>
                    <td className="py-3 px-4 font-mono text-cream-800">{t.workstation_code}</td>
                    <td className="py-3 px-4 text-[11px] text-cream-600 font-mono">{t.trigger_type}</td>
                    <td className="py-3 px-4 text-[11px] font-mono text-cream-700">{t.fault_code || "N/A"}</td>
                    <td className="py-3 px-4">
                      <span className={`font-mono text-[10px] font-bold ${
                        t.priority === "CRITICAL" || t.priority === "HIGH" ? "text-terracotta-700" : "text-cream-700"
                      }`}>
                        {t.priority}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-mono font-semibold ${
                        t.status === "RESOLVED" || t.status === "CLOSED"
                          ? "bg-sage-100 text-sage-800 border border-sage-500/30"
                          : "bg-terracotta-100 text-terracotta-800 border border-terracotta-500/30"
                      }`}>
                        {t.status}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-right">
                      {t.status === "OPEN" && (
                        <button
                          onClick={() => handleUpdateStatus(t.ticket_id, "RESOLVED")}
                          className="rounded border border-sage-500/30 bg-sage-50 px-2.5 py-1 text-[11px] font-medium text-sage-800 hover:bg-sage-100"
                        >
                          Resolve Ticket
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Modal: Add Manual Ticket */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="w-full max-w-md rounded-xl border border-cream-300 bg-cream-100 p-6 shadow-lg space-y-4">
            <div className="flex items-center justify-between border-b border-cream-300 pb-3">
              <h3 className="font-semibold text-sm text-cream-900">Log Maintenance Ticket</h3>
              <button onClick={() => setShowModal(false)} className="text-cream-600 hover:text-cream-900 text-xs">
                Cancel
              </button>
            </div>

            <form onSubmit={handleCreateTicket} className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-cream-900 mb-1">Ticket Number</label>
                <input
                  type="text"
                  required
                  value={ticketNumber}
                  onChange={(e) => setTicketNumber(e.target.value)}
                  placeholder="e.g. TICKET-2026-081"
                  className="w-full rounded-lg border border-cream-300 bg-cream-50 px-3 py-1.5 text-xs text-cream-900 font-mono"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-cream-900 mb-1">Workstation</label>
                  <input
                    type="text"
                    required
                    value={wsTarget}
                    onChange={(e) => setWsTarget(e.target.value)}
                    className="w-full rounded-lg border border-cream-300 bg-cream-50 px-3 py-1.5 text-xs text-cream-900 font-mono"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-cream-900 mb-1">Priority</label>
                  <select
                    value={priority}
                    onChange={(e) => setPriority(e.target.value)}
                    className="w-full rounded-lg border border-cream-300 bg-cream-50 px-3 py-1.5 text-xs text-cream-900 font-mono"
                  >
                    <option value="LOW">LOW</option>
                    <option value="MEDIUM">MEDIUM</option>
                    <option value="HIGH">HIGH</option>
                    <option value="CRITICAL">CRITICAL</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-cream-900 mb-1">Fault Code</label>
                <input
                  type="text"
                  value={faultCode}
                  onChange={(e) => setFaultCode(e.target.value)}
                  placeholder="e.g. VIB-BEARING-DEGRADE"
                  className="w-full rounded-lg border border-cream-300 bg-cream-50 px-3 py-1.5 text-xs text-cream-900 font-mono"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-cream-900 mb-1">Description</label>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Describe observed equipment issue..."
                  className="w-full rounded-lg border border-cream-300 bg-cream-50 px-3 py-1.5 text-xs text-cream-900 h-16"
                />
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-cream-300">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="rounded-lg border border-cream-300 bg-cream-200 px-3 py-1.5 text-xs font-medium text-cream-800"
                >
                  Close
                </button>
                <button
                  type="submit"
                  disabled={creating}
                  className="rounded-lg border border-cream-400 bg-cream-900 px-3 py-1.5 text-xs font-medium text-cream-50 hover:bg-cream-800 disabled:opacity-50"
                >
                  {creating ? "Saving..." : "Create Ticket"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
