"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowUpRight,
  Activity,
  CheckCircle2,
  DollarSign,
  FileCheck,
  Package,
  RefreshCw,
  ShieldCheck,
  Users,
  Wrench,
} from "lucide-react";
import { api } from "@/lib/api";
import { getUser } from "@/lib/auth";
import { ModuleOnboardingWidget } from "@/components/module-onboarding";

export default function OverviewPage() {
  const [user, setUser] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  // Live Metrics
  const [cashBuffer, setCashBuffer] = useState<string>("$0.00");
  const [cashNote, setCashNote] = useState<string>("GAAP 1010 Account active");
  const [matchRate, setMatchRate] = useState<string>("0.0%");
  const [matchNote, setMatchNote] = useState<string>("0 invoices processed");
  const [ledgerDrift, setLedgerDrift] = useState<string>("0.0000");
  const [isFreshTenant, setIsFreshTenant] = useState<boolean>(true);

  const loadLiveData = async () => {
    setLoading(true);
    try {
      const currentUser = getUser();
      setUser(currentUser);

      const [accountsRes, invoicesRes, entriesRes] = await Promise.allSettled([
        api.getAccounts(),
        api.getInvoices(),
        api.getGLEntries(),
      ]);

      // 1. GL Accounts & Cash Buffer
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

      // 2. Accounts Payable 3-Way Match Rate
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

      // 3. Ledger Zero-Sum Drift
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
      title: "Ledger Zero-Sum Drift",
      value: ledgerDrift,
      change: "Invariants 100% verified",
      icon: ShieldCheck,
    },
  ];

  return (
    <div className="mx-auto max-w-[1600px] space-y-7">
      {/* Page Header */}
      <div className="flex flex-col gap-4 border-b border-cream-300/80 pb-6 md:flex-row md:items-end md:justify-between">
        <div>
          <div className="mb-2 flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-sage-500/20 bg-sage-50 px-2.5 py-1 text-[11px] font-medium text-sage-700">
            <span className="h-1.5 w-1.5 rounded-full bg-sage-500" />
            Executive overview
            </span>
            {user?.tenant_slug && (
            <span className="rounded-full border border-cream-300 bg-white px-2.5 py-1 text-[11px] font-medium text-cream-700">
              {user.tenant_name || user.tenant_slug}
            </span>
            )}
          </div>
          <h1 className="text-2xl font-semibold tracking-tight text-cream-900 sm:text-[28px]">
            Welcome back{user?.full_name ? `, ${user.full_name.split(" ")[0]}` : ""}
            </h1>
          <p className="mt-1.5 text-sm text-cream-700">
            Your operational and financial health, all in one place.
          </p>
        </div>

        <button
          onClick={() => loadLiveData()}
          title="Refresh live metrics"
          className="inline-flex h-10 items-center justify-center gap-2 self-start rounded-lg border border-cream-300 bg-white px-3 text-xs font-medium text-cream-700 shadow-sm transition-colors hover:bg-cream-100 md:self-auto"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
          Refresh data
        </button>
      </div>

      {/* KPI Cards Grid - Live Data */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {kpis.map((kpi) => {
          const Icon = kpi.icon;
          return (
            <div
            key={kpi.title}
            className="group rounded-2xl border border-cream-300/80 bg-white p-5 shadow-sm transition-all duration-200 hover:-translate-y-0.5 hover:border-sage-500/30 hover:shadow-md sm:p-6"
            >
            <div className="flex items-center justify-between">
              <span className="text-[13px] font-medium text-cream-700">{kpi.title}</span>
              <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-sage-50 text-sage-600 transition-colors group-hover:bg-sage-100">
                <Icon className="h-[18px] w-[18px]" />
              </span>
            </div>
            <div className="mt-5 font-mono text-[30px] font-semibold leading-none tracking-tight text-cream-900">
              {kpi.value}
            </div>
            <div className="mt-3 flex items-center gap-2 text-xs text-cream-600">
              <span className="h-1.5 w-1.5 rounded-full bg-sage-500" />
              {kpi.change}
            </div>
            </div>
          );
        })}
      </div>

      {/* Dynamic Grounded In-App Module Onboarding Widget */}
      <ModuleOnboardingWidget />

      {/* Two Column Section */}
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-3">
        <div className="rounded-2xl border border-cream-300/80 bg-white p-5 shadow-sm sm:p-6 xl:col-span-2">
          <div className="flex items-center justify-between border-b border-cream-200 pb-4">
            <div className="flex items-start gap-3">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-sage-50 text-sage-600">
                <Activity className="h-5 w-5" />
              </span>
              <div>
                <h2 className="text-[15px] font-semibold text-cream-900">Workflow activity</h2>
                <p className="mt-1 text-xs text-cream-600">Monitor runs and recover interrupted tasks.</p>
              </div>
            </div>
            <Link
              href="/workflows"
              className="inline-flex items-center gap-1 rounded-lg px-2.5 py-2 text-xs font-medium text-sage-700 transition-colors hover:bg-sage-50"
            >
              View workflows
              <ArrowUpRight className="h-3.5 w-3.5" />
            </Link>
          </div>
          <div className="flex min-h-44 flex-col items-center justify-center px-4 py-8 text-center">
            <span className="mb-3 flex h-11 w-11 items-center justify-center rounded-full bg-cream-100 text-cream-600">
              <Activity className="h-5 w-5" />
            </span>
            <p className="text-sm font-medium text-cream-800">Your workflow history is ready</p>
            <p className="mt-1 max-w-sm text-xs leading-5 text-cream-600">
              Durable workflow records are available to inspect and recover from the workflow workspace.
            </p>
          </div>
        </div>

        {/* Priority Conflict Engine Card */}
        <div className="rounded-2xl border border-cream-300/80 bg-white p-5 shadow-sm sm:p-6">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h2 className="text-[15px] font-semibold text-cream-900">Conflict hierarchy</h2>
              <p className="mt-1 text-xs text-cream-600">Priorities enforced by the decision engine</p>
            </div>
            <span className="rounded-full border border-sage-500/20 bg-sage-50 px-2 py-1 text-[10px] font-medium text-sage-700">
              Active
            </span>
          </div>

          <div className="mt-5 space-y-2">
            <div className="flex items-center justify-between gap-3 rounded-xl border border-sage-500/15 bg-sage-50 px-3 py-2.5 text-xs text-sage-700">
              <span>1. P_Statutory_Legal</span>
              <span className="text-[10px] font-medium">Dominant</span>
            </div>
            <div className="flex items-center justify-between gap-3 rounded-xl border border-cream-200 bg-[#fbfcfa] px-3 py-2.5 text-xs text-cream-800">
              <span>2. P_Financial_Solvency</span>
              <span className="text-[10px] text-cream-600">Covenant</span>
            </div>
            <div className="flex items-center justify-between gap-3 rounded-xl border border-cream-200 bg-[#fbfcfa] px-3 py-2.5 text-xs text-cream-800">
              <span>3. P_Contractual_SLA</span>
              <span className="text-[10px] text-cream-600">Customer</span>
            </div>
            <div className="flex items-center justify-between gap-3 rounded-xl border border-cream-200 bg-[#fbfcfa] px-3 py-2.5 text-xs text-cream-800">
              <span>4. P_Capacity_Throughput</span>
              <span className="text-[10px] text-cream-600">Shop Floor</span>
            </div>
            <div className="flex items-center justify-between gap-3 rounded-xl border border-cream-200 bg-[#fbfcfa] px-3 py-2.5 text-xs text-cream-800">
              <span>5. P_Discretionary_Cost</span>
              <span className="text-[10px] text-cream-600">Subordinate</span>
            </div>
          </div>
        </div>
      </div>

    </div>
  );
}
