"use client";

import { useEffect, useState } from "react";
import {
  Wrench,
  Calendar,
  Clock,
  CheckCircle2,
  AlertCircle,
  Plus,
  RefreshCw,
  Radio,
  ArrowRight,
  ShieldCheck,
  Cpu,
  Layers,
  Activity,
  Zap,
} from "lucide-react";
import { api } from "@/lib/api";

type TabType = "schedules" | "visits" | "iot";

export default function MaintenancePage() {
  const [activeTab, setActiveTab] = useState<TabType>("schedules");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Schedules state
  const [schedules, setSchedules] = useState<any[]>([]);
  const [showScheduleModal, setShowScheduleModal] = useState(false);
  const [schedNumber, setSchedNumber] = useState("");
  const [schedAssetId, setSchedAssetId] = useState("");
  const [schedItemCode, setSchedItemCode] = useState("");
  const [schedPeriodicity, setSchedPeriodicity] = useState("MONTHLY");
  const [schedStartDate, setSchedStartDate] = useState(new Date().toISOString().split("T")[0]);
  const [schedEndDate, setSchedEndDate] = useState("");
  const [schedTaskDesc, setSchedTaskDesc] = useState("Routine Periodic Inspection & Servicing");
  const [creatingSchedule, setCreatingSchedule] = useState(false);

  // Visits state
  const [visits, setVisits] = useState<any[]>([]);
  const [showVisitModal, setShowVisitModal] = useState(false);
  const [visitNumber, setVisitNumber] = useState("");
  const [visitAssetId, setVisitAssetId] = useState("");
  const [visitScheduleId, setVisitScheduleId] = useState("");
  const [visitType, setVisitType] = useState("PREVENTIVE");
  const [visitTechnician, setVisitTechnician] = useState("");
  const [visitDowntime, setVisitDowntime] = useState("0");
  const [visitParts, setVisitParts] = useState("");
  const [visitRemarks, setVisitRemarks] = useState("");
  const [creatingVisit, setCreatingVisit] = useState(false);

  // IoT / Tickets state
  const [tickets, setTickets] = useState<any[]>([]);
  const [workstationCode, setWorkstationCode] = useState("WS-INJECTION-01");
  const [injectAnomaly, setInjectAnomaly] = useState(true);
  const [simulating, setSimulating] = useState(false);
  const [telemetryResult, setTelemetryResult] = useState<any | null>(null);
  const [showTicketModal, setShowTicketModal] = useState(false);
  const [ticketNumber, setTicketNumber] = useState("");
  const [wsTarget, setWsTarget] = useState("WS-CNC-01");
  const [faultCode, setFaultCode] = useState("VIB-BEARING-DEGRADE");
  const [ticketDescription, setTicketDescription] = useState("");
  const [ticketPriority, setTicketPriority] = useState("HIGH");
  const [creatingTicket, setCreatingTicket] = useState(false);

  // Assets list for dropdowns
  const [assets, setAssets] = useState<any[]>([]);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [schedRes, visitRes, ticketRes, assetRes] = await Promise.allSettled([
        api.getMaintenanceSchedules(),
        api.getMaintenanceVisits(),
        api.getTickets(),
        api.getAssets ? api.getAssets() : Promise.resolve([]),
      ]);

      if (schedRes.status === "fulfilled") setSchedules(schedRes.value || []);
      if (visitRes.status === "fulfilled") setVisits(visitRes.value || []);
      if (ticketRes.status === "fulfilled") setTickets(ticketRes.value || []);
      if (assetRes.status === "fulfilled") setAssets(assetRes.value || []);
    } catch (err: any) {
      setError(err.message || "Failed to load maintenance records.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  // --- Handlers: Schedules ---
  const handleCreateSchedule = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreatingSchedule(true);
    setError(null);
    try {
      await api.createMaintenanceSchedule({
        schedule_number: schedNumber.trim() || undefined,
        task_description: schedTaskDesc.trim() || "Routine Periodic Inspection & Servicing",
        asset_id: schedAssetId || undefined,
        item_code: schedItemCode.trim() || undefined,
        periodicity: schedPeriodicity,
        start_date: schedStartDate,
        end_date: schedEndDate || undefined,
        status: "ACTIVE",
      });
      setShowScheduleModal(false);
      setSchedNumber("");
      setSchedAssetId("");
      setSchedItemCode("");
      await loadData();
    } catch (err: any) {
      setError(err.message || "Failed to create maintenance schedule.");
    } finally {
      setCreatingSchedule(false);
    }
  };

  // --- Handlers: Visits ---
  const handleCreateVisit = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreatingVisit(true);
    setError(null);
    try {
      let partsList: any[] = [];
      if (visitParts.trim()) {
        try {
          partsList = JSON.parse(visitParts);
        } catch {
          partsList = [{ item_code: visitParts.trim(), qty: 1 }];
        }
      }

      await api.createMaintenanceVisit({
        visit_number: visitNumber.trim() || undefined,
        tasks_performed: visitRemarks.trim() || "Routine Maintenance Service",
        maintenance_schedule_id: visitScheduleId || undefined,
        schedule_id: visitScheduleId || undefined,
        asset_id: visitAssetId || undefined,
        maintenance_type: visitType,
        technician: visitTechnician.trim(),
        technician_name: visitTechnician.trim(),
        downtime_hours: parseFloat(visitDowntime) || 0,
        parts_replaced: partsList,
        completion_remarks: visitRemarks.trim() || undefined,
        status: "COMPLETED",
      });
      setShowVisitModal(false);
      setVisitNumber("");
      setVisitAssetId("");
      setVisitScheduleId("");
      setVisitTechnician("");
      setVisitDowntime("0");
      setVisitParts("");
      setVisitRemarks("");
      await loadData();
    } catch (err: any) {
      setError(err.message || "Failed to record maintenance visit.");
    } finally {
      setCreatingVisit(false);
    }
  };

  // --- Handlers: IoT ---
  const handleSimulateAndIngest = async () => {
    setSimulating(true);
    setError(null);
    try {
      const frame = await api.simulateTelemetry({
        workstation_code: workstationCode,
        inject_anomaly: injectAnomaly,
      });
      const plan = await api.ingestTelemetry(frame);
      setTelemetryResult({ frame, plan });
      const t = await api.getTickets();
      setTickets(t);
    } catch (err: any) {
      setError(err.message || "IoT telemetry ingestion failed.");
    } finally {
      setSimulating(false);
    }
  };

  const handleUpdateTicketStatus = async (ticketId: string, newStatus: string) => {
    try {
      await api.updateTicketStatus(ticketId, newStatus);
      const t = await api.getTickets();
      setTickets(t);
    } catch (err: any) {
      setError(err.message || "Failed to update ticket status.");
    }
  };

  const handleCreateTicket = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreatingTicket(true);
    try {
      await api.createTicket({
        ticket_number: ticketNumber.trim(),
        workstation_code: wsTarget,
        trigger_type: "MANUAL",
        fault_code: faultCode,
        description: ticketDescription.trim(),
        priority: ticketPriority,
      });
      setShowTicketModal(false);
      setTicketNumber("");
      setTicketDescription("");
      const t = await api.getTickets();
      setTickets(t);
    } catch (err: any) {
      setError(err.message || "Failed to create maintenance ticket.");
    } finally {
      setCreatingTicket(false);
    }
  };

  const activeSchedulesCount = schedules.filter((s) => s.status === "ACTIVE").length;
  const completedVisitsCount = visits.filter((v) => v.status === "COMPLETED").length;
  const openTicketsCount = tickets.filter((t) => t.status === "OPEN" || t.status === "IN_PROGRESS").length;

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between border-b border-cream-300 pb-5">
        <div>
          <h1 className="text-2xl font-serif font-bold text-cream-900 tracking-tight flex items-center gap-2">
            <Wrench className="w-6 h-6 text-cream-700" />
            Maintenance & Service Suite
          </h1>
          <p className="text-sm text-cream-600 mt-1">
            Preventive schedules, service dispatch logs, downtime analytics, and IoT predictive monitoring.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={loadData}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-2 text-xs font-medium text-cream-700 bg-white border border-cream-300 rounded hover:bg-cream-50 transition"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>
          {activeTab === "schedules" && (
            <button
              onClick={() => setShowScheduleModal(true)}
              className="flex items-center gap-1.5 px-3.5 py-2 text-xs font-medium text-white bg-cream-800 rounded hover:bg-cream-900 transition shadow-sm"
            >
              <Plus className="w-4 h-4" />
              New Schedule
            </button>
          )}
          {activeTab === "visits" && (
            <button
              onClick={() => setShowVisitModal(true)}
              className="flex items-center gap-1.5 px-3.5 py-2 text-xs font-medium text-white bg-cream-800 rounded hover:bg-cream-900 transition shadow-sm"
            >
              <Plus className="w-4 h-4" />
              Log Visit / Dispatch
            </button>
          )}
          {activeTab === "iot" && (
            <button
              onClick={() => setShowTicketModal(true)}
              className="flex items-center gap-1.5 px-3.5 py-2 text-xs font-medium text-white bg-cream-800 rounded hover:bg-cream-900 transition shadow-sm"
            >
              <Plus className="w-4 h-4" />
              New Manual Ticket
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded text-sm text-red-700 flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="text-red-500 hover:text-red-700 text-xs">Dismiss</button>
        </div>
      )}

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white p-4 rounded border border-cream-300 shadow-sm">
          <div className="flex items-center justify-between text-cream-500 mb-1">
            <span className="text-xs uppercase font-medium">Active Schedules</span>
            <Calendar className="w-4 h-4 text-cream-700" />
          </div>
          <div className="text-2xl font-serif font-bold text-cream-900">{activeSchedulesCount}</div>
          <div className="text-xs text-cream-500 mt-1">Periodic preventive routines</div>
        </div>

        <div className="bg-white p-4 rounded border border-cream-300 shadow-sm">
          <div className="flex items-center justify-between text-cream-500 mb-1">
            <span className="text-xs uppercase font-medium">Completed Visits</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
          </div>
          <div className="text-2xl font-serif font-bold text-emerald-700">{completedVisitsCount}</div>
          <div className="text-xs text-cream-500 mt-1">Service & repair logs</div>
        </div>

        <div className="bg-white p-4 rounded border border-cream-300 shadow-sm">
          <div className="flex items-center justify-between text-cream-500 mb-1">
            <span className="text-xs uppercase font-medium">Open Anomaly Tickets</span>
            <AlertCircle className="w-4 h-4 text-amber-600" />
          </div>
          <div className="text-2xl font-serif font-bold text-amber-700">{openTicketsCount}</div>
          <div className="text-xs text-cream-500 mt-1">IoT sensor triggers & manual</div>
        </div>

        <div className="bg-white p-4 rounded border border-cream-300 shadow-sm">
          <div className="flex items-center justify-between text-cream-500 mb-1">
            <span className="text-xs uppercase font-medium">Total Registered Assets</span>
            <Cpu className="w-4 h-4 text-cream-700" />
          </div>
          <div className="text-2xl font-serif font-bold text-cream-900">{assets.length}</div>
          <div className="text-xs text-cream-500 mt-1">Equipment under management</div>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-cream-300">
        <nav className="flex space-x-8" aria-label="Tabs">
          <button
            onClick={() => setActiveTab("schedules")}
            className={`py-3 px-1 border-b-2 font-medium text-sm transition flex items-center gap-2 ${
              activeTab === "schedules"
                ? "border-cream-900 text-cream-900 font-semibold"
                : "border-transparent text-cream-600 hover:text-cream-800 hover:border-cream-400"
            }`}
          >
            <Calendar className="w-4 h-4" />
            Preventive Schedules
            <span className="ml-1 text-xs bg-cream-200 text-cream-800 px-2 py-0.5 rounded-full">
              {schedules.length}
            </span>
          </button>
          <button
            onClick={() => setActiveTab("visits")}
            className={`py-3 px-1 border-b-2 font-medium text-sm transition flex items-center gap-2 ${
              activeTab === "visits"
                ? "border-cream-900 text-cream-900 font-semibold"
                : "border-transparent text-cream-600 hover:text-cream-800 hover:border-cream-400"
            }`}
          >
            <Clock className="w-4 h-4" />
            Service Dispatches & Visits
            <span className="ml-1 text-xs bg-cream-200 text-cream-800 px-2 py-0.5 rounded-full">
              {visits.length}
            </span>
          </button>
          <button
            onClick={() => setActiveTab("iot")}
            className={`py-3 px-1 border-b-2 font-medium text-sm transition flex items-center gap-2 ${
              activeTab === "iot"
                ? "border-cream-900 text-cream-900 font-semibold"
                : "border-transparent text-cream-600 hover:text-cream-800 hover:border-cream-400"
            }`}
          >
            <Radio className="w-4 h-4" />
            Predictive IoT & Edge Tickets
            <span className="ml-1 text-xs bg-cream-200 text-cream-800 px-2 py-0.5 rounded-full">
              {tickets.length}
            </span>
          </button>
        </nav>
      </div>

      {/* Tab 1: Preventive Schedules */}
      {activeTab === "schedules" && (
        <div className="space-y-4">
          <div className="bg-white rounded border border-cream-300 shadow-sm overflow-hidden">
            <div className="p-4 border-b border-cream-200 bg-cream-50 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-cream-900">Preventive Maintenance Schedules</h3>
              <span className="text-xs text-cream-600">{schedules.length} schedules registered</span>
            </div>
            {schedules.length === 0 ? (
              <div className="p-8 text-center text-sm text-cream-500">
                No preventive maintenance schedules found. Click "New Schedule" to configure a recurring routine.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs text-cream-800">
                  <thead className="bg-cream-100 text-cream-700 uppercase font-medium border-b border-cream-200">
                    <tr>
                      <th className="py-2.5 px-4">Schedule #</th>
                      <th className="py-2.5 px-4">Target Equipment</th>
                      <th className="py-2.5 px-4">Periodicity</th>
                      <th className="py-2.5 px-4">Start Date</th>
                      <th className="py-2.5 px-4">Next Due Date</th>
                      <th className="py-2.5 px-4">End Date</th>
                      <th className="py-2.5 px-4">Task Description</th>
                      <th className="py-2.5 px-4">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-cream-200">
                    {schedules.map((s) => (
                      <tr key={s.id || s.schedule_id} className="hover:bg-cream-50 transition">
                        <td className="py-3 px-4 font-mono font-medium text-cream-900">{s.schedule_number}</td>
                        <td className="py-3 px-4">
                          {s.asset ? (
                            <div>
                              <span className="font-semibold text-cream-900">{s.asset.asset_name}</span>
                              <span className="text-cream-500 text-[11px] block">{s.asset.asset_code}</span>
                            </div>
                          ) : s.item_code ? (
                            <span className="font-mono text-cream-800">{s.item_code}</span>
                          ) : (
                            <span className="text-cream-400">General Equipment</span>
                          )}
                        </td>
                        <td className="py-3 px-4">
                          <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-cream-200 text-cream-800">
                            {s.periodicity}
                          </span>
                        </td>
                        <td className="py-3 px-4 font-mono">{s.start_date}</td>
                        <td className="py-3 px-4 font-mono font-medium text-amber-800">
                          {s.next_due_date || "—"}
                        </td>
                        <td className="py-3 px-4 font-mono text-cream-500">{s.end_date || "Continuous"}</td>
                        <td className="py-3 px-4 text-cream-700 max-w-[200px] truncate">
                          {s.task_description || "Routine Servicing"}
                        </td>
                        <td className="py-3 px-4">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-medium ${
                              s.status === "ACTIVE"
                                ? "bg-emerald-100 text-emerald-800"
                                : s.status === "COMPLETED"
                                ? "bg-blue-100 text-blue-800"
                                : "bg-cream-200 text-cream-700"
                            }`}
                          >
                            {s.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Tab 2: Service Dispatches & Visits */}
      {activeTab === "visits" && (
        <div className="space-y-4">
          <div className="bg-white rounded border border-cream-300 shadow-sm overflow-hidden">
            <div className="p-4 border-b border-cream-200 bg-cream-50 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-cream-900">Maintenance Visits & Technician Dispatches</h3>
              <span className="text-xs text-cream-600">{visits.length} visits recorded</span>
            </div>
            {visits.length === 0 ? (
              <div className="p-8 text-center text-sm text-cream-500">
                No maintenance visits recorded. Click "Log Visit / Dispatch" to record field service or completed maintenance.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs text-cream-800">
                  <thead className="bg-cream-100 text-cream-700 uppercase font-medium border-b border-cream-200">
                    <tr>
                      <th className="py-2.5 px-4">Visit #</th>
                      <th className="py-2.5 px-4">Type</th>
                      <th className="py-2.5 px-4">Target Asset</th>
                      <th className="py-2.5 px-4">Technician</th>
                      <th className="py-2.5 px-4">Downtime</th>
                      <th className="py-2.5 px-4">Parts Replaced</th>
                      <th className="py-2.5 px-4">Remarks</th>
                      <th className="py-2.5 px-4">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-cream-200">
                    {visits.map((v) => (
                      <tr key={v.id || v.visit_id} className="hover:bg-cream-50 transition">
                        <td className="py-3 px-4 font-mono font-medium text-cream-900">{v.visit_number}</td>
                        <td className="py-3 px-4">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-medium ${
                              v.maintenance_type === "PREVENTIVE"
                                ? "bg-blue-100 text-blue-800"
                                : "bg-red-100 text-red-800"
                            }`}
                          >
                            {v.maintenance_type}
                          </span>
                        </td>
                        <td className="py-3 px-4">
                          {v.asset ? (
                            <span className="font-medium text-cream-900">{v.asset.asset_name}</span>
                          ) : (
                            <span className="text-cream-400">General</span>
                          )}
                        </td>
                        <td className="py-3 px-4 font-medium text-cream-800">{v.technician || v.technician_name || "—"}</td>
                        <td className="py-3 px-4 font-mono">
                          {v.downtime_hours ? `${v.downtime_hours} hrs` : "0 hrs"}
                        </td>
                        <td className="py-3 px-4">
                          {v.parts_replaced && v.parts_replaced.length > 0 ? (
                            <div className="flex flex-wrap gap-1">
                              {v.parts_replaced.map((p: any, idx: number) => (
                                <span key={idx} className="bg-cream-200 text-cream-800 px-1.5 py-0.5 rounded text-[10px] font-mono">
                                  {p.item_code || p.name} (x{p.qty || 1})
                                </span>
                              ))}
                            </div>
                          ) : (
                            <span className="text-cream-400">None</span>
                          )}
                        </td>
                        <td className="py-3 px-4 text-cream-600 max-w-[200px] truncate">
                          {v.completion_remarks || v.tasks_performed || "—"}
                        </td>
                        <td className="py-3 px-4">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-medium ${
                              v.status === "COMPLETED"
                                ? "bg-emerald-100 text-emerald-800"
                                : v.status === "IN_PROGRESS"
                                ? "bg-amber-100 text-amber-800"
                                : "bg-cream-200 text-cream-700"
                            }`}
                          >
                            {v.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Tab 3: Predictive IoT & Edge Tickets */}
      {activeTab === "iot" && (
        <div className="space-y-6">
          {/* Telemetry Simulator Card */}
          <div className="bg-white p-5 rounded border border-cream-300 shadow-sm space-y-4">
            <div className="flex items-center justify-between border-b border-cream-200 pb-3">
              <div className="flex items-center gap-2">
                <Radio className="w-5 h-5 text-cream-700" />
                <h3 className="text-sm font-semibold text-cream-900">Edge IoT Workstation Telemetry Simulator</h3>
              </div>
              <span className="text-xs bg-cream-200 text-cream-800 px-2 py-0.5 rounded font-mono">
                Predictive Maintenance Engine
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-xs font-medium text-cream-700 mb-1">Workstation Code</label>
                <select
                  value={workstationCode}
                  onChange={(e) => setWorkstationCode(e.target.value)}
                  className="w-full text-xs p-2 bg-cream-50 border border-cream-300 rounded focus:outline-none focus:border-cream-600 font-mono"
                >
                  <option value="WS-INJECTION-01">WS-INJECTION-01 (Hydraulic Press)</option>
                  <option value="WS-CNC-01">WS-CNC-01 (Milling Machine)</option>
                  <option value="WS-ROBOT-01">WS-ROBOT-01 (Assembly Arm)</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-cream-700 mb-1">Telemetry Condition</label>
                <div className="flex items-center gap-4 mt-2">
                  <label className="flex items-center gap-2 text-xs text-cream-800 cursor-pointer">
                    <input
                      type="radio"
                      name="anomaly"
                      checked={injectAnomaly}
                      onChange={() => setInjectAnomaly(true)}
                      className="text-cream-800 focus:ring-cream-700"
                    />
                    <span className="text-red-700 font-medium">Inject Thermal / Vibration Anomaly</span>
                  </label>
                  <label className="flex items-center gap-2 text-xs text-cream-800 cursor-pointer">
                    <input
                      type="radio"
                      name="anomaly"
                      checked={!injectAnomaly}
                      onChange={() => setInjectAnomaly(false)}
                      className="text-cream-800 focus:ring-cream-700"
                    />
                    <span className="text-emerald-700">Nominal Operation</span>
                  </label>
                </div>
              </div>

              <div className="flex items-end">
                <button
                  onClick={handleSimulateAndIngest}
                  disabled={simulating}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2 text-xs font-medium text-white bg-cream-800 rounded hover:bg-cream-900 transition disabled:opacity-50 shadow-sm"
                >
                  {simulating ? (
                    <>
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      Analyzing Telemetry...
                    </>
                  ) : (
                    <>
                      <Zap className="w-3.5 h-3.5 text-amber-400" />
                      Simulate & Ingest Telemetry
                    </>
                  )}
                </button>
              </div>
            </div>

            {telemetryResult && (
              <div className="mt-4 p-4 bg-cream-50 border border-cream-200 rounded text-xs space-y-2">
                <div className="flex items-center justify-between font-semibold text-cream-900">
                  <span>ML Analysis & Action Plan:</span>
                  <span className={`px-2 py-0.5 rounded text-[10px] font-medium ${
                    telemetryResult.plan.work_order_created || telemetryResult.plan.failure_probability >= 0.85
                      ? "bg-red-100 text-red-800"
                      : "bg-emerald-100 text-emerald-800"
                  }`}>
                    {telemetryResult.plan.work_order_created || telemetryResult.plan.failure_probability >= 0.85
                      ? "ANOMALY TRIGGERED"
                      : "HEALTHY"}
                  </span>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2 font-mono text-[11px] text-cream-700">
                  <div>Bearing Temp: {(telemetryResult.frame.bearing_temp_c ?? telemetryResult.frame.motor_temperature_c)?.toFixed(1)}°C</div>
                  <div>Vibration: {(telemetryResult.frame.vibration_rms_mm_s ?? telemetryResult.frame.vibration_mms)?.toFixed(2)} mm/s</div>
                  <div>Speed: {(telemetryResult.frame.rpm ?? telemetryResult.frame.conveyor_speed_rpm)?.toFixed(0)} RPM</div>
                  <div>Ticket: {telemetryResult.plan.ticket_number || (telemetryResult.plan.work_order_created ? "AUTO CREATED" : "NONE")}</div>
                </div>
                <p className="text-cream-800 font-sans italic">
                  {telemetryResult.plan.alarm_summary || (telemetryResult.plan.work_order_created ? `Ticket ${telemetryResult.plan.ticket_number} created for predictive servicing` : "Equipment operating within normal tolerances")}
                </p>
              </div>
            )}
          </div>

          {/* Tickets Table */}
          <div className="bg-white rounded border border-cream-300 shadow-sm overflow-hidden">
            <div className="p-4 border-b border-cream-200 bg-cream-50 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-cream-900">IoT Predictive Maintenance Tickets</h3>
              <span className="text-xs text-cream-600">{tickets.length} tickets recorded</span>
            </div>
            {tickets.length === 0 ? (
              <div className="p-8 text-center text-sm text-cream-500">
                No maintenance tickets found. Use the simulator above or click "New Manual Ticket".
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs text-cream-800">
                  <thead className="bg-cream-100 text-cream-700 uppercase font-medium border-b border-cream-200">
                    <tr>
                      <th className="py-2.5 px-4">Ticket #</th>
                      <th className="py-2.5 px-4">Workstation</th>
                      <th className="py-2.5 px-4">Trigger</th>
                      <th className="py-2.5 px-4">Fault Code</th>
                      <th className="py-2.5 px-4">Priority</th>
                      <th className="py-2.5 px-4">Status</th>
                      <th className="py-2.5 px-4 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-cream-200">
                    {tickets.map((t) => (
                      <tr key={t.id || t.ticket_id} className="hover:bg-cream-50 transition">
                        <td className="py-3 px-4 font-mono font-medium text-cream-900">{t.ticket_number}</td>
                        <td className="py-3 px-4 font-mono font-medium">{t.workstation_code}</td>
                        <td className="py-3 px-4">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-medium ${
                            t.trigger_type === "PREDICTIVE_ANOMALY" || t.trigger_type === "AUTO_TELEMETRY" ? "bg-amber-100 text-amber-800" : "bg-cream-200 text-cream-800"
                          }`}>
                            {t.trigger_type}
                          </span>
                        </td>
                        <td className="py-3 px-4 font-mono text-[11px] text-red-700">{t.fault_code || "—"}</td>
                        <td className="py-3 px-4">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-medium ${
                            t.priority === "CRITICAL"
                              ? "bg-red-200 text-red-900 font-bold"
                              : t.priority === "HIGH"
                              ? "bg-amber-100 text-amber-800 font-semibold"
                              : "bg-cream-100 text-cream-700"
                          }`}>
                            {t.priority}
                          </span>
                        </td>
                        <td className="py-3 px-4">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-medium ${
                            t.status === "COMPLETED" || t.status === "RESOLVED"
                              ? "bg-emerald-100 text-emerald-800"
                              : t.status === "IN_PROGRESS"
                              ? "bg-blue-100 text-blue-800"
                              : "bg-red-100 text-red-800"
                          }`}>
                            {t.status}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-right space-x-1">
                          {t.status === "OPEN" && (
                            <button
                              onClick={() => handleUpdateTicketStatus(t.id || t.ticket_id, "IN_PROGRESS")}
                              className="px-2 py-1 bg-cream-200 hover:bg-cream-300 text-cream-900 rounded text-[10px] font-medium transition"
                            >
                              Dispatch Tech
                            </button>
                          )}
                          {t.status === "IN_PROGRESS" && (
                            <button
                              onClick={() => handleUpdateTicketStatus(t.id || t.ticket_id, "RESOLVED")}
                              className="px-2 py-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded text-[10px] font-medium transition"
                            >
                              Resolve
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
        </div>
      )}

      {/* Modal: New Schedule */}
      {showScheduleModal && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-lg border border-cream-300 shadow-xl max-w-md w-full p-6 space-y-4">
            <h3 className="text-base font-semibold text-cream-900">New Preventive Maintenance Schedule</h3>
            <form onSubmit={handleCreateSchedule} className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-cream-700 mb-1">Schedule Number (Optional)</label>
                <input
                  type="text"
                  value={schedNumber}
                  onChange={(e) => setSchedNumber(e.target.value)}
                  placeholder="Auto-generated (e.g. PMS-2026-001)"
                  className="w-full text-xs p-2 bg-cream-50 border border-cream-300 rounded focus:outline-none focus:border-cream-600 font-mono"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-cream-700 mb-1">Target Asset</label>
                <select
                  value={schedAssetId}
                  onChange={(e) => setSchedAssetId(e.target.value)}
                  className="w-full text-xs p-2 bg-cream-50 border border-cream-300 rounded focus:outline-none focus:border-cream-600"
                >
                  <option value="">-- Select Asset or enter Item Code below --</option>
                  {assets.map((a) => (
                    <option key={a.asset_id || a.id} value={a.asset_id || a.id}>
                      {a.asset_name} ({a.asset_code})
                    </option>
                  ))}
                </select>
              </div>

              {!schedAssetId && (
                <div>
                  <label className="block text-xs font-medium text-cream-700 mb-1">Or Item Code</label>
                  <input
                    type="text"
                    value={schedItemCode}
                    onChange={(e) => setSchedItemCode(e.target.value)}
                    placeholder="e.g. ITM-ROBOTIC-ARM-01"
                    className="w-full text-xs p-2 bg-cream-50 border border-cream-300 rounded focus:outline-none focus:border-cream-600 font-mono"
                  />
                </div>
              )}

              <div>
                <label className="block text-xs font-medium text-cream-700 mb-1">Task Description *</label>
                <input
                  type="text"
                  required
                  value={schedTaskDesc}
                  onChange={(e) => setSchedTaskDesc(e.target.value)}
                  placeholder="e.g. Monthly Lubrication & Spindle Calibration"
                  className="w-full text-xs p-2 bg-cream-50 border border-cream-300 rounded focus:outline-none focus:border-cream-600"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-cream-700 mb-1">Periodicity *</label>
                <select
                  value={schedPeriodicity}
                  onChange={(e) => setSchedPeriodicity(e.target.value)}
                  className="w-full text-xs p-2 bg-cream-50 border border-cream-300 rounded focus:outline-none focus:border-cream-600 font-medium"
                >
                  <option value="DAILY">DAILY</option>
                  <option value="WEEKLY">WEEKLY</option>
                  <option value="MONTHLY">MONTHLY</option>
                  <option value="QUARTERLY">QUARTERLY</option>
                  <option value="HALF_YEARLY">HALF_YEARLY</option>
                  <option value="YEARLY">YEARLY</option>
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-cream-700 mb-1">Start Date *</label>
                  <input
                    type="date"
                    required
                    value={schedStartDate}
                    onChange={(e) => setSchedStartDate(e.target.value)}
                    className="w-full text-xs p-2 bg-cream-50 border border-cream-300 rounded focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-cream-700 mb-1">End Date</label>
                  <input
                    type="date"
                    value={schedEndDate}
                    onChange={(e) => setSchedEndDate(e.target.value)}
                    className="w-full text-xs p-2 bg-cream-50 border border-cream-300 rounded focus:outline-none"
                  />
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-cream-200">
                <button
                  type="button"
                  onClick={() => setShowScheduleModal(false)}
                  className="px-3.5 py-1.5 text-xs text-cream-700 hover:bg-cream-100 rounded transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creatingSchedule}
                  className="px-4 py-1.5 text-xs font-medium text-white bg-cream-800 hover:bg-cream-900 rounded transition shadow-sm"
                >
                  {creatingSchedule ? "Saving..." : "Create Schedule"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: New Visit */}
      {showVisitModal && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-lg border border-cream-300 shadow-xl max-w-md w-full p-6 space-y-4">
            <h3 className="text-base font-semibold text-cream-900">Log Maintenance Visit / Service Dispatch</h3>
            <form onSubmit={handleCreateVisit} className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-cream-700 mb-1">Visit Number (Optional)</label>
                <input
                  type="text"
                  value={visitNumber}
                  onChange={(e) => setVisitNumber(e.target.value)}
                  placeholder="Auto-generated (e.g. MNT-VISIT-2026-001)"
                  className="w-full text-xs p-2 bg-cream-50 border border-cream-300 rounded focus:outline-none focus:border-cream-600 font-mono"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-cream-700 mb-1">Associated Schedule (Optional)</label>
                <select
                  value={visitScheduleId}
                  onChange={(e) => setVisitScheduleId(e.target.value)}
                  className="w-full text-xs p-2 bg-cream-50 border border-cream-300 rounded focus:outline-none focus:border-cream-600 font-mono"
                >
                  <option value="">-- Standalone Visit --</option>
                  {schedules.map((s) => (
                    <option key={s.id || s.schedule_id} value={s.id || s.schedule_id}>
                      {s.schedule_number} ({s.periodicity})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-cream-700 mb-1">Target Asset</label>
                <select
                  value={visitAssetId}
                  onChange={(e) => setVisitAssetId(e.target.value)}
                  className="w-full text-xs p-2 bg-cream-50 border border-cream-300 rounded focus:outline-none focus:border-cream-600"
                >
                  <option value="">-- General Service --</option>
                  {assets.map((a) => (
                    <option key={a.asset_id || a.id} value={a.asset_id || a.id}>
                      {a.asset_name} ({a.asset_code})
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-cream-700 mb-1">Type *</label>
                  <select
                    value={visitType}
                    onChange={(e) => setVisitType(e.target.value)}
                    className="w-full text-xs p-2 bg-cream-50 border border-cream-300 rounded focus:outline-none font-medium"
                  >
                    <option value="PREVENTIVE">PREVENTIVE</option>
                    <option value="BREAKDOWN">BREAKDOWN</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-cream-700 mb-1">Technician *</label>
                  <input
                    type="text"
                    required
                    value={visitTechnician}
                    onChange={(e) => setVisitTechnician(e.target.value)}
                    placeholder="e.g. John Doe (Lead Tech)"
                    className="w-full text-xs p-2 bg-cream-50 border border-cream-300 rounded focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-cream-700 mb-1">Downtime Hours</label>
                <input
                  type="number"
                  step="0.1"
                  min="0"
                  value={visitDowntime}
                  onChange={(e) => setVisitDowntime(e.target.value)}
                  className="w-full text-xs p-2 bg-cream-50 border border-cream-300 rounded focus:outline-none font-mono"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-cream-700 mb-1">Parts Replaced (Item code or JSON)</label>
                <input
                  type="text"
                  value={visitParts}
                  onChange={(e) => setVisitParts(e.target.value)}
                  placeholder='e.g. BEARING-6204 or [{"item_code":"SEAL-O-RING","qty":2}]'
                  className="w-full text-xs p-2 bg-cream-50 border border-cream-300 rounded focus:outline-none font-mono"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-cream-700 mb-1">Completion Remarks</label>
                <textarea
                  rows={2}
                  value={visitRemarks}
                  onChange={(e) => setVisitRemarks(e.target.value)}
                  placeholder="Details of service work performed, calibrations, tests conducted..."
                  className="w-full text-xs p-2 bg-cream-50 border border-cream-300 rounded focus:outline-none"
                />
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-cream-200">
                <button
                  type="button"
                  onClick={() => setShowVisitModal(false)}
                  className="px-3.5 py-1.5 text-xs text-cream-700 hover:bg-cream-100 rounded transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creatingVisit}
                  className="px-4 py-1.5 text-xs font-medium text-white bg-cream-800 hover:bg-cream-900 rounded transition shadow-sm"
                >
                  {creatingVisit ? "Saving..." : "Log Completed Visit"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: New Manual Ticket */}
      {showTicketModal && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-lg border border-cream-300 shadow-xl max-w-md w-full p-6 space-y-4">
            <h3 className="text-base font-semibold text-cream-900">Create Manual Maintenance Ticket</h3>
            <form onSubmit={handleCreateTicket} className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-cream-700 mb-1">Ticket Number *</label>
                <input
                  type="text"
                  required
                  value={ticketNumber}
                  onChange={(e) => setTicketNumber(e.target.value)}
                  placeholder="MT-2026-XXXX"
                  className="w-full text-xs p-2 bg-cream-50 border border-cream-300 rounded focus:outline-none font-mono"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-cream-700 mb-1">Workstation *</label>
                  <input
                    type="text"
                    required
                    value={wsTarget}
                    onChange={(e) => setWsTarget(e.target.value)}
                    className="w-full text-xs p-2 bg-cream-50 border border-cream-300 rounded focus:outline-none font-mono"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-cream-700 mb-1">Priority</label>
                  <select
                    value={ticketPriority}
                    onChange={(e) => setTicketPriority(e.target.value)}
                    className="w-full text-xs p-2 bg-cream-50 border border-cream-300 rounded focus:outline-none font-medium"
                  >
                    <option value="LOW">LOW</option>
                    <option value="MEDIUM">MEDIUM</option>
                    <option value="HIGH">HIGH</option>
                    <option value="CRITICAL">CRITICAL</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-cream-700 mb-1">Fault Code</label>
                <input
                  type="text"
                  value={faultCode}
                  onChange={(e) => setFaultCode(e.target.value)}
                  className="w-full text-xs p-2 bg-cream-50 border border-cream-300 rounded focus:outline-none font-mono"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-cream-700 mb-1">Description *</label>
                <textarea
                  required
                  rows={2}
                  value={ticketDescription}
                  onChange={(e) => setTicketDescription(e.target.value)}
                  placeholder="Observed symptoms or failure details..."
                  className="w-full text-xs p-2 bg-cream-50 border border-cream-300 rounded focus:outline-none"
                />
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-cream-200">
                <button
                  type="button"
                  onClick={() => setShowTicketModal(false)}
                  className="px-3.5 py-1.5 text-xs text-cream-700 hover:bg-cream-100 rounded transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creatingTicket}
                  className="px-4 py-1.5 text-xs font-medium text-white bg-cream-800 hover:bg-cream-900 rounded transition shadow-sm"
                >
                  {creatingTicket ? "Saving..." : "Create Ticket"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
