"use client";

import { useEffect, useState } from "react";
import { Landmark, CheckCircle2, AlertCircle, RefreshCw, Send, Sparkles, FileText, ArrowRight } from "lucide-react";
import { api } from "@/lib/api";

export default function BankReconciliationPage() {
  const [receivables, setReceivables] = useState<any[]>([]);
  const [clearedTransactions, setClearedTransactions] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Ingestion Form
  const [counterparty, setCounterparty] = useState("");
  const [amount, setAmount] = useState("");
  const [remittance, setRemittance] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [feedResult, setFeedResult] = useState<any | null>(null);

  const loadReceivables = async () => {
    setLoading(true);
    setError(null);
    try {
      const orders = await api.getReceivables();
      setReceivables(orders);
    } catch (err: any) {
      setError(err.message || "Failed to load open receivables from database.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadReceivables();
  }, []);

  const handleIngestFeed = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    setFeedResult(null);

    try {
      const res = await api.ingestBankFeed({
        amount: parseFloat(amount),
        counterparty_name: counterparty.trim(),
        remittance_information: remittance.trim(),
      });

      setFeedResult(res);
      setClearedTransactions((prev) => [
        {
          id: res.transaction_id,
          counterparty,
          amount: parseFloat(amount),
          confidence: res.confidence_score,
          is_cleared: res.is_auto_cleared,
          order_number: res.matched_order_number,
          ledger_id: res.ledger_commit?.transaction_id,
          timestamp: new Date().toLocaleTimeString(),
        },
        ...prev,
      ]);

      setCounterparty("");
      setAmount("");
      setRemittance("");
      await loadReceivables();
    } catch (err: any) {
      setError(err.message || "Failed to ingest bank feed settlement.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between border-b border-cream-300 pb-5">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-cream-900">
            Continuous Bank Reconciliation
          </h1>
          <p className="text-xs text-cream-700 mt-1">
            Real-time open-banking settlement feeds matched against PostgreSQL receivables and posted to General Ledger.
          </p>
        </div>

        <button
          onClick={loadReceivables}
          disabled={loading}
          className="flex items-center gap-1.5 rounded-md border border-cream-300 bg-cream-100 px-3 py-1.5 text-xs font-medium text-cream-800 hover:bg-cream-200 transition-colors"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
          <span>Refresh Receivables</span>
        </button>
      </div>

      {error && (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-terracotta-50 border border-terracotta-500/30 text-terracotta-700 text-xs">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Live Ingestion Form & Result Banner */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Ingest Form Card */}
        <div className="rounded-xl border border-cream-300 bg-cream-100 p-5 shadow-xs space-y-4">
          <div className="flex items-center gap-2 border-b border-cream-300 pb-3">
            <Landmark className="h-4 w-4 text-cream-800" />
            <h2 className="text-xs font-semibold text-cream-900">Ingest Open-Banking Settlement</h2>
          </div>

          <form onSubmit={handleIngestFeed} className="space-y-3">
            <div>
              <label className="block text-xs font-medium text-cream-900 mb-1">Counterparty (Payer)</label>
              <input
                type="text"
                required
                value={counterparty}
                onChange={(e) => setCounterparty(e.target.value)}
                placeholder="e.g. Tesla Energy Inc."
                className="w-full rounded-lg border border-cream-300 bg-cream-50 px-3 py-1.5 text-xs text-cream-900"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-cream-900 mb-1">Settlement Amount ($)</label>
              <input
                type="number"
                step="0.01"
                required
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                placeholder="e.g. 50000.00"
                className="w-full rounded-lg border border-cream-300 bg-cream-50 px-3 py-1.5 text-xs text-cream-900 font-mono"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-cream-900 mb-1">Remittance Narrative</label>
              <input
                type="text"
                value={remittance}
                onChange={(e) => setRemittance(e.target.value)}
                placeholder="e.g. Settlement for delivery order"
                className="w-full rounded-lg border border-cream-300 bg-cream-50 px-3 py-1.5 text-xs text-cream-900"
              />
            </div>

            <button
              type="submit"
              disabled={submitting}
              className="w-full flex items-center justify-center gap-1.5 rounded-lg border border-cream-400 bg-cream-900 px-3 py-2 text-xs font-medium text-cream-50 hover:bg-cream-800 transition-colors disabled:opacity-50"
            >
              <Send className="h-3 w-3" />
              <span>{submitting ? "Evaluating Match..." : "Post Wire Transfer"}</span>
            </button>
          </form>
        </div>

        {/* Live Feed Result Stream */}
        <div className="lg:col-span-2 rounded-xl border border-cream-300 bg-cream-100 p-5 shadow-xs space-y-4">
          <div className="flex items-center justify-between border-b border-cream-300 pb-3">
            <h2 className="text-xs font-semibold text-cream-900">Live Auto-Clearing Stream</h2>
            <span className="text-[10px] font-mono text-sage-700 bg-sage-50 px-2 py-0.5 rounded border border-sage-500/20">
              Confidence &ge; 0.92 = Auto-Post to GL
            </span>
          </div>

          {clearedTransactions.length === 0 ? (
            <div className="py-8 text-center text-xs text-cream-600">
              No live settlements ingested in this session. Submit a wire transfer using the form on the left.
            </div>
          ) : (
            <div className="space-y-2">
              {clearedTransactions.map((tx, idx) => (
                <div
                  key={idx}
                  className={`p-3 rounded-lg border text-xs flex items-center justify-between ${
                    tx.is_cleared
                      ? "border-sage-500/30 bg-sage-50 text-sage-900"
                      : "border-cream-300 bg-cream-50 text-cream-900"
                  }`}
                >
                  <div className="space-y-0.5">
                    <div className="font-semibold flex items-center gap-1.5">
                      {tx.is_cleared && <CheckCircle2 className="h-3.5 w-3.5 text-sage-600" />}
                      <span>{tx.counterparty}</span>
                      <span className="font-mono text-cream-600">(${tx.amount.toFixed(2)})</span>
                    </div>
                    <div className="text-[11px] text-cream-600 font-mono">
                      {tx.is_cleared ? (
                        <span>Auto-cleared against {tx.order_number || "Receivable"} &bull; GL: TXN-{tx.ledger_id?.slice(0, 8)}</span>
                      ) : (
                        <span>Flagged for manual review &bull; Confidence: {(tx.confidence * 100).toFixed(1)}%</span>
                      )}
                    </div>
                  </div>
                  <span className="text-[10px] text-cream-500 font-mono">{tx.timestamp}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Open Receivables in Database */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-cream-900">Active Customer Receivables (Database Ledger)</h2>
          <span className="text-xs text-cream-600 font-mono">{receivables.length} receivables</span>
        </div>

        {receivables.length === 0 ? (
          <div className="rounded-xl border border-cream-300 bg-cream-100 p-6 text-center text-xs text-cream-600">
            No open sales receivables found for this organization.
          </div>
        ) : (
          <div className="rounded-xl border border-cream-300 bg-cream-100 overflow-hidden shadow-xs">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-cream-300 bg-cream-200/60 text-cream-800 font-medium text-[11px]">
                  <th className="py-2.5 px-4">Order #</th>
                  <th className="py-2.5 px-4">Customer</th>
                  <th className="py-2.5 px-4">Order Date</th>
                  <th className="py-2.5 px-4">Total Amount</th>
                  <th className="py-2.5 px-4">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-cream-200">
                {receivables.map((r) => (
                  <tr key={r.order_id} className="hover:bg-cream-50/50 transition-colors">
                    <td className="py-3 px-4 font-mono font-medium text-cream-900">{r.order_number}</td>
                    <td className="py-3 px-4 text-cream-800">{r.customer_name}</td>
                    <td className="py-3 px-4 text-cream-600 font-mono text-[11px]">{r.order_date}</td>
                    <td className="py-3 px-4 font-mono font-bold text-cream-900">
                      ${parseFloat(r.total_amount).toFixed(2)}
                    </td>
                    <td className="py-3 px-4">
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-sage-100 text-sage-800 border border-sage-500/20">
                        {r.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
