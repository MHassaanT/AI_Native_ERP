"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Plus, RefreshCw, AlertCircle, CheckCircle2 } from "lucide-react";
import { api, fetchWithTenant } from "@/lib/api";

const emptyFilters = { from_date: "", to_date: "", account_code: "", customer_id: "", supplier_id: "", contractor_id: "", activity: "", warehouse_id: "", item_id: "", cost_center: "", source_document_type: "", currency: "" };
const inputStyle = "mt-1 w-full rounded-lg border border-cream-300 bg-cream-50 px-3 py-2 text-xs text-cream-900";

export default function LedgerPage() {
  const [entries, setEntries] = useState<any[]>([]);
  const [accounts, setAccounts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [filters, setFilters] = useState(emptyFilters);
  const [appliedFilters, setAppliedFilters] = useState(emptyFilters);
  const [offset, setOffset] = useState(0);
  const [total, setTotal] = useState(0);
  const [totals, setTotals] = useState<{ currency: string; debit: string; credit: string }[]>([]);
  const [customers, setCustomers] = useState<any[]>([]);
  const [suppliers, setSuppliers] = useState<any[]>([]);
  const [warehouses, setWarehouses] = useState<any[]>([]);
  const [items, setItems] = useState<any[]>([]);
  const requestId = useRef(0);
  const [purpose, setPurpose] = useState("");
  const [postingDate, setPostingDate] = useState(() => new Date().toLocaleDateString("en-CA"));
  const [warehouseId, setWarehouseId] = useState("");
  const [itemId, setItemId] = useState("");

  // New Transaction Modal
  const [showModal, setShowModal] = useState(false);
  const [debitAccount, setDebitAccount] = useState("1300-RAW-MATERIALS");
  const [creditAccount, setCreditAccount] = useState("2100-AP-VENDORS");
  const [amount, setAmount] = useState("1250.00");
  const [sourceDoc, setSourceDoc] = useState("MANUAL_JOURNAL");
  const [staging, setStaging] = useState(false);
  const [commitResult, setCommitResult] = useState<any | null>(null);
  const [partyType, setPartyType] = useState("");
  const [partyId, setPartyId] = useState("");
  const [partySide, setPartySide] = useState("debit");
  const [parties, setParties] = useState<{ id: string; name: string }[]>([]);

  useEffect(() => {
    let current = true;
    setPartyId(""); setParties([]);
    if (partyType) fetchWithTenant(partyType === "CUSTOMER" ? "/commercial/customers" : "/ap/suppliers")
      .then(rows => { if (current) setParties(rows.map((row: any) => partyType === "CUSTOMER"
        ? { id: row.customer_id, name: row.customer_name } : { id: row.supplier_id, name: row.supplier_name })); })
      .catch((reason: Error) => { if (current) setError(reason.message); });
    return () => { current = false; };
  }, [partyType]);

  const loadData = useCallback(async () => {
    const id = ++requestId.current;
    setLoading(true);
    setError(null);
    try {
      const data = await api.getLedgerReport({ ...appliedFilters, limit: "100", offset: String(offset),
        transaction_id: new URLSearchParams(window.location.search).get("transaction_id") || "" });
      if (id !== requestId.current) return;
      setEntries(data.entries);
      setTotal(data.total);
      setTotals(data.totals);
    } catch (err: any) {
      if (id === requestId.current) { setEntries([]); setTotals([]); setTotal(0); setError(err.message || "Failed to load ledger."); }
    } finally {
      if (id === requestId.current) setLoading(false);
    }
  }, [appliedFilters, offset]);

  useEffect(() => { loadData(); return () => { requestId.current++; }; }, [loadData]);
  useEffect(() => {
    let current = true;
    Promise.all([api.getAccounts(), api.getCustomers(), api.getSuppliers(), api.getWarehouses(), api.getItems()])
      .then(([accounts, customers, suppliers, warehouses, items]) => {
        if (!current) return;
        setAccounts(accounts); setCustomers(customers); setSuppliers(suppliers); setWarehouses(warehouses); setItems(items);
        if (accounts.length) { setDebitAccount(accounts[0].account_code); setCreditAccount(accounts[Math.min(1, accounts.length - 1)].account_code); }
      }).catch((err: Error) => { if (current) setError(err.message); });
    return () => { current = false; };
  }, []);

  const updateFilter = (key: keyof typeof emptyFilters, value: string) => setFilters(previous => ({ ...previous, [key]: value }));
  const applyFilters = (event: React.FormEvent) => {
    event.preventDefault();
    if (filters.from_date && filters.to_date && filters.from_date > filters.to_date) {
      setError("From date must be on or before To date."); return;
    }
    setOffset(0); setAppliedFilters({ ...filters });
  };

  const handleStageTransaction = async (e: React.FormEvent) => {
    e.preventDefault();
    setStaging(true);
    setError(null);
    setCommitResult(null);

    const val = amount;


    try {
      const res = await api.stageTransaction({
        posting_date: postingDate,
        currency: "USD",
        source_document_type: sourceDoc,
        source_document_id: crypto.randomUUID(),
        entries: [
          {
            purpose: purpose.trim() || null,
            warehouse_id: warehouseId || null,
            item_id: itemId || null,
            account_code: debitAccount,
            ...(partyType && partyId && partySide === "debit" ? { party_type: partyType, party_id: partyId } : {}),
            cost_center: "PLANT-01",
            debit_amount: val,
            credit_amount: 0,
            currency: "USD",
          },
          {
            purpose: purpose.trim() || null,
            warehouse_id: warehouseId || null,
            item_id: itemId || null,
            account_code: creditAccount,
            ...(partyType && partyId && partySide === "credit" ? { party_type: partyType, party_id: partyId } : {}),
            cost_center: "CORP-FINANCE",
            debit_amount: 0,
            credit_amount: val,
            currency: "USD",
          },
        ],
        human_in_the_loop_approved: false,
        agent_id: "PORTAL_USER",
      });

      setCommitResult(res);
      setShowModal(false);
      await loadData();
    } catch (err: any) {
      setError(err.message || "Transaction rejected by Deterministic Ledger Engine.");
    } finally {
      setStaging(false);
    }
  };

  const isBalanced = totals.every(row => Math.abs(Number(row.debit) - Number(row.credit)) < 0.0001);
  const hasFilters = Object.values(appliedFilters).some(Boolean);
  const formatTotals = (field: "debit" | "credit") => totals.length
    ? totals.map(row => `${row.currency} ${Number(row[field]).toFixed(2)}`).join(" · ") : "0.00";

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between border-b border-cream-300 pb-5">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-cream-900">
            Deterministic General Ledger Engine
          </h1>
          <p className="text-xs text-cream-700 mt-1">
            Immutable double-entry book-of-record strictly enforcing zero-sum invariants and statutory period controls.
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
            onClick={() => setShowModal(true)}
            className="flex items-center gap-1.5 rounded-md border border-cream-400 bg-cream-900 px-3 py-1.5 text-xs font-medium text-cream-50 hover:bg-cream-800 transition-colors"
          >
            <Plus className="h-3.5 w-3.5" />
            <span>Post Balanced Transaction</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-terracotta-50 border border-terracotta-500/30 text-terracotta-700 text-xs">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <form onSubmit={applyFilters} className="rounded-xl border border-cream-300 bg-cream-100 p-4 space-y-4">
        <h2 className="text-sm font-semibold text-cream-900">Ledger filters</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3 text-xs">
          <label>From date<input type="date" value={filters.from_date} max={filters.to_date || undefined} onChange={e => updateFilter("from_date", e.target.value)} className={inputStyle} /></label>
          <label>To date<input type="date" value={filters.to_date} min={filters.from_date || undefined} onChange={e => updateFilter("to_date", e.target.value)} className={inputStyle} /></label>
          <label>Account<select value={filters.account_code} onChange={e => updateFilter("account_code", e.target.value)} className={inputStyle}><option value="">All accounts</option>{accounts.map(row => <option key={row.account_id} value={row.account_code}>{row.account_code} — {row.account_name}</option>)}</select></label>
          <label>Activity<select value={filters.activity} onChange={e => updateFilter("activity", e.target.value)} className={inputStyle}><option value="">All activities</option><option value="SALES">Sales</option><option value="BUYING">Buying</option><option value="SUBCONTRACTING">Subcontracting</option></select></label>
          <label>Customer<select value={filters.customer_id} onChange={e => updateFilter("customer_id", e.target.value)} className={inputStyle}><option value="">All customers</option>{customers.map(row => <option key={row.customer_id} value={row.customer_id}>{row.customer_name}</option>)}</select></label>
          <label>Supplier<select value={filters.supplier_id} onChange={e => updateFilter("supplier_id", e.target.value)} className={inputStyle}><option value="">All suppliers</option>{suppliers.map(row => <option key={row.supplier_id} value={row.supplier_id}>{row.supplier_name}</option>)}</select></label>
          <label>Contractor (subcontracting supplier)<select value={filters.contractor_id} onChange={e => updateFilter("contractor_id", e.target.value)} className={inputStyle}><option value="">All contractors</option>{suppliers.map(row => <option key={row.supplier_id} value={row.supplier_id}>{row.supplier_name}</option>)}</select></label>
          <label>Warehouse<select value={filters.warehouse_id} onChange={e => updateFilter("warehouse_id", e.target.value)} className={inputStyle}><option value="">All warehouses</option>{warehouses.map(row => <option key={row.warehouse_id} value={row.warehouse_id}>{row.warehouse_name}</option>)}</select></label>
          <label>Item<select value={filters.item_id} onChange={e => updateFilter("item_id", e.target.value)} className={inputStyle}><option value="">All items</option>{items.map(row => <option key={row.item_id} value={row.item_id}>{row.item_code} — {row.item_name}</option>)}</select></label>
          <label>Cost center<input value={filters.cost_center} onChange={e => updateFilter("cost_center", e.target.value)} placeholder="All cost centers" className={inputStyle} /></label>
          <label>Source type<input value={filters.source_document_type} onChange={e => updateFilter("source_document_type", e.target.value.toUpperCase())} placeholder="e.g. MANUAL_JOURNAL" className={inputStyle} /></label>
          <label>Currency<input maxLength={3} value={filters.currency} onChange={e => updateFilter("currency", e.target.value.toUpperCase())} placeholder="All currencies" className={inputStyle} /></label>
        </div>
        <p className="text-xs text-cream-700">Party filters show related journals. Item and warehouse filters show postings linked to matching source documents; amounts are journal amounts, not item allocations.</p>
        <div className="flex gap-2"><button type="submit" disabled={loading} className="rounded-lg bg-cream-900 text-cream-50 px-4 py-2 text-xs disabled:opacity-50">Apply filters</button><button type="button" onClick={() => { setFilters({ ...emptyFilters }); setAppliedFilters({ ...emptyFilters }); setOffset(0); }} className="rounded-lg border border-cream-300 px-4 py-2 text-xs">Reset</button></div>
      </form>

      {/* Ledger Verification Outcome */}
      {commitResult && (
        <div className="rounded-lg border border-sage-500/30 bg-sage-50 p-4 text-xs text-sage-900 space-y-1 font-mono">
          <div className="font-semibold flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-sage-600" />
            <span>Ledger Transaction Committed Successfully!</span>
          </div>
          <div className="text-[11px] text-sage-800">
            Transaction ID: {commitResult.transaction_id} &bull; Tier: {commitResult.autonomy_tier} &bull; Balanced Lines: {commitResult.lines_committed}
          </div>
        </div>
      )}

      {/* Ledger Balance Summary Card */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 font-mono">
        <div className="rounded-xl border border-cream-300 bg-cream-100 p-4 shadow-xs">
          <span className="text-xs text-cream-600">Matching Debits</span>
          <div className="mt-1 text-lg font-bold text-cream-900">{formatTotals("debit")}</div>
        </div>
        <div className="rounded-xl border border-cream-300 bg-cream-100 p-4 shadow-xs">
          <span className="text-xs text-cream-600">Matching Credits</span>
          <div className="mt-1 text-lg font-bold text-cream-900">{formatTotals("credit")}</div>
        </div>
        <div className="rounded-xl border border-cream-300 bg-cream-100 p-4 shadow-xs">
          <span className="text-xs text-cream-600">Matching Debit/Credit Difference</span>
          <div className="mt-1 flex items-center gap-1.5">
            <span className={`h-2 w-2 rounded-full ${isBalanced ? "bg-sage-600" : "bg-terracotta-600"}`} />
            <span className="text-sm font-bold text-cream-900">
              {isBalanced ? "MATCHING TOTALS BALANCED" : "MATCHING TOTALS DIFFER"}
            </span>
          </div>
        </div>
      </div>

      <p className="text-xs text-cream-700">Totals cover all matching postings. {hasFilters ? "A filtered selection can have different debits and credits; each complete journal remains balanced." : "Amounts are grouped by currency."}</p>

      {/* Entries List */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-cream-900">Immutable General Ledger Postings</h2>
          <span className="text-xs text-cream-600 font-mono">{total} matching postings</span>
        </div>

        {entries.length === 0 ? (
          <div className="rounded-xl border border-cream-300 bg-cream-100 p-8 text-center text-xs text-cream-600">
            {loading ? "Loading ledger postings…" : "No ledger postings match the selected filters."}
          </div>
        ) : (
          <div className="rounded-xl border border-cream-300 bg-cream-100 overflow-x-auto shadow-xs">
            <table className="w-full text-left text-xs border-collapse font-mono">
              <thead>
                <tr className="border-b border-cream-300 bg-cream-200/60 text-cream-800 font-medium text-[11px]">
                  <th className="py-2.5 px-4">Date</th>
                  <th className="py-2.5 px-4">Account Code</th>
                  <th className="py-2.5 px-4">From Account (Credit)</th>
                  <th className="py-2.5 px-4">To Account (Debit)</th>
                  <th className="py-2.5 px-4">Purpose / Reason</th>
                  <th className="py-2.5 px-4">Currency</th>
                  <th className="py-2.5 px-4">Cost Center</th>
                  <th className="py-2.5 px-4">Debit</th>
                  <th className="py-2.5 px-4">Credit</th>
                  <th className="py-2.5 px-4">Source Type</th>
                  <th className="py-2.5 px-4">Party</th>
                  <th className="py-2.5 px-4">Txn ID</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-cream-200">
                {entries.map((e) => (
                  <tr key={e.entry_id} className="hover:bg-cream-50/50 transition-colors">
                    <td className="py-3 px-4 text-cream-700">{e.posting_date}</td>
                    <td className="py-3 px-4 font-bold text-cream-900">{e.account_code}</td>
                    <td className="py-3 px-4 text-cream-700">{e.from_accounts?.join(", ") || "—"}</td>
                    <td className="py-3 px-4 text-cream-700">{e.to_accounts?.join(", ") || "—"}</td>
                    <td className="py-3 px-4 text-cream-700 min-w-[180px] whitespace-pre-wrap">{e.purpose || "—"}</td>
                    <td className="py-3 px-4 text-cream-700">{e.currency}</td>
                    <td className="py-3 px-4 text-cream-600 text-[11px]">{e.cost_center}</td>
                    <td className="py-3 px-4 text-cream-900">
                      {parseFloat(e.debit_amount) > 0 ? parseFloat(e.debit_amount).toFixed(2) : "-"}
                    </td>
                    <td className="py-3 px-4 text-cream-900">
                      {parseFloat(e.credit_amount) > 0 ? parseFloat(e.credit_amount).toFixed(2) : "-"}
                    </td>
                    <td className="py-3 px-4 text-[11px] text-cream-600">{e.source_document_type}</td>
                    <td className="py-3 px-4 text-[11px] text-cream-600">{e.party_name_snapshot || "—"}</td>
                    <td className="py-3 px-4 text-[11px] text-cream-500">{e.transaction_id.slice(0, 8)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="flex justify-between items-center text-xs text-cream-700">
        <span>{total ? `${offset + 1}–${Math.min(offset + entries.length, total)} of ${total}` : "0 postings"}</span>
        <div className="flex gap-2"><button disabled={loading || offset === 0} onClick={() => setOffset(Math.max(0, offset - 100))} className="rounded border border-cream-300 px-3 py-2 disabled:opacity-50">Previous</button><button disabled={loading || offset + 100 >= total} onClick={() => setOffset(offset + 100)} className="rounded border border-cream-300 px-3 py-2 disabled:opacity-50">Next</button></div>
      </div>

      {/* Modal: Post Transaction */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="w-full max-w-md max-h-[90vh] overflow-y-auto rounded-xl border border-cream-300 bg-cream-100 p-6 shadow-lg space-y-4">
            <div className="flex items-center justify-between border-b border-cream-300 pb-3">
              <h3 className="font-semibold text-sm text-cream-900">Stage Balanced Transaction</h3>
              <button onClick={() => setShowModal(false)} className="text-cream-600 hover:text-cream-900 text-xs">
                Cancel
              </button>
            </div>

            <form onSubmit={handleStageTransaction} className="space-y-3">
              <label className="block text-xs">Posting date<input required type="date" value={postingDate} onChange={e => setPostingDate(e.target.value)} className={inputStyle} /></label>
              <label className="block text-xs">Purpose / Reason<textarea maxLength={1000} value={purpose} onChange={e => setPurpose(e.target.value)} placeholder="Describe why this transaction is being posted" className={inputStyle} /></label>
              <label className="block text-xs">Source type<input required maxLength={64} value={sourceDoc} onChange={e => setSourceDoc(e.target.value)} className={inputStyle} /></label>
              <label className="block text-xs">Warehouse (optional)<select value={warehouseId} onChange={e => setWarehouseId(e.target.value)} className={inputStyle}><option value="">No warehouse</option>{warehouses.map(row => <option key={row.warehouse_id} value={row.warehouse_id}>{row.warehouse_name}</option>)}</select></label>
              <label className="block text-xs">Item (optional)<select value={itemId} onChange={e => setItemId(e.target.value)} className={inputStyle}><option value="">No item</option>{items.map(row => <option key={row.item_id} value={row.item_id}>{row.item_code} — {row.item_name}</option>)}</select></label>
              <div>
                <label htmlFor="ledger-to-account" className="block text-xs font-medium text-cream-900 mb-1">To Account (Debit)</label>
                <select id="ledger-to-account" required
                  value={debitAccount}
                  onChange={(e) => setDebitAccount(e.target.value)}
                  className="w-full rounded-lg border border-cream-300 bg-cream-50 px-3 py-1.5 text-xs text-cream-900 font-mono"
                >
                  {accounts.map((acc) => (
                    <option key={acc.account_id} value={acc.account_code}>
                      {acc.account_code} ({acc.account_name})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label htmlFor="ledger-from-account" className="block text-xs font-medium text-cream-900 mb-1">From Account (Credit)</label>
                <select id="ledger-from-account" required
                  value={creditAccount}
                  onChange={(e) => setCreditAccount(e.target.value)}
                  className="w-full rounded-lg border border-cream-300 bg-cream-50 px-3 py-1.5 text-xs text-cream-900 font-mono"
                >
                  {accounts.map((acc) => (
                    <option key={acc.account_id} value={acc.account_code}>
                      {acc.account_code} ({acc.account_name})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-cream-900 mb-1">Transfer Amount ($)</label>
                <input
                  type="number"
                  step="0.01"
                  min="0.01"
                  required
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  className="w-full rounded-lg border border-cream-300 bg-cream-50 px-3 py-1.5 text-xs text-cream-900 font-mono"
                />
              </div>

              <fieldset className="space-y-2 rounded border border-cream-300 p-3 text-xs">
                <legend className="px-1 font-medium">Party attribution</legend>
                <p className="text-cream-700">Attribute only the receivable/payable leg. General adjustments remain unallocated to an invoice.</p>
                <label className="block">Party type<select value={partyType} onChange={e => setPartyType(e.target.value)} className="mt-1 w-full rounded border bg-cream-50 p-2"><option value="">No party</option><option value="CUSTOMER">Customer</option><option value="SUPPLIER">Supplier</option></select></label>
                {partyType && <><label className="block">Party<select required value={partyId} onChange={e => setPartyId(e.target.value)} className="mt-1 w-full rounded border bg-cream-50 p-2"><option value="">Choose a party</option>{parties.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}</select></label><label className="block">Control leg<select value={partySide} onChange={e => setPartySide(e.target.value)} className="mt-1 w-full rounded border bg-cream-50 p-2"><option value="debit">Debit account</option><option value="credit">Credit account</option></select></label></>}
              </fieldset>

              <div className="flex justify-end gap-2 pt-3 border-t border-cream-300">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="rounded-lg border border-cream-300 bg-cream-200 px-3 py-1.5 text-xs font-medium text-cream-800"
                >
                  Close
                </button>
                <button
                  type="submit"
                  disabled={staging}
                  className="rounded-lg border border-cream-400 bg-cream-900 px-3 py-1.5 text-xs font-medium text-cream-50 hover:bg-cream-800 disabled:opacity-50"
                >
                  {staging ? "Verifying Invariants..." : "Commit Transaction"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
