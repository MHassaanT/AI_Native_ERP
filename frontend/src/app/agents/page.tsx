"use client";

import { Suspense, useEffect, useState, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import {
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  ChevronRight,
  Clock,
  Cpu,
  Layers,
  Play,
  Plus,
  RefreshCw,
  Send,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  X,
  Package,
  DollarSign,
  Activity,
  Users,
  FileText,
  Mail,
  MessageSquare,
  Bot,
  Terminal,
  ExternalLink,
  ChevronDown,
} from "lucide-react";
import { api } from "@/lib/api";

interface AutonomousAgentDef {
  agent_id: string;
  name: string;
  slug: string;
  domain: string;
  description: string;
  autonomy_level: string;
  trigger_type: string;
  is_active: boolean;
  config?: any;
}

interface AutonomousRun {
  run_id: string;
  agent_name: string;
  trigger_type: string;
  status: string;
  summary: string;
  error_message?: string;
  started_at: string;
  completed_at?: string;
  execution_metrics?: any;
  step_logs?: any[];
}

interface AutonomousComm {
  comm_id: string;
  run_id: string;
  agent_name: string;
  channel: string;
  recipient: string;
  subject?: string;
  body: string;
  status: string;
  external_message_id?: string;
  created_at: string;
}

const DOMAIN_STYLES: Record<string, { label: string; badge: string; icon: any }> = {
  PROCUREMENT: { label: "Procurement", badge: "bg-sage-100 text-sage-800 border-sage-300", icon: Package },
  SALES: { label: "Sales & SDR", badge: "bg-blue-50 text-blue-800 border-blue-200", icon: FileText },
  INVENTORY: { label: "Inventory", badge: "bg-purple-50 text-purple-800 border-purple-200", icon: Layers },
  HR: { label: "HR & Workforce", badge: "bg-cyan-50 text-cyan-800 border-cyan-200", icon: Users },
  MANUFACTURING: { label: "MES & Quality", badge: "bg-amberGold-100 text-amberGold-800 border-amberGold-300", icon: Activity },
  FINANCE: { label: "Finance & GL", badge: "bg-indigo-50 text-indigo-800 border-indigo-200", icon: DollarSign },
};

function AgentsContent() {
  const searchParams = useSearchParams();
  const dagIdParam = searchParams ? searchParams.get("dag_id") : null;

  const [activeTab, setActiveTab] = useState<"SUPERVISORS" | "DAGS">("SUPERVISORS");

  // Autonomous Workforce States
  const [agents, setAgents] = useState<AutonomousAgentDef[]>([]);
  const [runs, setRuns] = useState<AutonomousRun[]>([]);
  const [communications, setCommunications] = useState<AutonomousComm[]>([]);
  const [loadingAgents, setLoadingAgents] = useState(false);
  const [runningAgentSlug, setRunningAgentSlug] = useState<string | null>(null);
  const [runningAll, setRunningAll] = useState(false);
  const [selectedRun, setSelectedRun] = useState<AutonomousRun | null>(null);
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; text: string } | null>(null);

  // Mesh & DAG States
  const [agentStates, setAgentStates] = useState<Record<string, string>>({
    FINANCIAL_CONTROLLER: "IDLE",
    SUPPLY_CHAIN: "IDLE",
    PRODUCTION: "IDLE",
    REVENUE: "IDLE",
    WORKFORCE: "IDLE",
    COMPLIANCE: "IDLE",
  });
  const [activeDag, setActiveDag] = useState<any | null>(null);
  const [dagsList, setDagsList] = useState<any[]>([]);
  const [loadingDag, setLoadingDag] = useState(false);
  const [showDispatchModal, setShowDispatchModal] = useState(false);

  // RFQ Dispatch Form
  const [customerName, setCustomerName] = useState("AeroDynamics GmbH");
  const [inquiryText, setInquiryText] = useState("Need 500 units IP67 industrial enclosures by Q4.");
  const [dispatching, setDispatching] = useState(false);
  const [dispatchError, setDispatchError] = useState<string | null>(null);

  // Collision Arbitration Result
  const [arbitrating, setArbitrating] = useState(false);
  const [arbitrationResult, setArbitrationResult] = useState<any | null>(null);
  const [arbitrationError, setArbitrationError] = useState<string | null>(null);

  const loadAutonomousData = useCallback(async () => {
    try {
      setLoadingAgents(true);
      const [agentsData, runsData, commsData] = await Promise.allSettled([
        api.listAutonomousAgents(),
        api.listAutonomousRuns(25),
        api.listAutonomousCommunications(25),
      ]);

      if (agentsData.status === "fulfilled" && Array.isArray(agentsData.value)) {
        setAgents(agentsData.value);
      }
      if (runsData.status === "fulfilled" && Array.isArray(runsData.value)) {
        setRuns(runsData.value);
      }
      if (commsData.status === "fulfilled" && Array.isArray(commsData.value)) {
        setCommunications(commsData.value);
      }
    } catch (err: any) {
      console.error("Failed to load autonomous workforce data:", err);
    } finally {
      setLoadingAgents(false);
    }
  }, []);

  const loadAgentStates = async () => {
    try {
      const states = await api.getAgentStates();
      setAgentStates(states);
    } catch {
      // Keep default states
    }
  };

  const loadDagsList = async () => {
    try {
      const list = await api.listDags();
      if (Array.isArray(list)) {
        setDagsList(list);
      }
    } catch {
      // Fallback
    }
  };

  const fetchDag = useCallback(async (dagId?: string) => {
    setLoadingDag(true);
    try {
      let dag = null;
      if (dagId) {
        dag = await api.getDag(dagId);
      } else {
        dag = await api.getLatestDag();
      }
      if (dag && dag.dag_id) {
        setActiveDag(dag);
      }
    } catch (err) {
      console.warn("Could not fetch active DAG:", err);
    } finally {
      setLoadingDag(false);
    }
  }, []);

  useEffect(() => {
    loadAutonomousData();
    loadAgentStates();
    loadDagsList();
    fetchDag(dagIdParam || undefined);
  }, [dagIdParam, fetchDag, loadAutonomousData]);

  // Real-time polling while DAG is running
  useEffect(() => {
    if (!activeDag || activeDag.status === "COMPLETED" || activeDag.status === "FAILED") return;
    const interval = setInterval(async () => {
      try {
        const updated = await api.getDag(activeDag.dag_id);
        if (updated && updated.dag_id) {
          setActiveDag(updated);
        }
        await loadAgentStates();
      } catch {
        // Handled
      }
    }, 1000);
    return () => clearInterval(interval);
  }, [activeDag]);

  const handleRunAgent = async (slug: string) => {
    try {
      setRunningAgentSlug(slug);
      setFeedback(null);
      const res = await api.runAutonomousAgent(slug, "MANUAL");
      setFeedback({
        type: "success",
        text: `Agent cycle completed: ${res.summary || res.status}`,
      });
      await loadAutonomousData();
    } catch (err: any) {
      setFeedback({
        type: "error",
        text: err.message || `Failed to run agent ${slug}`,
      });
    } finally {
      setRunningAgentSlug(null);
    }
  };

  const handleRunAllAgents = async () => {
    try {
      setRunningAll(true);
      setFeedback(null);
      const res = await api.runAllAutonomousAgents();
      setFeedback({
        type: "success",
        text: `Autonomous workforce cycle complete! ${res.total_agents} agents executed.`,
      });
      await loadAutonomousData();
    } catch (err: any) {
      setFeedback({
        type: "error",
        text: err.message || "Failed to run all agents",
      });
    } finally {
      setRunningAll(false);
    }
  };

  const handleDispatchRFQ = async (e: React.FormEvent) => {
    e.preventDefault();
    setDispatching(true);
    setDispatchError(null);
    try {
      const res = await api.dispatchRFQ({
        customer_name: customerName,
        inquiry_text: inquiryText,
      });
      setActiveDag({
        dag_id: res.dag_id,
        nodes: res.nodes || [],
        status: res.status || "DISPATCHED",
        customer_name: customerName,
        inquiry_text: inquiryText,
      });
      setShowDispatchModal(false);
      await loadAgentStates();
      await loadDagsList();
    } catch (err: any) {
      setDispatchError(err.message || "Failed to dispatch RFQ DAG");
    } finally {
      setDispatching(false);
    }
  };

  const handleSimulateConflict = async () => {
    setArbitrating(true);
    setArbitrationError(null);
    try {
      const proposals = [
        {
          task_id: "task_prod_safety_01",
          agent_id: "PRODUCTION",
          tenant_id: "00000000-0000-0000-0000-000000000001",
          policy_class: "STATUTORY_LEGAL",
          resource_keys: ["workstation:WS-CNC-01"],
          state_mutation: { action: "EMERGENCY_HALT", reason: "Spindle vibration threshold exceeded" },
          monetary_value: 0.0,
          risk_score: 0.95,
          audit_rationale: "OSHA statutory machine safety override.",
        },
        {
          task_id: "task_rev_rush_01",
          agent_id: "REVENUE",
          tenant_id: "00000000-0000-0000-0000-000000000001",
          policy_class: "CONTRACTUAL_SLA",
          resource_keys: ["workstation:WS-CNC-01"],
          state_mutation: { action: "EXPEDITE_JOB", job_id: "JOB-AERO-09" },
          monetary_value: 48000.0,
          risk_score: 0.15,
          audit_rationale: "Tier-1 Customer Contractual SLA delivery penalty defense.",
        },
      ];

      const res = await api.arbitrateAgentCollision(proposals);
      setArbitrationResult(res);
    } catch (err: any) {
      setArbitrationError(err.message || "Failed to execute mathematical arbitration");
    } finally {
      setArbitrating(false);
    }
  };

  return (
    <div className="space-y-6 pb-16">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-cream-300 pb-5">
        <div>
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-cream-200 text-cream-900 border border-cream-300 shadow-2xs">
              <Bot className="w-5 h-5 text-cream-900" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-2xl font-bold tracking-tight text-cream-900 font-serif">
                  Autonomous Workforce Command Center
                </h1>
                <span className="text-xs px-2.5 py-0.5 rounded-full bg-sage-100 text-sage-800 border border-sage-300 font-medium inline-flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-sage-500 animate-ping" />
                  Live Gemini 3.8 Flash
                </span>
              </div>
              <p className="text-xs text-cream-700 mt-1">
                Multi-agent autonomous workforce across Procurement, Sales, Inventory, HR, MES, and Finance with WhatsApp & Gmail integration.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            onClick={() => loadAutonomousData()}
            disabled={loadingAgents}
            className="flex items-center gap-1.5 px-3.5 py-2 text-xs font-medium bg-cream-100 hover:bg-cream-200 text-cream-800 rounded-lg border border-cream-300 transition shadow-2xs"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loadingAgents ? "animate-spin" : ""}`} />
            Refresh Telemetry
          </button>
          <button
            onClick={handleRunAllAgents}
            disabled={runningAll}
            className="flex items-center gap-2 px-4 py-2 text-xs font-medium bg-cream-900 hover:bg-cream-800 text-cream-50 rounded-lg shadow-sm transition disabled:opacity-50"
          >
            {runningAll ? (
              <RefreshCw className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Sparkles className="w-3.5 h-3.5 text-amberGold-400" />
            )}
            Run All Agent Cycles
          </button>
        </div>
      </div>

      {/* Main Mode Tabs */}
      <div className="flex items-center gap-3 border-b border-cream-300 pb-1">
        <button
          onClick={() => setActiveTab("SUPERVISORS")}
          className={`flex items-center gap-2 px-3 py-2 text-xs transition border-b-2 ${
            activeTab === "SUPERVISORS"
              ? "border-cream-900 text-cream-900 font-semibold"
              : "border-transparent text-cream-600 hover:text-cream-900"
          }`}
        >
          <Bot className="w-4 h-4" />
          Autonomous Domain Supervisors (EAIWP)
        </button>
        <button
          onClick={() => setActiveTab("DAGS")}
          className={`flex items-center gap-2 px-3 py-2 text-xs transition border-b-2 ${
            activeTab === "DAGS"
              ? "border-cream-900 text-cream-900 font-semibold"
              : "border-transparent text-cream-600 hover:text-cream-900"
          }`}
        >
          <Cpu className="w-4 h-4" />
          Agent Mesh & Hierarchical DAGs
        </button>
      </div>

      {/* Feedback banner */}
      {feedback && (
        <div
          className={`flex items-center justify-between p-4 rounded-xl border text-sm shadow-2xs ${
            feedback.type === "success"
              ? "bg-sage-50 text-sage-800 border-sage-300"
              : "bg-terracotta-50 text-terracotta-800 border-terracotta-300"
          }`}
        >
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 shrink-0 text-sage-600" />
            <span>{feedback.text}</span>
          </div>
          <button onClick={() => setFeedback(null)} className="text-xs opacity-75 hover:opacity-100">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {activeTab === "SUPERVISORS" ? (
        <div className="space-y-6">
          {/* 6 Autonomous Supervisors Grid */}
          <div>
            <div className="flex items-center justify-between mb-3.5">
              <h2 className="text-xs font-semibold text-cream-900 tracking-wide uppercase">
                Active Domain Supervisors ({agents.length})
              </h2>
              <span className="text-xs text-cream-600">
                Governed by Human-in-the-Loop Thresholds & Multi-Channel Gateways
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {agents.map((agent) => {
                const domainStyle = DOMAIN_STYLES[agent.domain] || {
                  label: agent.domain,
                  badge: "bg-cream-200 text-cream-800 border-cream-300",
                  icon: Bot,
                };
                const DomainIcon = domainStyle.icon;
                const isRunning = runningAgentSlug === agent.slug || runningAll;

                return (
                  <div
                    key={agent.agent_id}
                    className="bg-cream-100 border border-cream-300 rounded-xl p-5 hover:border-cream-400 hover:shadow-sm transition flex flex-col justify-between shadow-2xs space-y-4"
                  >
                    <div>
                      {/* Top badges */}
                      <div className="flex items-center justify-between gap-2 mb-3">
                        <span
                          className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-lg text-[11px] font-semibold border ${domainStyle.badge}`}
                        >
                          <DomainIcon className="w-3.5 h-3.5" />
                          {domainStyle.label}
                        </span>

                        <span className="inline-flex items-center gap-1.5 text-[11px] text-sage-700 bg-sage-50 border border-sage-200 px-2 py-0.5 rounded-full font-mono font-medium">
                          <span className="w-1.5 h-1.5 rounded-full bg-sage-500" />
                          {agent.autonomy_level}
                        </span>
                      </div>

                      {/* Agent Title & Description */}
                      <h3 className="text-sm font-bold text-cream-900 mb-1.5">{agent.name}</h3>
                      <p className="text-xs text-cream-700 leading-relaxed line-clamp-3">
                        {agent.description}
                      </p>
                    </div>

                    {/* Footer Controls */}
                    <div className="pt-3 border-t border-cream-300 flex items-center justify-between gap-2">
                      <span className="text-[11px] font-mono text-cream-600">
                        Trigger: {agent.trigger_type}
                      </span>
                      <button
                        onClick={() => handleRunAgent(agent.slug)}
                        disabled={isRunning}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-cream-900 hover:bg-cream-800 text-cream-50 rounded-lg transition shadow-2xs disabled:opacity-50"
                      >
                        {isRunning ? (
                          <RefreshCw className="w-3 h-3 animate-spin" />
                        ) : (
                          <Play className="w-3 h-3 fill-current" />
                        )}
                        <span>{isRunning ? "Running..." : "Run Cycle Now"}</span>
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Activity Logs & Multi-Channel Feed */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Live Execution Runs Table (2 cols) */}
            <div className="lg:col-span-2 bg-cream-100 border border-cream-300 rounded-xl p-5 shadow-2xs space-y-4">
              <div className="flex items-center justify-between border-b border-cream-300 pb-3">
                <div className="flex items-center gap-2">
                  <Terminal className="w-4 h-4 text-cream-800" />
                  <h3 className="text-xs font-semibold text-cream-900 uppercase tracking-wide">
                    Live Execution Runs & Traceability
                  </h3>
                </div>
                <span className="text-xs text-cream-600">{runs.length} logged runs</span>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left">
                  <thead className="text-[10px] font-mono uppercase text-cream-600 border-b border-cream-300">
                    <tr>
                      <th className="pb-2">Agent / Run ID</th>
                      <th className="pb-2">Trigger</th>
                      <th className="pb-2">Status</th>
                      <th className="pb-2">Summary</th>
                      <th className="pb-2">Time</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-cream-200 font-mono">
                    {runs.length === 0 ? (
                      <tr>
                        <td colSpan={5} className="py-6 text-center text-cream-600">
                          No execution runs recorded yet. Click "Run Cycle Now" above to initiate a cycle.
                        </td>
                      </tr>
                    ) : (
                      runs.map((r) => {
                        const isSuccess = r.status === "COMPLETED";
                        const isPendingApproval = r.status === "AWAITING_APPROVAL";
                        return (
                          <tr
                            key={r.run_id}
                            onClick={() => setSelectedRun(r)}
                            className="hover:bg-cream-200/50 cursor-pointer transition"
                          >
                            <td className="py-2.5 pr-2">
                              <span className="text-cream-900 font-semibold block">{r.agent_name}</span>
                              <span className="text-[10px] text-cream-500">{r.run_id.slice(0, 8)}...</span>
                            </td>
                            <td className="py-2.5 text-cream-700">{r.trigger_type}</td>
                            <td className="py-2.5">
                              <span
                                className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                                  isSuccess
                                    ? "bg-sage-100 text-sage-800 border-sage-300"
                                    : isPendingApproval
                                    ? "bg-amberGold-100 text-amberGold-800 border-amberGold-300"
                                    : "bg-terracotta-100 text-terracotta-800 border-terracotta-300"
                                }`}
                              >
                                {r.status}
                              </span>
                            </td>
                            <td className="py-2.5 pr-2 text-cream-800 font-sans text-xs max-w-xs truncate">
                              {r.summary || "Cycle executed successfully."}
                            </td>
                            <td className="py-2.5 text-cream-600 text-[11px] whitespace-nowrap">
                              {new Date(r.started_at).toLocaleTimeString()}
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Outbound Communications Ledger (1 col) */}
            <div className="bg-cream-100 border border-cream-300 rounded-xl p-5 shadow-2xs space-y-4 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between border-b border-cream-300 pb-3 mb-3">
                  <div className="flex items-center gap-2">
                    <MessageSquare className="w-4 h-4 text-cream-800" />
                    <h3 className="text-xs font-semibold text-cream-900 uppercase tracking-wide">
                      Outbound Communications
                    </h3>
                  </div>
                  <span className="text-[10px] px-2 py-0.5 rounded bg-sage-100 text-sage-800 border border-sage-200 font-mono">
                    WhatsApp + Gmail
                  </span>
                </div>

                <div className="space-y-3 max-h-[480px] overflow-y-auto pr-1">
                  {communications.length === 0 ? (
                    <div className="p-8 text-center text-xs text-cream-600">
                      No communications dispatched yet.
                    </div>
                  ) : (
                    communications.map((comm) => (
                      <div
                        key={comm.comm_id}
                        className="p-3 rounded-lg bg-cream-50 border border-cream-200 space-y-1.5 text-xs font-mono"
                      >
                        <div className="flex items-center justify-between text-[11px]">
                          <span
                            className={`px-1.5 py-0.5 rounded font-bold border text-[10px] ${
                              comm.channel === "WHATSAPP"
                                ? "bg-sage-100 text-sage-800 border-sage-300"
                                : "bg-blue-50 text-blue-800 border-blue-200"
                            }`}
                          >
                            {comm.channel}
                          </span>
                          <span className="text-cream-500 text-[10px]">
                            {new Date(comm.created_at).toLocaleTimeString()}
                          </span>
                        </div>

                        <div className="text-cream-900 font-semibold truncate">
                          To: {comm.recipient}
                        </div>
                        {comm.subject && (
                          <div className="text-cream-700 text-[11px] truncate">
                            Sub: {comm.subject}
                          </div>
                        )}
                        <p className="text-cream-700 font-sans text-xs leading-relaxed line-clamp-2">
                          "{comm.body}"
                        </p>
                        {comm.external_message_id && (
                          <div className="text-[10px] text-cream-500 pt-1">
                            Ext ID: {comm.external_message_id}
                          </div>
                        )}
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Selected Run Details Modal */}
          {selectedRun && (
            <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
              <div className="bg-cream-50 border border-cream-300 rounded-2xl max-w-2xl w-full p-6 space-y-4 shadow-xl text-cream-900">
                <div className="flex items-center justify-between border-b border-cream-300 pb-3">
                  <h3 className="text-base font-semibold text-cream-900 flex items-center gap-2">
                    <Terminal className="w-5 h-5 text-cream-800" />
                    Agent Run Trace: {selectedRun.agent_name}
                  </h3>
                  <button onClick={() => setSelectedRun(null)} className="text-cream-500 hover:text-cream-900">
                    <X className="w-5 h-5" />
                  </button>
                </div>

                <div className="text-xs space-y-3 font-mono">
                  <div className="grid grid-cols-2 gap-2 p-3 bg-cream-100 rounded-lg border border-cream-300">
                    <div>
                      <span className="text-cream-500 block">Run ID:</span>
                      <span className="text-cream-900 font-semibold">{selectedRun.run_id}</span>
                    </div>
                    <div>
                      <span className="text-cream-500 block">Status:</span>
                      <span className="text-sage-700 font-bold">{selectedRun.status}</span>
                    </div>
                    <div>
                      <span className="text-cream-500 block">Trigger:</span>
                      <span className="text-cream-800">{selectedRun.trigger_type}</span>
                    </div>
                    <div>
                      <span className="text-cream-500 block">Started:</span>
                      <span className="text-cream-800">{new Date(selectedRun.started_at).toLocaleString()}</span>
                    </div>
                  </div>

                  <div>
                    <span className="text-cream-700 font-sans font-semibold block mb-1">Execution Summary:</span>
                    <p className="p-3 bg-cream-100 rounded-lg border border-cream-300 text-cream-900 font-sans text-xs leading-relaxed">
                      {selectedRun.summary}
                    </p>
                  </div>

                  {selectedRun.execution_metrics && (
                    <div>
                      <span className="text-cream-700 font-semibold block mb-1">Execution Metrics:</span>
                      <pre className="p-3 bg-cream-100 rounded-lg border border-cream-300 text-cream-800 text-[11px] overflow-x-auto">
                        {JSON.stringify(selectedRun.execution_metrics, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>

                <div className="flex justify-end pt-2 border-t border-cream-300">
                  <button
                    onClick={() => setSelectedRun(null)}
                    className="px-4 py-1.5 text-xs font-medium bg-cream-200 hover:bg-cream-300 text-cream-900 rounded-lg border border-cream-300"
                  >
                    Close
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      ) : (
        /* Agent Mesh & DAG Orchestrator Tab */
        <div className="space-y-6">
          {/* Agent Mesh Status Pills */}
          <div className="rounded-xl border border-cream-300 bg-cream-100 p-5 shadow-2xs">
            <div className="flex items-center justify-between border-b border-cream-300 pb-3">
              <h2 className="text-xs font-semibold text-cream-900 uppercase tracking-wide">
                Autonomous Agent Topology (6 Nodes)
              </h2>
              <span className="font-mono text-[10px] text-cream-700">Sandboxed Subagent Contexts</span>
            </div>

            <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
              {Object.entries(agentStates).map(([agent, state]) => (
                <div
                  key={agent}
                  className="rounded-lg border border-cream-300 bg-cream-50 p-3 flex flex-col justify-between"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-[9px] uppercase font-semibold text-cream-700">
                      {agent.replace("_", " ")}
                    </span>
                    <span className={`h-2 w-2 rounded-full ${state === "BUSY" ? "bg-amberGold-500 animate-pulse" : "bg-sage-500"}`} />
                  </div>
                  <div className="mt-2 text-xs font-mono font-semibold text-cream-900">
                    {state}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* DAG Flow Section */}
          <div className="rounded-xl border border-cream-300 bg-cream-100 p-6 shadow-2xs space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-cream-300 pb-4">
              <div>
                <div className="flex items-center gap-3">
                  <h2 className="text-sm font-semibold text-cream-900">
                    Hierarchical Task DAG Visualizer
                  </h2>
                  {activeDag && (
                    <span className="rounded bg-cream-200 px-2 py-0.5 text-[10px] font-mono text-cream-800 border border-cream-300">
                      {activeDag.dag_id}
                    </span>
                  )}
                </div>
                <p className="text-xs text-cream-700 mt-0.5">
                  Strict topological sorting guarantees causal sequence and invariant compliance before mutation.
                </p>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => fetchDag(activeDag?.dag_id)}
                  disabled={loadingDag}
                  className="inline-flex items-center gap-1.5 rounded-md border border-cream-300 bg-cream-50 px-3 py-1.5 text-xs text-cream-800 hover:bg-cream-200"
                >
                  <RefreshCw className={`h-3 w-3 ${loadingDag ? "animate-spin" : ""}`} />
                  <span>Refresh DAG</span>
                </button>
                <button
                  onClick={() => setShowDispatchModal(!showDispatchModal)}
                  className="inline-flex items-center gap-1.5 rounded-md bg-cream-900 px-3 py-1.5 text-xs font-medium text-cream-50 hover:bg-cream-800 transition-colors shadow-xs"
                >
                  <Plus className="h-3 w-3" />
                  <span>Dispatch Inbound RFQ</span>
                </button>
              </div>
            </div>

            {/* Recent DAGs Selector Row */}
            {dagsList.length > 0 && (
              <div className="flex items-center gap-2 overflow-x-auto pb-1 text-xs">
                <span className="text-[10px] font-mono text-cream-600 shrink-0 uppercase font-semibold">Recent Inbound DAGs:</span>
                {dagsList.map((d: any) => (
                  <button
                    key={d.dag_id}
                    onClick={() => fetchDag(d.dag_id)}
                    className={`px-2.5 py-1 rounded text-[11px] font-mono whitespace-nowrap transition-colors border ${
                      activeDag?.dag_id === d.dag_id
                        ? "bg-cream-900 text-cream-50 border-cream-900 font-semibold"
                        : "bg-cream-50 text-cream-700 border-cream-300 hover:bg-cream-200"
                    }`}
                  >
                    {d.customer_name || "Commercial RFQ"} ({d.dag_id}) • {d.status}
                  </button>
                ))}
              </div>
            )}

            {/* Modal / Inline Drawer for Dispatching New RFQ */}
            {showDispatchModal && (
              <div className="rounded-lg border border-cream-400 bg-cream-50 p-5 space-y-4 shadow-sm animate-fadeIn">
                <div className="flex items-center justify-between border-b border-cream-300 pb-2">
                  <span className="text-xs font-semibold text-cream-900">Dispatch Inbound RFQ DAG to Mesh</span>
                  <button onClick={() => setShowDispatchModal(false)} className="text-cream-600 hover:text-cream-900">
                    <X className="h-4 w-4" />
                  </button>
                </div>
                <form onSubmit={handleDispatchRFQ} className="space-y-3">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                      <label className="block text-[11px] font-medium text-cream-800 mb-1">
                        Customer / Inquiring Organization
                      </label>
                      <input
                        type="text"
                        required
                        value={customerName}
                        onChange={(e) => setCustomerName(e.target.value)}
                        className="w-full rounded-md border border-cream-300 bg-cream-100 px-3 py-1.5 text-xs text-cream-900 focus:outline-hidden focus:border-cream-500"
                        placeholder="e.g. AeroDynamics GmbH"
                      />
                    </div>
                    <div>
                      <label className="block text-[11px] font-medium text-cream-800 mb-1">
                        Commercial Inquiry Text
                      </label>
                      <input
                        type="text"
                        required
                        value={inquiryText}
                        onChange={(e) => setInquiryText(e.target.value)}
                        className="w-full rounded-md border border-cream-300 bg-cream-100 px-3 py-1.5 text-xs text-cream-900 focus:outline-hidden focus:border-cream-500"
                        placeholder="Order specifications..."
                      />
                    </div>
                  </div>
                  {dispatchError && <p className="text-[11px] text-terracotta-700">{dispatchError}</p>}
                  <div className="flex justify-end gap-2">
                    <button
                      type="button"
                      onClick={() => setShowDispatchModal(false)}
                      className="rounded-md border border-cream-300 bg-cream-100 px-3 py-1.5 text-xs text-cream-800 hover:bg-cream-200"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={dispatching}
                      className="inline-flex items-center gap-1.5 rounded-md border border-cream-400 bg-cream-900 px-4 py-1.5 text-xs font-medium text-cream-50 hover:bg-cream-800 disabled:opacity-50"
                    >
                      <Send className="h-3 w-3" />
                      <span>{dispatching ? "Formulating DAG..." : "Execute DAG"}</span>
                    </button>
                  </div>
                </form>
              </div>
            )}

            {loadingDag && !activeDag ? (
              <div className="py-12 text-center text-xs font-mono text-cream-600">
                <RefreshCw className="h-6 w-6 animate-spin mx-auto text-cream-400 mb-2" />
                <span>Loading task DAG topology...</span>
              </div>
            ) : activeDag ? (
              <div className="space-y-4">
                <div className="text-xs font-mono text-cream-800 flex items-center justify-between bg-cream-50 p-3 rounded-lg border border-cream-200">
                  <div>
                    <span className="text-[10px] text-cream-600 uppercase font-bold block">Event Source:</span>
                    <span className="font-semibold text-cream-900">{activeDag.customer_name || "Commercial Customer"}</span>
                    {activeDag.inquiry_text && (
                      <span className="text-cream-600 text-[11px] ml-2 italic truncate max-w-md inline-block align-bottom">
                        &ldquo;{activeDag.inquiry_text}&rdquo;
                      </span>
                    )}
                  </div>
                  <div className="text-right">
                    <span className="text-[10px] text-cream-600 uppercase font-bold block">Status:</span>
                    <span className={`font-semibold ${activeDag.status === "COMPLETED" ? "text-sage-700" : "text-amberGold-600 animate-pulse"}`}>
                      {activeDag.status}
                    </span>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                  {activeDag.nodes?.map((node: any, idx: number) => {
                    const isCompleted = node.status === "COMPLETED";
                    const isRunning = node.status === "RUNNING";
                    return (
                      <div
                        key={node.task_id}
                        className="relative rounded-lg border border-cream-300 bg-cream-50 p-4 shadow-2xs space-y-3 flex flex-col justify-between"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-mono text-xs font-bold text-cream-700">
                            T{idx + 1}
                          </span>
                          <span className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-mono ${
                            isCompleted
                              ? "bg-sage-100 text-sage-800"
                              : isRunning
                              ? "bg-amberGold-100 text-amberGold-800 animate-pulse"
                              : "bg-cream-200 text-cream-700"
                          }`}>
                            {isCompleted && <CheckCircle2 className="h-3 w-3 text-sage-600" />}
                            {isRunning && <RefreshCw className="h-3 w-3 animate-spin text-amberGold-600" />}
                            <span>{node.status}</span>
                          </span>
                        </div>

                        <div>
                          <div className="text-xs font-semibold text-cream-900">{node.name}</div>
                          <div className="text-[11px] font-mono text-cream-700 mt-0.5">
                            Agent: <span className="font-semibold">{node.agent_id}</span>
                          </div>
                        </div>

                        {/* Node Output Preview if Completed */}
                        {node.output_result && (
                          <div className="rounded border border-cream-200 bg-cream-100/70 p-2 text-[10px] font-mono text-cream-800 space-y-0.5">
                            <span className="text-[9px] text-cream-500 font-bold block uppercase">Agent Output:</span>
                            {node.output_result.po_number && (
                              <div>PO#: <span className="font-semibold text-cream-900">{node.output_result.po_number}</span></div>
                            )}
                            {node.output_result.requested_sku && (
                              <div>SKU: <span className="font-semibold text-cream-900">{node.output_result.requested_sku}</span></div>
                            )}
                            {node.output_result.quantity && (
                              <div>Qty: <span className="font-semibold text-cream-900">{node.output_result.quantity}</span></div>
                            )}
                            {node.output_result.order_number && (
                              <div>SO#: <span className="font-semibold text-cream-900">{node.output_result.order_number}</span></div>
                            )}
                            {node.output_result.invoice_number && (
                              <div>Inv#: <span className="font-semibold text-cream-900">{node.output_result.invoice_number}</span></div>
                            )}
                          </div>
                        )}

                        <div className="pt-2 border-t border-cream-200 text-[10px] font-mono text-cream-600 flex items-center justify-between">
                          <span>
                            Deps: {Array.isArray(node.dependencies) && node.dependencies.length > 0 ? `${node.dependencies.length} prior` : "Root"}
                          </span>
                          <span className={isCompleted ? "text-sage-700 font-medium" : isRunning ? "text-amberGold-700 font-medium" : "text-cream-500"}>
                            {isCompleted ? "Completed" : isRunning ? "Active" : "Pending"}
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ) : (
              <div className="rounded-xl border border-cream-300 bg-cream-50 p-8 text-center space-y-4">
                <Layers className="h-8 w-8 text-cream-400 mx-auto" />
                <div className="space-y-1">
                  <h3 className="text-xs font-semibold text-cream-900">
                    No Active Multi-Agent DAG Execution
                  </h3>
                  <p className="text-[11px] text-cream-600 max-w-md mx-auto">
                    Dispatch an inbound commercial RFQ to observe dynamic task graph generation and subagent context sandboxing.
                  </p>
                </div>
              </div>
            )}
          </div>

          {/* Conflict Resolution Interactive Engine */}
          <div className="rounded-xl border border-cream-300 bg-cream-100 p-6 shadow-2xs space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-cream-300 pb-4">
              <div>
                <h2 className="text-sm font-semibold text-cream-900">
                  Deterministic Conflict Resolution Engine
                </h2>
                <p className="text-[11px] text-cream-700 mt-0.5">
                  Executes strict partial order arbitration when competing domain subagents collide over shared resources.
                </p>
              </div>
              <button
                onClick={handleSimulateConflict}
                disabled={arbitrating}
                className="inline-flex items-center gap-1.5 rounded-md border border-cream-400 bg-cream-900 px-3.5 py-1.5 text-xs font-medium text-cream-50 hover:bg-cream-800 disabled:opacity-50"
              >
                <Play className="h-3.5 w-3.5" />
                <span>{arbitrating ? "Arbitrating..." : "Simulate Live Machine Collision"}</span>
              </button>
            </div>

            {arbitrationError && (
              <div className="rounded border border-terracotta-100 bg-terracotta-50 p-3 text-xs text-terracotta-700">
                {arbitrationError}
              </div>
            )}

            {arbitrationResult && (
              <div className="rounded-lg border border-cream-300 bg-cream-50 p-5 space-y-4 animate-fadeIn">
                <div className="flex items-center justify-between border-b border-cream-200 pb-3">
                  <div className="flex items-center gap-2 text-xs font-semibold text-cream-900">
                    <ShieldCheck className="h-4 w-4 text-sage-600" />
                    <span>Arbitration Completed • Collision Arbitrated</span>
                  </div>
                  <span className="font-mono text-[10px] text-cream-700">
                    P_Statutory_Legal (Rank 5) &gt; P_Contractual_SLA (Rank 3)
                  </span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono">
                  <div className="rounded border border-sage-200 bg-sage-50/60 p-3">
                    <span className="text-sage-700 block text-[10px] font-bold">STAGED ACTION (WINNER):</span>
                    <span className="font-semibold text-cream-900 mt-1 block">
                      PRODUCTION Agent • STATUTORY_LEGAL (Rank 5)
                    </span>
                    <p className="text-[11px] text-cream-700 mt-1">
                      Machine safety vibration limit override executed on workstation:WS-CNC-01.
                    </p>
                  </div>

                  <div className="rounded border border-terracotta-200 bg-terracotta-50/60 p-3">
                    <span className="text-terracotta-700 block text-[10px] font-bold">PREEMPTED ACTION (LOSER):</span>
                    <span className="font-semibold text-cream-900 mt-1 block">
                      REVENUE Agent • CONTRACTUAL_SLA (Rank 3)
                    </span>
                    <p className="text-[11px] text-cream-700 mt-1">
                      VIP expedite order preempted. Preemption signal emitted with bounded replanning search space.
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default function AgentsPage() {
  return (
    <Suspense
      fallback={
        <div className="py-20 text-center text-xs font-mono text-cream-600">
          <RefreshCw className="h-6 w-6 animate-spin mx-auto text-cream-400 mb-2" />
          <span>Connecting to autonomous workforce command center...</span>
        </div>
      }
    >
      <AgentsContent />
    </Suspense>
  );
}
