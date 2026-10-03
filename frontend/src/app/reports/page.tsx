"use client";

import { useEffect, useState } from "react";
import {
  BarChart3,
  RefreshCw,
  Search,
  CheckCircle2,
  Calendar,
  AlertCircle,
  FileText,
  DollarSign,
  TrendingUp,
  Layers,
  Building2,
  Globe,
  Clock,
  ArrowRight,
  Filter,
} from "lucide-react";
import { api } from "@/lib/api";

type TabType = "trial-balance" | "balance-sheet" | "profit-loss" | "cash-flow" | "aging" | "stock-ops" | "consolidation";

export default function ReportsHubPage() {
  const [activeTab, setActiveTab] = useState<TabType>("trial-balance");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Filter States
  const [fromDate, setFromDate] = useState(() => {
    const d = new Date();
    return `${d.getFullYear()}-01-01`;
  });
  const [toDate, setToDate] = useState(() => new Date().toISOString().split("T")[0]);

  // Report Data States
  const [trialBalance, setTrialBalance] = useState<any>(null);
  const [balanceSheet, setBalanceSheet] = useState<any>(null);
  const [profitAndLoss, setProfitAndLoss] = useState<any>(null);
  const [cashFlow, setCashFlow] = useState<any>(null);
  const [arAging, setArAging] = useState<any>(null);
  const [apAging, setApAging] = useState<any>(null);
  const [stockBalance, setStockBalance] = useState<any>(null);
  const [productionAnalytics, setProductionAnalytics] = useState<any>(null);
  const [companies, setCompanies] = useState<any[]>([]);
  const [interCompanyTx, setInterCompanyTx] = useState<any[]>([]);
  const [consolidatedTb, setConsolidatedTb] = useState<any>(null);
  const [exchangeRates, setExchangeRates] = useState<any[]>([]);
  const [revaluations, setRevaluations] = useState<any[]>([]);

  // FX Reval Modal State
  const [showRevalModal, setShowRevalModal] = useState(false);
  const [revalNotes, setRevalNotes] = useState("");
  const [revalLoading, setRevalLoading] = useState(false);

  // New Company Modal State
  const [showCompanyModal, setShowCompanyModal] = useState(false);
  const [newCompany, setNewCompany] = useState({
    company_name: "",
    company_code: "",
    default_currency: "USD",
    is_group: false,
  });

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      if (activeTab === "trial-balance") {
        const data = await api.getTrialBalance({ from_date: fromDate, to_date: toDate });
        setTrialBalance(data);
      } else if (activeTab === "balance-sheet") {
        const data = await api.getBalanceSheet(toDate);
        setBalanceSheet(data);
      } else if (activeTab === "profit-loss") {
        const data = await api.getProfitAndLoss({ from_date: fromDate, to_date: toDate });
        setProfitAndLoss(data);
      } else if (activeTab === "cash-flow") {
        const data = await api.getCashFlow({ from_date: fromDate, to_date: toDate });
        setCashFlow(data);
      } else if (activeTab === "aging") {
        const [ar, ap] = await Promise.all([
          api.getArAging(toDate),
          api.getApAging(toDate),
        ]);
        setArAging(ar);
        setApAging(ap);
      } else if (activeTab === "stock-ops") {
        const [sb, pa] = await Promise.all([
          api.getStockBalanceReport(),
          api.getProductionAnalytics(),
        ]);
        setStockBalance(sb);
        setProductionAnalytics(pa);
      } else if (activeTab === "consolidation") {
        const [comps, txs, ctb, rates, revs] = await Promise.all([
          api.getCompanies(),
          api.getInterCompanyTransactions(),
          api.getConsolidatedTrialBalance({ from_date: fromDate, to_date: toDate }),
          api.getExchangeRates(),
          api.getExchangeRevaluations(),
        ]);
        setCompanies(comps);
        setInterCompanyTx(txs);
        setConsolidatedTb(ctb);
        setExchangeRates(rates);
        setRevaluations(revs);
      }
    } catch (err: any) {
      console.error(err);
      setError(err.message || "Failed to load reporting data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [activeTab, fromDate, toDate]);

  const handleRunRevaluation = async () => {
    setRevalLoading(true);
    try {
      await api.executeExchangeRevaluation({
        posting_date: toDate,
        base_currency: "USD",
        notes: revalNotes || "Periodic FX Revaluation",
      });
      setShowRevalModal(false);
      setRevalNotes("");
      await loadData();
    } catch (err: any) {
      alert("Revaluation error: " + err.message);
    } finally {
      setRevalLoading(false);
    }
  };

  const handleCreateCompany = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.createCompany(newCompany);
      setShowCompanyModal(false);
      setNewCompany({ company_name: "", company_code: "", default_currency: "USD", is_group: false });
      await loadData();
    } catch (err: any) {
      alert("Error creating company: " + err.message);
    }
  };

  return (
    <div className="min-h-screen bg-[#FDFBF7] text-[#2D2A26] p-6 lg:p-10">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between pb-6 border-b border-[#E5E0D8] gap-4">
        <div>
          <div className="flex items-center gap-3">
            <span className="p-2.5 rounded-xl bg-[#2D2A26] text-[#FDFBF7] shadow-sm">
              <BarChart3 className="w-5 h-5" />
            </span>
            <div>
              <h1 className="text-2xl font-semibold tracking-tight text-[#1A1816]">
                Enterprise Analytics & Reports Hub
              </h1>
              <p className="text-sm text-[#736B63] mt-0.5">
                Financial statements, aging analyses, stock valuation, multi-company group consolidation & FX engine
              </p>
            </div>
          </div>
        </div>

        {/* Global Date & Action Bar */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2 bg-white px-3 py-1.5 rounded-xl border border-[#E5E0D8] text-xs">
            <Calendar className="w-3.5 h-3.5 text-[#736B63]" />
            <span className="text-[#736B63]">From:</span>
            <input
              type="date"
              value={fromDate}
              onChange={(e) => setFromDate(e.target.value)}
              className="bg-transparent text-[#2D2A26] focus:outline-none"
            />
            <span className="text-[#736B63] ml-2">To:</span>
            <input
              type="date"
              value={toDate}
              onChange={(e) => setToDate(e.target.value)}
              className="bg-transparent text-[#2D2A26] focus:outline-none"
            />
          </div>

          <button
            onClick={loadData}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-2 bg-white hover:bg-[#F7F4EE] border border-[#E5E0D8] rounded-xl text-xs font-medium transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 text-[#736B63] ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="flex items-center gap-2 mt-6 overflow-x-auto pb-2 border-b border-[#E5E0D8]">
        {[
          { id: "trial-balance", label: "Trial Balance (4-Col)", icon: FileText },
          { id: "balance-sheet", label: "Balance Sheet", icon: Building2 },
          { id: "profit-loss", label: "Profit & Loss (P&L)", icon: TrendingUp },
          { id: "cash-flow", label: "Cash Flow Statement", icon: DollarSign },
          { id: "aging", label: "AR & AP Aging", icon: Clock },
          { id: "stock-ops", label: "Stock & MES Analytics", icon: Layers },
          { id: "consolidation", label: "Group Consolidation & FX", icon: Globe },
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as TabType)}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-medium transition-all whitespace-nowrap ${
                isActive
                  ? "bg-[#2D2A26] text-[#FDFBF7] shadow-sm"
                  : "bg-white text-[#736B63] hover:text-[#2D2A26] hover:bg-[#F7F4EE] border border-[#E5E0D8]"
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Error state */}
      {error && (
        <div className="mt-4 p-4 rounded-xl bg-red-50 border border-red-200 text-red-700 text-sm flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Tab Contents */}
      <div className="mt-6">
        {/* ========================================================================= */}
        {/* 1. TRIAL BALANCE TAB */}
        {/* ========================================================================= */}
        {activeTab === "trial-balance" && (
          <div className="space-y-4">
            {trialBalance && (
              <>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="p-4 bg-white rounded-2xl border border-[#E5E0D8]">
                    <span className="text-xs text-[#736B63]">Opening Debits</span>
                    <p className="text-xl font-bold text-[#1A1816] mt-1">
                      ${Number(trialBalance.totals?.opening_debit || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </p>
                  </div>
                  <div className="p-4 bg-white rounded-2xl border border-[#E5E0D8]">
                    <span className="text-xs text-[#736B63]">Period Movement</span>
                    <p className="text-xl font-bold text-[#1A1816] mt-1">
                      ${Number(trialBalance.totals?.period_debit || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </p>
                  </div>
                  <div className="p-4 bg-white rounded-2xl border border-[#E5E0D8]">
                    <span className="text-xs text-[#736B63]">Closing Balanced Total</span>
                    <p className="text-xl font-bold text-[#1A1816] mt-1">
                      ${Number(trialBalance.totals?.closing_debit || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </p>
                  </div>
                  <div className="p-4 bg-white rounded-2xl border border-[#E5E0D8]">
                    <span className="text-xs text-[#736B63]">Balance Verification</span>
                    <div className="flex items-center gap-2 mt-1">
                      {trialBalance.totals?.is_balanced ? (
                        <span className="px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800 flex items-center gap-1">
                          <CheckCircle2 className="w-3.5 h-3.5" />
                          Balanced (Diff: $0.00)
                        </span>
                      ) : (
                        <span className="px-2.5 py-1 rounded-full text-xs font-medium bg-rose-100 text-rose-800">
                          Variance: ${Number(trialBalance.totals?.difference || 0).toFixed(2)}
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                <div className="bg-white rounded-2xl border border-[#E5E0D8] overflow-hidden">
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-[#FAF7F0] border-b border-[#E5E0D8] text-[#736B63]">
                        <tr>
                          <th className="py-3 px-4 font-semibold">Account Code</th>
                          <th className="py-3 px-4 text-right font-semibold">Opening Dr</th>
                          <th className="py-3 px-4 text-right font-semibold">Opening Cr</th>
                          <th className="py-3 px-4 text-right font-semibold">Period Dr</th>
                          <th className="py-3 px-4 text-right font-semibold">Period Cr</th>
                          <th className="py-3 px-4 text-right font-semibold">Closing Dr</th>
                          <th className="py-3 px-4 text-right font-semibold">Closing Cr</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#E5E0D8]">
                        {trialBalance.rows?.map((row: any) => (
                          <tr key={row.account_code} className="hover:bg-[#FAF7F0] transition-colors">
                            <td className="py-3 px-4 font-mono font-medium text-[#1A1816]">{row.account_code}</td>
                            <td className="py-3 px-4 text-right">{Number(row.opening_debit).toFixed(2)}</td>
                            <td className="py-3 px-4 text-right">{Number(row.opening_credit).toFixed(2)}</td>
                            <td className="py-3 px-4 text-right font-medium text-emerald-700">+{Number(row.period_debit).toFixed(2)}</td>
                            <td className="py-3 px-4 text-right font-medium text-amber-700">+{Number(row.period_credit).toFixed(2)}</td>
                            <td className="py-3 px-4 text-right font-semibold text-[#1A1816]">{Number(row.closing_debit).toFixed(2)}</td>
                            <td className="py-3 px-4 text-right font-semibold text-[#1A1816]">{Number(row.closing_credit).toFixed(2)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </>
            )}
          </div>
        )}

        {/* ========================================================================= */}
        {/* 2. BALANCE SHEET TAB */}
        {/* ========================================================================= */}
        {activeTab === "balance-sheet" && (
          <div className="space-y-6">
            {balanceSheet && (
              <>
                <div className="p-4 bg-white rounded-2xl border border-[#E5E0D8] flex items-center justify-between">
                  <div>
                    <span className="text-xs text-[#736B63]">Accounting Equation Check</span>
                    <h3 className="text-lg font-bold text-[#1A1816] mt-0.5">
                      Assets (${Number(balanceSheet.total_assets).toFixed(2)}) = Liabilities & Equity (${Number(balanceSheet.total_liabilities_and_equity).toFixed(2)})
                    </h3>
                  </div>
                  {balanceSheet.is_balanced ? (
                    <span className="px-3 py-1.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 flex items-center gap-1.5">
                      <CheckCircle2 className="w-4 h-4" /> Perfect Invariant Parity
                    </span>
                  ) : (
                    <span className="px-3 py-1.5 rounded-full text-xs font-semibold bg-rose-100 text-rose-800">
                      Unbalanced
                    </span>
                  )}
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {/* Assets Column */}
                  <div className="bg-white rounded-2xl border border-[#E5E0D8] p-5">
                    <div className="flex justify-between items-center pb-3 border-b border-[#E5E0D8]">
                      <h4 className="font-semibold text-sm text-[#1A1816]">Assets</h4>
                      <span className="font-bold text-sm text-emerald-800">
                        ${Number(balanceSheet.total_assets).toFixed(2)}
                      </span>
                    </div>
                    <div className="divide-y divide-[#E5E0D8] mt-3">
                      {balanceSheet.assets?.map((a: any) => (
                        <div key={a.account_code} className="py-2.5 flex justify-between text-xs">
                          <span className="font-mono text-[#736B63]">{a.account_code}</span>
                          <span className="font-medium text-[#1A1816]">${Number(a.balance).toFixed(2)}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Liabilities & Equity Column */}
                  <div className="bg-white rounded-2xl border border-[#E5E0D8] p-5 space-y-6">
                    <div>
                      <div className="flex justify-between items-center pb-3 border-b border-[#E5E0D8]">
                        <h4 className="font-semibold text-sm text-[#1A1816]">Liabilities</h4>
                        <span className="font-bold text-sm text-amber-800">
                          ${Number(balanceSheet.total_liabilities).toFixed(2)}
                        </span>
                      </div>
                      <div className="divide-y divide-[#E5E0D8] mt-3">
                        {balanceSheet.liabilities?.map((l: any) => (
                          <div key={l.account_code} className="py-2.5 flex justify-between text-xs">
                            <span className="font-mono text-[#736B63]">{l.account_code}</span>
                            <span className="font-medium text-[#1A1816]">${Number(l.balance).toFixed(2)}</span>
                          </div>
                        ))}
                      </div>
                    </div>

                    <div>
                      <div className="flex justify-between items-center pb-3 border-b border-[#E5E0D8]">
                        <h4 className="font-semibold text-sm text-[#1A1816]">Equity & Retained Earnings</h4>
                        <span className="font-bold text-sm text-[#1A1816]">
                          ${Number(balanceSheet.total_equity + balanceSheet.retained_earnings).toFixed(2)}
                        </span>
                      </div>
                      <div className="divide-y divide-[#E5E0D8] mt-3">
                        {balanceSheet.equity?.map((e: any) => (
                          <div key={e.account_code} className="py-2.5 flex justify-between text-xs">
                            <span className="font-mono text-[#736B63]">{e.account_code}</span>
                            <span className="font-medium text-[#1A1816]">${Number(e.balance).toFixed(2)}</span>
                          </div>
                        ))}
                        <div className="py-2.5 flex justify-between text-xs font-semibold text-emerald-800 bg-emerald-50/50 px-2 rounded">
                          <span>Retained Earnings (Period Net Profit)</span>
                          <span>${Number(balanceSheet.retained_earnings).toFixed(2)}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </>
            )}
          </div>
        )}

        {/* ========================================================================= */}
        {/* 3. PROFIT AND LOSS TAB */}
        {/* ========================================================================= */}
        {activeTab === "profit-loss" && (
          <div className="space-y-4 max-w-4xl mx-auto">
            {profitAndLoss && (
              <div className="bg-white rounded-2xl border border-[#E5E0D8] p-6 space-y-6">
                <div className="flex items-center justify-between pb-4 border-b border-[#E5E0D8]">
                  <h3 className="font-semibold text-base text-[#1A1816]">Income Statement (P&L)</h3>
                  <span className="text-xs text-[#736B63]">{profitAndLoss.from_date} to {profitAndLoss.to_date}</span>
                </div>

                {/* Operating Revenue */}
                <div>
                  <div className="flex justify-between text-xs font-semibold text-[#736B63] uppercase tracking-wider pb-2 border-b border-[#E5E0D8]">
                    <span>Operating Revenue (4000s)</span>
                    <span className="text-[#1A1816]">${Number(profitAndLoss.total_revenue).toFixed(2)}</span>
                  </div>
                  <div className="divide-y divide-[#E5E0D8] mt-2">
                    {profitAndLoss.revenue?.map((r: any) => (
                      <div key={r.account_code} className="py-2 flex justify-between text-xs">
                        <span className="font-mono text-[#736B63]">{r.account_code}</span>
                        <span className="font-medium text-[#1A1816]">${Number(r.amount).toFixed(2)}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Cost of Goods Sold */}
                <div>
                  <div className="flex justify-between text-xs font-semibold text-[#736B63] uppercase tracking-wider pb-2 border-b border-[#E5E0D8]">
                    <span>Cost of Goods Sold (COGS 5000s)</span>
                    <span className="text-rose-700">-${Number(profitAndLoss.total_cogs).toFixed(2)}</span>
                  </div>
                  <div className="divide-y divide-[#E5E0D8] mt-2">
                    {profitAndLoss.cogs?.map((c: any) => (
                      <div key={c.account_code} className="py-2 flex justify-between text-xs">
                        <span className="font-mono text-[#736B63]">{c.account_code}</span>
                        <span className="font-medium text-rose-700">${Number(c.amount).toFixed(2)}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Gross Profit Summary */}
                <div className="p-3 bg-[#FAF7F0] rounded-xl flex justify-between items-center font-bold text-sm text-[#1A1816]">
                  <span>Gross Profit</span>
                  <span>${Number(profitAndLoss.gross_profit).toFixed(2)}</span>
                </div>

                {/* Operating Expenses */}
                <div>
                  <div className="flex justify-between text-xs font-semibold text-[#736B63] uppercase tracking-wider pb-2 border-b border-[#E5E0D8]">
                    <span>Operating Expenses (6000s)</span>
                    <span className="text-amber-800">-${Number(profitAndLoss.total_operating_expenses).toFixed(2)}</span>
                  </div>
                  <div className="divide-y divide-[#E5E0D8] mt-2">
                    {profitAndLoss.operating_expenses?.map((e: any) => (
                      <div key={e.account_code} className="py-2 flex justify-between text-xs">
                        <span className="font-mono text-[#736B63]">{e.account_code}</span>
                        <span className="font-medium text-amber-800">${Number(e.amount).toFixed(2)}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Net Profit Summary */}
                <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl flex justify-between items-center font-bold text-base text-emerald-900">
                  <span>Net Income / Profit</span>
                  <span>${Number(profitAndLoss.net_profit).toFixed(2)}</span>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ========================================================================= */}
        {/* 4. CASH FLOW STATEMENT */}
        {/* ========================================================================= */}
        {activeTab === "cash-flow" && (
          <div className="space-y-4 max-w-4xl mx-auto">
            {cashFlow && (
              <div className="bg-white rounded-2xl border border-[#E5E0D8] p-6 space-y-6">
                <div className="flex items-center justify-between pb-4 border-b border-[#E5E0D8]">
                  <h3 className="font-semibold text-base text-[#1A1816]">Statement of Cash Flows</h3>
                  <span className="text-xs text-[#736B63]">{cashFlow.from_date} to {cashFlow.to_date}</span>
                </div>

                <div className="space-y-4">
                  <div className="p-4 bg-[#FAF7F0] rounded-xl flex justify-between items-center">
                    <div>
                      <h4 className="font-semibold text-sm text-[#1A1816]">Operating Activities</h4>
                      <p className="text-xs text-[#736B63] mt-0.5">Net income from operations</p>
                    </div>
                    <span className="font-bold text-sm text-emerald-800">
                      ${Number(cashFlow.operating_activities?.cash_flow || 0).toFixed(2)}
                    </span>
                  </div>

                  <div className="p-4 bg-[#FAF7F0] rounded-xl flex justify-between items-center">
                    <div>
                      <h4 className="font-semibold text-sm text-[#1A1816]">Investing Activities</h4>
                      <p className="text-xs text-[#736B63] mt-0.5">Capital expenditure & asset additions</p>
                    </div>
                    <span className="font-bold text-sm text-amber-800">
                      ${Number(cashFlow.investing_activities?.cash_flow || 0).toFixed(2)}
                    </span>
                  </div>

                  <div className="p-4 bg-[#FAF7F0] rounded-xl flex justify-between items-center">
                    <div>
                      <h4 className="font-semibold text-sm text-[#1A1816]">Financing Activities</h4>
                      <p className="text-xs text-[#736B63] mt-0.5">Equity, loans & borrowing movements</p>
                    </div>
                    <span className="font-bold text-sm text-[#1A1816]">
                      ${Number(cashFlow.financing_activities?.cash_flow || 0).toFixed(2)}
                    </span>
                  </div>
                </div>

                <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl flex justify-between items-center font-bold text-base text-emerald-900">
                  <span>Net Change in Cash</span>
                  <span>${Number(cashFlow.net_change_in_cash).toFixed(2)}</span>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ========================================================================= */}
        {/* 5. AGING TAB (AR & AP) */}
        {/* ========================================================================= */}
        {activeTab === "aging" && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* AR Aging */}
            <div className="bg-white rounded-2xl border border-[#E5E0D8] p-5 space-y-4">
              <div className="flex justify-between items-center pb-3 border-b border-[#E5E0D8]">
                <h4 className="font-semibold text-sm text-[#1A1816]">Accounts Receivable (AR) Aging</h4>
                <span className="text-xs font-bold text-emerald-800">
                  Total: ${Number(arAging?.total_receivables || 0).toFixed(2)}
                </span>
              </div>
              <div className="grid grid-cols-5 gap-2 text-center">
                {[
                  { label: "0-30d", val: arAging?.buckets?.range_0_30 },
                  { label: "31-60d", val: arAging?.buckets?.range_31_60 },
                  { label: "61-90d", val: arAging?.buckets?.range_61_90 },
                  { label: "91-120d", val: arAging?.buckets?.range_91_120 },
                  { label: "120d+", val: arAging?.buckets?.range_above_120 },
                ].map((b) => (
                  <div key={b.label} className="p-2.5 bg-[#FAF7F0] rounded-xl border border-[#E5E0D8]">
                    <span className="text-[10px] text-[#736B63] block font-medium">{b.label}</span>
                    <span className="text-xs font-bold text-[#1A1816] mt-0.5 block">
                      ${Number(b.val || 0).toFixed(0)}
                    </span>
                  </div>
                ))}
              </div>
              <div className="max-h-60 overflow-y-auto divide-y divide-[#E5E0D8]">
                {arAging?.details?.map((d: any, idx: number) => (
                  <div key={idx} className="py-2 flex justify-between text-xs">
                    <div>
                      <span className="font-mono text-[#1A1816]">{d.account_code}</span>
                      <span className="text-[#736B63] text-[10px] ml-2">({d.days_overdue} days)</span>
                    </div>
                    <span className="font-medium text-emerald-800">${Number(d.amount).toFixed(2)}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* AP Aging */}
            <div className="bg-white rounded-2xl border border-[#E5E0D8] p-5 space-y-4">
              <div className="flex justify-between items-center pb-3 border-b border-[#E5E0D8]">
                <h4 className="font-semibold text-sm text-[#1A1816]">Accounts Payable (AP) Aging</h4>
                <span className="text-xs font-bold text-amber-800">
                  Total: ${Number(apAging?.total_payables || 0).toFixed(2)}
                </span>
              </div>
              <div className="grid grid-cols-5 gap-2 text-center">
                {[
                  { label: "0-30d", val: apAging?.buckets?.range_0_30 },
                  { label: "31-60d", val: apAging?.buckets?.range_31_60 },
                  { label: "61-90d", val: apAging?.buckets?.range_61_90 },
                  { label: "91-120d", val: apAging?.buckets?.range_91_120 },
                  { label: "120d+", val: apAging?.buckets?.range_above_120 },
                ].map((b) => (
                  <div key={b.label} className="p-2.5 bg-[#FAF7F0] rounded-xl border border-[#E5E0D8]">
                    <span className="text-[10px] text-[#736B63] block font-medium">{b.label}</span>
                    <span className="text-xs font-bold text-amber-900 mt-0.5 block">
                      ${Number(b.val || 0).toFixed(0)}
                    </span>
                  </div>
                ))}
              </div>
              <div className="max-h-60 overflow-y-auto divide-y divide-[#E5E0D8]">
                {apAging?.details?.map((d: any, idx: number) => (
                  <div key={idx} className="py-2 flex justify-between text-xs">
                    <div>
                      <span className="font-mono text-[#1A1816]">{d.account_code}</span>
                      <span className="text-[#736B63] text-[10px] ml-2">({d.days_overdue} days)</span>
                    </div>
                    <span className="font-medium text-amber-900">${Number(d.amount).toFixed(2)}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ========================================================================= */}
        {/* 6. STOCK & MES ANALYTICS */}
        {/* ========================================================================= */}
        {activeTab === "stock-ops" && (
          <div className="space-y-6">
            {/* KPI Cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="p-4 bg-white rounded-2xl border border-[#E5E0D8]">
                <span className="text-xs text-[#736B63]">Inventory Valuation</span>
                <p className="text-xl font-bold text-[#1A1816] mt-1">
                  ${Number(stockBalance?.total_valuation_value || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                </p>
              </div>
              <div className="p-4 bg-white rounded-2xl border border-[#E5E0D8]">
                <span className="text-xs text-[#736B63]">Total Production Units</span>
                <p className="text-xl font-bold text-[#1A1816] mt-1">
                  {Number(productionAnalytics?.total_produced_qty || 0).toLocaleString()}
                </p>
              </div>
              <div className="p-4 bg-white rounded-2xl border border-[#E5E0D8]">
                <span className="text-xs text-[#736B63]">MES Work Order Completion</span>
                <p className="text-xl font-bold text-emerald-800 mt-1">
                  {productionAnalytics?.completion_rate_pct || 0}%
                </p>
              </div>
              <div className="p-4 bg-white rounded-2xl border border-[#E5E0D8]">
                <span className="text-xs text-[#736B63]">Yield vs Scrap %</span>
                <p className="text-xl font-bold text-[#1A1816] mt-1">
                  {productionAnalytics?.yield_rate_pct || 100}% Yield
                </p>
              </div>
            </div>

            {/* Stock Balance Table */}
            <div className="bg-white rounded-2xl border border-[#E5E0D8] overflow-hidden">
              <div className="p-4 border-b border-[#E5E0D8] flex justify-between items-center">
                <h4 className="font-semibold text-sm text-[#1A1816]">Stock Balance & Valuation Per Warehouse</h4>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-[#FAF7F0] border-b border-[#E5E0D8] text-[#736B63]">
                    <tr>
                      <th className="py-3 px-4 font-semibold">Item Code</th>
                      <th className="py-3 px-4 font-semibold">Item Name</th>
                      <th className="py-3 px-4 font-semibold">Warehouse</th>
                      <th className="py-3 px-4 text-right font-semibold">Qty</th>
                      <th className="py-3 px-4 text-right font-semibold">Valuation Rate</th>
                      <th className="py-3 px-4 text-right font-semibold">Total Value</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#E5E0D8]">
                    {stockBalance?.rows?.map((row: any, idx: number) => (
                      <tr key={idx} className="hover:bg-[#FAF7F0] transition-colors">
                        <td className="py-3 px-4 font-mono font-medium text-[#1A1816]">{row.item_code}</td>
                        <td className="py-3 px-4 text-[#736B63]">{row.item_name}</td>
                        <td className="py-3 px-4">{row.warehouse_name}</td>
                        <td className="py-3 px-4 text-right font-semibold text-[#1A1816]">{Number(row.current_qty).toFixed(2)}</td>
                        <td className="py-3 px-4 text-right">${Number(row.valuation_rate).toFixed(2)}</td>
                        <td className="py-3 px-4 text-right font-semibold text-emerald-800">${Number(row.stock_value).toFixed(2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* ========================================================================= */}
        {/* 7. GROUP CONSOLIDATION & FX REVALUATION */}
        {/* ========================================================================= */}
        {activeTab === "consolidation" && (
          <div className="space-y-6">
            {/* Top Toolbar */}
            <div className="flex justify-between items-center">
              <div>
                <h3 className="text-base font-semibold text-[#1A1816]">Holding Group Hierarchy & Inter-Company Eliminations</h3>
                <p className="text-xs text-[#736B63]">Consolidated financial statements with automatic elimination of partner transactions</p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setShowCompanyModal(true)}
                  className="px-3 py-2 bg-white hover:bg-[#F7F4EE] border border-[#E5E0D8] rounded-xl text-xs font-medium text-[#2D2A26] transition-colors"
                >
                  + Add Company Entity
                </button>
                <button
                  onClick={() => setShowRevalModal(true)}
                  className="px-3.5 py-2 bg-[#2D2A26] text-[#FDFBF7] hover:bg-[#1A1816] rounded-xl text-xs font-medium transition-colors shadow-sm"
                >
                  Run FX Revaluation
                </button>
              </div>
            </div>

            {/* Consolidated Summary */}
            {consolidatedTb && (
              <div className="p-4 bg-white rounded-2xl border border-[#E5E0D8] flex flex-wrap items-center justify-between gap-4">
                <div>
                  <span className="text-xs text-[#736B63]">Inter-Company Eliminations</span>
                  <p className="text-xl font-bold text-amber-800 mt-0.5">
                    ${Number(consolidatedTb.consolidated_totals?.intercompany_elimination || 0).toFixed(2)}
                  </p>
                </div>
                <div>
                  <span className="text-xs text-[#736B63]">Consolidated Debits</span>
                  <p className="text-xl font-bold text-[#1A1816] mt-0.5">
                    ${Number(consolidatedTb.consolidated_totals?.consolidated_closing_debit || 0).toFixed(2)}
                  </p>
                </div>
                <div>
                  <span className="text-xs text-[#736B63]">Consolidated Credits</span>
                  <p className="text-xl font-bold text-[#1A1816] mt-0.5">
                    ${Number(consolidatedTb.consolidated_totals?.consolidated_closing_credit || 0).toFixed(2)}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <span className="px-3 py-1.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 flex items-center gap-1.5">
                    <CheckCircle2 className="w-4 h-4" /> Eliminations Reconciled
                  </span>
                </div>
              </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Companies List */}
              <div className="bg-white rounded-2xl border border-[#E5E0D8] p-5">
                <h4 className="font-semibold text-sm text-[#1A1816] pb-3 border-b border-[#E5E0D8]">
                  Entity Directory ({companies.length})
                </h4>
                <div className="divide-y divide-[#E5E0D8] mt-3">
                  {companies.map((c) => (
                    <div key={c.company_id} className="py-3 flex justify-between items-center text-xs">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-[#1A1816]">{c.company_name}</span>
                          <span className="px-2 py-0.5 bg-[#FAF7F0] border border-[#E5E0D8] rounded text-[10px] font-mono">
                            {c.company_code}
                          </span>
                          {c.is_group && (
                            <span className="px-2 py-0.5 bg-blue-100 text-blue-800 rounded text-[10px] font-medium">
                              Holding Group
                            </span>
                          )}
                        </div>
                        <span className="text-[#736B63] text-[10px]">Currency: {c.default_currency}</span>
                      </div>
                      <span className="text-emerald-700 text-xs font-medium">Active</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Exchange Rates & Revaluation Log */}
              <div className="bg-white rounded-2xl border border-[#E5E0D8] p-5 space-y-4">
                <h4 className="font-semibold text-sm text-[#1A1816] pb-3 border-b border-[#E5E0D8]">
                  FX Currency Spot Rates & Revaluation History
                </h4>
                <div className="space-y-2">
                  <span className="text-xs font-medium text-[#736B63]">Active Exchange Rates</span>
                  <div className="grid grid-cols-2 gap-2">
                    {exchangeRates.map((r) => (
                      <div key={r.rate_id} className="p-2.5 bg-[#FAF7F0] rounded-xl border border-[#E5E0D8] text-xs">
                        <span className="font-bold text-[#1A1816]">{r.from_currency} / {r.to_currency}</span>
                        <span className="block text-emerald-800 font-mono mt-0.5">{Number(r.exchange_rate).toFixed(4)}</span>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="pt-2">
                  <span className="text-xs font-medium text-[#736B63]">Revaluation History</span>
                  <div className="divide-y divide-[#E5E0D8] mt-2 max-h-48 overflow-y-auto">
                    {revaluations.map((rv) => (
                      <div key={rv.revaluation_id} className="py-2.5 flex justify-between items-center text-xs">
                        <div>
                          <span className="font-mono font-medium text-[#1A1816]">{rv.revaluation_number}</span>
                          <span className="block text-[10px] text-[#736B63]">{rv.posting_date} - {rv.notes}</span>
                        </div>
                        <span className="font-bold text-emerald-800">+${Number(rv.total_gain_loss).toFixed(2)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* FX Reval Modal */}
      {showRevalModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <div className="bg-white rounded-2xl border border-[#E5E0D8] max-w-md w-full p-6 shadow-xl space-y-4">
            <h3 className="font-semibold text-base text-[#1A1816]">Execute Automated FX Balance Sheet Revaluation</h3>
            <p className="text-xs text-[#736B63]">
              Calculates spot variances on foreign currency asset & liability accounts, and automatically posts balanced GL entries to 4900-UNREALIZED-FX-GAIN-LOSS.
            </p>
            <div>
              <label className="block text-xs font-medium text-[#736B63] mb-1">Revaluation Date</label>
              <input
                type="date"
                value={toDate}
                onChange={(e) => setToDate(e.target.value)}
                className="w-full px-3 py-2 bg-[#FAF7F0] border border-[#E5E0D8] rounded-xl text-xs text-[#2D2A26]"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-[#736B63] mb-1">Journal Notes</label>
              <input
                type="text"
                placeholder="e.g. Q4 FX Revaluation"
                value={revalNotes}
                onChange={(e) => setRevalNotes(e.target.value)}
                className="w-full px-3 py-2 bg-[#FAF7F0] border border-[#E5E0D8] rounded-xl text-xs text-[#2D2A26]"
              />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setShowRevalModal(false)}
                className="px-3.5 py-2 bg-white hover:bg-[#F7F4EE] border border-[#E5E0D8] rounded-xl text-xs font-medium text-[#736B63]"
              >
                Cancel
              </button>
              <button
                onClick={handleRunRevaluation}
                disabled={revalLoading}
                className="px-4 py-2 bg-[#2D2A26] hover:bg-[#1A1816] text-[#FDFBF7] rounded-xl text-xs font-semibold"
              >
                {revalLoading ? "Computing & Posting..." : "Post Revaluation"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Add Company Modal */}
      {showCompanyModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <form onSubmit={handleCreateCompany} className="bg-white rounded-2xl border border-[#E5E0D8] max-w-md w-full p-6 shadow-xl space-y-4">
            <h3 className="font-semibold text-base text-[#1A1816]">Create Company Entity</h3>
            <div>
              <label className="block text-xs font-medium text-[#736B63] mb-1">Company Name</label>
              <input
                type="text"
                required
                placeholder="Apex Global UK Ltd"
                value={newCompany.company_name}
                onChange={(e) => setNewCompany({ ...newCompany, company_name: e.target.value })}
                className="w-full px-3 py-2 bg-[#FAF7F0] border border-[#E5E0D8] rounded-xl text-xs text-[#2D2A26]"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-[#736B63] mb-1">Company Code</label>
                <input
                  type="text"
                  required
                  placeholder="APEX-UK"
                  value={newCompany.company_code}
                  onChange={(e) => setNewCompany({ ...newCompany, company_code: e.target.value })}
                  className="w-full px-3 py-2 bg-[#FAF7F0] border border-[#E5E0D8] rounded-xl text-xs text-[#2D2A26]"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-[#736B63] mb-1">Currency</label>
                <input
                  type="text"
                  required
                  placeholder="USD"
                  value={newCompany.default_currency}
                  onChange={(e) => setNewCompany({ ...newCompany, default_currency: e.target.value })}
                  className="w-full px-3 py-2 bg-[#FAF7F0] border border-[#E5E0D8] rounded-xl text-xs text-[#2D2A26]"
                />
              </div>
            </div>
            <div className="flex items-center gap-2 pt-1">
              <input
                type="checkbox"
                id="isGroup"
                checked={newCompany.is_group}
                onChange={(e) => setNewCompany({ ...newCompany, is_group: e.target.checked })}
                className="rounded border-[#E5E0D8]"
              />
              <label htmlFor="isGroup" className="text-xs text-[#1A1816]">Holding Group (Consolidation Parent)</label>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setShowCompanyModal(false)}
                className="px-3.5 py-2 bg-white hover:bg-[#F7F4EE] border border-[#E5E0D8] rounded-xl text-xs font-medium text-[#736B63]"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-4 py-2 bg-[#2D2A26] hover:bg-[#1A1816] text-[#FDFBF7] rounded-xl text-xs font-semibold"
              >
                Create Entity
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
