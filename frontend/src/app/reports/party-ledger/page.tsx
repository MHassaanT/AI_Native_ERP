"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { fetchWithTenant } from "@/lib/api";

type Party = { id: string; name: string };
type Journal = {
  party_name: string; balance_convention: string; legacy_note: string; total_rows: number;
  workspace_unattributed_control_entry_count: number;
  unallocated_balances_by_currency: { currency: string; balance: string }[];
  totals_by_currency: { currency: string; opening_balance: string; debit: string; credit: string; closing_balance: string }[];
  rows: { entry_id: string; posting_date: string; currency: string; account_code: string; party_name_snapshot: string;
    debit_amount: string; credit_amount: string; running_balance: string; source_document_type: string;
    source_document_id: string; source_url: string }[];
  outstanding_invoices: { invoice_id: string; invoice_number: string; currency: string; due_date: string | null;
    outstanding: string; overdue_days: number | null }[];
};

const today = () => new Date().toISOString().slice(0, 10);
const money = (value: string) => {
  const [whole, rawFraction = ""] = String(value).split(".");
  const fraction = rawFraction.padEnd(4, "0").replace(/0+$/, "").padEnd(2, "0");
  return `${whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",")}.${fraction}`;
};

export default function PartyLedgerPage() {
  const [type, setType] = useState("CUSTOMER");
  const [parties, setParties] = useState<Party[]>([]);
  const [party, setParty] = useState("");
  const [from, setFrom] = useState(() => `${today().slice(0, 4)}-01-01`);
  const [to, setTo] = useState(today);
  const [currency, setCurrency] = useState("");
  const [offset, setOffset] = useState(0);
  const [version, setVersion] = useState(0);
  const [journal, setJournal] = useState<Journal | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const pageSize = 100;

  useEffect(() => {
    let current = true;
    setParties([]); setParty(""); setJournal(null); setError(""); setOffset(0);
    fetchWithTenant(type === "CUSTOMER" ? "/commercial/customers" : "/ap/suppliers").then(rows => {
      if (!current) return;
      const options: Party[] = rows.map((row: any) => type === "CUSTOMER"
        ? { id: row.customer_id, name: row.customer_name } : { id: row.supplier_id, name: row.supplier_name });
      setParties(options); setParty(options[0]?.id || "");
    }).catch((reason: Error) => { if (current) setError(reason.message); });
    return () => { current = false; };
  }, [type]);

  useEffect(() => {
    if (!party) return;
    let current = true;
    setLoading(true); setError(""); setJournal(null);
    const params = new URLSearchParams({ from_date: from, to_date: to, offset: String(offset), limit: String(pageSize) });
    if (currency.trim()) params.set("currency", currency.toUpperCase().trim());
    fetchWithTenant(`/reports/party-ledger/${type}/${party}?${params}`).then(data => {
      if (current) setJournal(data);
    }).catch((reason: Error) => { if (current) setError(reason.message); })
      .finally(() => { if (current) setLoading(false); });
    return () => { current = false; };
  }, [type, party, from, to, currency, offset, version]);

  return <main className="space-y-6 p-6">
    <header className="flex flex-wrap justify-between gap-3 border-b pb-4"><div><h1 className="text-2xl font-semibold">Customer and supplier journals</h1><p className="mt-1 text-sm text-stone-600">Opening balances, journal movements and invoice settlements, separately for each currency.</p></div><Link href="/reports/enterprise" className="text-sm underline">All reports</Link></header>
    <section className="flex flex-wrap items-end gap-3 rounded-lg border bg-white p-4">
      <label className="grid gap-1 text-sm">Party type<select value={type} onChange={e => setType(e.target.value)} className="rounded border p-2"><option value="CUSTOMER">Customer</option><option value="SUPPLIER">Supplier</option></select></label>
      <label className="grid gap-1 text-sm">{type === "CUSTOMER" ? "Customer" : "Supplier"}<select value={party} onChange={e => { setParty(e.target.value); setOffset(0); }} className="min-w-56 rounded border p-2"><option value="">Select a party</option>{parties.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}</select></label>
      <label className="grid gap-1 text-sm">From<input type="date" value={from} onChange={e => { setFrom(e.target.value); setOffset(0); }} className="rounded border p-2"/></label>
      <label className="grid gap-1 text-sm">To<input type="date" value={to} onChange={e => { setTo(e.target.value); setOffset(0); }} className="rounded border p-2"/></label>
      <label className="grid gap-1 text-sm">Currency<input value={currency} maxLength={3} placeholder="All" onChange={e => { setCurrency(e.target.value); setOffset(0); }} className="w-24 rounded border p-2 uppercase"/></label>
      <button onClick={() => setVersion(v => v + 1)} disabled={loading || !party} className="rounded bg-stone-900 px-4 py-2 text-white disabled:opacity-50">Refresh</button>
    </section>
    {error && <p role="alert" className="rounded bg-red-50 p-3 text-red-800">{error}</p>}
    {loading && <p role="status">Loading journal…</p>}
    {journal && <>
      <section><h2 className="mb-2 text-lg font-semibold">{journal.party_name}</h2><p className="mb-3 text-sm text-stone-600">Balance convention: {journal.balance_convention}. Totals cover the entire selected period, including rows on other pages.</p>
        <div className="overflow-auto"><table className="w-full text-left text-sm"><thead><tr>{["Currency", "Opening balance", "Debits", "Credits", "Closing balance"].map(text => <th className="border-b p-2" key={text}>{text}</th>)}</tr></thead><tbody>{journal.totals_by_currency.map(row => <tr key={row.currency}><td className="p-2">{row.currency}</td>{[row.opening_balance, row.debit, row.credit, row.closing_balance].map((value, i) => <td className="p-2" key={i}>{money(value)}</td>)}</tr>)}</tbody></table></div>
        {!journal.totals_by_currency.length && <p className="py-3 text-sm">No attributed journal entries for this selection.</p>}
      </section>
      <section className="overflow-auto"><h2 className="mb-2 text-lg font-semibold">Transactions</h2><table className="w-full text-left text-sm"><thead><tr>{["Date", "Currency", "Account", "Party at posting", "Debit", "Credit", "Running balance", "Source"].map(text => <th className="whitespace-nowrap border-b p-2" key={text}>{text}</th>)}</tr></thead><tbody>{journal.rows.map(row => <tr key={row.entry_id}><td className="whitespace-nowrap border-b p-2">{row.posting_date}</td><td className="border-b p-2">{row.currency}</td><td className="border-b p-2">{row.account_code}</td><td className="border-b p-2">{row.party_name_snapshot}</td><td className="border-b p-2">{money(row.debit_amount)}</td><td className="border-b p-2">{money(row.credit_amount)}</td><td className="border-b p-2">{money(row.running_balance)}</td><td className="border-b p-2"><Link className="underline" href={row.source_url}>{row.source_document_type.replaceAll("_", " ")}</Link></td></tr>)}</tbody></table>
        {!journal.rows.length && <p className="py-3 text-sm">No movements in this period.</p>}
        <div className="mt-3 flex items-center gap-3 text-sm"><button className="rounded border px-3 py-1 disabled:opacity-50" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - pageSize))}>Previous</button><span>{journal.total_rows ? offset + 1 : 0}–{Math.min(offset + pageSize, journal.total_rows)} of {journal.total_rows}</span><button className="rounded border px-3 py-1 disabled:opacity-50" disabled={offset + pageSize >= journal.total_rows} onClick={() => setOffset(offset + pageSize)}>Next</button></div>
      </section>
      <section className="overflow-auto"><h2 className="mb-2 text-lg font-semibold">Outstanding invoices as of {to}</h2><table className="w-full text-left text-sm"><thead><tr>{["Invoice", "Currency", "Due date", "Outstanding", "Days overdue"].map(text => <th className="border-b p-2" key={text}>{text}</th>)}</tr></thead><tbody>{journal.outstanding_invoices.map(row => <tr key={row.invoice_id}><td className="p-2">{row.invoice_number}</td><td className="p-2">{row.currency}</td><td className="p-2">{row.due_date || "Not recorded"}</td><td className="p-2">{money(row.outstanding)}</td><td className="p-2">{row.overdue_days ?? "Unknown"}</td></tr>)}</tbody></table></section>
      {journal.unallocated_balances_by_currency.length > 0 && <p className="text-sm">Unallocated movements are included in the party balance but not assigned to invoice ageing: {journal.unallocated_balances_by_currency.map(row => `${row.currency} ${money(row.balance)}`).join("; ")}.</p>}
      <p className="rounded border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950">{journal.legacy_note} Unattributed control entries across the workspace through this date: {journal.workspace_unattributed_control_entry_count}. This count covers all parties, not only the selected party.</p>
    </>}
  </main>;
}
