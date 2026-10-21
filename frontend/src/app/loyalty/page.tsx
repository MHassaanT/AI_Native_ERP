"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { Award, RefreshCw } from "lucide-react";

export default function LoyaltyPage() {
  const [programs, setPrograms] = useState<any[]>([]);
  const [customers, setCustomers] = useState<any[]>([]);
  const [invoices, setInvoices] = useState<any[]>([]);
  const [programId, setProgramId] = useState("");
  const [customerId, setCustomerId] = useState("");
  const [invoiceId, setInvoiceId] = useState("");
  const [points, setPoints] = useState("10");
  const [balance, setBalance] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    setError("");
    try {
      const [programRows, customerRows, invoiceRows] = await Promise.all([
        api.getMasterData("loyalty-programs"), api.getCustomers(), api.getSalesInvoices(),
      ]);
      setPrograms(programRows.filter((row: any) => row.is_active));
      setCustomers(customerRows.filter((row: any) => row.is_active));
      setInvoices(invoiceRows.filter((row: any) => ["ISSUED", "PAID"].includes(row.status)));
      if (!programId && programRows.length) setProgramId(programRows[0].loyalty_program_id);
      if (!customerId && customerRows.length) setCustomerId(customerRows[0].customer_id);
    } catch (e: any) { setError(e.message || "Could not load loyalty data."); }
  }

  const eligibleInvoices = useMemo(
    () => invoices.filter((invoice) => invoice.customer_id === customerId), [invoices, customerId],
  );
  const selectedInvoice = eligibleInvoices.find((invoice) => invoice.invoice_id === invoiceId);

  useEffect(() => { void load(); }, []);
  useEffect(() => {
    if (!eligibleInvoices.some((invoice) => invoice.invoice_id === invoiceId))
      setInvoiceId(eligibleInvoices[0]?.invoice_id || "");
  }, [eligibleInvoices, invoiceId]);
  useEffect(() => {
    if (!programId || !customerId) return;
    void api.getLoyaltyBalance(programId, customerId)
      .then((result) => setBalance(String(result.balance)))
      .catch((e: any) => setError(e.message || "Could not load balance."));
  }, [programId, customerId]);

  async function post(kind: "earn" | "redeem") {
    setBusy(true); setError(""); setMessage("");
    try {
      const result = kind === "earn"
        ? await api.earnLoyaltyPoints({ loyalty_program_id: programId, customer_id: customerId, invoice_id: invoiceId })
        : await api.redeemLoyaltyPoints({ loyalty_program_id: programId, customer_id: customerId, points: Number(points) });
      setBalance(String(result.balance));
      setMessage(kind === "earn" ? `Points earned. New balance: ${result.balance}.` : `Points redeemed for ${result.credit_value} credit. New balance: ${result.balance}.`);
    } catch (e: any) { setError(e.message || "Loyalty transaction failed."); }
    finally { setBusy(false); }
  }

  return <div className="mx-auto max-w-5xl space-y-6">
    <header className="flex items-start justify-between"><div><div className="flex items-center gap-2 text-sage-700"><Award className="h-5 w-5"/><span className="text-xs font-semibold uppercase tracking-[0.16em]">Selling · POS</span></div><h1 className="mt-2 text-3xl font-semibold">Customer Loyalty</h1><p className="mt-1 text-sm text-cream-600">Earn and redeem points with a tenant-scoped, auditable points ledger.</p></div><button onClick={() => void load()} className="rounded-lg border border-cream-300 bg-white p-2" aria-label="Refresh"><RefreshCw className="h-4 w-4"/></button></header>
    {error && <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">{error}</div>}
    {message && <div className="rounded-lg border border-sage-200 bg-sage-50 p-3 text-sm text-sage-800">{message}</div>}
    {!programs.length || !customers.length ? <div className="rounded-xl border border-cream-200 bg-white p-8 text-sm text-cream-600">Create an active Loyalty Program and an active customer to start tracking points.</div> : <>
      <section className="grid gap-4 rounded-xl border border-cream-200 bg-white p-5 md:grid-cols-3">
        <label className="space-y-1 text-xs font-medium">Program<select value={programId} onChange={(e) => setProgramId(e.target.value)} className="w-full rounded-lg border border-cream-300 p-2 text-sm">{programs.map((p) => <option key={p.loyalty_program_id} value={p.loyalty_program_id}>{p.program_name}</option>)}</select></label>
        <label className="space-y-1 text-xs font-medium">Customer<select value={customerId} onChange={(e) => setCustomerId(e.target.value)} className="w-full rounded-lg border border-cream-300 p-2 text-sm">{customers.map((c) => <option key={c.customer_id} value={c.customer_id}>{c.customer_name}</option>)}</select></label>
        <div className="rounded-lg bg-sage-50 p-3"><div className="text-xs text-sage-700">Available points</div><div className="mt-1 text-2xl font-semibold text-sage-900">{balance ?? "—"}</div></div>
      </section>
      <section className="grid gap-5 md:grid-cols-2">
        <div className="space-y-4 rounded-xl border border-cream-200 bg-white p-5"><h2 className="font-semibold">Earn points</h2>
          <label className="block space-y-1 text-sm"><span className="text-cream-700">Eligible invoice</span><select value={invoiceId} onChange={(e) => setInvoiceId(e.target.value)} className="w-full rounded-lg border border-cream-300 px-3 py-2" disabled={!eligibleInvoices.length}><option value="">Select an invoice</option>{eligibleInvoices.map((invoice) => <option key={invoice.invoice_id} value={invoice.invoice_id}>{invoice.invoice_number} · {invoice.currency} {invoice.subtotal} · {invoice.status}</option>)}</select></label>
          <p className="text-sm text-cream-600">Points are calculated from the selected invoice subtotal ({selectedInvoice ? `${selectedInvoice.currency} ${selectedInvoice.subtotal}` : "—"}).</p>
          <button disabled={busy || !invoiceId} onClick={() => void post("earn")} className="rounded-lg bg-sage-700 px-4 py-2 text-sm font-medium text-white disabled:opacity-50">{busy ? "Processing…" : "Post earning"}</button>
        </div>
        <div className="space-y-4 rounded-xl border border-cream-200 bg-white p-5"><h2 className="font-semibold">Redeem points</h2><label className="block space-y-1 text-sm"><span className="text-cream-700">Points to redeem</span><input type="number" min="0.0001" step="0.0001" value={points} onChange={(e) => setPoints(e.target.value)} className="w-full rounded-lg border border-cream-300 px-3 py-2"/></label><button disabled={busy} onClick={() => void post("redeem")} className="rounded-lg bg-sage-700 px-4 py-2 text-sm font-medium text-white disabled:opacity-50">{busy ? "Processing…" : "Redeem"}</button></div>
      </section>
    </>}
  </div>;
}
