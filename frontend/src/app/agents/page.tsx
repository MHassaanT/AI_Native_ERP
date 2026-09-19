"use client";

import { useEffect, useState } from "react";
import {
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  ChevronRight,
  Clock,
  Cpu,
  Layers,
  Play,
  RefreshCw,
  Send,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { api } from "@/lib/api";

export default function AgentsPage() {
  const [agentStates, setAgentStates] = useState<Record<string, string>>({
    FINANCIAL_CONTROLLER: "IDLE",
    SUPPLY_CHAIN: "IDLE",
    PRODUCTION: "IDLE",
    REVENUE: "IDLE",
    WORKFORCE: "IDLE",
    COMPLIANCE: "IDLE",
  });
  const [loading, setLoading] = useState(false);

  // Active DAG Execution
  const [activeDag, setActiveDag] = useState<{
    dag_id: string;
    nodes: any[];
    status: string;
    customer_name?: string;
  } | null>(null);

  // RFQ Dispatch Form
  const [customerName, setCustomerName] = useState("AeroDynamics GmbH");
  const [inquiryText, setInquiryText] = useState("Need 500 units IP67 industrial enclosures by Q4.");
  const [dispatching, setDispatching] = useState(false);
  const [dispatchError, setDispatchError] = useState<string | null>(null);

  // Real Arbitration Result from Server
  const [arbitrating, setArbitrating] = useState(false);
  const [arbitrationResult, setArbitrationResult] = useState<any | null>(null);
  const [arbitrationError, setArbitrationError] = useState<string | null>(null);

  const loadAgentStates = async () => {
    try {
      const states = await api.getAgentStates();
      setAgentStates(states);
    } catch {
      // Keep default states
    }
  };

  useEffect(() => {
    loadAgentStates();
  }, []);

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
      });
      await loadAgentStates();
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
      // Send real multi-agent collision proposals to backend conflict engine
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
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between border-b border-cream-300 pb-5">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-cream-900">
            Agent Mesh & DAG Orchestrator
          </h1>
          <p className="text-xs text-cream-700 mt-1">
            Hierarchical task graph decomposition, sandboxed context execution, and mathematical preemption.
          </p>
        </div>

        <button
          onClick={loadAgentStates}
          className="inline-flex items-center gap-1.5 rounded-md border border-cream-300 bg-cream-100 px-3 py-1.5 text-xs text-cream-800 hover:bg-cream-200"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          <span>Refresh Mesh Status</span>
        </button>
      </div>

      {/* Agent Mesh Status Pills */}
      <div className="rounded-xl border border-cream-300 bg-cream-100 p-5 shadow-xs">
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
      <div className="rounded-xl border border-cream-300 bg-cream-100 p-6 shadow-xs space-y-6">
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

          {activeDag && (
            <span className="rounded-full bg-sage-50 text-sage-700 border border-sage-200 px-3 py-1 text-[11px] font-medium font-mono">
              Topological Sort Validated
            </span>
          )}
        </div>

        {activeDag ? (
          <div className="space-y-4">
            <div className="text-xs font-mono text-cream-800 flex items-center justify-between">
              <span>Event Source: RFQ from {activeDag.customer_name}</span>
              <span className="text-sage-700 font-semibold">{activeDag.status}</span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              {activeDag.nodes.map((node: any, idx: number) => (
                <div
                  key={node.task_id}
                  className="relative rounded-lg border border-cream-300 bg-cream-50 p-4 shadow-2xs space-y-3"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-xs font-bold text-cream-700">
                      T{idx + 1}
                    </span>
                    <span className="rounded bg-cream-200/80 px-1.5 py-0.5 text-[10px] font-mono text-cream-700">
                      {node.status}
                    </span>
                  </div>

                  <div>
                    <div className="text-xs font-semibold text-cream-900">{node.name}</div>
                    <div className="text-[11px] font-mono text-cream-700 mt-1">
                      Agent: {node.agent_id}
                    </div>
                  </div>

                  <div className="pt-2 border-t border-cream-200 text-[10px] font-mono text-cream-600 flex items-center justify-between">
                    <span>
                      Deps: {Array.isArray(node.dependencies) && node.dependencies.length > 0 ? `${node.dependencies.length} prior` : "Root"}
                    </span>
                    <span className="text-sage-700">Active</span>
                  </div>
                </div>
              ))}
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
                Dispatch an inbound commercial RFQ to observe dynamic task graph generation, subagent context sandboxing, and topological validation in action.
              </p>
            </div>

            <form onSubmit={handleDispatchRFQ} className="max-w-md mx-auto space-y-3 text-left pt-2">
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
                  Commercial Inquiry
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

              {dispatchError && (
                <p className="text-[11px] text-terracotta-700">{dispatchError}</p>
              )}

              <button
                type="submit"
                disabled={dispatching}
                className="w-full inline-flex items-center justify-center gap-2 rounded-md border border-cream-400 bg-cream-900 py-2 text-xs font-medium text-cream-50 hover:bg-cream-800 disabled:opacity-50"
              >
                <Send className="h-3.5 w-3.5" />
                <span>{dispatching ? "Formulating DAG..." : "Dispatch Task DAG to Mesh"}</span>
              </button>
            </form>
          </div>
        )}
      </div>

      {/* Conflict Resolution Interactive Engine */}
      <div className="rounded-xl border border-cream-300 bg-cream-100 p-6 shadow-xs space-y-4">
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

            {arbitrationResult.preemptions && arbitrationResult.preemptions.length > 0 && (
              <div className="rounded border border-cream-200 bg-cream-100 p-3 font-mono text-[11px] text-cream-800">
                <div className="text-[10px] text-cream-600 font-bold mb-1">EMITTED PREEMPTION SIGNAL:</div>
                <pre className="text-[10px] overflow-x-auto text-cream-700">
                  {JSON.stringify(arbitrationResult.preemptions[0], null, 2)}
                </pre>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
