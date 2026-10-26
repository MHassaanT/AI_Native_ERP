"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { BarChart3, CalendarDays, RefreshCw } from "lucide-react";
import { fetchWithTenant } from "@/lib/api";

const reports = [
  ["Accounting", "customer-ledger-summary", "Customer Ledger Summary"],
  ["Accounting", "supplier-ledger-summary", "Supplier Ledger Summary"],
  ["Accounting", "gross-profit-analysis", "Gross Profit by Item and Customer"],
  ["Accounting", "sales-invoice-trends", "Sales Invoice Trends"],
  ["Accounting", "purchase-invoice-trends", "Purchase Invoice Trends"],
  ["Buying", "purchase-analytics", "Purchase Analytics"],
  ["Buying", "purchase-order-analytics", "Purchase Orders: Status and Overdue"],
  ["Buying", "supplier-wise-sales-analytics", "Supplier Sourcing by Item"],
  ["Buying", "procurement-tracker", "MR → PO → GRN Tracker"],
  ["Buying", "subcontracting-materials", "Subcontractor Material Supply and Ageing"],
  ["Buying", "subcontracting-finished-goods", "Subcontracted Finished Goods Receipts"],
  ["Buying", "item-wise-purchase-history", "Item-wise Purchase History"],
  ["Buying", "items-to-be-requested", "Items Below Reorder Level"],
  ["Selling", "sales-analytics", "Sales by Item, Customer and Territory"],
  ["Selling", "item-wise-sales-history", "Item-wise Sales History"],
  ["Selling", "sales-order-analysis", "Pending Delivery and Billing"],
  ["Selling", "quotation-trends", "Quotation Trends"],
  ["Selling", "sales-order-trends", "Sales Order Trends"],
  ["Selling", "inactive-customers", "Inactive Customers"],
  ["Stock", "stock-projected-quantity", "Projected Stock Quantity"],
  ["Stock", "stock-ageing", "Stock Ageing (FIFO estimate)"],
  ["Stock", "stock-analytics", "Stock Analytics"],
  ["Stock", "delivery-note-trends", "Delivery Note Trends"],
  ["Stock", "item-shortage-report", "Item Shortage Report"],
  ["HR", "hr-analytics", "Headcount and Attrition"],
  ["HR", "leave-balance-summary", "Leave Balance Summary"],
  ["HR", "employee-birthdays", "Employee Birthdays"],
  ["HR", "recruitment-funnel", "Recruitment Funnel"],
  ["Support", "support-sla-compliance", "Support SLA Compliance"],
  ["Support", "support-agent-performance", "Support Agent Performance"],
] as const;

type Report = (typeof reports)[number];
const today = () => new Date().toISOString().slice(0, 10);
const yearStart = () => `${new Date().getFullYear()}-01-01`;
const display = (value: unknown) => value == null ? "—" : typeof value === "object" ? JSON.stringify(value) : String(value);

export default function EnterpriseReportsPage() {
  const [selected, setSelected] = useState<Report>(reports[0]);
  const [from, setFrom] = useState(yearStart);
  const [to, setTo] = useState(today);
  const [itemId, setItemId] = useState("");
  const [partyId, setPartyId] = useState("");
  const [currency, setCurrency] = useState("");
  const [territory, setTerritory] = useState("");
  const [granularity, setGranularity] = useState("month");
  const [statusFilter, setStatusFilter] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({ from_date: from, to_date: to });
      if (itemId.trim()) params.set("item_id", itemId.trim());
      if (partyId.trim()) params.set("party_id", partyId.trim());
      if (currency.trim()) params.set("currency", currency.trim().toUpperCase());
      if (territory.trim()) params.set("territory", territory.trim());
      if (["sales-invoice-trends", "purchase-invoice-trends"].includes(selected[1])) {
        params.set("granularity", granularity);
        params.set("page", String(page));
        params.set("page_size", "50");
        if (statusFilter) params.set("status", statusFilter);
      }
      if (selected[1] === "employee-birthdays") params.set("month", String(new Date(`${to}T00:00:00`).getMonth() + 1));
      if (selected[1] === "leave-balance-summary") params.set("fiscal_year", to.slice(0, 4));
      setData(await fetchWithTenant(`/reports/enterprise/${selected[1]}?${params.toString()}`));
    } catch (e: any) {
      setError(e.message || "Unable to load report");
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [from, to, selected, itemId, partyId, currency, territory, granularity, statusFilter, page]);

  useEffect(() => { void load(); }, [load]);

  const isInvoiceTrend = ["sales-invoice-trends", "purchase-invoice-trends"].includes(selected[1]);
  const rows: any[] = Array.isArray(data) ? data : Array.isArray(data?.rows) ? data.rows : Array.isArray(data?.documents) ? data.documents : [];
  const metrics = data && !Array.isArray(data) ? Object.entries(data).filter(([key, value]) => !["series", "documents", "pagination", "comparison"].includes(key) && !Array.isArray(value) && (value === null || typeof value !== "object")) : [];
  const headers = Array.from(new Set(rows.flatMap((row) => Object.keys(row))));
  const series: any[] = Array.isArray(data?.series) ? data.series : [];
  const maxAmount = Math.max(1, ...series.map((row) => Math.abs(Number(row.amount ?? 0))));

  return <main className="min-h-screen bg-stone-50 p-6 text-stone-900 lg:p-10">
    <header className="flex flex-wrap items-center justify-between gap-4 border-b border-stone-200 pb-5">
      <div className="flex items-center gap-3"><span className="rounded-xl bg-stone-900 p-2.5 text-white"><BarChart3 className="h-5 w-5" /></span><div><h1 className="text-2xl font-semibold">Enterprise Reports</h1><p className="mt-1 text-sm text-stone-600">{reports.length} cross-module operational and financial reports</p></div></div>
      <div className="flex flex-wrap gap-4"><Link href="/reports/party-ledger" className="text-sm text-blue-700 underline">Customer / supplier journals</Link><Link href="/reports" className="text-sm text-blue-700 underline">Financial statements and consolidation</Link></div>
    </header>
    <section className="mt-6 flex flex-wrap items-end gap-3 rounded-xl border border-stone-200 bg-white p-4">
      <label className="grid gap-1 text-xs text-stone-600">Report<select value={selected[1]} onChange={(e) => setSelected(reports.find((r) => r[1] === e.target.value)!)} className="min-w-72 rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm text-stone-900">{reports.map(([group, key, title]) => <option key={key} value={key}>{group} · {title}</option>)}</select></label>
      <label className="grid gap-1 text-xs text-stone-600"><span className="flex items-center gap-1"><CalendarDays className="h-3 w-3"/>From</span><input type="date" value={from} onChange={(e) => setFrom(e.target.value)} className="rounded-lg border border-stone-300 px-3 py-2 text-sm" /></label>
      <label className="grid gap-1 text-xs text-stone-600"><span className="flex items-center gap-1"><CalendarDays className="h-3 w-3"/>To / As of</span><input type="date" value={to} onChange={(e) => setTo(e.target.value)} className="rounded-lg border border-stone-300 px-3 py-2 text-sm" /></label>
      <label className="grid gap-1 text-xs text-stone-600">Item ID<input value={itemId} onChange={(e) => setItemId(e.target.value)} placeholder="Optional UUID" className="w-52 rounded-lg border border-stone-300 px-3 py-2 text-sm" /></label>
      <label className="grid gap-1 text-xs text-stone-600">Party ID<input value={partyId} onChange={(e) => setPartyId(e.target.value)} placeholder="Supplier or customer UUID" className="w-56 rounded-lg border border-stone-300 px-3 py-2 text-sm" /></label>
      <label className="grid gap-1 text-xs text-stone-600">Currency<input value={currency} onChange={(e) => setCurrency(e.target.value)} maxLength={3} placeholder="USD" className="w-24 rounded-lg border border-stone-300 px-3 py-2 text-sm uppercase" /></label>
      {isInvoiceTrend && <label className="grid gap-1 text-xs text-stone-600">Period<select value={granularity} onChange={(e) => { setGranularity(e.target.value); setPage(1); }} className="rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm"><option value="day">Day</option><option value="month">Month</option><option value="quarter">Quarter</option><option value="year">Year</option></select></label>}
      {isInvoiceTrend && <label className="grid gap-1 text-xs text-stone-600">Status<select value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }} className="rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm"><option value="">All active</option>{(selected[1] === "sales-invoice-trends" ? ["ISSUED", "PAID", "CANCELLED"] : ["UNMATCHED", "MATCHED", "DISPUTED", "STAGED", "POSTED"]).map((value) => <option key={value} value={value}>{value}</option>)}</select></label>}
      {selected[1] === "item-wise-sales-history" && <label className="grid gap-1 text-xs text-stone-600">Sales partner territory<input value={territory} onChange={(e) => setTerritory(e.target.value)} placeholder="Optional" className="w-44 rounded-lg border border-stone-300 px-3 py-2 text-sm" /></label>}
      <button onClick={() => void load()} disabled={loading} className="flex items-center gap-2 rounded-lg bg-stone-900 px-4 py-2 text-sm text-white disabled:opacity-50"><RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />Refresh</button>
    </section>
    <section className="mt-5 rounded-xl border border-stone-200 bg-white p-5">
      <div className="mb-4"><p className="text-xs font-medium uppercase tracking-wide text-stone-500">{selected[0]}</p><h2 className="text-lg font-semibold">{selected[2]}</h2></div>
      {error && <p role="alert" className="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-800">{error}</p>}
      {loading && <p className="text-sm text-stone-500">Loading report…</p>}
      {!loading && metrics.length > 0 && <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{metrics.map(([key, value]) => <div key={key} className="rounded-lg bg-stone-50 p-3"><p className="text-xs capitalize text-stone-500">{key.replaceAll("_", " ")}</p><p className="mt-1 break-words text-lg font-semibold">{display(value)}</p></div>)}</div>}
      {!loading && isInvoiceTrend && data?.comparison && <div className="mb-5 overflow-x-auto rounded-lg border border-stone-200"><table className="min-w-full text-left text-sm"><thead className="bg-stone-50 text-xs text-stone-600"><tr>{["Currency", "Current amount", "Previous amount", "Change", "Change %", "Current docs", "Previous docs"].map((label) => <th key={label} className="px-3 py-2">{label}</th>)}</tr></thead><tbody>{(data.comparison.by_currency ?? []).map((row: any) => <tr key={row.currency}><td className="px-3 py-2 font-medium">{row.currency}</td><td className="px-3 py-2">{display(row.current_amount)}</td><td className="px-3 py-2">{display(row.previous_amount)}</td><td className="px-3 py-2">{display(row.amount_change)}</td><td className="px-3 py-2">{row.amount_change_percent == null ? "—" : `${Number(row.amount_change_percent).toFixed(2)}%`}</td><td className="px-3 py-2">{row.current_documents}</td><td className="px-3 py-2">{row.previous_documents}</td></tr>)}</tbody></table></div>}
      {!loading && isInvoiceTrend && series.length > 0 && <div className="mb-5 space-y-3 rounded-lg border border-stone-200 p-4"><h3 className="text-sm font-semibold">Amount by period</h3>{series.map((row, index) => <div key={`${row.period}-${row.status}-${row.currency}-${index}`} className="grid grid-cols-[7rem_7rem_1fr_auto] items-center gap-3 text-xs"><span>{row.period}</span><span className="text-stone-600">{row.status} · {row.currency}</span><div className="h-3 overflow-hidden rounded bg-stone-100"><div className="h-full rounded bg-emerald-600" style={{ width: `${Math.max(1, Math.abs(Number(row.amount ?? 0)) / maxAmount * 100)}%` }} /></div><span>{display(row.amount)}</span></div>)}</div>}
      {!loading && rows.length > 0 && <div className="overflow-x-auto"><table className="min-w-full border-collapse text-left text-sm"><thead><tr>{headers.map((key) => <th key={key} className="border-b border-stone-200 px-3 py-2 text-xs font-semibold capitalize text-stone-600">{key.replaceAll("_", " ")}</th>)}</tr></thead><tbody>{rows.map((row, i) => <tr key={i} className="odd:bg-stone-50">{headers.map((key) => <td key={key} className="max-w-80 border-b border-stone-100 px-3 py-2 align-top">{key === "source_url" && row[key] ? <Link href={row[key]} className="text-blue-700 underline">Open journal</Link> : display(row[key])}</td>)}</tr>)}</tbody></table></div>}
      {!loading && isInvoiceTrend && data?.pagination?.total_pages > 1 && <div className="mt-4 flex items-center justify-between text-sm"><span>Page {data.pagination.page} of {data.pagination.total_pages} · {data.pagination.total_documents} invoices</span><div className="flex gap-2"><button onClick={() => setPage((value) => Math.max(1, value - 1))} disabled={page <= 1} className="rounded border px-3 py-1 disabled:opacity-40">Previous</button><button onClick={() => setPage((value) => Math.min(data.pagination.total_pages, value + 1))} disabled={page >= data.pagination.total_pages} className="rounded border px-3 py-1 disabled:opacity-40">Next</button></div></div>}
      {!loading && data != null && rows.length === 0 && metrics.length === 0 && <pre className="overflow-auto rounded-lg bg-stone-50 p-4 text-xs">{JSON.stringify(data, null, 2)}</pre>}
      {!loading && data != null && rows.length === 0 && metrics.length > 0 && <p className="mt-3 text-sm text-stone-500">No detail rows returned for this selection.</p>}
      {!loading && data != null && rows.length === 0 && metrics.length === 0 && !error && <p className="text-sm text-stone-500">No results.</p>}
    </section>
  </main>;
}
