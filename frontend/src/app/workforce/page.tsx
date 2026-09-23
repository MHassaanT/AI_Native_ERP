"use client";

import { useEffect, useState } from "react";
import {
  Users,
  Plus,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  ShieldAlert,
  Award,
  FileText,
  Calendar,
  Clock,
  ArrowRightLeft,
  ShieldCheck,
} from "lucide-react";
import { api } from "@/lib/api";

export default function WorkforcePage() {
  const [employees, setEmployees] = useState<any[]>([]);
  const [certifications, setCertifications] = useState<any[]>([]);
  const [expenses, setExpenses] = useState<any[]>([]);
  const [shifts, setShifts] = useState<any[]>([]);
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

  // Schedule Shift Modal
  const [showShiftModal, setShowShiftModal] = useState(false);
  const [newShiftCode, setNewShiftCode] = useState("");
  const [shiftEmpCode, setShiftEmpCode] = useState("");
  const [shiftDate, setShiftDate] = useState(new Date().toISOString().split("T")[0]);
  const [shiftStartTime, setShiftStartTime] = useState("07:00");
  const [shiftEndTime, setShiftEndTime] = useState("15:00");
  const [creatingShift, setCreatingShift] = useState(false);

  // Shift Trade Simulator State
  const [reqEmpCode, setReqEmpCode] = useState("EMP-OPERATOR-01");
  const [targetEmpCode, setTargetEmpCode] = useState("EMP-MANAGER-001");
  const [tradeShiftCode, setTradeShiftCode] = useState("SHIFT-CNC-M1");
  const [proposedStart, setProposedStart] = useState("2026-09-24T07:00");
  const [priorEnd, setPriorEnd] = useState("2026-09-23T23:00"); // 8h rest by default -> triggers 11h rest violation
  const [durationHours, setDurationHours] = useState("8.0");
  const [currentWeeklyHours, setCurrentWeeklyHours] = useState("36.0");
  const [evaluatingTrade, setEvaluatingTrade] = useState(false);
  const [tradeResult, setTradeResult] = useState<any | null>(null);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [empList, certList, expList, shiftList] = await Promise.all([
        api.getEmployees().catch(() => []),
        api.getCertifications().catch(() => ({ certifications: [] })),
        api.getExpenses().catch(() => []),
        api.getShifts().catch(() => []),
      ]);
      setEmployees(empList);
      setCertifications(certList.certifications || []);
      setExpenses(expList);
      setShifts(shiftList || []);

      if (empList.length > 0) {
        if (!shiftEmpCode) setShiftEmpCode(empList[0].employee_code);
        if (!reqEmpCode) setReqEmpCode(empList[0].employee_code);
        if (empList.length > 1 && targetEmpCode === empList[0].employee_code) {
          setTargetEmpCode(empList[1].employee_code);
        }
      }
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

  const handleCreateShift = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreatingShift(true);
    try {
      const startDateTime = `${shiftDate}T${shiftStartTime}:00`;
      const endDateTime = `${shiftDate}T${shiftEndTime}:00`;
      await api.createShift({
        shift_code: newShiftCode.trim().toUpperCase(),
        employee_code: shiftEmpCode,
        shift_date: shiftDate,
        start_time: startDateTime,
        end_time: endDateTime,
        status: "SCHEDULED",
      });
      setShowShiftModal(false);
      setNewShiftCode("");
      await loadData();
    } catch (err: any) {
      setError(err.message || "Failed to schedule shift.");
    } finally {
      setCreatingShift(false);
    }
  };

  const handleEvaluateTrade = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    setEvaluatingTrade(true);
    setError(null);
    setTradeResult(null);

    try {
      const payload: any = {
        requesting_employee: reqEmpCode,
        target_employee: targetEmpCode,
        shift_code: tradeShiftCode.trim() || undefined,
        shift_duration_hours: parseFloat(durationHours) || 8.0,
      };

      if (proposedStart) {
        payload.target_proposed_shift_start = `${proposedStart}:00`;
      }
      if (priorEnd) {
        payload.target_previous_shift_end = `${priorEnd}:00`;
      }
      if (currentWeeklyHours) {
        payload.target_current_weekly_hours = parseFloat(currentWeeklyHours);
      }

      const res = await api.evaluateShiftTrade(payload);
      setTradeResult(res);

      // If approved, refresh shift list to show updated assignment
      if (res.is_approved) {
        await loadData();
      }
    } catch (err: any) {
      setError(err.message || "Shift trade evaluation failed.");
    } finally {
      setEvaluatingTrade(false);
    }
  };

  // Helper presets to easily demonstrate labor law invariants
  const applyPreset = (type: "REST_VIOLATION" | "OVERTIME_VIOLATION" | "COMPLIANT") => {
    if (type === "REST_VIOLATION") {
      setPriorEnd("2026-09-23T23:00");
      setProposedStart("2026-09-24T07:00"); // 8h interval (< 11h)
      setCurrentWeeklyHours("32.0");
      setDurationHours("8.0");
    } else if (type === "OVERTIME_VIOLATION") {
      setPriorEnd("2026-09-23T15:00");
      setProposedStart("2026-09-24T07:00"); // 16h interval (compliant)
      setCurrentWeeklyHours("42.0"); // 42h + 8h = 50h (> 48h ceiling)
      setDurationHours("8.0");
    } else {
      setPriorEnd("2026-09-23T15:00");
      setProposedStart("2026-09-24T07:00"); // 16h interval (compliant)
      setCurrentWeeklyHours("32.0"); // 32h + 8h = 40h (compliant)
      setDurationHours("8.0");
    }
  };

  return (
    <div className="space-y-8">
      {/* 1. Header */}
      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between border-b border-cream-300 pb-5">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-cream-900">
            Workforce, Shift Scheduling & Autonomous Policy Auditing
          </h1>
          <p className="text-xs text-cream-700 mt-1">
            Statutory labor constraint defense (11h rest interval, 48h rolling week) and real-time receipt policy auditing.
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
            className="flex items-center gap-1.5 rounded-md border border-cream-300 bg-cream-100 px-3 py-1.5 text-xs font-medium text-cream-800 hover:bg-cream-200 transition-colors"
          >
            <Plus className="h-3.5 w-3.5" />
            <span>Add Employee</span>
          </button>
          <button
            onClick={() => {
              setNewShiftCode(`SHIFT-${Math.floor(100 + Math.random() * 900)}`);
              setShowShiftModal(true);
            }}
            className="flex items-center gap-1.5 rounded-md border border-cream-400 bg-cream-900 px-3 py-1.5 text-xs font-medium text-cream-50 hover:bg-cream-800 transition-colors"
          >
            <Calendar className="h-3.5 w-3.5" />
            <span>Schedule Shift</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-terracotta-50 border border-terracotta-500/30 text-terracotta-700 text-xs">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* 2. Top Grid: Expense Auditor & Shift Trade Simulator */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Panel A: Autonomous Travel Expense Auditor */}
        <div className="rounded-xl border border-cream-300 bg-cream-100 p-5 shadow-xs space-y-4">
          <div className="flex items-center justify-between border-b border-cream-300 pb-3">
            <div className="flex items-center gap-2">
              <FileText className="h-4 w-4 text-cream-800" />
              <h2 className="text-xs font-semibold text-cream-900">Autonomous Travel Expense Auditor</h2>
            </div>
            <span className="text-[10px] font-mono text-cream-600">Policy: $75 Meal Cap &bull; Alcohol Prohibited</span>
          </div>

          <form onSubmit={handleAuditExpense} className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-cream-900 mb-1">Employee</label>
                <select
                  value={empCode}
                  onChange={(e) => setEmpCode(e.target.value)}
                  className="w-full rounded-lg border border-cream-300 bg-cream-50 px-2.5 py-1.5 text-xs text-cream-900 font-mono"
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
                  className="w-full rounded-lg border border-cream-300 bg-cream-50 px-2.5 py-1.5 text-xs text-cream-900 font-mono"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3 items-end">
              <div>
                <label className="block text-xs font-medium text-cream-900 mb-1">Category</label>
                <select
                  value={expenseCategory}
                  onChange={(e) => setExpenseCategory(e.target.value)}
                  className="w-full rounded-lg border border-cream-300 bg-cream-50 px-2.5 py-1.5 text-xs text-cream-900 font-mono"
                >
                  <option value="MEALS">MEALS (Cap $75)</option>
                  <option value="LODGING">LODGING (Cap $500)</option>
                  <option value="TRANSPORT">TRANSPORT</option>
                  <option value="SUPPLIES">SUPPLIES</option>
                </select>
              </div>

              <div className="flex items-center justify-between pb-1">
                <label className="flex items-center gap-1.5 text-xs text-cream-800 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={hasAlcohol}
                    onChange={(e) => setHasAlcohol(e.target.checked)}
                    className="rounded border-cream-300 text-cream-900"
                  />
                  <span>Contains Alcohol</span>
                </label>
                <button
                  type="submit"
                  disabled={auditing}
                  className="rounded-lg border border-cream-400 bg-cream-900 px-3 py-1.5 text-xs font-medium text-cream-50 hover:bg-cream-800 transition-colors disabled:opacity-50"
                >
                  {auditing ? "Auditing..." : "Audit Claim"}
                </button>
              </div>
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
                  General Ledger Auto-Reimbursement: TXN-{auditResult.ledger_commit.transaction_id?.slice(0, 8)}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Panel B: Statutory Shift Trade & Labor Law Defense Simulator */}
        <div className="rounded-xl border border-cream-300 bg-cream-100 p-5 shadow-xs space-y-4">
          <div className="flex items-center justify-between border-b border-cream-300 pb-3">
            <div className="flex items-center gap-2">
              <ArrowRightLeft className="h-4 w-4 text-cream-800" />
              <h2 className="text-xs font-semibold text-cream-900">Statutory Shift Trade & Labor Invariant Simulator</h2>
            </div>
            <span className="text-[10px] font-mono text-cream-600">Rest &ge; 11h &bull; Max &le; 48h/wk</span>
          </div>

          {/* Quick presets */}
          <div className="flex items-center gap-1.5 text-[11px] overflow-x-auto pb-1">
            <span className="text-cream-600 font-mono text-[10px]">Test Presets:</span>
            <button
              type="button"
              onClick={() => applyPreset("REST_VIOLATION")}
              className="rounded-md border border-cream-300 bg-cream-50 px-2 py-0.5 text-terracotta-700 hover:bg-cream-200"
            >
              11h Rest Violation
            </button>
            <button
              type="button"
              onClick={() => applyPreset("OVERTIME_VIOLATION")}
              className="rounded-md border border-cream-300 bg-cream-50 px-2 py-0.5 text-terracotta-700 hover:bg-cream-200"
            >
              48h Overtime Violation
            </button>
            <button
              type="button"
              onClick={() => applyPreset("COMPLIANT")}
              className="rounded-md border border-cream-300 bg-cream-50 px-2 py-0.5 text-sage-700 hover:bg-cream-200"
            >
              Compliant Trade
            </button>
          </div>

          <form onSubmit={handleEvaluateTrade} className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-cream-900 mb-1">Requesting Operator</label>
                <select
                  value={reqEmpCode}
                  onChange={(e) => setReqEmpCode(e.target.value)}
                  className="w-full rounded-lg border border-cream-300 bg-cream-50 px-2.5 py-1.5 text-xs text-cream-900 font-mono"
                >
                  {employees.map((e) => (
                    <option key={e.employee_id} value={e.employee_code}>
                      {e.employee_code} ({e.first_name})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-cream-900 mb-1">Target Peer Operator</label>
                <select
                  value={targetEmpCode}
                  onChange={(e) => setTargetEmpCode(e.target.value)}
                  className="w-full rounded-lg border border-cream-300 bg-cream-50 px-2.5 py-1.5 text-xs text-cream-900 font-mono"
                >
                  {employees.map((e) => (
                    <option key={e.employee_id} value={e.employee_code}>
                      {e.employee_code} ({e.first_name})
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-2">
              <div>
                <label className="block text-[11px] font-medium text-cream-900 mb-1">Prior Shift End</label>
                <input
                  type="datetime-local"
                  value={priorEnd}
                  onChange={(e) => setPriorEnd(e.target.value)}
                  className="w-full rounded-lg border border-cream-300 bg-cream-50 px-2 py-1 text-[11px] text-cream-900 font-mono"
                />
              </div>

              <div>
                <label className="block text-[11px] font-medium text-cream-900 mb-1">Proposed Start</label>
                <input
                  type="datetime-local"
                  value={proposedStart}
                  onChange={(e) => setProposedStart(e.target.value)}
                  className="w-full rounded-lg border border-cream-300 bg-cream-50 px-2 py-1 text-[11px] text-cream-900 font-mono"
                />
              </div>

              <div>
                <label className="block text-[11px] font-medium text-cream-900 mb-1">Prior Wk Hours</label>
                <input
                  type="number"
                  step="0.5"
                  value={currentWeeklyHours}
                  onChange={(e) => setCurrentWeeklyHours(e.target.value)}
                  className="w-full rounded-lg border border-cream-300 bg-cream-50 px-2 py-1 text-[11px] text-cream-900 font-mono"
                />
              </div>
            </div>

            <div className="flex justify-end pt-1">
              <button
                type="submit"
                disabled={evaluatingTrade}
                className="rounded-lg border border-cream-400 bg-cream-900 px-3 py-1.5 text-xs font-medium text-cream-50 hover:bg-cream-800 transition-colors disabled:opacity-50"
              >
                {evaluatingTrade ? "Evaluating..." : "Evaluate Shift Trade"}
              </button>
            </div>
          </form>

          {tradeResult && (
            <div
              className={`p-3 rounded-lg border text-xs font-mono space-y-1 ${
                tradeResult.is_approved
                  ? "border-sage-500/30 bg-sage-50 text-sage-900"
                  : "border-terracotta-500/30 bg-terracotta-50 text-terracotta-900"
              }`}
            >
              <div className="font-semibold flex items-center gap-1.5">
                {tradeResult.is_approved ? (
                  <CheckCircle2 className="h-4 w-4 text-sage-600" />
                ) : (
                  <ShieldAlert className="h-4 w-4 text-terracotta-600" />
                )}
                <span>
                  {tradeResult.is_approved
                    ? "Shift Trade Approved & Committed to Schedule"
                    : "Shift Trade Blocked by Statutory Invariant Guard"}
                </span>
              </div>
              <div className="text-[11px]">
                {tradeResult.evaluation_summary}
              </div>
              <div className="text-[10px] text-cream-600 flex gap-4 pt-1">
                <span>Rest Interval: {tradeResult.rest_interval_hours ?? "N/A"}h (Req &ge; 11h)</span>
                <span>Weekly Total: {tradeResult.projected_weekly_hours ?? "N/A"}h (Max &le; 48h)</span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 3. Middle Grid: Workforce Roster & Operator Safety Certifications */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Table 1: Workforce Roster */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-cream-900 flex items-center gap-2">
              <Users className="h-4 w-4 text-cream-700" />
              <span>Plant Workforce Roster</span>
            </h2>
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
                {employees.length === 0 && (
                  <tr>
                    <td colSpan={4} className="py-6 text-center text-xs text-cream-500">
                      No employees registered yet. Click &quot;+ Add Employee&quot; above.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Table 2: Operator Safety Certifications */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-cream-900 flex items-center gap-2">
              <Award className="h-4 w-4 text-cream-700" />
              <span>Operator Safety Certifications (PostgreSQL)</span>
            </h2>
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
                {certifications.length === 0 && (
                  <tr>
                    <td colSpan={4} className="py-6 text-center text-xs text-cream-500">
                      Zero certifications recorded. Certifications are loaded per active machine role.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* 4. Bottom Section: Scheduled Factory Shifts (PostgreSQL) */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Calendar className="h-4 w-4 text-cream-800" />
            <h2 className="text-sm font-semibold text-cream-900">Scheduled Factory Shifts (PostgreSQL)</h2>
          </div>
          <span className="text-xs text-cream-600 font-mono">{shifts.length} shifts scheduled</span>
        </div>

        <div className="rounded-xl border border-cream-300 bg-cream-100 overflow-hidden shadow-xs">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-cream-300 bg-cream-200/60 text-cream-800 font-medium text-[11px]">
                <th className="py-2.5 px-4">Shift Code</th>
                <th className="py-2.5 px-4">Assigned Operator</th>
                <th className="py-2.5 px-4">Date</th>
                <th className="py-2.5 px-4">Start Time</th>
                <th className="py-2.5 px-4">End Time</th>
                <th className="py-2.5 px-4">Status</th>
                <th className="py-2.5 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-cream-200">
              {shifts.map((s) => (
                <tr key={s.shift_id} className="hover:bg-cream-50/50 transition-colors">
                  <td className="py-3 px-4 font-mono font-semibold text-cream-900">{s.shift_code}</td>
                  <td className="py-3 px-4 text-cream-800">
                    <span className="font-medium">{s.employee_name || s.employee_code}</span>
                    <span className="text-[10px] font-mono text-cream-500 ml-1.5">({s.employee_code})</span>
                  </td>
                  <td className="py-3 px-4 font-mono text-cream-700">{s.shift_date}</td>
                  <td className="py-3 px-4 font-mono text-[11px] text-cream-600">
                    {s.start_time?.slice(11, 16) || s.start_time}
                  </td>
                  <td className="py-3 px-4 font-mono text-[11px] text-cream-600">
                    {s.end_time?.slice(11, 16) || s.end_time}
                  </td>
                  <td className="py-3 px-4">
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-mono font-semibold border ${
                        s.status === "TRANSFERRED"
                          ? "bg-sage-100 text-sage-800 border-sage-500/30"
                          : "bg-cream-200 text-cream-800 border-cream-400"
                      }`}
                    >
                      {s.status}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-right">
                    <button
                      onClick={() => {
                        setTradeShiftCode(s.shift_code);
                        setReqEmpCode(s.employee_code);
                        if (s.start_time) {
                          setProposedStart(s.start_time.slice(0, 16));
                        }
                      }}
                      className="text-xs font-medium text-cream-700 hover:text-cream-900 underline"
                    >
                      Simulate Swap
                    </button>
                  </td>
                </tr>
              ))}
              {shifts.length === 0 && (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-xs text-cream-500">
                    Zero scheduled shifts in database. Click &quot;Schedule Shift&quot; in the header above to create your first plant shift.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Modal 1: Add Employee */}
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

      {/* Modal 2: Schedule Shift */}
      {showShiftModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="w-full max-w-md rounded-xl border border-cream-300 bg-cream-100 p-6 shadow-lg space-y-4">
            <div className="flex items-center justify-between border-b border-cream-300 pb-3">
              <h3 className="font-semibold text-sm text-cream-900">Schedule Plant Shift (PostgreSQL)</h3>
              <button onClick={() => setShowShiftModal(false)} className="text-cream-600 hover:text-cream-900 text-xs">
                Cancel
              </button>
            </div>

            <form onSubmit={handleCreateShift} className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-cream-900 mb-1">Shift Code</label>
                <input
                  type="text"
                  required
                  value={newShiftCode}
                  onChange={(e) => setNewShiftCode(e.target.value)}
                  placeholder="e.g. SHIFT-CNC-M1"
                  className="w-full rounded-lg border border-cream-300 bg-cream-50 px-3 py-1.5 text-xs text-cream-900 font-mono"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-cream-900 mb-1">Assigned Operator</label>
                <select
                  value={shiftEmpCode}
                  onChange={(e) => setShiftEmpCode(e.target.value)}
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
                <label className="block text-xs font-medium text-cream-900 mb-1">Shift Date</label>
                <input
                  type="date"
                  required
                  value={shiftDate}
                  onChange={(e) => setShiftDate(e.target.value)}
                  className="w-full rounded-lg border border-cream-300 bg-cream-50 px-3 py-1.5 text-xs text-cream-900 font-mono"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-cream-900 mb-1">Start Time</label>
                  <input
                    type="time"
                    required
                    value={shiftStartTime}
                    onChange={(e) => setShiftStartTime(e.target.value)}
                    className="w-full rounded-lg border border-cream-300 bg-cream-50 px-3 py-1.5 text-xs text-cream-900 font-mono"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-cream-900 mb-1">End Time</label>
                  <input
                    type="time"
                    required
                    value={shiftEndTime}
                    onChange={(e) => setShiftEndTime(e.target.value)}
                    className="w-full rounded-lg border border-cream-300 bg-cream-50 px-3 py-1.5 text-xs text-cream-900 font-mono"
                  />
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-cream-300">
                <button
                  type="button"
                  onClick={() => setShowShiftModal(false)}
                  className="rounded-lg border border-cream-300 bg-cream-200 px-3 py-1.5 text-xs font-medium text-cream-800"
                >
                  Close
                </button>
                <button
                  type="submit"
                  disabled={creatingShift}
                  className="rounded-lg border border-cream-400 bg-cream-900 px-3 py-1.5 text-xs font-medium text-cream-50 hover:bg-cream-800 disabled:opacity-50"
                >
                  {creatingShift ? "Scheduling..." : "Confirm Schedule"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
