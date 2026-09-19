"use client";

import { useEffect, useState } from "react";
import { Layers, Plus, RefreshCw, AlertCircle, CheckCircle2, ShieldCheck, ArrowRight } from "lucide-react";
import { api } from "@/lib/api";

export default function LedgerPage() {
  const [entries, setEntries] = useState<any[]>([]);
  const [accounts, setAccounts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // New Transaction Modal
  const [showModal, setShowModal] = useState(false);
  const [debitAccount, setDebitAccount] = useState("1300-RAW-MATERIALS");
  const [creditAccount, setCreditAccount] = useState("2100-AP-VENDORS");
  const [amount, setAmount] = useState("1250.00");
  const [sourceDoc, setSourceDoc] = useState("MANUAL_JOURNAL");
  const [staging, setStaging] = useState(false);
  const [commitResult, setCommitResult] = useState<any | null>(null);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [glEntries, chartOfAccounts] = await Promise.all([
        api.getGLEntries(),
        api.getAccounts(),
      ]);
      setEntries(glEntries);
      setAccounts(chartOfAccounts);
    } catch (err: any) {
      setError(err.message || "Failed to query ledger records from PostgreSQL.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleStageTransaction = async (e: React.FormEvent) => {
    e.preventDefault();
    setStaging(true);
    setError(null);
    setCommitResult(null);

    const val = parseFloat(amount);
    const today = new Date().toISOString().split("T")[0];

    try {
      const res = await api.stageTransaction({
        posting_date: today,
        currency: "USD",
        source_document_type: sourceDoc,
        source_document_id: "00000000-0000-0000-0000-000000000000",
        entries: [
          {
            account_code: debitAccount,
            cost_center: "PLANT-01",
            debit_amount: val,
            credit_amount: 0,
            currency: "USD",
          },
          {
            account_code: creditAccount,
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

  const totalDebits = entries.reduce((acc, curr) => acc + parseFloat(curr.debit_amount || 0), 0);
  const totalCredits = entries.reduce((acc, curr) => acc + parseFloat(curr.credit_amount || 0), 0);
  const isBalanced = Math.abs(totalDebits - totalCredits) < 0.0001;

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
          <span className="text-xs text-cream-600">Total Posted Debits</span>
          <div className="mt-1 text-lg font-bold text-cream-900">${totalDebits.toFixed(2)}</div>
        </div>
        <div className="rounded-xl border border-cream-300 bg-cream-100 p-4 shadow-xs">
          <span className="text-xs text-cream-600">Total Posted Credits</span>
          <div className="mt-1 text-lg font-bold text-cream-900">${totalCredits.toFixed(2)}</div>
        </div>
        <div className="rounded-xl border border-cream-300 bg-cream-100 p-4 shadow-xs">
          <span className="text-xs text-cream-600">Zero-Sum Balance Invariant</span>
          <div className="mt-1 flex items-center gap-1.5">
            <span className={`h-2 w-2 rounded-full ${isBalanced ? "bg-sage-600" : "bg-terracotta-600"}`} />
            <span className="text-sm font-bold text-cream-900">
              {isBalanced ? "STRICT ZERO-SUM BALANCED" : "IMBALANCE DETECTED"}
            </span>
          </div>
        </div>
      </div>

      {/* Entries List */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-cream-900">Immutable General Ledger Postings</h2>
          <span className="text-xs text-cream-600 font-mono">{entries.length} postings</span>
        </div>

        {entries.length === 0 ? (
          <div className="rounded-xl border border-cream-300 bg-cream-100 p-8 text-center text-xs text-cream-600">
            No ledger transactions posted yet. Use "Post Balanced Transaction" above to create an entry.
          </div>
        ) : (
          <div className="rounded-xl border border-cream-300 bg-cream-100 overflow-hidden shadow-xs">
            <table className="w-full text-left text-xs border-collapse font-mono">
              <thead>
                <tr className="border-b border-cream-300 bg-cream-200/60 text-cream-800 font-medium text-[11px]">
                  <th className="py-2.5 px-4">Date</th>
                  <th className="py-2.5 px-4">Account Code</th>
                  <th className="py-2.5 px-4">Cost Center</th>
                  <th className="py-2.5 px-4">Debit</th>
                  <th className="py-2.5 px-4">Credit</th>
                  <th className="py-2.5 px-4">Source Type</th>
                  <th className="py-2.5 px-4">Txn ID</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-cream-200">
                {entries.map((e) => (
                  <tr key={e.entry_id} className="hover:bg-cream-50/50 transition-colors">
                    <td className="py-3 px-4 text-cream-700">{e.posting_date}</td>
                    <td className="py-3 px-4 font-bold text-cream-900">{e.account_code}</td>
                    <td className="py-3 px-4 text-cream-600 text-[11px]">{e.cost_center}</td>
                    <td className="py-3 px-4 text-cream-900">
                      {parseFloat(e.debit_amount) > 0 ? `$${parseFloat(e.debit_amount).toFixed(2)}` : "-"}
                    </td>
                    <td className="py-3 px-4 text-cream-900">
                      {parseFloat(e.credit_amount) > 0 ? `$${parseFloat(e.credit_amount).toFixed(2)}` : "-"}
                    </td>
                    <td className="py-3 px-4 text-[11px] text-cream-600">{e.source_document_type}</td>
                    <td className="py-3 px-4 text-[11px] text-cream-500">{e.transaction_id.slice(0, 8)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Modal: Post Transaction */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="w-full max-w-md rounded-xl border border-cream-300 bg-cream-100 p-6 shadow-lg space-y-4">
            <div className="flex items-center justify-between border-b border-cream-300 pb-3">
              <h3 className="font-semibold text-sm text-cream-900">Stage Balanced Transaction</h3>
              <button onClick={() => setShowModal(false)} className="text-cream-600 hover:text-cream-900 text-xs">
                Cancel
              </button>
            </div>

            <form onSubmit={handleStageTransaction} className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-cream-900 mb-1">Debit Account</label>
                <select
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
                <label className="block text-xs font-medium text-cream-900 mb-1">Credit Account</label>
                <select
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
                  required
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  className="w-full rounded-lg border border-cream-300 bg-cream-50 px-3 py-1.5 text-xs text-cream-900 font-mono"
                />
              </div>

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
