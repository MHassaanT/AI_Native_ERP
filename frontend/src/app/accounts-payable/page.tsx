"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, ShieldAlert, Plus, RefreshCw, FileText, Check, AlertCircle } from "lucide-react";
import { api } from "@/lib/api";

export default function AccountsPayablePage() {
  const [invoices, setInvoices] = useState<any[]>([]);
  const [purchaseOrders, setPurchaseOrders] = useState<any[]>([]);
  const [goodsReceipts, setGoodsReceipts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [matchingId, setMatchingId] = useState<string | null>(null);
  const [matchResult, setMatchResult] = useState<any | null>(null);
  const [error, setError] = useState<string | null>(null);

  // New Invoice Form Modal
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newInvNumber, setNewInvNumber] = useState("");
  const [newSubtotal, setNewSubtotal] = useState("");
  const [selectedPoId, setSelectedPoId] = useState("");
  const [creating, setCreating] = useState(false);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [invs, pos, grns] = await Promise.all([
        api.getInvoices(),
        api.getPurchaseOrders(),
        api.getGoodsReceipts(),
      ]);
      setInvoices(invs);
      setPurchaseOrders(pos);
      setGoodsReceipts(grns);
    } catch (err: any) {
      setError(err.message || "Failed to load accounts payable records from database.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleMatch = async (invoiceId: string) => {
    setMatchingId(invoiceId);
    setError(null);
    try {
      const result = await api.matchInvoice(invoiceId);
      setMatchResult(result);
      await loadData();
    } catch (err: any) {
      setError(err.message || "3-Way match evaluation failed.");
    } finally {
      setMatchingId(null);
    }
  };

  const handleCreateInvoice = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedPoId) return;
    setCreating(true);
    try {
      const po = purchaseOrders.find((p) => p.po_id === selectedPoId);
      if (!po) throw new Error("Selected PO not found.");

      const grn = goodsReceipts.find((g) => g.po_id === selectedPoId) || goodsReceipts[0];

      await api.createInvoice({
        invoice_number: newInvNumber,
        supplier_id: po.supplier_id,
        po_id: po.po_id,
        grn_id: grn ? grn.grn_id : null,
        invoice_date: new Date().toISOString().split("T")[0],
        subtotal: parseFloat(newSubtotal),
        tax_amount: 0,
      });

      setShowCreateModal(false);
      setNewInvNumber("");
      setNewSubtotal("");
      await loadData();
    } catch (err: any) {
      setError(err.message || "Failed to create invoice.");
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between border-b border-cream-300 pb-5">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-cream-900">
            Accounts Payable &bull; Automated 3-Way Matching
          </h1>
          <p className="text-xs text-cream-700 mt-1">
            Real-time tripartite tolerance verification against PostgreSQL supplier invoices, POs, and GRNs.
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
            onClick={() => setShowCreateModal(true)}
            className="flex items-center gap-1.5 rounded-md border border-cream-400 bg-cream-900 px-3 py-1.5 text-xs font-medium text-cream-50 hover:bg-cream-800 transition-colors"
          >
            <Plus className="h-3.5 w-3.5" />
            <span>New Vendor Invoice</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-terracotta-50 border border-terracotta-500/30 text-terracotta-700 text-xs">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Match Result Banner */}
      {matchResult && (
        <div
          className={`rounded-lg border p-4 text-xs ${
            matchResult.is_matched
              ? "border-sage-500/30 bg-sage-50 text-sage-800"
              : "border-terracotta-500/30 bg-terracotta-50 text-terracotta-800"
          }`}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5 font-semibold">
              {matchResult.is_matched ? (
                <CheckCircle2 className="h-5 w-5 text-sage-600" />
              ) : (
                <ShieldAlert className="h-5 w-5 text-terracotta-600" />
              )}
              <span>
                Invoice {matchResult.invoice_number}: {matchResult.matching_status}
              </span>
            </div>
            <span className="font-mono text-[10px] px-2 py-0.5 rounded bg-cream-100">
              Variance: {matchResult.tolerance_summary?.overall_variance_percentage || "0.00"}%
            </span>
          </div>
          {matchResult.dispute_notice && (
            <p className="mt-2 text-[11px] font-mono">
              Dispute: {matchResult.dispute_notice.dispute_reason} (Action: {matchResult.dispute_notice.action_recommended})
            </p>
          )}
          {matchResult.ledger_result && (
            <p className="mt-1 text-[11px] font-mono text-sage-700">
              Ledger committed: TXN-{matchResult.ledger_result.transaction_id.slice(0, 8)}
            </p>
          )}
        </div>
      )}

      {/* Invoices List */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-cream-900">Registered Supplier Invoices</h2>
          <span className="text-xs text-cream-600 font-mono">{invoices.length} invoices found</span>
        </div>

        {invoices.length === 0 ? (
          <div className="rounded-xl border border-cream-300 bg-cream-100 p-8 text-center space-y-3">
            <FileText className="h-8 w-8 text-cream-400 mx-auto" />
            <div className="text-xs text-cream-800 font-medium">No supplier invoices found in database</div>
            <p className="text-[11px] text-cream-600 max-w-sm mx-auto">
              Create a supplier invoice linked to an active purchase order to execute automated 3-way matching.
            </p>
            <button
              onClick={() => setShowCreateModal(true)}
              className="inline-flex items-center gap-1.5 rounded-md border border-cream-400 bg-cream-900 px-3 py-1.5 text-xs font-medium text-cream-50 hover:bg-cream-800"
            >
              <Plus className="h-3.5 w-3.5" />
              <span>Create First Invoice</span>
            </button>
          </div>
        ) : (
          <div className="rounded-xl border border-cream-300 bg-cream-100 overflow-hidden shadow-xs">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-cream-300 bg-cream-200/60 text-cream-800 font-medium text-[11px]">
                  <th className="py-2.5 px-4">Invoice #</th>
                  <th className="py-2.5 px-4">Date</th>
                  <th className="py-2.5 px-4">Amount</th>
                  <th className="py-2.5 px-4">PO / GRN</th>
                  <th className="py-2.5 px-4">Match Status</th>
                  <th className="py-2.5 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-cream-200">
                {invoices.map((inv) => (
                  <tr key={inv.invoice_id} className="hover:bg-cream-50/50 transition-colors">
                    <td className="py-3 px-4 font-mono font-medium text-cream-900">{inv.invoice_number}</td>
                    <td className="py-3 px-4 text-cream-700">{inv.invoice_date}</td>
                    <td className="py-3 px-4 font-mono font-bold text-cream-900">
                      ${parseFloat(inv.total_amount).toFixed(2)}
                    </td>
                    <td className="py-3 px-4 text-[11px] font-mono text-cream-600">
                      {inv.po_id ? `PO: ${inv.po_id.slice(0, 8)}` : "Direct Bill"}
                    </td>
                    <td className="py-3 px-4">
                      <span
                        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold font-mono ${
                          inv.matching_status === "MATCHED"
                            ? "bg-sage-100 text-sage-800 border border-sage-500/30"
                            : inv.matching_status === "DISPUTED"
                            ? "bg-terracotta-100 text-terracotta-800 border border-terracotta-500/30"
                            : "bg-cream-200 text-cream-800 border border-cream-300"
                        }`}
                      >
                        {inv.matching_status}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-right">
                      {inv.matching_status === "UNMATCHED" && (
                        <button
                          onClick={() => handleMatch(inv.invoice_id)}
                          disabled={matchingId === inv.invoice_id}
                          className="rounded border border-cream-400 bg-cream-900 px-2.5 py-1 text-[11px] font-medium text-cream-50 hover:bg-cream-800 transition-colors disabled:opacity-50"
                        >
                          {matchingId === inv.invoice_id ? "Matching..." : "Execute Match"}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Modal: Create Vendor Invoice */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="w-full max-w-md rounded-xl border border-cream-300 bg-cream-100 p-6 shadow-lg space-y-4">
            <div className="flex items-center justify-between border-b border-cream-300 pb-3">
              <h3 className="font-semibold text-sm text-cream-900">Register Vendor Invoice</h3>
              <button
                onClick={() => setShowCreateModal(false)}
                className="text-cream-600 hover:text-cream-900 text-xs"
              >
                Cancel
              </button>
            </div>

            <form onSubmit={handleCreateInvoice} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-cream-900 mb-1">Invoice Number</label>
                <input
                  type="text"
                  required
                  value={newInvNumber}
                  onChange={(e) => setNewInvNumber(e.target.value)}
                  placeholder="e.g. INV-2026-9901"
                  className="w-full rounded-lg border border-cream-300 bg-cream-50 px-3 py-1.5 text-xs text-cream-900 font-mono"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-cream-900 mb-1">Purchase Order</label>
                <select
                  required
                  value={selectedPoId}
                  onChange={(e) => setSelectedPoId(e.target.value)}
                  className="w-full rounded-lg border border-cream-300 bg-cream-50 px-3 py-1.5 text-xs text-cream-900 font-mono"
                >
                  <option value="">Select PO to match...</option>
                  {purchaseOrders.map((p) => (
                    <option key={p.po_id} value={p.po_id}>
                      {p.po_number} (${parseFloat(p.total_amount).toFixed(2)})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-cream-900 mb-1">Invoice Total Amount ($)</label>
                <input
                  type="number"
                  step="0.01"
                  required
                  value={newSubtotal}
                  onChange={(e) => setNewSubtotal(e.target.value)}
                  placeholder="e.g. 14700.00"
                  className="w-full rounded-lg border border-cream-300 bg-cream-50 px-3 py-1.5 text-xs text-cream-900 font-mono"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="rounded-lg border border-cream-300 bg-cream-200 px-3 py-1.5 text-xs font-medium text-cream-800"
                >
                  Close
                </button>
                <button
                  type="submit"
                  disabled={creating}
                  className="rounded-lg border border-cream-400 bg-cream-900 px-3 py-1.5 text-xs font-medium text-cream-50 hover:bg-cream-800 disabled:opacity-50"
                >
                  {creating ? "Saving..." : "Create Invoice"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
