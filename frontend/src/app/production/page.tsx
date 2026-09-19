"use client";

import { useEffect, useState } from "react";
import { Activity, Plus, RefreshCw, AlertCircle, Play, ShieldAlert, CheckCircle2, Clock } from "lucide-react";
import { api } from "@/lib/api";

export default function ProductionPage() {
  const [workstations, setWorkstations] = useState<any[]>([]);
  const [workOrders, setWorkOrders] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Solved Schedule Result
  const [scheduleResult, setScheduleResult] = useState<any | null>(null);
  const [solving, setSolving] = useState(false);

  // Fault simulation
  const [faultingCode, setFaultingCode] = useState<string | null>(null);
  const [faultResult, setFaultResult] = useState<any | null>(null);

  // New Workstation Modal
  const [showWsModal, setShowWsModal] = useState(false);
  const [wsCode, setWsCode] = useState("");
  const [wsName, setWsName] = useState("");
  const [wsRate, setWsRate] = useState("45.00");
  const [creatingWs, setCreatingWs] = useState(false);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [wsList, woList] = await Promise.all([
        api.getWorkstations(),
        api.getWorkOrders(),
      ]);
      setWorkstations(wsList);
      setWorkOrders(woList);
    } catch (err: any) {
      setError(err.message || "Failed to load factory floor data from database.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleSolveSchedule = async () => {
    setSolving(true);
    setError(null);
    try {
      const res = await api.solveSchedule();
      setScheduleResult(res);
    } catch (err: any) {
      setError(err.message || "CP-SAT schedule optimization failed.");
    } finally {
      setSolving(false);
    }
  };

  const handleSimulateFault = async (code: string) => {
    setFaultingCode(code);
    setError(null);
    try {
      const res = await api.simulateFaultReroute(code);
      setFaultResult(res);
      await loadData();
    } catch (err: any) {
      setError(err.message || "Fault simulation failed.");
    } finally {
      setFaultingCode(null);
    }
  };

  const handleCreateWorkstation = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreatingWs(true);
    try {
      await api.createWorkstation({
        workstation_code: wsCode.trim().toUpperCase(),
        workstation_name: wsName.trim(),
        hourly_rate: parseFloat(wsRate),
        status: "OPERATIONAL",
      });
      setShowWsModal(false);
      setWsCode("");
      setWsName("");
      await loadData();
    } catch (err: any) {
      setError(err.message || "Failed to register workstation.");
    } finally {
      setCreatingWs(false);
    }
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between border-b border-cream-300 pb-5">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-cream-900">
            Shop Floor & CP-SAT Autonomous Production Scheduling
          </h1>
          <p className="text-xs text-cream-700 mt-1">
            Global makespan minimization enforcing non-overlapping machine bounds and dynamic failure rerouting.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={loadData}
            disabled={loading}
            className="flex items-center gap-1.5 rounded-md border border-cream-300 bg-cream-100 px-3 py-1.5 text-xs font-medium text-cream-800 hover:bg-cream-200 transition-colors"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
            <span>Refresh</span>
          </button>
          <button
            onClick={() => setShowWsModal(true)}
            className="flex items-center gap-1.5 rounded-md border border-cream-300 bg-cream-100 px-3 py-1.5 text-xs font-medium text-cream-800 hover:bg-cream-200 transition-colors"
          >
            <Plus className="h-3.5 w-3.5" />
            <span>Add Workstation</span>
          </button>
          <button
            onClick={handleSolveSchedule}
            disabled={solving}
            className="flex items-center gap-1.5 rounded-md border border-cream-400 bg-cream-900 px-3 py-1.5 text-xs font-medium text-cream-50 hover:bg-cream-800 transition-colors disabled:opacity-50"
          >
            <Play className="h-3.5 w-3.5" />
            <span>{solving ? "Optimizing CP-SAT..." : "Solve Schedule (OR-Tools)"}</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-terracotta-50 border border-terracotta-500/30 text-terracotta-700 text-xs">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Schedule Optimization Result Banner */}
      {scheduleResult && (
        <div className="rounded-lg border border-sage-500/30 bg-sage-50 p-4 text-xs text-sage-900 space-y-2">
          <div className="flex items-center justify-between">
            <div className="font-semibold flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-sage-600" />
              <span>OR-Tools CP-SAT Global Optimization: {scheduleResult.status}</span>
            </div>
            <span className="font-mono text-[11px] font-bold bg-sage-100 px-2 py-0.5 rounded text-sage-800">
              Makespan: {scheduleResult.makespan_minutes} mins (Solved in {scheduleResult.solve_time_seconds.toFixed(3)}s)
            </span>
          </div>

          <div className="space-y-1.5 pt-2 border-t border-sage-500/20">
            <span className="text-[11px] font-medium text-sage-800">Scheduled Operation Dispatches:</span>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
              {scheduleResult.scheduled_operations?.map((op: any, i: number) => (
                <div key={i} className="p-2 rounded bg-cream-50/80 border border-sage-500/20 font-mono text-[11px] flex justify-between">
                  <span>{op.job_id} &bull; {op.workstation_code}</span>
                  <span className="text-sage-700 font-bold">[{op.start_minute}m &rarr; {op.end_minute}m]</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Fault Simulation Result Banner */}
      {faultResult && (
        <div className="rounded-lg border border-terracotta-500/30 bg-terracotta-50 p-4 text-xs text-terracotta-900 space-y-1">
          <div className="font-semibold flex items-center gap-2">
            <ShieldAlert className="h-4 w-4 text-terracotta-600" />
            <span>Dynamic Fault Reroute Committed</span>
          </div>
          <p className="text-[11px] font-mono text-terracotta-800">
            Workstation {faultResult.faulted_workstation_code} evacuated. {faultResult.evacuated_operations_count} operations dynamically rerouted.
            New makespan: {faultResult.reoptimized_schedule?.makespan_minutes} mins.
          </p>
        </div>
      )}

      {/* Workstations Grid */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-cream-900">Shop Floor Machinery Registry</h2>
          <span className="text-xs text-cream-600 font-mono">{workstations.length} workstations</span>
        </div>

        {workstations.length === 0 ? (
          <div className="rounded-xl border border-cream-300 bg-cream-100 p-6 text-center text-xs text-cream-600">
            No workstations configured on factory floor.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {workstations.map((ws) => (
              <div key={ws.workstation_id} className="rounded-xl border border-cream-300 bg-cream-100 p-4 shadow-xs space-y-3">
                <div className="flex items-start justify-between">
                  <div>
                    <span className="font-mono text-xs font-bold text-cream-900">{ws.workstation_code}</span>
                    <h3 className="text-[11px] text-cream-700 leading-tight mt-0.5">{ws.workstation_name}</h3>
                  </div>
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-mono font-semibold ${
                      ws.status === "OPERATIONAL"
                        ? "bg-sage-100 text-sage-800 border border-sage-500/30"
                        : "bg-terracotta-100 text-terracotta-800 border border-terracotta-500/30"
                    }`}
                  >
                    {ws.status}
                  </span>
                </div>

                <div className="space-y-1 text-[11px] font-mono text-cream-600 border-t border-cream-300 pt-2">
                  <div className="flex justify-between">
                    <span>Hourly Rate:</span>
                    <span className="text-cream-900 font-bold">${parseFloat(ws.hourly_rate).toFixed(2)}/hr</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Health Score:</span>
                    <span className="text-cream-900 font-bold">{parseFloat(ws.health_score).toFixed(0)}%</span>
                  </div>
                </div>

                <button
                  onClick={() => handleSimulateFault(ws.workstation_code)}
                  disabled={faultingCode === ws.workstation_code || ws.status === "FAULT"}
                  className="w-full rounded border border-terracotta-500/30 bg-terracotta-50 px-2 py-1 text-[11px] font-medium text-terracotta-800 hover:bg-terracotta-100 transition-colors disabled:opacity-50"
                >
                  {faultingCode === ws.workstation_code ? "Simulating..." : "Simulate Machine Fault"}
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Work Orders List */}
      <div className="space-y-3">
        <h2 className="text-sm font-semibold text-cream-900">Active Work Orders</h2>
        {workOrders.length === 0 ? (
          <div className="rounded-xl border border-cream-300 bg-cream-100 p-6 text-center text-xs text-cream-600">
            No work orders active. Click "Solve Schedule (OR-Tools)" to generate scheduling proposals.
          </div>
        ) : (
          <div className="rounded-xl border border-cream-300 bg-cream-100 overflow-hidden shadow-xs">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-cream-300 bg-cream-200/60 text-cream-800 font-medium text-[11px]">
                  <th className="py-2.5 px-4">Work Order #</th>
                  <th className="py-2.5 px-4">Planned Qty</th>
                  <th className="py-2.5 px-4">Produced Qty</th>
                  <th className="py-2.5 px-4">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-cream-200">
                {workOrders.map((wo) => (
                  <tr key={wo.work_order_id} className="hover:bg-cream-50/50 transition-colors">
                    <td className="py-3 px-4 font-mono font-medium text-cream-900">{wo.work_order_number}</td>
                    <td className="py-3 px-4 font-mono text-cream-900">{parseFloat(wo.planned_quantity).toFixed(0)}</td>
                    <td className="py-3 px-4 font-mono text-cream-700">{parseFloat(wo.produced_quantity).toFixed(0)}</td>
                    <td className="py-3 px-4">
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-cream-200 text-cream-800">
                        {wo.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Modal: Add Workstation */}
      {showWsModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="w-full max-w-md rounded-xl border border-cream-300 bg-cream-100 p-6 shadow-lg space-y-4">
            <div className="flex items-center justify-between border-b border-cream-300 pb-3">
              <h3 className="font-semibold text-sm text-cream-900">Register Factory Workstation</h3>
              <button onClick={() => setShowWsModal(false)} className="text-cream-600 hover:text-cream-900 text-xs">
                Cancel
              </button>
            </div>

            <form onSubmit={handleCreateWorkstation} className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-cream-900 mb-1">Workstation Code</label>
                <input
                  type="text"
                  required
                  value={wsCode}
                  onChange={(e) => setWsCode(e.target.value)}
                  placeholder="e.g. WS-LASER-01"
                  className="w-full rounded-lg border border-cream-300 bg-cream-50 px-3 py-1.5 text-xs text-cream-900 font-mono"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-cream-900 mb-1">Machine Name</label>
                <input
                  type="text"
                  required
                  value={wsName}
                  onChange={(e) => setWsName(e.target.value)}
                  placeholder="e.g. Fiber Laser Cutting Cell"
                  className="w-full rounded-lg border border-cream-300 bg-cream-50 px-3 py-1.5 text-xs text-cream-900"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-cream-900 mb-1">Hourly Cost Rate ($/hr)</label>
                <input
                  type="number"
                  step="0.01"
                  required
                  value={wsRate}
                  onChange={(e) => setWsRate(e.target.value)}
                  className="w-full rounded-lg border border-cream-300 bg-cream-50 px-3 py-1.5 text-xs text-cream-900 font-mono"
                />
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-cream-300">
                <button
                  type="button"
                  onClick={() => setShowWsModal(false)}
                  className="rounded-lg border border-cream-300 bg-cream-200 px-3 py-1.5 text-xs font-medium text-cream-800"
                >
                  Close
                </button>
                <button
                  type="submit"
                  disabled={creatingWs}
                  className="rounded-lg border border-cream-400 bg-cream-900 px-3 py-1.5 text-xs font-medium text-cream-50 hover:bg-cream-800 disabled:opacity-50"
                >
                  {creatingWs ? "Saving..." : "Add Workstation"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
