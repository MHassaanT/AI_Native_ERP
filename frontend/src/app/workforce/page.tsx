"use client";

import { useEffect, useState } from "react";
import { Users, Plus, RefreshCw, AlertCircle, CheckCircle2, ShieldAlert, Award, FileText, Send } from "lucide-react";
import { api } from "@/lib/api";

export default function WorkforcePage() {
  const [employees, setEmployees] = useState<any[]>([]);
  const [certifications, setCertifications] = useState<any[]>([]);
  const [expenses, setExpenses] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Expense Claim Form
  const [empCode, setEmpCode] = useState("EMP-OPERATOR-01");
  const [expenseCategory, setExpenseCategory] = useState("MEALS");
  const [expenseAmount, setExpenseAmount] = useState("45.00");
  const [hasAlcohol, setHasAlcohol] = useState(false);
  const [receiptText, setReceiptText] = useState("Client working dinner, main course, mineral water");
  const [auditing, setAuditing] = useState(false);
  const [auditResult, setAuditResult] = useState<any | null>(null);

  // New Employee Modal
  const [showEmpModal, setShowEmpModal] = useState(false);
  const [newCode, setNewCode] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [department, setDepartment] = useState("Machining Operations");
  const [creatingEmp, setCreatingEmp] = useState(false);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [empList, certList, expList] = await Promise.all([
        api.getEmployees(),
        api.getCertifications(),
        api.getExpenses(),
      ]);
      setEmployees(empList);
      setCertifications(certList.certifications || []);
      setExpenses(expList);
    } catch (err: any) {
      setError(err.message || "Failed to query workforce data from database.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleAuditExpense = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuditing(true);
    setError(null);
    setAuditResult(null);

    try {
      const res = await api.auditExpense({
        employee_code: empCode,
        expense_category: expenseCategory,
        claim_date: new Date().toISOString().split("T")[0],
        total_amount: parseFloat(expenseAmount),
        contains_alcohol: hasAlcohol,
        receipt_text: receiptText,
      });

      setAuditResult(res);
      await loadData();
    } catch (err: any) {
      setError(err.message || "Expense claim audit failed.");
    } finally {
      setAuditing(false);
    }
  };

  const handleCreateEmployee = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreatingEmp(true);
    try {
      await api.createEmployee({
        employee_code: newCode.trim().toUpperCase(),
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        email: email.trim().toLowerCase(),
        department,
        certifications: [],
        max_weekly_hours: 48,
      });
      setShowEmpModal(false);
      setNewCode("");
      setFirstName("");
      setLastName("");
      setEmail("");
      await loadData();
    } catch (err: any) {
      setError(err.message || "Failed to add employee.");
    } finally {
      setCreatingEmp(false);
    }
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between border-b border-cream-300 pb-5">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-cream-900">
            Workforce, Operator Certifications & Autonomous Expense Auditing
          </h1>
          <p className="text-xs text-cream-700 mt-1">
            Statutory labor constraint defense (11h rest, 48h week) and real-time receipt policy auditing.
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
            onClick={() => setShowEmpModal(true)}
            className="flex items-center gap-1.5 rounded-md border border-cream-400 bg-cream-900 px-3 py-1.5 text-xs font-medium text-cream-50 hover:bg-cream-800 transition-colors"
          >
            <Plus className="h-3.5 w-3.5" />
            <span>Add Employee</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-terracotta-50 border border-terracotta-500/30 text-terracotta-700 text-xs">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Expense Policy Auditor Panel */}
      <div className="rounded-xl border border-cream-300 bg-cream-100 p-5 shadow-xs space-y-4">
        <div className="flex items-center justify-between border-b border-cream-300 pb-3">
          <div className="flex items-center gap-2">
            <FileText className="h-4 w-4 text-cream-800" />
            <h2 className="text-xs font-semibold text-cream-900">Autonomous Travel Expense Auditor</h2>
          </div>
          <span className="text-[10px] font-mono text-cream-600">Policy: $75 Meal Cap &bull; Alcohol Prohibited</span>
        </div>

        <form onSubmit={handleAuditExpense} className="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
          <div>
            <label className="block text-xs font-medium text-cream-900 mb-1">Employee</label>
            <select
              value={empCode}
              onChange={(e) => setEmpCode(e.target.value)}
              className="w-full rounded-lg border border-cream-300 bg-cream-50 px-3 py-1.5 text-xs text-cream-900 font-mono"
            >
              {employees.map((e) => (
                <option key={e.employee_id} value={e.employee_code}>
                  {e.employee_code} ({e.first_name} {e.last_name})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-cream-900 mb-1">Amount ($)</label>
            <input
              type="number"
              step="0.01"
              required
              value={expenseAmount}
              onChange={(e) => setExpenseAmount(e.target.value)}
              className="w-full rounded-lg border border-cream-300 bg-cream-50 px-3 py-1.5 text-xs text-cream-900 font-mono"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-cream-900 mb-1">Category</label>
            <select
              value={expenseCategory}
              onChange={(e) => setExpenseCategory(e.target.value)}
              className="w-full rounded-lg border border-cream-300 bg-cream-50 px-3 py-1.5 text-xs text-cream-900 font-mono"
            >
              <option value="MEALS">MEALS</option>
              <option value="LODGING">LODGING</option>
              <option value="TRANSPORT">TRANSPORT</option>
              <option value="SUPPLIES">SUPPLIES</option>
            </select>
          </div>

          <div className="flex items-center gap-3">
            <label className="flex items-center gap-1.5 text-xs text-cream-800 cursor-pointer">
              <input
                type="checkbox"
                checked={hasAlcohol}
                onChange={(e) => setHasAlcohol(e.target.checked)}
                className="rounded border-cream-300 text-cream-900"
              />
              <span>Alcohol</span>
            </label>
            <button
              type="submit"
              disabled={auditing}
              className="flex-1 rounded-lg border border-cream-400 bg-cream-900 px-3 py-1.5 text-xs font-medium text-cream-50 hover:bg-cream-800 transition-colors disabled:opacity-50"
            >
              {auditing ? "Auditing..." : "Audit Claim"}
            </button>
          </div>
        </form>

        {auditResult && (
          <div
            className={`p-3 rounded-lg border text-xs font-mono space-y-1 ${
              auditResult.is_auto_approved
                ? "border-sage-500/30 bg-sage-50 text-sage-900"
                : "border-terracotta-500/30 bg-terracotta-50 text-terracotta-900"
            }`}
          >
            <div className="font-semibold flex items-center gap-1.5">
              {auditResult.is_auto_approved ? (
                <CheckCircle2 className="h-4 w-4 text-sage-600" />
              ) : (
                <ShieldAlert className="h-4 w-4 text-terracotta-600" />
              )}
              <span>{auditResult.audit_summary}</span>
            </div>
            {auditResult.policy_violations?.length > 0 && (
              <div className="text-[11px] text-terracotta-700">
                Violations: {auditResult.policy_violations.join("; ")}
              </div>
            )}
            {auditResult.ledger_commit && (
              <div className="text-[11px] text-sage-700">
                General Ledger Auto-Reimbursement: TXN-{auditResult.ledger_commit.transaction_id.slice(0, 8)}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Two Column Layout: Employees & Safety Certifications */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Employees */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-cream-900">Plant Workforce Roster</h2>
            <span className="text-xs text-cream-600 font-mono">{employees.length} operators</span>
          </div>

          <div className="rounded-xl border border-cream-300 bg-cream-100 overflow-hidden shadow-xs">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-cream-300 bg-cream-200/60 text-cream-800 font-medium text-[11px]">
                  <th className="py-2.5 px-4">Code</th>
                  <th className="py-2.5 px-4">Name</th>
                  <th className="py-2.5 px-4">Department</th>
                  <th className="py-2.5 px-4">Max Hours</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-cream-200">
                {employees.map((emp) => (
                  <tr key={emp.employee_id} className="hover:bg-cream-50/50 transition-colors">
                    <td className="py-3 px-4 font-mono font-medium text-cream-900">{emp.employee_code}</td>
                    <td className="py-3 px-4 text-cream-800">{emp.first_name} {emp.last_name}</td>
                    <td className="py-3 px-4 text-[11px] text-cream-600">{emp.department}</td>
                    <td className="py-3 px-4 font-mono text-cream-700">{emp.max_weekly_hours}h/wk</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Safety Certifications */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-cream-900">Operator Safety Certifications (PostgreSQL)</h2>
            <span className="text-xs text-cream-600 font-mono">{certifications.length} certifications</span>
          </div>

          <div className="rounded-xl border border-cream-300 bg-cream-100 overflow-hidden shadow-xs">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-cream-300 bg-cream-200/60 text-cream-800 font-medium text-[11px]">
                  <th className="py-2.5 px-4">Operator</th>
                  <th className="py-2.5 px-4">Certification</th>
                  <th className="py-2.5 px-4">Expires</th>
                  <th className="py-2.5 px-4">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-cream-200">
                {certifications.map((c, i) => (
                  <tr key={i} className="hover:bg-cream-50/50 transition-colors">
                    <td className="py-3 px-4 font-mono font-medium text-cream-900">{c.employee_code}</td>
                    <td className="py-3 px-4 text-cream-800">
                      <div className="font-medium">{c.certification_name}</div>
                      <div className="text-[10px] font-mono text-cream-500">{c.certification_code}</div>
                    </td>
                    <td className="py-3 px-4 font-mono text-[11px] text-cream-600">{c.expires_at?.slice(0, 10)}</td>
                    <td className="py-3 px-4">
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-sage-100 text-sage-800 border border-sage-500/30">
                        VALID
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Modal: Add Employee */}
      {showEmpModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="w-full max-w-md rounded-xl border border-cream-300 bg-cream-100 p-6 shadow-lg space-y-4">
            <div className="flex items-center justify-between border-b border-cream-300 pb-3">
              <h3 className="font-semibold text-sm text-cream-900">Add Workforce Employee</h3>
              <button onClick={() => setShowEmpModal(false)} className="text-cream-600 hover:text-cream-900 text-xs">
                Cancel
              </button>
            </div>

            <form onSubmit={handleCreateEmployee} className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-cream-900 mb-1">Employee Code</label>
                <input
                  type="text"
                  required
                  value={newCode}
                  onChange={(e) => setNewCode(e.target.value)}
                  placeholder="e.g. EMP-OPERATOR-03"
                  className="w-full rounded-lg border border-cream-300 bg-cream-50 px-3 py-1.5 text-xs text-cream-900 font-mono"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-cream-900 mb-1">First Name</label>
                  <input
                    type="text"
                    required
                    value={firstName}
                    onChange={(e) => setFirstName(e.target.value)}
                    className="w-full rounded-lg border border-cream-300 bg-cream-50 px-3 py-1.5 text-xs text-cream-900"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-cream-900 mb-1">Last Name</label>
                  <input
                    type="text"
                    required
                    value={lastName}
                    onChange={(e) => setLastName(e.target.value)}
                    className="w-full rounded-lg border border-cream-300 bg-cream-50 px-3 py-1.5 text-xs text-cream-900"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-cream-900 mb-1">Email</label>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@plant.internal"
                  className="w-full rounded-lg border border-cream-300 bg-cream-50 px-3 py-1.5 text-xs text-cream-900"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-cream-900 mb-1">Department</label>
                <input
                  type="text"
                  required
                  value={department}
                  onChange={(e) => setDepartment(e.target.value)}
                  className="w-full rounded-lg border border-cream-300 bg-cream-50 px-3 py-1.5 text-xs text-cream-900"
                />
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-cream-300">
                <button
                  type="button"
                  onClick={() => setShowEmpModal(false)}
                  className="rounded-lg border border-cream-300 bg-cream-200 px-3 py-1.5 text-xs font-medium text-cream-800"
                >
                  Close
                </button>
                <button
                  type="submit"
                  disabled={creatingEmp}
                  className="rounded-lg border border-cream-400 bg-cream-900 px-3 py-1.5 text-xs font-medium text-cream-50 hover:bg-cream-800 disabled:opacity-50"
                >
                  {creatingEmp ? "Saving..." : "Add Employee"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
