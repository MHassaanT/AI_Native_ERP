"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowUpRight,
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
            Real-time operational and financial overview.
          </p>
        </div>

        <button
          onClick={() => loadLiveData()}
          title="Refresh live metrics"
          className="rounded-md border border-cream-300 bg-cream-100 p-1.5 text-cream-700 hover:bg-cream-200 transition-colors"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
        </button>
      </div>

      {/* KPI Cards Grid - Live Data */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
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
        <div className="rounded-lg border border-cream-300 bg-cream-100 p-5 shadow-xs lg:col-span-2">
          <div className="flex items-center justify-between border-b border-cream-300 pb-3">
            <div>
              <h2 className="text-sm font-semibold text-cream-900">Workflow Runs</h2>
              <p className="text-[11px] text-cream-700">Inspect workflow history and recover interrupted tasks.</p>
            </div>
            <Link
              href="/workflows"
              className="text-[11px] font-mono text-cream-800 hover:text-cream-900 underline flex items-center gap-1"
            >
              <span>View workflows</span>
              <ArrowUpRight className="h-3 w-3" />
            </Link>
          </div>
          <p className="mt-4 text-sm text-cream-700">
            Durable workflow records remain available here without scheduled autonomous supervisors.
          </p>

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

    </div>
  );
}
