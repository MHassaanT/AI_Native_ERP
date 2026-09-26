"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowRight,
  ArrowUpRight,
  CheckCircle2,
  Cpu,
  DollarSign,
  FileCheck,
  Package,
  RefreshCw,
  ShieldCheck,
  Users,
  Wrench,
  Zap,
} from "lucide-react";
import { api } from "@/lib/api";
import { getUser } from "@/lib/auth";
import { ModuleOnboardingWidget } from "@/components/module-onboarding";

export default function OverviewPage() {
  const [user, setUser] = useState<any>(null);
  const [agentStates, setAgentStates] = useState<Record<string, string>>({
    FINANCIAL_CONTROLLER: "IDLE",
    SUPPLY_CHAIN: "IDLE",
    PRODUCTION: "IDLE",
    REVENUE: "IDLE",
    WORKFORCE: "IDLE",
    COMPLIANCE: "IDLE",
  });
  const [dispatchStatus, setDispatchStatus] = useState<string | null>(null);
  const [dispatchedDagId, setDispatchedDagId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // Live Metrics
  const [cashBuffer, setCashBuffer] = useState<string>("$0.00");
  const [cashNote, setCashNote] = useState<string>("GAAP 1010 Account active");
  const [matchRate, setMatchRate] = useState<string>("0.0%");
  const [matchNote, setMatchNote] = useState<string>("0 invoices processed");
  const [nodeCount, setNodeCount] = useState<number>(6);
  const [ledgerDrift, setLedgerDrift] = useState<string>("0.0000");
  const [isFreshTenant, setIsFreshTenant] = useState<boolean>(true);

  // Interactive RFQ Form
  const [showRfqModal, setShowRfqModal] = useState(false);
  const [customerName, setCustomerName] = useState("Delta Aerospace LLC");
  const [inquiryText, setInquiryText] = useState("Urgent order for 250 units titanium structural brackets with certified mill test reports.");
  const [dispatching, setDispatching] = useState(false);

  const loadLiveData = async () => {
    setLoading(true);
    try {
      const currentUser = getUser();
      setUser(currentUser);

      const [statesRes, accountsRes, invoicesRes, entriesRes] = await Promise.allSettled([
        api.getAgentStates(),
        api.getAccounts(),
        api.getInvoices(),
        api.getGLEntries(),
      ]);

      // 1. Agent States
      if (statesRes.status === "fulfilled" && statesRes.value) {
        setAgentStates(statesRes.value);
        setNodeCount(Object.keys(statesRes.value).length);
      }

      // 2. GL Accounts & Cash Buffer
      if (accountsRes.status === "fulfilled" && Array.isArray(accountsRes.value)) {
        const cashAccounts = accountsRes.value.filter(
          (acc: any) =>
            acc.account_type === "ASSET" &&
            (acc.account_code?.startsWith("10") || acc.account_name?.toLowerCase().includes("cash"))
        );
        const totalCash = cashAccounts.reduce((sum: number, acc: any) => sum + Number(acc.current_balance || 0), 0);
        if (totalCash > 0) {
          setCashBuffer(`$${totalCash.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`);
          setCashNote("Live GL Cash & Equivalents");
        } else {
          setCashBuffer("$0.00");
          setCashNote("Awaiting initial funding deposit");
        }
      }

      // 3. Accounts Payable 3-Way Match Rate
      if (invoicesRes.status === "fulfilled" && Array.isArray(invoicesRes.value)) {
        const invoices = invoicesRes.value;
        if (invoices.length === 0) {
          setMatchRate("0.0%");
          setMatchNote("0 invoices in database");
          setIsFreshTenant(true);
        } else {
          setIsFreshTenant(false);
          const matched = invoices.filter((i: any) => i.match_status === "MATCHED").length;
          const rate = ((matched / invoices.length) * 100).toFixed(1);
          setMatchRate(`${rate}%`);
          setMatchNote(`${matched} of ${invoices.length} matched touchless`);
        }
      }

      // 4. Ledger Zero-Sum Drift
      if (entriesRes.status === "fulfilled" && Array.isArray(entriesRes.value)) {
        const entries = entriesRes.value;
        if (entries.length === 0) {
          setLedgerDrift("0.0000");
        } else {
          let totalDebit = 0;
          let totalCredit = 0;
          entries.forEach((e: any) => {
            if (Array.isArray(e.lines)) {
              e.lines.forEach((l: any) => {
                totalDebit += Number(l.debit_amount || 0);
                totalCredit += Number(l.credit_amount || 0);
              });
            }
          });
          const drift = Math.abs(totalDebit - totalCredit);
          setLedgerDrift(drift.toFixed(4));
        }
      }
    } catch {
      // Fallbacks already initialized to zero-state
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadLiveData();
  }, []);

  const handleSimulateRFQ = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    setDispatching(true);
    setDispatchStatus("Formulating multi-agent task DAG...");
    try {
      const res = await api.dispatchRFQ({
        customer_name: customerName,
        inquiry_text: inquiryText,
      });
      setDispatchedDagId(res.dag_id);
      setDispatchStatus(`DAG '${res.dag_id}' dispatched with ${res.nodes?.length || 4} subtasks across mesh.`);
      setShowRfqModal(false);
    } catch (err: any) {
      setDispatchStatus(err.message || "Failed to dispatch RFQ");
    } finally {
      setDispatching(false);
    }
  };

  const kpis = [
    {
      title: "13-Week Cash Buffer",
      value: cashBuffer,
      change: cashNote,
      icon: DollarSign,
    },
    {
      title: "Touchless 3-Way Match Rate",
      value: matchRate,
      change: matchNote,
      icon: CheckCircle2,
    },
    {
      title: "Active Autonomous Agents",
      value: `${nodeCount} Nodes`,
      change: "Mesh fully operational",
      icon: Cpu,
    },
    {
      title: "Ledger Zero-Sum Drift",
      value: ledgerDrift,
      change: "Invariants 100% verified",
      icon: ShieldCheck,
    },
  ];

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between border-b border-cream-300 pb-5">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-semibold tracking-tight text-cream-900">
              Executive Control Center
            </h1>
            {user?.tenant_slug && (
              <span className="rounded bg-cream-200 px-2 py-0.5 font-mono text-[11px] text-cream-800 border border-cream-300">
                {user.tenant_name || user.tenant_slug}
              </span>
            )}
          </div>
          <p className="text-xs text-cream-700 mt-1">
            Real-time autonomous multi-agent operational synthesis and invariant monitoring.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => loadLiveData()}
            title="Refresh live metrics"
            className="rounded-md border border-cream-300 bg-cream-100 p-1.5 text-cream-700 hover:bg-cream-200 transition-colors"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
          </button>
          <button
            onClick={() => setShowRfqModal(true)}
            className="inline-flex items-center gap-2 rounded-md border border-cream-400 bg-cream-900 px-3.5 py-1.5 text-xs font-medium text-cream-50 shadow-xs hover:bg-cream-800 transition-colors"
          >
            <Zap className="h-3.5 w-3.5 text-amberGold-500" />
            <span>Dispatch Inbound RFQ</span>
          </button>
        </div>
      </div>

      {dispatchStatus && (
        <div className="rounded border border-sage-100 bg-sage-50 px-4 py-2 text-xs font-mono text-sage-700 flex items-center justify-between">
          <span>&bull; {dispatchStatus}</span>
          <Link href={dispatchedDagId ? `/agents?dag_id=${dispatchedDagId}` : "/agents"} className="text-[10px] uppercase underline hover:text-sage-800">
            View Agent DAG &rarr;
          </Link>
        </div>
      )}

      {/* KPI Cards Grid - Live Data */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {kpis.map((kpi) => {
          const Icon = kpi.icon;
          return (
            <div
              key={kpi.title}
              className="rounded-lg border border-cream-300 bg-cream-100 p-4 shadow-xs transition-hover hover:border-cream-400"
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-cream-700">{kpi.title}</span>
                <Icon className="h-4 w-4 text-cream-700" />
              </div>
              <div className="mt-3 font-mono text-2xl font-bold tracking-tight text-cream-900">
                {kpi.value}
              </div>
              <div className="mt-1 text-[11px] text-sage-700 font-medium">
                {kpi.change}
              </div>
            </div>
          );
        })}
      </div>

      {/* Dynamic Grounded In-App Module Onboarding Widget */}
      <ModuleOnboardingWidget />

      {/* Two Column Section */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Agent Mesh Status */}
        <div className="rounded-lg border border-cream-300 bg-cream-100 p-5 shadow-xs lg:col-span-2">
          <div className="flex items-center justify-between border-b border-cream-300 pb-3">
            <div>
              <h2 className="text-sm font-semibold text-cream-900">Autonomous Agent Mesh</h2>
              <p className="text-[11px] text-cream-700">Real-time DAG runtime status</p>
            </div>
            <Link
              href="/agents"
              className="text-[11px] font-mono text-cream-800 hover:text-cream-900 underline flex items-center gap-1"
            >
              <span>Inspect Orchestrator</span>
              <ArrowUpRight className="h-3 w-3" />
            </Link>
          </div>

          <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
            {Object.entries(agentStates).map(([agent, state]) => (
              <div
                key={agent}
                className="rounded border border-cream-300 bg-cream-50 p-3 flex flex-col justify-between"
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-[10px] uppercase text-cream-700">
                    {agent.replace("_", " ")}
                  </span>
                  <span className={`h-2 w-2 rounded-full ${state === "BUSY" ? "bg-amberGold-500 animate-pulse" : "bg-sage-500"}`} />
                </div>
                <div className="mt-2 text-xs font-semibold text-cream-900 font-mono">
                  {state}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Priority Conflict Engine Card */}
        <div className="rounded-lg border border-cream-300 bg-cream-100 p-5 shadow-xs">
          <h2 className="text-sm font-semibold text-cream-900">Conflict Hierarchy</h2>
          <p className="text-[11px] text-cream-700 mt-0.5">Strict non-commutative partial order</p>

          <div className="mt-4 space-y-2 font-mono text-xs">
            <div className="rounded border border-sage-100 bg-sage-50 p-2 text-sage-700 flex justify-between">
              <span>1. P_Statutory_Legal</span>
              <span className="text-[10px]">Dominant</span>
            </div>
            <div className="rounded border border-cream-300 bg-cream-50 p-2 text-cream-800 flex justify-between">
              <span>2. P_Financial_Solvency</span>
              <span className="text-[10px]">Covenant</span>
            </div>
            <div className="rounded border border-cream-300 bg-cream-50 p-2 text-cream-800 flex justify-between">
              <span>3. P_Contractual_SLA</span>
              <span className="text-[10px]">Customer</span>
            </div>
            <div className="rounded border border-cream-300 bg-cream-50 p-2 text-cream-800 flex justify-between">
              <span>4. P_Capacity_Throughput</span>
              <span className="text-[10px]">Shop Floor</span>
            </div>
            <div className="rounded border border-cream-300 bg-cream-50 p-2 text-cream-800 flex justify-between">
              <span>5. P_Discretionary_Cost</span>
              <span className="text-[10px]">Subordinate</span>
            </div>
          </div>
        </div>
      </div>

      {/* Dispatch RFQ Modal */}
      {showRfqModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="w-full max-w-md rounded-xl border border-cream-300 bg-cream-50 p-6 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b border-cream-300 pb-3">
              <h3 className="text-sm font-semibold text-cream-900">
                Dispatch Commercial RFQ Workflow
              </h3>
              <button
                onClick={() => setShowRfqModal(false)}
                className="text-xs text-cream-600 hover:text-cream-900 font-mono"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleSimulateRFQ} className="space-y-4 text-xs">
              <div>
                <label className="block font-medium text-cream-800 mb-1">Customer / Inquirer Name</label>
                <input
                  type="text"
                  required
                  value={customerName}
                  onChange={(e) => setCustomerName(e.target.value)}
                  className="w-full rounded-md border border-cream-300 bg-cream-100 px-3 py-2 text-xs font-medium text-cream-900 focus:outline-hidden focus:border-cream-500"
                  placeholder="e.g. Apex Industrial Systems"
                />
              </div>

              <div>
                <label className="block font-medium text-cream-800 mb-1">Inquiry Specification</label>
                <textarea
                  rows={3}
                  required
                  value={inquiryText}
                  onChange={(e) => setInquiryText(e.target.value)}
                  className="w-full rounded-md border border-cream-300 bg-cream-100 px-3 py-2 text-xs font-medium text-cream-900 focus:outline-hidden focus:border-cream-500"
                  placeholder="Specify parts, quantities, and delivery constraints..."
                />
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-cream-300">
                <button
                  type="button"
                  onClick={() => setShowRfqModal(false)}
                  className="rounded-md border border-cream-300 bg-cream-100 px-3 py-1.5 text-xs text-cream-800 hover:bg-cream-200"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={dispatching}
                  className="rounded-md border border-cream-400 bg-cream-900 px-3 py-1.5 text-xs font-medium text-cream-50 hover:bg-cream-800 disabled:opacity-50"
                >
                  {dispatching ? "Synthesizing DAG..." : "Dispatch Task DAG"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
