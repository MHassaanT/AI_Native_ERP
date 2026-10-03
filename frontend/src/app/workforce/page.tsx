"use client";

import { useEffect, useState } from "react";
import {
  Users,
  Building,
  Briefcase,
  UserCheck,
  UserX,
  Clock,
  Calendar,
  CalendarCheck,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Plus,
  RefreshCw,
  DollarSign,
  FileText,
  CreditCard,
  ShieldCheck,
  Layers,
  ChevronRight,
  TrendingUp,
  Receipt,
  ArrowRight,
  Send,
  CheckSquare,
  ListTodo,
  UserPlus,
  FolderPlus,
  Check,
} from "lucide-react";
import { api } from "@/lib/api";

type TabType = "employees" | "attendance" | "leaves" | "structures" | "payroll" | "expenses";
type EmpSubTabType = "directory" | "org" | "checklists";

export default function WorkforcePage() {
  const [activeTab, setActiveTab] = useState<TabType>("employees");
  const [empSubTab, setEmpSubTab] = useState<EmpSubTabType>("directory");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Data states
  const [employees, setEmployees] = useState<any[]>([]);
  const [departments, setDepartments] = useState<any[]>([]);
  const [designations, setDesignations] = useState<any[]>([]);
  const [shiftTypes, setShiftTypes] = useState<any[]>([]);
  const [attendances, setAttendances] = useState<any[]>([]);
  const [leaveTypes, setLeaveTypes] = useState<any[]>([]);
  const [leaveApps, setLeaveApps] = useState<any[]>([]);
  const [components, setComponents] = useState<any[]>([]);
  const [structures, setStructures] = useState<any[]>([]);
  const [salarySlips, setSalarySlips] = useState<any[]>([]);
  const [batchPayrolls, setBatchPayrolls] = useState<any[]>([]);
  const [advances, setAdvances] = useState<any[]>([]);
  const [expenses, setExpenses] = useState<any[]>([]);
  const [onboardings, setOnboardings] = useState<any[]>([]);
  const [separations, setSeparations] = useState<any[]>([]);

  // Modals & Action States
  const [showEmpModal, setShowEmpModal] = useState(false);
  const [newEmpCode, setNewEmpCode] = useState("");
  const [newEmpFirstName, setNewEmpFirstName] = useState("");
  const [newEmpLastName, setNewEmpLastName] = useState("");
  const [newEmpEmail, setNewEmpEmail] = useState("");
  const [newEmpDeptId, setNewEmpDeptId] = useState("");
  const [newEmpDesigId, setNewEmpDesigId] = useState("");
  const [newEmpGender, setNewEmpGender] = useState("MALE");
  const [newEmpDoj, setNewEmpDoj] = useState(new Date().toISOString().split("T")[0]);

  // Department Modal State
  const [showDeptModal, setShowDeptModal] = useState(false);
  const [newDeptName, setNewDeptName] = useState("");

  // Designation Modal State
  const [showDesigModal, setShowDesigModal] = useState(false);
  const [newDesigName, setNewDesigName] = useState("");
  const [newDesigDesc, setNewDesigDesc] = useState("");

  // Leave Type Modal State
  const [showLeaveTypeModal, setShowLeaveTypeModal] = useState(false);
  const [newLeaveTypeName, setNewLeaveTypeName] = useState("");
  const [newLeaveTypeMaxDays, setNewLeaveTypeMaxDays] = useState("14");
  const [newLeaveTypeCarryForward, setNewLeaveTypeCarryForward] = useState(false);
  const [newLeaveTypeIsLwp, setNewLeaveTypeIsLwp] = useState(false);
  const [leaveModalError, setLeaveModalError] = useState<string | null>(null);
  const [empModalError, setEmpModalError] = useState<string | null>(null);

  // Onboarding Modal & Action State
  const [showOnboardingModal, setShowOnboardingModal] = useState(false);
  const [onbEmpId, setOnbEmpId] = useState("");
  const [onbApplicantName, setOnbApplicantName] = useState("");
  const [onbJoiningDate, setOnbJoiningDate] = useState(new Date().toISOString().split("T")[0]);
  const [onbTaskInput, setOnbTaskInput] = useState(
    "Collect Identity & Tax Verification Documents\nProvision Corporate Email and Workspace Accounts\nHardware & Laptop Handover\nHealth & Safety Compliance Orientation"
  );

  // Separation Modal & Action State
  const [showSeparationModal, setShowSeparationModal] = useState(false);
  const [sepEmpId, setSepEmpId] = useState("");
  const [sepResignDate, setSepResignDate] = useState(new Date().toISOString().split("T")[0]);
  const [sepNotes, setSepNotes] = useState("Voluntary resignation");
  const [sepTaskInput, setSepTaskInput] = useState(
    "Revoke System Access & Accounts\nRecover Hardware & Access Badges\nConduct Exit Interview\nIssue Experience & Relieving Certificate"
  );

  // Attendance Punch State
  const [punchEmpId, setPunchEmpId] = useState("");
  const [punchDate, setPunchDate] = useState(new Date().toISOString().split("T")[0]);
  const [punchInTime, setPunchInTime] = useState("09:00");
  const [punchOutTime, setPunchOutTime] = useState("17:00");
  const [punchStatus, setPunchStatus] = useState("PRESENT");

  // Leave Form State
  const [leaveEmpId, setLeaveEmpId] = useState("");
  const [leaveTypeId, setLeaveTypeId] = useState("");
  const [leaveFromDate, setLeaveFromDate] = useState(new Date().toISOString().split("T")[0]);
  const [leaveToDate, setLeaveToDate] = useState(new Date().toISOString().split("T")[0]);
  const [leaveDays, setLeaveDays] = useState("1.0");
  const [leaveReason, setLeaveReason] = useState("Personal leave");

  // Salary Component & Structure State
  const [compName, setCompName] = useState("");
  const [compCode, setCompCode] = useState("");
  const [compType, setCompType] = useState<"EARNING" | "DEDUCTION">("EARNING");
  const [compCalcType, setCompCalcType] = useState<"FIXED" | "FORMULA">("FIXED");
  const [compFormula, setCompFormula] = useState("");

  // Salary Structure Package Builder State
  const [newStructName, setNewStructName] = useState("");
  const [newStructFreq, setNewStructFreq] = useState("MONTHLY");
  const [newStructCurrency, setNewStructCurrency] = useState("USD");
  const [structItemsMap, setStructItemsMap] = useState<
    Record<string, { selected: boolean; amount: string; formula: string }>
  >({});

  // Salary Assignment State
  const [assignEmpId, setAssignEmpId] = useState("");
  const [assignStructId, setAssignStructId] = useState("");
  const [assignBaseSalary, setAssignBaseSalary] = useState("5000");

  // Batch Payroll State
  const [batchPostingDate, setBatchPostingDate] = useState(new Date().toISOString().split("T")[0]);
  const [batchStartDate, setBatchStartDate] = useState("2026-09-01");
  const [batchEndDate, setBatchEndDate] = useState("2026-09-30");

  // Advance State
  const [advEmpId, setAdvEmpId] = useState("");
  const [advAmount, setAdvAmount] = useState("1000");
  const [advPurpose, setAdvPurpose] = useState("Medical & Relocation Assistance");
  const [advMonthlyEmi, setAdvMonthlyEmi] = useState("200");

  const loadAll = async () => {
    setLoading(true);
    setError(null);
    try {
      const [
        emps,
        depts,
        desigs,
        shifts,
        atts,
        lTypes,
        lApps,
        comps,
        structs,
        slips,
        batches,
        advs,
        exps,
        onbs,
        seps,
      ] = await Promise.all([
        api.getEmployeesHR().catch(() => []),
        api.getDepartments().catch(() => []),
        api.getDesignations().catch(() => []),
        api.getShiftTypes().catch(() => []),
        api.getAttendances().catch(() => []),
        api.getLeaveTypes().catch(() => []),
        api.getLeaveApplications().catch(() => []),
        api.getSalaryComponents().catch(() => []),
        api.getSalaryStructures().catch(() => []),
        api.getSalarySlips().catch(() => []),
        api.getBatchPayrolls().catch(() => []),
        api.getAdvances().catch(() => []),
        api.getExpenses().catch(() => []),
        api.getOnboardings().catch(() => []),
        api.getSeparations().catch(() => []),
      ]);

      setEmployees(emps || []);
      setDepartments(depts || []);
      setDesignations(desigs || []);
      setShiftTypes(shifts || []);
      setAttendances(atts || []);
      setLeaveTypes(lTypes || []);
      setLeaveApps(lApps || []);
      setComponents(comps || []);
      setStructures(structs || []);
      setSalarySlips(slips || []);
      setBatchPayrolls(batches || []);
      setAdvances(advs || []);
      setExpenses(exps || []);
      setOnboardings(onbs || []);
      setSeparations(seps || []);

      if (emps && emps.length > 0) {
        if (!punchEmpId) setPunchEmpId(emps[0].employee_id);
        if (!leaveEmpId) setLeaveEmpId(emps[0].employee_id);
        if (!assignEmpId) setAssignEmpId(emps[0].employee_id);
        if (!advEmpId) setAdvEmpId(emps[0].employee_id);
        if (!onbEmpId) setOnbEmpId(emps[0].employee_id);
        if (!sepEmpId) setSepEmpId(emps[0].employee_id);
      }
      if (lTypes && lTypes.length > 0) {
        if (!leaveTypeId || !lTypes.some((t: any) => t.leave_type_id === leaveTypeId)) {
          setLeaveTypeId(lTypes[0].leave_type_id);
        }
      }
      if (structs && structs.length > 0 && !assignStructId) {
        setAssignStructId(structs[0].structure_id);
      }
    } catch (err: any) {
      setError(err.message || "Failed to load workforce & payroll data.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAll();
  }, []);

  const openAddEmployeeModal = () => {
    setEmpModalError(null);
    const existingNums = employees
      .map((e) => {
        const match = (e.employee_code || "").match(/(\d+)$/);
        return match ? parseInt(match[1], 10) : 0;
      })
      .filter((n) => n > 0);
    const nextNum = existingNums.length > 0 ? Math.max(...existingNums) + 1 : employees.length + 1;
    const suggestedCode = `EMP-${String(nextNum).padStart(3, "0")}`;
    setNewEmpCode(suggestedCode);
    setShowEmpModal(true);
  };

  const handleCreateLeaveType = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLeaveModalError(null);
    setSuccess(null);
    try {
      await api.createLeaveType({
        type_name: newLeaveTypeName.trim(),
        max_days_allowed: parseInt(newLeaveTypeMaxDays, 10) || 0,
        is_carry_forward: newLeaveTypeCarryForward,
        is_lwp: newLeaveTypeIsLwp,
      });

      setSuccess(`Leave Type "${newLeaveTypeName.trim()}" created successfully!`);
      setShowLeaveTypeModal(false);
      setNewLeaveTypeName("");
      setNewLeaveTypeMaxDays("14");
      setNewLeaveTypeCarryForward(false);
      setNewLeaveTypeIsLwp(false);
      await loadAll();
    } catch (err: any) {
      const msg = err.message || "Failed to create leave type.";
      setError(msg);
      setLeaveModalError(msg);
    }
  };

  const handleCreateEmployee = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setEmpModalError(null);
    setSuccess(null);
    try {
      const selectedDept = departments.find((d) => d.department_id === newEmpDeptId);
      const selectedDesig = designations.find((d) => d.designation_id === newEmpDesigId);

      await api.createEmployeeFull({
        employee_code: newEmpCode.trim(),
        first_name: newEmpFirstName.trim(),
        last_name: newEmpLastName.trim(),
        email: newEmpEmail.trim(),
        department_name: selectedDept?.department_name || "General",
        department_id: newEmpDeptId || undefined,
        designation_name: selectedDesig?.designation_name || "Staff",
        designation_id: newEmpDesigId || undefined,
        gender: newEmpGender,
        date_of_joining: newEmpDoj,
        employment_type: "FULL_TIME",
      });

      setSuccess(`Employee ${newEmpCode} created successfully!`);
      setShowEmpModal(false);
      setNewEmpCode("");
      setNewEmpFirstName("");
      setNewEmpLastName("");
      setNewEmpEmail("");
      loadAll();
    } catch (err: any) {
      const msg = err.message || "Failed to create employee.";
      setError(msg);
      setEmpModalError(msg);
    }
  };

  const handlePunchAttendance = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    try {
      const inDateTime = punchStatus === "PRESENT" || punchStatus === "HALF_DAY" 
        ? `${punchDate}T${punchInTime}:00Z` 
        : undefined;
      const outDateTime = punchStatus === "PRESENT" || punchStatus === "HALF_DAY" 
        ? `${punchDate}T${punchOutTime}:00Z` 
        : undefined;

      await api.markAttendance({
        employee_id: punchEmpId,
        attendance_date: punchDate,
        status: punchStatus,
        in_time: inDateTime,
        out_time: outDateTime,
        remarks: "Web Punch Logger",
      });

      setSuccess(`Attendance recorded for ${punchDate} (${punchStatus}).`);
      loadAll();
    } catch (err: any) {
      setError(err.message || "Failed to record attendance.");
    }
  };

  const handleSubmitLeave = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    try {
      await api.submitLeaveApplication({
        employee_id: leaveEmpId,
        leave_type_id: leaveTypeId,
        from_date: leaveFromDate,
        to_date: leaveToDate,
        total_leave_days: parseFloat(leaveDays),
        is_half_day: false,
        reason: leaveReason,
      });

      setSuccess("Leave application submitted for approval!");
      loadAll();
    } catch (err: any) {
      setError(err.message || "Failed to submit leave application.");
    }
  };

  const handleApproveLeave = async (appId: string) => {
    setError(null);
    setSuccess(null);
    try {
      await api.approveLeaveApplication(appId);
      setSuccess("Leave request approved!");
      loadAll();
    } catch (err: any) {
      setError(err.message || "Failed to approve leave.");
    }
  };

  const handleRejectLeave = async (appId: string) => {
    setError(null);
    setSuccess(null);
    try {
      await api.rejectLeaveApplication(appId, "Operational requirements");
      setSuccess("Leave request rejected.");
      loadAll();
    } catch (err: any) {
      setError(err.message || "Failed to reject leave.");
    }
  };

  const handleCreateComponent = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    try {
      await api.createSalaryComponent({
        component_name: compName,
        component_code: compCode,
        component_type: compType,
        calculation_type: compCalcType,
        formula_expression: compCalcType === "FORMULA" ? compFormula : undefined,
        account_code: compType === "EARNING" ? "6100-SALARY-EXPENSE" : "2130-BENEFITS-PAYABLE",
      });

      setSuccess(`Salary component ${compCode} created!`);
      setCompName("");
      setCompCode("");
      setCompFormula("");
      loadAll();
    } catch (err: any) {
      setError(err.message || "Failed to create component.");
    }
  };

  const handleCreateDepartment = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    try {
      const res = await api.createDepartment({
        department_name: newDeptName.trim(),
      });
      setSuccess(`Department "${newDeptName}" created successfully!`);
      setNewDeptName("");
      setShowDeptModal(false);
      await loadAll();
      if (res?.department_id) {
        setNewEmpDeptId(res.department_id);
      }
    } catch (err: any) {
      setError(err.message || "Failed to create department.");
    }
  };

  const handleCreateDesignation = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    try {
      const res = await api.createDesignation({
        designation_name: newDesigName.trim(),
        description: newDesigDesc.trim() || undefined,
      });
      setSuccess(`Designation "${newDesigName}" created successfully!`);
      setNewDesigName("");
      setNewDesigDesc("");
      setShowDesigModal(false);
      await loadAll();
      if (res?.designation_id) {
        setNewEmpDesigId(res.designation_id);
      }
    } catch (err: any) {
      setError(err.message || "Failed to create designation.");
    }
  };

  const handleCreateSalaryStructure = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    try {
      const selectedItems = Object.entries(structItemsMap)
        .filter(([_, val]) => val.selected)
        .map(([compId, val]) => ({
          component_id: compId,
          amount: parseFloat(val.amount || "0"),
          formula_expression: val.formula || undefined,
        }));

      if (selectedItems.length === 0) {
        setError("Please select at least one salary component to include in the package structure.");
        return;
      }

      const hasEarning = selectedItems.some((item) => {
        const comp = components.find((c) => c.component_id === item.component_id);
        return comp?.component_type === "EARNING";
      });
      if (!hasEarning) {
        setError("A salary package must include at least one EARNING component (e.g. Basic Salary) so that Gross Pay is positive.");
        return;
      }

      const res = await api.createSalaryStructure({
        structure_name: newStructName.trim(),
        payroll_frequency: newStructFreq,
        currency: newStructCurrency,
        items: selectedItems,
      });

      setSuccess(`Salary Structure Package "${newStructName}" created with ${selectedItems.length} components!`);
      setNewStructName("");
      setStructItemsMap({});
      await loadAll();
      if (res?.structure_id) {
        setAssignStructId(res.structure_id);
      }
    } catch (err: any) {
      setError(err.message || "Failed to create salary structure package.");
    }
  };

  const handleStartOnboarding = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    try {
      const taskList = onbTaskInput
        .split("\n")
        .map((t) => t.trim())
        .filter((t) => t.length > 0);

      await api.startOnboarding({
        employee_id: onbEmpId,
        job_applicant_name: onbApplicantName.trim() || undefined,
        date_of_joining: onbJoiningDate,
        task_names: taskList.length > 0 ? taskList : undefined,
      });

      setSuccess("Employee onboarding workflow started with checklist!");
      setShowOnboardingModal(false);
      setOnbApplicantName("");
      loadAll();
    } catch (err: any) {
      setError(err.message || "Failed to initiate onboarding.");
    }
  };

  const handleCompleteOnboardingTask = async (onboardingId: string, taskId: string) => {
    setError(null);
    setSuccess(null);
    try {
      await api.completeOnboardingTask(onboardingId, taskId);
      setSuccess("Onboarding task completed!");
      loadAll();
    } catch (err: any) {
      setError(err.message || "Failed to complete onboarding task.");
    }
  };

  const handleStartSeparation = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    try {
      const taskList = sepTaskInput
        .split("\n")
        .map((t) => t.trim())
        .filter((t) => t.length > 0);

      await api.startSeparation({
        employee_id: sepEmpId,
        resignation_date: sepResignDate,
        exit_interview_notes: sepNotes.trim() || undefined,
        task_names: taskList.length > 0 ? taskList : undefined,
      });

      setSuccess("Employee separation exit workflow initialized!");
      setShowSeparationModal(false);
      loadAll();
    } catch (err: any) {
      setError(err.message || "Failed to start separation workflow.");
    }
  };

  const handleCompleteSeparationTask = async (separationId: string, taskId: string) => {
    setError(null);
    setSuccess(null);
    try {
      await api.completeSeparationTask(separationId, taskId);
      setSuccess("Separation clearance task completed!");
      loadAll();
    } catch (err: any) {
      setError(err.message || "Failed to complete separation task.");
    }
  };

  const handleAssignStructure = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    try {
      await api.assignSalaryStructure({
        employee_id: assignEmpId,
        structure_id: assignStructId,
        from_date: new Date().toISOString().split("T")[0],
        base_salary: parseFloat(assignBaseSalary),
      });

      setSuccess("Salary structure assigned to employee successfully!");
      loadAll();
    } catch (err: any) {
      setError(err.message || "Failed to assign salary structure.");
    }
  };

  const handleRunBatchPayroll = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    try {
      const res = await api.generateBatchPayroll({
        posting_date: batchPostingDate,
        start_date: batchStartDate,
        end_date: batchEndDate,
      });

      setSuccess(`Batch payroll generated! Created ${res.salary_slips_count} salary slips ($${res.total_net_pay} Net Pay).`);
      loadAll();
    } catch (err: any) {
      setError(err.message || "Failed to generate batch payroll.");
    }
  };

  const handleSubmitSlip = async (slipId: string) => {
    setError(null);
    setSuccess(null);
    try {
      await api.submitSalarySlip(slipId);
      setSuccess("Salary Slip submitted and General Ledger double-entry journals posted!");
      loadAll();
    } catch (err: any) {
      setError(err.message || "Failed to submit salary slip.");
    }
  };

  const handleSubmitBatch = async (batchId: string) => {
    setError(null);
    setSuccess(null);
    try {
      await api.submitBatchPayroll(batchId);
      setSuccess("Batch payroll submitted! Mass General Ledger journals posted.");
      loadAll();
    } catch (err: any) {
      setError(err.message || "Failed to submit batch payroll.");
    }
  };

  const handleCreateAdvance = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    try {
      await api.createAdvance({
        employee_id: advEmpId,
        advance_amount: parseFloat(advAmount),
        purpose: advPurpose,
        monthly_deduction_amount: parseFloat(advMonthlyEmi),
        posting_date: new Date().toISOString().split("T")[0],
      });

      setSuccess("Employee advance created and queued for disbursement!");
      loadAll();
    } catch (err: any) {
      setError(err.message || "Failed to create advance.");
    }
  };

  const handleDisburseAdvance = async (advanceId: string) => {
    setError(null);
    setSuccess(null);
    try {
      await api.disburseAdvance(advanceId);
      setSuccess("Advance disbursed! Bank payout and clearing GL entries posted.");
      loadAll();
    } catch (err: any) {
      setError(err.message || "Failed to disburse advance.");
    }
  };

  const handleReimburseExpense = async (claimId: string) => {
    setError(null);
    setSuccess(null);
    try {
      await api.reimburseExpense(claimId);
      setSuccess("Expense claim reimbursed! GL entries committed.");
      loadAll();
    } catch (err: any) {
      setError(err.message || "Failed to reimburse expense claim.");
    }
  };

  return (
    <div className="min-h-screen bg-[#faf9f6] text-stone-900 pb-16">
      {/* Header */}
      <header className="border-b border-stone-200 bg-white/80 backdrop-blur sticky top-0 z-30 px-6 py-4">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="px-2 py-0.5 text-xs font-semibold bg-amber-100 text-amber-900 rounded">
                Phase 4 Parity
              </span>
              <h1 className="text-xl font-bold tracking-tight text-stone-900">
                Human Resources & Payroll Suite
              </h1>
            </div>
            <p className="text-xs text-stone-500 mt-1">
              ERPNext Parity: Personnel Lifecycle, Attendance & Shifts, Leaves, Compensation & Batch Payroll
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={loadAll}
              disabled={loading}
              className="inline-flex items-center gap-2 px-3 py-1.5 text-xs font-medium bg-stone-100 hover:bg-stone-200 text-stone-700 rounded-lg transition"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
              Refresh
            </button>
            <button
              onClick={openAddEmployeeModal}
              className="inline-flex items-center gap-2 px-3.5 py-1.5 text-xs font-medium bg-stone-900 hover:bg-stone-800 text-white rounded-lg shadow-sm transition"
            >
              <Plus className="w-3.5 h-3.5" />
              New Employee
            </button>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="max-w-7xl mx-auto mt-4 flex overflow-x-auto gap-2 border-b border-stone-100 pb-1 scrollbar-none">
          {[
            { id: "employees", label: "Employees & Org", icon: Users },
            { id: "attendance", label: "Attendance & Shifts", icon: Clock },
            { id: "leaves", label: "Leave Management", icon: CalendarCheck },
            { id: "structures", label: "Salary Structures", icon: Layers },
            { id: "payroll", label: "Payroll & Slips", icon: DollarSign },
            { id: "expenses", label: "Expenses & Advances", icon: Receipt },
          ].map((tab) => {
            const Icon = tab.icon;
            const active = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as TabType)}
                className={`inline-flex items-center gap-2 px-3.5 py-2 text-xs font-medium whitespace-nowrap rounded-t-lg transition border-b-2 ${
                  active
                    ? "border-stone-900 text-stone-900 bg-stone-50/50"
                    : "border-transparent text-stone-500 hover:text-stone-800 hover:bg-stone-50"
                }`}
              >
                <Icon className={`w-4 h-4 ${active ? "text-stone-900" : "text-stone-400"}`} />
                {tab.label}
              </button>
            );
          })}
        </div>
      </header>

      {/* Main Container */}
      <main className="max-w-7xl mx-auto px-6 py-6 space-y-6">
        {/* Alerts */}
        {error && (
          <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center justify-between">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              <span>{error}</span>
            </div>
            <button onClick={() => setError(null)} className="text-rose-500 hover:text-rose-700">
              ✕
            </button>
          </div>
        )}
        {success && (
          <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-center justify-between">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
              <span>{success}</span>
            </div>
            <button onClick={() => setSuccess(null)} className="text-emerald-500 hover:text-emerald-700">
              ✕
            </button>
          </div>
        )}

        {/* ============================================================== */}
        {/* TAB 1: EMPLOYEES & ORG */}
        {/* ============================================================== */}
        {activeTab === "employees" && (
          <div className="space-y-6">
            {/* Sub-navigation & Action Header */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-4 rounded-xl border border-stone-200 shadow-sm">
              {/* Sub-tab pills */}
              <div className="flex items-center gap-1.5 p-1 bg-stone-100 rounded-lg">
                <button
                  onClick={() => setEmpSubTab("directory")}
                  className={`px-3 py-1.5 rounded-md text-xs font-medium transition ${
                    empSubTab === "directory"
                      ? "bg-white text-stone-900 shadow-sm font-semibold"
                      : "text-stone-600 hover:text-stone-900"
                  }`}
                >
                  <Users className="w-3.5 h-3.5 inline mr-1.5" />
                  Directory ({employees.length})
                </button>
                <button
                  onClick={() => setEmpSubTab("org")}
                  className={`px-3 py-1.5 rounded-md text-xs font-medium transition ${
                    empSubTab === "org"
                      ? "bg-white text-stone-900 shadow-sm font-semibold"
                      : "text-stone-600 hover:text-stone-900"
                  }`}
                >
                  <Building className="w-3.5 h-3.5 inline mr-1.5" />
                  Departments & Designations ({departments.length + designations.length})
                </button>
                <button
                  onClick={() => setEmpSubTab("checklists")}
                  className={`px-3 py-1.5 rounded-md text-xs font-medium transition ${
                    empSubTab === "checklists"
                      ? "bg-white text-stone-900 shadow-sm font-semibold"
                      : "text-stone-600 hover:text-stone-900"
                  }`}
                >
                  <ListTodo className="w-3.5 h-3.5 inline mr-1.5" />
                  Onboarding & Exit Checklists ({onboardings.length + separations.length})
                </button>
              </div>

              {/* Action Buttons */}
              <div className="flex flex-wrap items-center gap-2">
                <button
                  onClick={() => setShowDeptModal(true)}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-stone-100 hover:bg-stone-200 text-stone-700 rounded-lg transition"
                >
                  <Building className="w-3.5 h-3.5" />
                  + Dept
                </button>
                <button
                  onClick={() => setShowDesigModal(true)}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-stone-100 hover:bg-stone-200 text-stone-700 rounded-lg transition"
                >
                  <Briefcase className="w-3.5 h-3.5" />
                  + Designation
                </button>
                {empSubTab === "checklists" ? (
                  <>
                    <button
                      onClick={() => setShowOnboardingModal(true)}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-emerald-700 hover:bg-emerald-800 text-white rounded-lg transition shadow-sm"
                    >
                      <UserPlus className="w-3.5 h-3.5" />
                      Start Onboarding
                    </button>
                    <button
                      onClick={() => setShowSeparationModal(true)}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-stone-700 hover:bg-stone-800 text-white rounded-lg transition shadow-sm"
                    >
                      <UserX className="w-3.5 h-3.5" />
                      Start Exit
                    </button>
                  </>
                ) : (
                  <button
                    onClick={openAddEmployeeModal}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-stone-900 hover:bg-stone-800 text-white rounded-lg transition shadow-sm"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    New Employee
                  </button>
                )}
              </div>
            </div>

            {/* SUB-VIEW 1: DIRECTORY */}
            {empSubTab === "directory" && (
              <>
                {/* Metric Cards */}
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                  <div className="bg-white p-4 rounded-xl border border-stone-200 shadow-sm">
                    <span className="text-xs font-medium text-stone-500">Active Workforce</span>
                    <p className="text-2xl font-bold text-stone-900 mt-1">
                      {employees.filter((e) => e.status === "ACTIVE").length}
                    </p>
                    <p className="text-[10px] text-stone-400 mt-1">Full-time & contracted staff</p>
                  </div>
                  <div className="bg-white p-4 rounded-xl border border-stone-200 shadow-sm">
                    <span className="text-xs font-medium text-stone-500">Departments</span>
                    <p className="text-2xl font-bold text-stone-900 mt-1">{departments.length}</p>
                    <p className="text-[10px] text-stone-400 mt-1">Operational business units</p>
                  </div>
                  <div className="bg-white p-4 rounded-xl border border-stone-200 shadow-sm">
                    <span className="text-xs font-medium text-stone-500">Designations</span>
                    <p className="text-2xl font-bold text-stone-900 mt-1">{designations.length}</p>
                    <p className="text-[10px] text-stone-400 mt-1">Functional job titles</p>
                  </div>
                  <div className="bg-white p-4 rounded-xl border border-stone-200 shadow-sm">
                    <span className="text-xs font-medium text-stone-500">Separated / Left</span>
                    <p className="text-2xl font-bold text-stone-900 mt-1">
                      {employees.filter((e) => e.status === "LEFT").length}
                    </p>
                    <p className="text-[10px] text-stone-400 mt-1">Offboarded personnel</p>
                  </div>
                </div>

                {/* Employee Directory */}
                <div className="bg-white rounded-xl border border-stone-200 shadow-sm overflow-hidden">
                  <div className="p-4 border-b border-stone-200 flex items-center justify-between">
                    <div>
                      <h2 className="text-sm font-semibold text-stone-900">Personnel Directory</h2>
                      <p className="text-xs text-stone-500 mt-0.5">Master employee records with organizational alignment</p>
                    </div>
                  </div>

                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-stone-50/75 border-b border-stone-200 text-stone-500">
                        <tr>
                          <th className="px-4 py-3 font-medium">Employee</th>
                          <th className="px-4 py-3 font-medium">Code</th>
                          <th className="px-4 py-3 font-medium">Department</th>
                          <th className="px-4 py-3 font-medium">Designation</th>
                          <th className="px-4 py-3 font-medium">Date of Joining</th>
                          <th className="px-4 py-3 font-medium">Status</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-stone-100">
                        {employees.map((emp) => (
                          <tr key={emp.employee_id} className="hover:bg-stone-50/50 transition">
                            <td className="px-4 py-3">
                              <div className="font-medium text-stone-900">
                                {emp.first_name} {emp.last_name}
                              </div>
                              <div className="text-[10px] text-stone-400">{emp.email}</div>
                            </td>
                            <td className="px-4 py-3 font-mono text-stone-700">{emp.employee_code}</td>
                            <td className="px-4 py-3 text-stone-600">{emp.department || "General"}</td>
                            <td className="px-4 py-3 text-stone-600">{emp.designation || "Staff"}</td>
                            <td className="px-4 py-3 text-stone-600">{emp.date_of_joining || "—"}</td>
                            <td className="px-4 py-3">
                              <span
                                className={`px-2 py-0.5 text-[10px] font-semibold rounded ${
                                  emp.status === "ACTIVE"
                                    ? "bg-emerald-100 text-emerald-800"
                                    : emp.status === "LEFT"
                                    ? "bg-rose-100 text-rose-800"
                                    : "bg-stone-100 text-stone-700"
                                }`}
                              >
                                {emp.status}
                              </span>
                            </td>
                          </tr>
                        ))}
                        {employees.length === 0 && (
                          <tr>
                            <td colSpan={6} className="text-center py-8 text-stone-400">
                              No employees registered. Click "New Employee" to create one.
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              </>
            )}

            {/* SUB-VIEW 2: DEPARTMENTS & DESIGNATIONS */}
            {empSubTab === "org" && (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Departments Card */}
                <div className="bg-white rounded-xl border border-stone-200 shadow-sm overflow-hidden">
                  <div className="p-4 border-b border-stone-200 flex items-center justify-between">
                    <div>
                      <h3 className="text-sm font-semibold text-stone-900 flex items-center gap-2">
                        <Building className="w-4 h-4 text-stone-600" />
                        Departments ({departments.length})
                      </h3>
                      <p className="text-xs text-stone-500 mt-0.5">Corporate business units and divisions</p>
                    </div>
                    <button
                      onClick={() => setShowDeptModal(true)}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-stone-900 hover:bg-stone-800 text-white rounded-lg transition"
                    >
                      <Plus className="w-3.5 h-3.5" />
                      Add Department
                    </button>
                  </div>
                  <div className="divide-y divide-stone-100 max-h-[460px] overflow-y-auto">
                    {departments.map((dept) => {
                      const empCount = employees.filter(
                        (e) => e.department === dept.department_name || e.department_id === dept.department_id
                      ).length;
                      return (
                        <div key={dept.department_id} className="p-4 hover:bg-stone-50/50 transition flex items-center justify-between">
                          <div>
                            <p className="text-xs font-semibold text-stone-900">{dept.department_name}</p>
                            <p className="text-[11px] text-stone-400 mt-0.5">
                              ID: <span className="font-mono">{dept.department_id?.slice(0, 8)}...</span>
                            </p>
                          </div>
                          <span className="px-2.5 py-1 text-[11px] font-medium bg-stone-100 text-stone-700 rounded-full">
                            {empCount} {empCount === 1 ? "Employee" : "Employees"}
                          </span>
                        </div>
                      );
                    })}
                    {departments.length === 0 && (
                      <div className="p-8 text-center text-xs text-stone-400">
                        No departments found. Click "+ Add Department" to create one.
                      </div>
                    )}
                  </div>
                </div>

                {/* Designations Card */}
                <div className="bg-white rounded-xl border border-stone-200 shadow-sm overflow-hidden">
                  <div className="p-4 border-b border-stone-200 flex items-center justify-between">
                    <div>
                      <h3 className="text-sm font-semibold text-stone-900 flex items-center gap-2">
                        <Briefcase className="w-4 h-4 text-stone-600" />
                        Designations & Roles ({designations.length})
                      </h3>
                      <p className="text-xs text-stone-500 mt-0.5">Job titles, responsibilities, and functional roles</p>
                    </div>
                    <button
                      onClick={() => setShowDesigModal(true)}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-stone-900 hover:bg-stone-800 text-white rounded-lg transition"
                    >
                      <Plus className="w-3.5 h-3.5" />
                      Add Designation
                    </button>
                  </div>
                  <div className="divide-y divide-stone-100 max-h-[460px] overflow-y-auto">
                    {designations.map((desig) => {
                      const empCount = employees.filter(
                        (e) => e.designation === desig.designation_name || e.designation_id === desig.designation_id
                      ).length;
                      return (
                        <div key={desig.designation_id} className="p-4 hover:bg-stone-50/50 transition flex items-center justify-between">
                          <div>
                            <p className="text-xs font-semibold text-stone-900">{desig.designation_name}</p>
                            <p className="text-[11px] text-stone-500 mt-0.5">
                              {desig.description || "General Staff Position"}
                            </p>
                          </div>
                          <span className="px-2.5 py-1 text-[11px] font-medium bg-stone-100 text-stone-700 rounded-full">
                            {empCount} {empCount === 1 ? "Employee" : "Employees"}
                          </span>
                        </div>
                      );
                    })}
                    {designations.length === 0 && (
                      <div className="p-8 text-center text-xs text-stone-400">
                        No designations found. Click "+ Add Designation" to create one.
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* SUB-VIEW 3: ONBOARDING & SEPARATION CHECKLISTS */}
            {empSubTab === "checklists" && (
              <div className="space-y-6">
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  {/* Onboarding Workflows Column */}
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <h3 className="text-sm font-bold text-stone-900 flex items-center gap-2">
                          <UserPlus className="w-4 h-4 text-emerald-700" />
                          Employee Onboarding Checklists ({onboardings.length})
                        </h3>
                        <p className="text-xs text-stone-500 mt-0.5">New hire readiness with itemized check-offs</p>
                      </div>
                      <button
                        onClick={() => setShowOnboardingModal(true)}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-emerald-700 hover:bg-emerald-800 text-white rounded-lg transition shadow-sm"
                      >
                        <Plus className="w-3.5 h-3.5" />
                        Start Onboarding
                      </button>
                    </div>

                    {onboardings.map((onb) => {
                      const emp = employees.find((e) => e.employee_id === onb.employee_id);
                      const tasks = onb.tasks || [];
                      const completedCount = tasks.filter((t: any) => t.is_completed).length;
                      const progressPct = tasks.length > 0 ? Math.round((completedCount / tasks.length) * 100) : 0;
                      return (
                        <div key={onb.onboarding_id} className="bg-white rounded-xl border border-stone-200 p-4 shadow-sm space-y-3">
                          <div className="flex items-start justify-between">
                            <div>
                              <div className="flex items-center gap-2">
                                <span className="font-mono text-xs font-semibold text-stone-900">{onb.onboarding_number}</span>
                                <span
                                  className={`px-2 py-0.5 text-[10px] font-bold rounded ${
                                    onb.status === "COMPLETED"
                                      ? "bg-emerald-100 text-emerald-800"
                                      : onb.status === "IN_PROGRESS"
                                      ? "bg-blue-100 text-blue-800"
                                      : "bg-amber-100 text-amber-800"
                                  }`}
                                >
                                  {onb.status}
                                </span>
                              </div>
                              <p className="text-xs font-medium text-stone-800 mt-1">
                                {emp ? `${emp.first_name} ${emp.last_name} (${emp.employee_code})` : onb.job_applicant_name || "New Hire"}
                              </p>
                              <p className="text-[11px] text-stone-400">Joining Date: {onb.date_of_joining}</p>
                            </div>
                            <div className="text-right">
                              <span className="text-xs font-bold text-stone-800">{progressPct}%</span>
                              <p className="text-[10px] text-stone-400">{completedCount} of {tasks.length} tasks</p>
                            </div>
                          </div>

                          {/* Progress bar */}
                          <div className="w-full h-1.5 bg-stone-100 rounded-full overflow-hidden">
                            <div
                              className="h-full bg-emerald-600 transition-all duration-300"
                              style={{ width: `${progressPct}%` }}
                            />
                          </div>

                          {/* Checklist items */}
                          <div className="space-y-1.5 pt-1">
                            {tasks.map((t: any) => (
                              <div
                                key={t.task_id}
                                className={`flex items-center justify-between p-2 rounded-lg text-xs border ${
                                  t.is_completed ? "bg-emerald-50/50 border-emerald-100 text-stone-600" : "bg-stone-50 border-stone-200 text-stone-800"
                                }`}
                              >
                                <div className="flex items-center gap-2.5">
                                  {t.is_completed ? (
                                    <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
                                  ) : (
                                    <button
                                      type="button"
                                      onClick={() => handleCompleteOnboardingTask(onb.onboarding_id, t.task_id)}
                                      className="w-4 h-4 rounded border border-stone-400 hover:border-emerald-600 hover:bg-emerald-50 flex items-center justify-center transition"
                                      title="Click to mark complete"
                                    />
                                  )}
                                  <span className={t.is_completed ? "line-through text-stone-400" : "font-medium"}>
                                    {t.task_name}
                                  </span>
                                </div>
                                {t.is_completed ? (
                                  <span className="text-[10px] text-emerald-700 font-medium">Done</span>
                                ) : (
                                  <button
                                    type="button"
                                    onClick={() => handleCompleteOnboardingTask(onb.onboarding_id, t.task_id)}
                                    className="px-2 py-0.5 text-[10px] font-medium bg-emerald-700 hover:bg-emerald-800 text-white rounded transition"
                                  >
                                    Verify
                                  </button>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      );
                    })}

                    {onboardings.length === 0 && (
                      <div className="bg-white rounded-xl border border-stone-200 p-8 text-center text-xs text-stone-400">
                        No onboarding checklists active. Click "+ Start Onboarding" to create one.
                      </div>
                    )}
                  </div>

                  {/* Separation Workflows Column */}
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <h3 className="text-sm font-bold text-stone-900 flex items-center gap-2">
                          <UserX className="w-4 h-4 text-rose-700" />
                          Employee Separation / Exit Checklists ({separations.length})
                        </h3>
                        <p className="text-xs text-stone-500 mt-0.5">Clearance, asset return, and offboarding workflows</p>
                      </div>
                      <button
                        onClick={() => setShowSeparationModal(true)}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-stone-800 hover:bg-stone-900 text-white rounded-lg transition shadow-sm"
                      >
                        <Plus className="w-3.5 h-3.5" />
                        Start Exit
                      </button>
                    </div>

                    {separations.map((sep) => {
                      const emp = employees.find((e) => e.employee_id === sep.employee_id);
                      const tasks = sep.tasks || [];
                      const completedCount = tasks.filter((t: any) => t.is_completed).length;
                      const progressPct = tasks.length > 0 ? Math.round((completedCount / tasks.length) * 100) : 0;
                      return (
                        <div key={sep.separation_id} className="bg-white rounded-xl border border-stone-200 p-4 shadow-sm space-y-3">
                          <div className="flex items-start justify-between">
                            <div>
                              <div className="flex items-center gap-2">
                                <span className="font-mono text-xs font-semibold text-stone-900">{sep.separation_number}</span>
                                <span
                                  className={`px-2 py-0.5 text-[10px] font-bold rounded ${
                                    sep.status === "COMPLETED"
                                      ? "bg-rose-100 text-rose-800"
                                      : sep.status === "IN_PROGRESS"
                                      ? "bg-blue-100 text-blue-800"
                                      : "bg-amber-100 text-amber-800"
                                  }`}
                                >
                                  {sep.status}
                                </span>
                              </div>
                              <p className="text-xs font-medium text-stone-800 mt-1">
                                {emp ? `${emp.first_name} ${emp.last_name} (${emp.employee_code})` : "Departing Employee"}
                              </p>
                              <p className="text-[11px] text-stone-400">Resignation Date: {sep.resignation_date}</p>
                              {sep.exit_interview_notes && (
                                <p className="text-[11px] text-stone-500 italic mt-0.5">"{sep.exit_interview_notes}"</p>
                              )}
                            </div>
                            <div className="text-right">
                              <span className="text-xs font-bold text-stone-800">{progressPct}%</span>
                              <p className="text-[10px] text-stone-400">{completedCount} of {tasks.length} tasks</p>
                            </div>
                          </div>

                          {/* Progress bar */}
                          <div className="w-full h-1.5 bg-stone-100 rounded-full overflow-hidden">
                            <div
                              className="h-full bg-rose-600 transition-all duration-300"
                              style={{ width: `${progressPct}%` }}
                            />
                          </div>

                          {/* Checklist items */}
                          <div className="space-y-1.5 pt-1">
                            {tasks.map((t: any) => (
                              <div
                                key={t.task_id}
                                className={`flex items-center justify-between p-2 rounded-lg text-xs border ${
                                  t.is_completed ? "bg-rose-50/40 border-rose-100 text-stone-600" : "bg-stone-50 border-stone-200 text-stone-800"
                                }`}
                              >
                                <div className="flex items-center gap-2.5">
                                  {t.is_completed ? (
                                    <CheckCircle2 className="w-4 h-4 text-rose-600 flex-shrink-0" />
                                  ) : (
                                    <button
                                      type="button"
                                      onClick={() => handleCompleteSeparationTask(sep.separation_id, t.task_id)}
                                      className="w-4 h-4 rounded border border-stone-400 hover:border-rose-600 hover:bg-rose-50 flex items-center justify-center transition"
                                      title="Click to mark complete"
                                    />
                                  )}
                                  <span className={t.is_completed ? "line-through text-stone-400" : "font-medium"}>
                                    {t.task_name}
                                  </span>
                                </div>
                                {t.is_completed ? (
                                  <span className="text-[10px] text-rose-700 font-medium">Cleared</span>
                                ) : (
                                  <button
                                    type="button"
                                    onClick={() => handleCompleteSeparationTask(sep.separation_id, t.task_id)}
                                    className="px-2 py-0.5 text-[10px] font-medium bg-stone-800 hover:bg-stone-900 text-white rounded transition"
                                  >
                                    Clear
                                  </button>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      );
                    })}

                    {separations.length === 0 && (
                      <div className="bg-white rounded-xl border border-stone-200 p-8 text-center text-xs text-stone-400">
                        No exit separation workflows active. Click "+ Start Exit" when an employee departs.
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ============================================================== */}
        {/* TAB 2: ATTENDANCE & SHIFTS */}
        {/* ============================================================== */}
        {activeTab === "attendance" && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Punch Attendance Form */}
            <div className="bg-white p-5 rounded-xl border border-stone-200 shadow-sm space-y-4">
              <div className="border-b border-stone-100 pb-3">
                <h2 className="text-sm font-semibold text-stone-900">Punch Daily Attendance</h2>
                <p className="text-xs text-stone-500 mt-0.5">Record shift check-ins with automated late/early metrics</p>
              </div>

              <form onSubmit={handlePunchAttendance} className="space-y-3 text-xs">
                <div>
                  <label className="block text-stone-600 font-medium mb-1">Employee</label>
                  <select
                    value={punchEmpId}
                    onChange={(e) => setPunchEmpId(e.target.value)}
                    className="w-full px-3 py-2 border border-stone-200 rounded-lg bg-stone-50 text-stone-900 focus:outline-none focus:ring-1 focus:ring-stone-400"
                  >
                    {employees.map((e) => (
                      <option key={e.employee_id} value={e.employee_id}>
                        {e.employee_code} — {e.first_name} {e.last_name}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-stone-600 font-medium mb-1">Date</label>
                    <input
                      type="date"
                      value={punchDate}
                      onChange={(e) => setPunchDate(e.target.value)}
                      className="w-full px-3 py-2 border border-stone-200 rounded-lg bg-stone-50 text-stone-900 focus:outline-none focus:ring-1 focus:ring-stone-400"
                    />
                  </div>
                  <div>
                    <label className="block text-stone-600 font-medium mb-1">Status</label>
                    <select
                      value={punchStatus}
                      onChange={(e) => setPunchStatus(e.target.value)}
                      className="w-full px-3 py-2 border border-stone-200 rounded-lg bg-stone-50 text-stone-900 focus:outline-none focus:ring-1 focus:ring-stone-400"
                    >
                      <option value="PRESENT">PRESENT</option>
                      <option value="HALF_DAY">HALF_DAY</option>
                      <option value="ABSENT">ABSENT</option>
                      <option value="ON_LEAVE">ON_LEAVE</option>
                    </select>
                  </div>
                </div>

                {punchStatus !== "ABSENT" && (
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-stone-600 font-medium mb-1">In Time</label>
                      <input
                        type="time"
                        value={punchInTime}
                        onChange={(e) => setPunchInTime(e.target.value)}
                        className="w-full px-3 py-2 border border-stone-200 rounded-lg bg-stone-50 text-stone-900 focus:outline-none focus:ring-1 focus:ring-stone-400"
                      />
                    </div>
                    <div>
                      <label className="block text-stone-600 font-medium mb-1">Out Time</label>
                      <input
                        type="time"
                        value={punchOutTime}
                        onChange={(e) => setPunchOutTime(e.target.value)}
                        className="w-full px-3 py-2 border border-stone-200 rounded-lg bg-stone-50 text-stone-900 focus:outline-none focus:ring-1 focus:ring-stone-400"
                      />
                    </div>
                  </div>
                )}

                <button
                  type="submit"
                  className="w-full py-2 bg-stone-900 hover:bg-stone-800 text-white rounded-lg font-medium transition"
                >
                  Log Punch Record
                </button>
              </form>
            </div>

            {/* Attendance Log Table */}
            <div className="lg:col-span-2 bg-white rounded-xl border border-stone-200 shadow-sm overflow-hidden">
              <div className="p-4 border-b border-stone-200 flex items-center justify-between">
                <div>
                  <h2 className="text-sm font-semibold text-stone-900">Attendance Log</h2>
                  <p className="text-xs text-stone-500 mt-0.5">Punch history with compliance late/early calculations</p>
                </div>
              </div>

              <div className="overflow-x-auto max-h-[460px] overflow-y-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-stone-50/75 border-b border-stone-200 text-stone-500 sticky top-0">
                    <tr>
                      <th className="px-4 py-3 font-medium">Date</th>
                      <th className="px-4 py-3 font-medium">Status</th>
                      <th className="px-4 py-3 font-medium">In / Out</th>
                      <th className="px-4 py-3 font-medium">Hours</th>
                      <th className="px-4 py-3 font-medium">Compliance</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-stone-100">
                    {attendances.map((att) => (
                      <tr key={att.attendance_id} className="hover:bg-stone-50/50 transition">
                        <td className="px-4 py-3 font-mono text-stone-800">{att.attendance_date}</td>
                        <td className="px-4 py-3">
                          <span
                            className={`px-2 py-0.5 text-[10px] font-semibold rounded ${
                              att.status === "PRESENT"
                                ? "bg-emerald-100 text-emerald-800"
                                : att.status === "HALF_DAY"
                                ? "bg-amber-100 text-amber-800"
                                : "bg-rose-100 text-rose-800"
                            }`}
                          >
                            {att.status}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-stone-600">
                          {att.in_time ? new Date(att.in_time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "—"}
                          {" → "}
                          {att.out_time ? new Date(att.out_time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "—"}
                        </td>
                        <td className="px-4 py-3 font-mono text-stone-700">{att.working_hours}h</td>
                        <td className="px-4 py-3">
                          <div className="flex gap-1.5">
                            {att.late_entry && (
                              <span className="px-1.5 py-0.5 text-[9px] bg-rose-100 text-rose-700 rounded font-medium">
                                Late Entry
                              </span>
                            )}
                            {att.early_exit && (
                              <span className="px-1.5 py-0.5 text-[9px] bg-amber-100 text-amber-700 rounded font-medium">
                                Early Exit
                              </span>
                            )}
                            {!att.late_entry && !att.early_exit && att.status === "PRESENT" && (
                              <span className="text-emerald-600 text-[11px] font-medium flex items-center gap-1">
                                <CheckCircle2 className="w-3 h-3" /> Compliant
                              </span>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                    {attendances.length === 0 && (
                      <tr>
                        <td colSpan={5} className="text-center py-8 text-stone-400">
                          No attendance logs found. Use the punch logger to record daily presence.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* ============================================================== */}
        {/* TAB 3: LEAVE MANAGEMENT */}
        {/* ============================================================== */}
        {activeTab === "leaves" && (
          <div className="space-y-6">
            <div className="flex items-center justify-between bg-white p-4 rounded-xl border border-stone-200 shadow-sm">
              <div>
                <h3 className="text-sm font-semibold text-stone-900">Leave Policies & Entitlements</h3>
                <p className="text-xs text-stone-500 mt-0.5">Automated entitlement balance tracking, quota enforcement, and approval flows</p>
              </div>
              <button
                type="button"
                onClick={() => {
                  setLeaveModalError(null);
                  setShowLeaveTypeModal(true);
                }}
                className="inline-flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-medium bg-stone-900 hover:bg-stone-800 text-white rounded-lg shadow-sm transition"
              >
                <Plus className="w-3.5 h-3.5" />
                New Leave Type
              </button>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Submit Leave Application */}
              <div className="bg-white p-5 rounded-xl border border-stone-200 shadow-sm space-y-4">
                <div className="border-b border-stone-100 pb-3">
                  <h2 className="text-sm font-semibold text-stone-900">Apply for Leave</h2>
                  <p className="text-xs text-stone-500 mt-0.5">Submit request with automated entitlement balance validation</p>
                </div>

                <form onSubmit={handleSubmitLeave} className="space-y-3 text-xs">
                  <div>
                    <label className="block text-stone-600 font-medium mb-1">Employee</label>
                    <select
                      value={leaveEmpId}
                      onChange={(e) => setLeaveEmpId(e.target.value)}
                      className="w-full px-3 py-2 border border-stone-200 rounded-lg bg-stone-50 text-stone-900 focus:outline-none focus:ring-1 focus:ring-stone-400"
                    >
                      {employees.map((e) => (
                        <option key={e.employee_id} value={e.employee_id}>
                          {e.employee_code} — {e.first_name} {e.last_name}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <label className="text-stone-600 font-medium">Leave Type</label>
                      <button
                        type="button"
                        onClick={() => {
                          setLeaveModalError(null);
                          setShowLeaveTypeModal(true);
                        }}
                        className="text-[10px] text-stone-700 hover:text-stone-900 font-semibold underline flex items-center gap-0.5"
                      >
                        <Plus className="w-2.5 h-2.5" /> New Type
                      </button>
                    </div>
                    <select
                      value={leaveTypeId}
                      onChange={(e) => setLeaveTypeId(e.target.value)}
                      className="w-full px-3 py-2 border border-stone-200 rounded-lg bg-stone-50 text-stone-900 focus:outline-none focus:ring-1 focus:ring-stone-400"
                    >
                      {leaveTypes.length === 0 ? (
                        <option value="">No leave types configured — Click + New Type</option>
                      ) : (
                        leaveTypes.map((t) => (
                          <option key={t.leave_type_id} value={t.leave_type_id}>
                            {t.type_name} {t.is_lwp ? "(Unpaid/LWP)" : `(Max ${t.max_days_allowed}d)`}
                          </option>
                        ))
                      )}
                    </select>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-stone-600 font-medium mb-1">From Date</label>
                      <input
                        type="date"
                        value={leaveFromDate}
                        onChange={(e) => setLeaveFromDate(e.target.value)}
                        className="w-full px-3 py-2 border border-stone-200 rounded-lg bg-stone-50 text-stone-900 focus:outline-none focus:ring-1 focus:ring-stone-400"
                      />
                    </div>
                    <div>
                      <label className="block text-stone-600 font-medium mb-1">To Date</label>
                      <input
                        type="date"
                        value={leaveToDate}
                        onChange={(e) => setLeaveToDate(e.target.value)}
                        className="w-full px-3 py-2 border border-stone-200 rounded-lg bg-stone-50 text-stone-900 focus:outline-none focus:ring-1 focus:ring-stone-400"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-stone-600 font-medium mb-1">Total Days</label>
                    <input
                      type="number"
                      step="0.5"
                      value={leaveDays}
                      onChange={(e) => setLeaveDays(e.target.value)}
                      className="w-full px-3 py-2 border border-stone-200 rounded-lg bg-stone-50 text-stone-900 focus:outline-none focus:ring-1 focus:ring-stone-400"
                    />
                  </div>

                  <div>
                    <label className="block text-stone-600 font-medium mb-1">Reason</label>
                    <textarea
                      rows={2}
                      value={leaveReason}
                      onChange={(e) => setLeaveReason(e.target.value)}
                      className="w-full px-3 py-2 border border-stone-200 rounded-lg bg-stone-50 text-stone-900 focus:outline-none focus:ring-1 focus:ring-stone-400"
                    />
                  </div>

                  <button
                    type="submit"
                    className="w-full py-2 bg-stone-900 hover:bg-stone-800 text-white rounded-lg font-medium transition"
                  >
                    Submit Application
                  </button>
                </form>
              </div>

              {/* Leave Applications Queue */}
              <div className="lg:col-span-2 bg-white rounded-xl border border-stone-200 shadow-sm overflow-hidden">
                <div className="p-4 border-b border-stone-200 flex items-center justify-between">
                  <div>
                    <h2 className="text-sm font-semibold text-stone-900">Leave Applications & Approval Queue</h2>
                    <p className="text-xs text-stone-500 mt-0.5">Manager authorization queue with 1-click decisioning</p>
                  </div>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-stone-50/75 border-b border-stone-200 text-stone-500">
                      <tr>
                        <th className="px-4 py-3 font-medium">Application #</th>
                        <th className="px-4 py-3 font-medium">Period</th>
                        <th className="px-4 py-3 font-medium">Days</th>
                        <th className="px-4 py-3 font-medium">Reason</th>
                        <th className="px-4 py-3 font-medium">Status</th>
                        <th className="px-4 py-3 font-medium text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-stone-100">
                      {leaveApps.map((app) => (
                        <tr key={app.application_id} className="hover:bg-stone-50/50 transition">
                          <td className="px-4 py-3 font-mono text-stone-900 font-medium">{app.application_number}</td>
                          <td className="px-4 py-3 text-stone-600">
                            {app.from_date} → {app.to_date}
                          </td>
                          <td className="px-4 py-3 font-medium text-stone-800">{app.total_leave_days}d</td>
                          <td className="px-4 py-3 text-stone-600 max-w-xs truncate">{app.reason}</td>
                          <td className="px-4 py-3">
                            <span
                              className={`px-2 py-0.5 text-[10px] font-semibold rounded ${
                                app.status === "APPROVED"
                                  ? "bg-emerald-100 text-emerald-800"
                                  : app.status === "REJECTED"
                                  ? "bg-rose-100 text-rose-800"
                                  : "bg-amber-100 text-amber-800"
                              }`}
                            >
                              {app.status}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-right">
                            {app.status === "SUBMITTED" ? (
                              <div className="flex items-center justify-end gap-1.5">
                                <button
                                  onClick={() => handleApproveLeave(app.application_id)}
                                  className="px-2 py-1 text-[10px] font-medium bg-emerald-600 hover:bg-emerald-700 text-white rounded transition"
                                >
                                  Approve
                                </button>
                                <button
                                  onClick={() => handleRejectLeave(app.application_id)}
                                  className="px-2 py-1 text-[10px] font-medium bg-rose-600 hover:bg-rose-700 text-white rounded transition"
                                >
                                  Reject
                                </button>
                              </div>
                            ) : (
                              <span className="text-stone-400 text-[10px]">Processed</span>
                            )}
                          </td>
                        </tr>
                      ))}
                      {leaveApps.length === 0 && (
                        <tr>
                          <td colSpan={6} className="text-center py-8 text-stone-400">
                            No leave applications submitted yet.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>

            {/* Configured Leave Types & Policies Card */}
            <div className="bg-white rounded-xl border border-stone-200 shadow-sm overflow-hidden">
              <div className="p-4 border-b border-stone-200 flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-semibold text-stone-900">Configured Leave Types ({leaveTypes.length})</h3>
                  <p className="text-xs text-stone-500 mt-0.5">Active company leave categories, annual allowances, and carry-forward rules</p>
                </div>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-stone-50/75 border-b border-stone-200 text-stone-500">
                    <tr>
                      <th className="px-4 py-3 font-medium">Leave Type Name</th>
                      <th className="px-4 py-3 font-medium">Annual Quota</th>
                      <th className="px-4 py-3 font-medium">Carry Forward</th>
                      <th className="px-4 py-3 font-medium">Classification</th>
                      <th className="px-4 py-3 font-medium">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-stone-100">
                    {leaveTypes.map((t) => (
                      <tr key={t.leave_type_id} className="hover:bg-stone-50/50 transition">
                        <td className="px-4 py-3 font-medium text-stone-900">{t.type_name}</td>
                        <td className="px-4 py-3 text-stone-700">{t.is_lwp ? "0 (Uncapped / Unpaid)" : `${t.max_days_allowed} days / year`}</td>
                        <td className="px-4 py-3">
                          <span className={`px-2 py-0.5 text-[10px] font-semibold rounded ${t.is_carry_forward ? "bg-emerald-100 text-emerald-800" : "bg-stone-100 text-stone-600"}`}>
                            {t.is_carry_forward ? "Accumulative (Carry Forward)" : "Annual Use-or-Lose"}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <span className={`px-2 py-0.5 text-[10px] font-semibold rounded ${t.is_lwp ? "bg-amber-100 text-amber-800" : "bg-emerald-100 text-emerald-800"}`}>
                            {t.is_lwp ? "Unpaid / LWP" : "Paid Leave"}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <span className="px-2 py-0.5 text-[10px] font-semibold rounded bg-emerald-100 text-emerald-800">Active</span>
                        </td>
                      </tr>
                    ))}
                    {leaveTypes.length === 0 && (
                      <tr>
                        <td colSpan={5} className="text-center py-6 text-stone-400">
                          No leave types configured. Click "+ New Leave Type" to set up policies.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* ============================================================== */}
        {/* TAB 4: SALARY STRUCTURES & COMPONENTS */}
        {/* ============================================================== */}
        {activeTab === "structures" && (
          <div className="space-y-6">
            {/* Explanatory Hierarchy Guide */}
            <div className="bg-stone-50 border border-stone-200 rounded-xl p-4 flex flex-col md:flex-row items-center justify-between gap-3 text-xs text-stone-600">
              <div className="flex items-center gap-2 font-medium text-stone-900">
                <span className="w-5 h-5 rounded-full bg-stone-900 text-white flex items-center justify-center text-[10px]">i</span>
                <span>Compensation Architecture Flow:</span>
              </div>
              <div className="flex flex-wrap items-center gap-2 text-[11px]">
                <span className="px-2.5 py-1 bg-white border border-stone-200 rounded-md font-medium text-stone-800">
                  1. Define Components (e.g. SL - Salaru, Basic)
                </span>
                <ArrowRight className="w-3.5 h-3.5 text-stone-400" />
                <span className="px-2.5 py-1 bg-white border border-stone-200 rounded-md font-medium text-stone-800">
                  2. Assemble into Salary Structure Package
                </span>
                <ArrowRight className="w-3.5 h-3.5 text-stone-400" />
                <span className="px-2.5 py-1 bg-white border border-stone-200 rounded-md font-medium text-stone-800">
                  3. Assign Package to Employee
                </span>
              </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Card 1: Define Salary Component */}
              <div className="bg-white p-5 rounded-xl border border-stone-200 shadow-sm space-y-4">
                <div className="border-b border-stone-100 pb-3">
                  <span className="text-[10px] font-bold text-amber-700 uppercase tracking-wider">Step 1</span>
                  <h2 className="text-sm font-semibold text-stone-900">Define Salary Component</h2>
                  <p className="text-xs text-stone-500 mt-0.5">Earnings and deductions with formula arithmetic</p>
                </div>

                <form onSubmit={handleCreateComponent} className="space-y-3 text-xs">
                  <div className="space-y-3">
                    <div>
                      <label className="block text-stone-600 font-medium mb-1">Component Name</label>
                      <input
                        type="text"
                        placeholder="House Rent Allowance"
                        value={compName}
                        onChange={(e) => setCompName(e.target.value)}
                        className="w-full px-3 py-2 border border-stone-200 rounded-lg bg-stone-50 text-stone-900 focus:outline-none focus:ring-1 focus:ring-stone-400"
                        required
                      />
                    </div>
                    <div>
                      <label className="block text-stone-600 font-medium mb-1">Component Code</label>
                      <input
                        type="text"
                        placeholder="HRA"
                        value={compCode}
                        onChange={(e) => setCompCode(e.target.value)}
                        className="w-full px-3 py-2 border border-stone-200 rounded-lg bg-stone-50 text-stone-900 focus:outline-none focus:ring-1 focus:ring-stone-400"
                        required
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-stone-600 font-medium mb-1">Type</label>
                      <select
                        value={compType}
                        onChange={(e) => setCompType(e.target.value as any)}
                        className="w-full px-3 py-2 border border-stone-200 rounded-lg bg-stone-50 text-stone-900 focus:outline-none focus:ring-1 focus:ring-stone-400"
                      >
                        <option value="EARNING">EARNING</option>
                        <option value="DEDUCTION">DEDUCTION</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-stone-600 font-medium mb-1">Calculation</label>
                      <select
                        value={compCalcType}
                        onChange={(e) => setCompCalcType(e.target.value as any)}
                        className="w-full px-3 py-2 border border-stone-200 rounded-lg bg-stone-50 text-stone-900 focus:outline-none focus:ring-1 focus:ring-stone-400"
                      >
                        <option value="FIXED">FIXED AMOUNT</option>
                        <option value="FORMULA">FORMULA</option>
                      </select>
                    </div>
                  </div>

                  {compCalcType === "FORMULA" && (
                    <div>
                      <label className="block text-stone-600 font-medium mb-1">
                        Formula Expression (e.g. `base * 0.40`)
                      </label>
                      <input
                        type="text"
                        placeholder="base * 0.40"
                        value={compFormula}
                        onChange={(e) => setCompFormula(e.target.value)}
                        className="w-full px-3 py-2 border border-stone-200 rounded-lg bg-stone-50 text-stone-900 focus:outline-none focus:ring-1 focus:ring-stone-400"
                        required
                      />
                    </div>
                  )}

                  <button
                    type="submit"
                    className="w-full py-2 bg-stone-900 hover:bg-stone-800 text-white rounded-lg font-medium transition"
                  >
                    Save Component
                  </button>
                </form>
              </div>

              {/* Card 2: Build Salary Structure Package (Problem 1 Fix) */}
              <div className="bg-white p-5 rounded-xl border border-stone-200 shadow-sm space-y-4">
                <div className="border-b border-stone-100 pb-3">
                  <span className="text-[10px] font-bold text-amber-700 uppercase tracking-wider">Step 2</span>
                  <h2 className="text-sm font-semibold text-stone-900">Build Structure Package</h2>
                  <p className="text-xs text-stone-500 mt-0.5">Bundle created components into a unified package</p>
                </div>

                <form onSubmit={handleCreateSalaryStructure} className="space-y-3 text-xs">
                  <div>
                    <label className="block text-stone-600 font-medium mb-1">Structure Package Name</label>
                    <input
                      type="text"
                      placeholder="e.g. Full-Time Engineering Package"
                      value={newStructName}
                      onChange={(e) => setNewStructName(e.target.value)}
                      className="w-full px-3 py-2 border border-stone-200 rounded-lg bg-stone-50 text-stone-900 focus:outline-none focus:ring-1 focus:ring-stone-400"
                      required
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-stone-600 font-medium mb-1">Frequency</label>
                      <select
                        value={newStructFreq}
                        onChange={(e) => setNewStructFreq(e.target.value)}
                        className="w-full px-3 py-2 border border-stone-200 rounded-lg bg-stone-50 text-stone-900 focus:outline-none focus:ring-1 focus:ring-stone-400"
                      >
                        <option value="MONTHLY">Monthly</option>
                        <option value="BI_WEEKLY">Bi-Weekly</option>
                        <option value="WEEKLY">Weekly</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-stone-600 font-medium mb-1">Currency</label>
                      <input
                        type="text"
                        value={newStructCurrency}
                        onChange={(e) => setNewStructCurrency(e.target.value)}
                        className="w-full px-3 py-2 border border-stone-200 rounded-lg bg-stone-50 text-stone-900 focus:outline-none focus:ring-1 focus:ring-stone-400"
                        required
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-stone-600 font-medium mb-1">Select Included Components</label>
                    <div className="border border-stone-200 rounded-lg p-2 max-h-40 overflow-y-auto space-y-2 bg-stone-50/50">
                      {components.map((c) => {
                        const isChecked = !!structItemsMap[c.component_id]?.selected;
                        const currentVal = structItemsMap[c.component_id]?.amount || "0";
                        return (
                          <div
                            key={c.component_id}
                            className={`p-2 rounded border transition flex flex-col gap-1.5 ${
                              isChecked ? "bg-white border-stone-400 shadow-xs" : "border-stone-200 bg-white/60"
                            }`}
                          >
                            <div className="flex items-center justify-between">
                              <label className="flex items-center gap-2 cursor-pointer">
                                <input
                                  type="checkbox"
                                  checked={isChecked}
                                  onChange={(e) => {
                                    setStructItemsMap((prev) => ({
                                      ...prev,
                                      [c.component_id]: {
                                        selected: e.target.checked,
                                        amount: prev[c.component_id]?.amount || (c.calculation_type === "FIXED" ? "500" : "0"),
                                        formula: prev[c.component_id]?.formula || (c.formula_expression || ""),
                                      },
                                    }));
                                  }}
                                  className="rounded border-stone-300 text-stone-900 focus:ring-stone-400"
                                />
                                <span className="font-semibold text-stone-900">{c.component_code}</span>
                                <span className="text-[10px] text-stone-500">({c.component_name})</span>
                              </label>
                              <span
                                className={`px-1.5 py-0.5 text-[9px] font-bold rounded ${
                                  c.component_type === "EARNING"
                                    ? "bg-emerald-100 text-emerald-800"
                                    : "bg-rose-100 text-rose-800"
                                }`}
                              >
                                {c.component_type}
                              </span>
                            </div>
                            {isChecked && (
                              <div className="flex items-center gap-2 pt-1 border-t border-stone-100">
                                {c.calculation_type === "FORMULA" ? (
                                  <span className="text-[10px] font-mono text-stone-500">
                                    Formula: {c.formula_expression || "base * 0.40"}
                                  </span>
                                ) : (
                                  <div className="flex items-center gap-1.5 w-full">
                                    <span className="text-[10px] text-stone-500">Amount ($):</span>
                                    <input
                                      type="number"
                                      step="50"
                                      value={currentVal}
                                      onChange={(e) => {
                                        const val = e.target.value;
                                        setStructItemsMap((prev) => ({
                                          ...prev,
                                          [c.component_id]: {
                                            ...prev[c.component_id],
                                            selected: true,
                                            amount: val,
                                          },
                                        }));
                                      }}
                                      className="w-full px-2 py-1 text-xs border border-stone-200 rounded bg-white"
                                    />
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                        );
                      })}
                      {components.length === 0 && (
                        <p className="text-center py-4 text-stone-400 text-xs">
                          No components created yet. Define one in Step 1 first.
                        </p>
                      )}
                    </div>
                  </div>

                  <button
                    type="submit"
                    className="w-full py-2 bg-stone-900 hover:bg-stone-800 text-white rounded-lg font-medium transition"
                  >
                    Save Structure Package
                  </button>
                </form>
              </div>

              {/* Card 3: Assign Salary Structure */}
              <div className="bg-white p-5 rounded-xl border border-stone-200 shadow-sm space-y-4">
                <div className="border-b border-stone-100 pb-3">
                  <span className="text-[10px] font-bold text-amber-700 uppercase tracking-wider">Step 3</span>
                  <h2 className="text-sm font-semibold text-stone-900">Assign Package to Employee</h2>
                  <p className="text-xs text-stone-500 mt-0.5">Link compensation structure with employee base wage</p>
                </div>

                {structures.length === 0 ? (
                  <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-amber-800 text-xs flex items-start gap-2">
                    <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0 text-amber-600" />
                    <div>
                      <p className="font-semibold">No Salary Structures Defined Yet</p>
                      <p className="text-[11px] text-amber-700 mt-0.5">
                        Your salary components (like <strong>SL - Salaru</strong>) must be bundled into a Salary Structure first in <strong>Step 2</strong>. Then you can select and assign the package here.
                      </p>
                    </div>
                  </div>
                ) : (
                  <form onSubmit={handleAssignStructure} className="space-y-3 text-xs">
                    <div>
                      <label className="block text-stone-600 font-medium mb-1">Employee</label>
                      <select
                        value={assignEmpId}
                        onChange={(e) => setAssignEmpId(e.target.value)}
                        className="w-full px-3 py-2 border border-stone-200 rounded-lg bg-stone-50 text-stone-900 focus:outline-none focus:ring-1 focus:ring-stone-400"
                      >
                        {employees.map((e) => (
                          <option key={e.employee_id} value={e.employee_id}>
                            {e.employee_code} — {e.first_name} {e.last_name}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div>
                      <label className="block text-stone-600 font-medium mb-1">Salary Structure Package</label>
                      <select
                        value={assignStructId}
                        onChange={(e) => setAssignStructId(e.target.value)}
                        className="w-full px-3 py-2 border border-stone-200 rounded-lg bg-stone-50 text-stone-900 focus:outline-none focus:ring-1 focus:ring-stone-400"
                      >
                        {structures.map((s) => (
                          <option key={s.structure_id} value={s.structure_id}>
                            {s.structure_name} ({s.payroll_frequency}) — {s.items?.length || 0} component(s)
                          </option>
                        ))}
                      </select>
                    </div>

                    {/* Preview of components bundled in selected structure */}
                    {(() => {
                      const selStruct = structures.find((s) => s.structure_id === assignStructId) || structures[0];
                      if (!selStruct || !selStruct.items || selStruct.items.length === 0) return null;
                      return (
                        <div className="p-2.5 bg-stone-50 border border-stone-200 rounded-lg space-y-1">
                          <span className="text-[10px] font-semibold text-stone-600">Bundled in this package:</span>
                          <div className="flex flex-wrap gap-1">
                            {selStruct.items.map((itm: any, idx: number) => (
                              <span
                                key={idx}
                                className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
                                  itm.component?.component_type === "DEDUCTION"
                                    ? "bg-rose-100 text-rose-800"
                                    : "bg-emerald-100 text-emerald-800"
                                }`}
                              >
                                {itm.component?.component_code || itm.component?.component_name || "Component"}:{" "}
                                {itm.formula_expression ? itm.formula_expression : `$${parseFloat(itm.amount || 0).toFixed(0)}`}
                              </span>
                            ))}
                          </div>
                        </div>
                      );
                    })()}

                    <div>
                      <label className="block text-stone-600 font-medium mb-1">Base Monthly Salary ($)</label>
                      <input
                        type="number"
                        step="100"
                        value={assignBaseSalary}
                        onChange={(e) => setAssignBaseSalary(e.target.value)}
                        className="w-full px-3 py-2 border border-stone-200 rounded-lg bg-stone-50 text-stone-900 focus:outline-none focus:ring-1 focus:ring-stone-400"
                        required
                      />
                    </div>

                    <button
                      type="submit"
                      className="w-full py-2 bg-stone-900 hover:bg-stone-800 text-white rounded-lg font-medium transition"
                    >
                      Authorize Assignment
                    </button>
                  </form>
                )}
              </div>
            </div>

            {/* Active Salary Structures Catalog Table */}
            <div className="bg-white rounded-xl border border-stone-200 shadow-sm overflow-hidden">
              <div className="p-4 border-b border-stone-200">
                <h3 className="text-sm font-semibold text-stone-900">Active Salary Structure Packages ({structures.length})</h3>
                <p className="text-xs text-stone-500 mt-0.5">Assembled compensation packages with bundled components</p>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-stone-50/75 border-b border-stone-200 text-stone-500">
                    <tr>
                      <th className="px-4 py-3 font-medium">Package Name</th>
                      <th className="px-4 py-3 font-medium">Frequency</th>
                      <th className="px-4 py-3 font-medium">Currency</th>
                      <th className="px-4 py-3 font-medium">Bundled Components</th>
                      <th className="px-4 py-3 font-medium text-right">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-stone-100">
                    {structures.map((s) => (
                      <tr key={s.structure_id} className="hover:bg-stone-50/50 transition">
                        <td className="px-4 py-3 font-semibold text-stone-900">{s.structure_name}</td>
                        <td className="px-4 py-3 text-stone-600">{s.payroll_frequency}</td>
                        <td className="px-4 py-3 text-stone-600 font-mono">{s.currency}</td>
                        <td className="px-4 py-3">
                          <div className="flex flex-wrap gap-1">
                            {(s.items || []).map((itm: any, idx: number) => (
                              <span
                                key={idx}
                                className={`px-1.5 py-0.5 text-[10px] font-semibold rounded ${
                                  itm.component?.component_type === "DEDUCTION"
                                    ? "bg-rose-100 text-rose-800"
                                    : "bg-emerald-100 text-emerald-800"
                                }`}
                              >
                                {itm.component?.component_code || "COMP"}:{" "}
                                {itm.formula_expression ? itm.formula_expression : `$${parseFloat(itm.amount || 0).toFixed(0)}`}
                              </span>
                            ))}
                            {(!s.items || s.items.length === 0) && (
                              <span className="text-stone-400 italic">No components</span>
                            )}
                          </div>
                        </td>
                        <td className="px-4 py-3 text-right">
                          <span className="px-2 py-0.5 text-[10px] font-bold rounded bg-emerald-100 text-emerald-800">
                            Active
                          </span>
                        </td>
                      </tr>
                    ))}
                    {structures.length === 0 && (
                      <tr>
                        <td colSpan={5} className="text-center py-6 text-stone-400">
                          No salary structures packaged yet. Use Step 2 above to bundle components into a structure.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Components Catalog Table */}
            <div className="bg-white rounded-xl border border-stone-200 shadow-sm overflow-hidden">
              <div className="p-4 border-b border-stone-200">
                <h3 className="text-sm font-semibold text-stone-900">Active Salary Components Catalog ({components.length})</h3>
                <p className="text-xs text-stone-500 mt-0.5">Underlying earnings and deduction elements available for bundling</p>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-stone-50/75 border-b border-stone-200 text-stone-500">
                    <tr>
                      <th className="px-4 py-3 font-medium">Code</th>
                      <th className="px-4 py-3 font-medium">Name</th>
                      <th className="px-4 py-3 font-medium">Type</th>
                      <th className="px-4 py-3 font-medium">Calculation</th>
                      <th className="px-4 py-3 font-medium">Formula</th>
                      <th className="px-4 py-3 font-medium">Account Code</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-stone-100">
                    {components.map((c) => (
                      <tr key={c.component_id} className="hover:bg-stone-50/50 transition">
                        <td className="px-4 py-3 font-mono text-stone-900 font-medium">{c.component_code}</td>
                        <td className="px-4 py-3 text-stone-800">{c.component_name}</td>
                        <td className="px-4 py-3">
                          <span
                            className={`px-2 py-0.5 text-[10px] font-semibold rounded ${
                              c.component_type === "EARNING"
                                ? "bg-emerald-100 text-emerald-800"
                                : "bg-rose-100 text-rose-800"
                            }`}
                          >
                            {c.component_type}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-stone-600">{c.calculation_type}</td>
                        <td className="px-4 py-3 font-mono text-stone-700">{c.formula_expression || "—"}</td>
                        <td className="px-4 py-3 font-mono text-stone-500">{c.account_code}</td>
                      </tr>
                    ))}
                    {components.length === 0 && (
                      <tr>
                        <td colSpan={6} className="text-center py-6 text-stone-400">
                          No salary components configured.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* ============================================================== */}
        {/* TAB 5: PAYROLL RUNS & SALARY SLIPS */}
        {/* ============================================================== */}
        {activeTab === "payroll" && (
          <div className="space-y-6">
            {/* Batch Monthly Payroll Runner */}
            <div className="bg-white p-5 rounded-xl border border-stone-200 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div>
                <h2 className="text-sm font-semibold text-stone-900">Batch Monthly Payroll Engine</h2>
                <p className="text-xs text-stone-500 mt-0.5">
                  1-Click batch pay run: evaluates attendance, deducts LWP, calculates tax/benefits, and generates paystubs
                </p>
              </div>

              <form onSubmit={handleRunBatchPayroll} className="flex flex-wrap items-center gap-3">
                <input
                  type="date"
                  value={batchPostingDate}
                  onChange={(e) => setBatchPostingDate(e.target.value)}
                  className="px-3 py-1.5 text-xs border border-stone-200 rounded-lg bg-stone-50 text-stone-900"
                />
                <button
                  type="submit"
                  className="inline-flex items-center gap-2 px-4 py-1.5 text-xs font-medium bg-stone-900 hover:bg-stone-800 text-white rounded-lg shadow-sm transition"
                >
                  <DollarSign className="w-3.5 h-3.5" />
                  Generate Monthly Payroll
                </button>
              </form>
            </div>

            {/* Batch Payroll Runs Table */}
            {batchPayrolls.length > 0 && (
              <div className="bg-white rounded-xl border border-stone-200 shadow-sm overflow-hidden">
                <div className="p-4 border-b border-stone-200">
                  <h3 className="text-sm font-semibold text-stone-900">Batch Payroll Batches</h3>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-stone-50/75 border-b border-stone-200 text-stone-500">
                      <tr>
                        <th className="px-4 py-3 font-medium">Batch #</th>
                        <th className="px-4 py-3 font-medium">Posting Date</th>
                        <th className="px-4 py-3 font-medium">Period</th>
                        <th className="px-4 py-3 font-medium">Total Gross</th>
                        <th className="px-4 py-3 font-medium">Total Net Pay</th>
                        <th className="px-4 py-3 font-medium">Status</th>
                        <th className="px-4 py-3 font-medium text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-stone-100">
                      {batchPayrolls.map((batch) => (
                        <tr key={batch.payroll_entry_id} className="hover:bg-stone-50/50 transition">
                          <td className="px-4 py-3 font-mono font-medium text-stone-900">{batch.payroll_number}</td>
                          <td className="px-4 py-3 text-stone-600">{batch.posting_date}</td>
                          <td className="px-4 py-3 text-stone-600">
                            {batch.start_date} → {batch.end_date}
                          </td>
                          <td className="px-4 py-3 font-mono text-stone-800">${parseFloat(batch.total_gross_pay || 0).toFixed(2)}</td>
                          <td className="px-4 py-3 font-mono font-semibold text-emerald-700">${parseFloat(batch.total_net_pay || 0).toFixed(2)}</td>
                          <td className="px-4 py-3">
                            <span
                              className={`px-2 py-0.5 text-[10px] font-semibold rounded ${
                                batch.status === "SUBMITTED"
                                  ? "bg-emerald-100 text-emerald-800"
                                  : "bg-amber-100 text-amber-800"
                              }`}
                            >
                              {batch.status}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-right">
                            {batch.status === "DRAFT" ? (
                              <button
                                onClick={() => handleSubmitBatch(batch.payroll_entry_id)}
                                disabled={parseFloat(batch.total_gross_pay || 0) <= 0 || parseFloat(batch.total_net_pay || 0) < 0}
                                title={
                                  parseFloat(batch.total_gross_pay || 0) <= 0
                                    ? "Cannot submit: Total Gross must be > 0"
                                    : parseFloat(batch.total_net_pay || 0) < 0
                                    ? "Cannot submit: Total Net Pay cannot be negative"
                                    : "Submit and post mass GL journal entries"
                                }
                                className={`px-3 py-1 text-[10px] font-medium rounded transition ${
                                  parseFloat(batch.total_gross_pay || 0) <= 0 || parseFloat(batch.total_net_pay || 0) < 0
                                    ? "bg-stone-200 text-stone-400 cursor-not-allowed"
                                    : "bg-stone-900 hover:bg-stone-800 text-white"
                                }`}
                              >
                                Submit & Post GL
                              </button>
                            ) : (
                              <span className="text-emerald-600 font-medium text-[10px] flex items-center justify-end gap-1">
                                <CheckCircle2 className="w-3 h-3" /> Disbursed
                              </span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Individual Salary Slips */}
            <div className="bg-white rounded-xl border border-stone-200 shadow-sm overflow-hidden">
              <div className="p-4 border-b border-stone-200 flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-semibold text-stone-900">Individual Paystubs & Salary Slips</h3>
                  <p className="text-xs text-stone-500 mt-0.5">Itemized earnings, statutory tax withholdings, and net salary disbursement</p>
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-stone-50/75 border-b border-stone-200 text-stone-500">
                    <tr>
                      <th className="px-4 py-3 font-medium">Slip #</th>
                      <th className="px-4 py-3 font-medium">Period</th>
                      <th className="px-4 py-3 font-medium">LWP Days</th>
                      <th className="px-4 py-3 font-medium">Payment Days</th>
                      <th className="px-4 py-3 font-medium">Gross Pay</th>
                      <th className="px-4 py-3 font-medium">Deductions</th>
                      <th className="px-4 py-3 font-medium">Net Pay</th>
                      <th className="px-4 py-3 font-medium">Status</th>
                      <th className="px-4 py-3 font-medium text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-stone-100">
                    {salarySlips.map((slip) => (
                      <tr key={slip.slip_id} className="hover:bg-stone-50/50 transition">
                        <td className="px-4 py-3 font-mono font-medium text-stone-900">{slip.slip_number}</td>
                        <td className="px-4 py-3 text-stone-600">
                          {slip.start_date} → {slip.end_date}
                        </td>
                        <td className="px-4 py-3 text-rose-600 font-medium">{slip.leave_without_pay_days}d</td>
                        <td className="px-4 py-3 text-stone-700">{slip.payment_days}d</td>
                        <td className="px-4 py-3 font-mono text-stone-800">${parseFloat(slip.gross_pay || 0).toFixed(2)}</td>
                        <td className="px-4 py-3 font-mono text-rose-700">-${parseFloat(slip.total_deductions || 0).toFixed(2)}</td>
                        <td className="px-4 py-3 font-mono font-semibold text-emerald-700">${parseFloat(slip.net_pay || 0).toFixed(2)}</td>
                        <td className="px-4 py-3">
                          <span
                            className={`px-2 py-0.5 text-[10px] font-semibold rounded ${
                              slip.status === "SUBMITTED"
                                ? "bg-emerald-100 text-emerald-800"
                                : "bg-amber-100 text-amber-800"
                            }`}
                          >
                            {slip.status}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-right">
                          {slip.status === "DRAFT" ? (
                            <button
                              onClick={() => handleSubmitSlip(slip.slip_id)}
                              disabled={parseFloat(slip.gross_pay || 0) <= 0 || parseFloat(slip.net_pay || 0) < 0}
                              title={
                                parseFloat(slip.gross_pay || 0) <= 0
                                  ? "Cannot submit: Gross Pay must be > 0"
                                  : parseFloat(slip.net_pay || 0) < 0
                                  ? "Cannot submit: Net Pay cannot be negative"
                                  : "Submit to General Ledger"
                              }
                              className={`px-2.5 py-1 text-[10px] font-medium rounded transition ${
                                parseFloat(slip.gross_pay || 0) <= 0 || parseFloat(slip.net_pay || 0) < 0
                                  ? "bg-stone-200 text-stone-400 cursor-not-allowed"
                                  : "bg-emerald-600 hover:bg-emerald-700 text-white"
                              }`}
                            >
                              Submit GL
                            </button>
                          ) : (
                            <span className="text-stone-400 text-[10px]">Posted</span>
                          )}
                        </td>
                      </tr>
                    ))}
                    {salarySlips.length === 0 && (
                      <tr>
                        <td colSpan={9} className="text-center py-8 text-stone-400">
                          No salary slips generated yet. Click "Generate Monthly Payroll" to run batch payroll.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* ============================================================== */}
        {/* TAB 6: EXPENSES & ADVANCES */}
        {/* ============================================================== */}
        {activeTab === "expenses" && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Employee Advance Form */}
              <div className="bg-white p-5 rounded-xl border border-stone-200 shadow-sm space-y-4">
                <div className="border-b border-stone-100 pb-3">
                  <h2 className="text-sm font-semibold text-stone-900">Request Employee Advance / Loan</h2>
                  <p className="text-xs text-stone-500 mt-0.5">Disburse advance loans with automated salary slip EMI deduction</p>
                </div>

                <form onSubmit={handleCreateAdvance} className="space-y-3 text-xs">
                  <div>
                    <label className="block text-stone-600 font-medium mb-1">Employee</label>
                    <select
                      value={advEmpId}
                      onChange={(e) => setAdvEmpId(e.target.value)}
                      className="w-full px-3 py-2 border border-stone-200 rounded-lg bg-stone-50 text-stone-900 focus:outline-none focus:ring-1 focus:ring-stone-400"
                    >
                      {employees.map((e) => (
                        <option key={e.employee_id} value={e.employee_id}>
                          {e.employee_code} — {e.first_name} {e.last_name}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-stone-600 font-medium mb-1">Principal Amount ($)</label>
                      <input
                        type="number"
                        step="50"
                        value={advAmount}
                        onChange={(e) => setAdvAmount(e.target.value)}
                        className="w-full px-3 py-2 border border-stone-200 rounded-lg bg-stone-50 text-stone-900 focus:outline-none focus:ring-1 focus:ring-stone-400"
                        required
                      />
                    </div>
                    <div>
                      <label className="block text-stone-600 font-medium mb-1">Monthly EMI ($)</label>
                      <input
                        type="number"
                        step="25"
                        value={advMonthlyEmi}
                        onChange={(e) => setAdvMonthlyEmi(e.target.value)}
                        className="w-full px-3 py-2 border border-stone-200 rounded-lg bg-stone-50 text-stone-900 focus:outline-none focus:ring-1 focus:ring-stone-400"
                        required
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-stone-600 font-medium mb-1">Purpose / Description</label>
                    <input
                      type="text"
                      value={advPurpose}
                      onChange={(e) => setAdvPurpose(e.target.value)}
                      className="w-full px-3 py-2 border border-stone-200 rounded-lg bg-stone-50 text-stone-900 focus:outline-none focus:ring-1 focus:ring-stone-400"
                      required
                    />
                  </div>

                  <button
                    type="submit"
                    className="w-full py-2 bg-stone-900 hover:bg-stone-800 text-white rounded-lg font-medium transition"
                  >
                    Sanction Advance Request
                  </button>
                </form>
              </div>

              {/* Advance List & Disbursement */}
              <div className="bg-white rounded-xl border border-stone-200 shadow-sm overflow-hidden flex flex-col">
                <div className="p-4 border-b border-stone-200">
                  <h3 className="text-sm font-semibold text-stone-900">Active Employee Advances & Recovery</h3>
                </div>
                <div className="overflow-x-auto flex-1">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-stone-50/75 border-b border-stone-200 text-stone-500">
                      <tr>
                        <th className="px-4 py-3 font-medium">Advance #</th>
                        <th className="px-4 py-3 font-medium">Amount</th>
                        <th className="px-4 py-3 font-medium">Monthly EMI</th>
                        <th className="px-4 py-3 font-medium">Repaid</th>
                        <th className="px-4 py-3 font-medium">Status</th>
                        <th className="px-4 py-3 font-medium text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-stone-100">
                      {advances.map((adv) => (
                        <tr key={adv.advance_id} className="hover:bg-stone-50/50 transition">
                          <td className="px-4 py-3 font-mono font-medium text-stone-900">{adv.advance_number}</td>
                          <td className="px-4 py-3 font-mono text-stone-800">${parseFloat(adv.advance_amount || 0).toFixed(2)}</td>
                          <td className="px-4 py-3 font-mono text-stone-600">${parseFloat(adv.monthly_deduction_amount || 0).toFixed(2)}</td>
                          <td className="px-4 py-3 font-mono text-emerald-700">${parseFloat(adv.repaid_amount || 0).toFixed(2)}</td>
                          <td className="px-4 py-3">
                            <span
                              className={`px-2 py-0.5 text-[10px] font-semibold rounded ${
                                adv.status === "PAID"
                                  ? "bg-emerald-100 text-emerald-800"
                                  : adv.status === "REPAID"
                                  ? "bg-blue-100 text-blue-800"
                                  : "bg-amber-100 text-amber-800"
                              }`}
                            >
                              {adv.status}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-right">
                            {adv.status === "PENDING" ? (
                              <button
                                onClick={() => handleDisburseAdvance(adv.advance_id)}
                                className="px-2.5 py-1 text-[10px] font-medium bg-emerald-600 hover:bg-emerald-700 text-white rounded transition"
                              >
                                Disburse Payout
                              </button>
                            ) : (
                              <span className="text-stone-400 text-[10px]">Active</span>
                            )}
                          </td>
                        </tr>
                      ))}
                      {advances.length === 0 && (
                        <tr>
                          <td colSpan={6} className="text-center py-8 text-stone-400">
                            No employee advances issued.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>

            {/* Expense Claims Table with 1-Click GL Reimbursement */}
            <div className="bg-white rounded-xl border border-stone-200 shadow-sm overflow-hidden">
              <div className="p-4 border-b border-stone-200">
                <h3 className="text-sm font-semibold text-stone-900">Expense Claims & Operational Reimbursement</h3>
                <p className="text-xs text-stone-500 mt-0.5">Audited receipts with 1-click General Ledger bank reimbursement</p>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-stone-50/75 border-b border-stone-200 text-stone-500">
                    <tr>
                      <th className="px-4 py-3 font-medium">Claim #</th>
                      <th className="px-4 py-3 font-medium">Date</th>
                      <th className="px-4 py-3 font-medium">Merchant</th>
                      <th className="px-4 py-3 font-medium">Category</th>
                      <th className="px-4 py-3 font-medium">Amount</th>
                      <th className="px-4 py-3 font-medium">Status</th>
                      <th className="px-4 py-3 font-medium text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-stone-100">
                    {expenses.map((exp) => (
                      <tr key={exp.claim_id} className="hover:bg-stone-50/50 transition">
                        <td className="px-4 py-3 font-mono font-medium text-stone-900">{exp.claim_number}</td>
                        <td className="px-4 py-3 text-stone-600">{exp.claim_date}</td>
                        <td className="px-4 py-3 text-stone-800 font-medium">{exp.merchant_name}</td>
                        <td className="px-4 py-3">
                          <span className="px-2 py-0.5 text-[10px] bg-stone-100 text-stone-700 rounded font-medium">
                            {exp.category}
                          </span>
                        </td>
                        <td className="px-4 py-3 font-mono font-semibold text-stone-900">
                          ${parseFloat(exp.total_amount || 0).toFixed(2)} {exp.currency}
                        </td>
                        <td className="px-4 py-3">
                          <span
                            className={`px-2 py-0.5 text-[10px] font-semibold rounded ${
                              exp.status === "PAID"
                                ? "bg-emerald-100 text-emerald-800"
                                : exp.status === "AUTO_APPROVED" || exp.status === "APPROVED"
                                ? "bg-blue-100 text-blue-800"
                                : "bg-amber-100 text-amber-800"
                            }`}
                          >
                            {exp.status}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-right">
                          {exp.status !== "PAID" ? (
                            <button
                              onClick={() => handleReimburseExpense(exp.claim_id)}
                              className="px-2.5 py-1 text-[10px] font-medium bg-stone-900 hover:bg-stone-800 text-white rounded transition"
                            >
                              Reimburse (GL)
                            </button>
                          ) : (
                            <span className="text-emerald-600 text-[10px] font-medium flex items-center justify-end gap-1">
                              <CheckCircle2 className="w-3 h-3" /> Reimbursed
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                    {expenses.length === 0 && (
                      <tr>
                        <td colSpan={7} className="text-center py-8 text-stone-400">
                          No expense claims logged.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Modal: New Employee */}
      {showEmpModal && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl border border-stone-200 shadow-xl max-w-md w-full p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-stone-100 pb-3">
              <div>
                <h3 className="text-sm font-bold text-stone-900">Add New Workforce Employee</h3>
                <p className="text-xs text-stone-500 mt-0.5">Register staff with corporate credentials</p>
              </div>
              <button onClick={() => setShowEmpModal(false)} className="text-stone-400 hover:text-stone-700">
                ✕
              </button>
            </div>

            {empModalError && (
              <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg text-rose-700 text-xs flex items-start gap-2">
                <AlertCircle className="w-4 h-4 shrink-0 mt-0.5 text-rose-600" />
                <div className="flex-1">
                  <p className="font-semibold">Employee Creation Error</p>
                  <p className="mt-0.5">{empModalError}</p>
                </div>
              </div>
            )}

            <form onSubmit={handleCreateEmployee} className="space-y-3 text-xs">
              <div>
                <label className="block text-stone-600 font-medium mb-1">Employee Code</label>
                <input
                  type="text"
                  placeholder="EMP-ENG-001"
                  value={newEmpCode}
                  onChange={(e) => setNewEmpCode(e.target.value)}
                  className="w-full px-3 py-2 border border-stone-200 rounded-lg bg-stone-50 text-stone-900 focus:outline-none focus:ring-1 focus:ring-stone-400"
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-stone-600 font-medium mb-1">First Name</label>
                  <input
                    type="text"
                    placeholder="Alan"
                    value={newEmpFirstName}
                    onChange={(e) => setNewEmpFirstName(e.target.value)}
                    className="w-full px-3 py-2 border border-stone-200 rounded-lg bg-stone-50 text-stone-900 focus:outline-none focus:ring-1 focus:ring-stone-400"
                    required
                  />
                </div>
                <div>
                  <label className="block text-stone-600 font-medium mb-1">Last Name</label>
                  <input
                    type="text"
                    placeholder="Turing"
                    value={newEmpLastName}
                    onChange={(e) => setNewEmpLastName(e.target.value)}
                    className="w-full px-3 py-2 border border-stone-200 rounded-lg bg-stone-50 text-stone-900 focus:outline-none focus:ring-1 focus:ring-stone-400"
                    required
                  />
                </div>
              </div>

              <div>
                <label className="block text-stone-600 font-medium mb-1">Corporate Email</label>
                <input
                  type="email"
                  placeholder="alan.turing@company.org"
                  value={newEmpEmail}
                  onChange={(e) => setNewEmpEmail(e.target.value)}
                  className="w-full px-3 py-2 border border-stone-200 rounded-lg bg-stone-50 text-stone-900 focus:outline-none focus:ring-1 focus:ring-stone-400"
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="text-stone-600 font-medium">Department</label>
                    <button
                      type="button"
                      onClick={() => setShowDeptModal(true)}
                      className="text-[10px] text-stone-700 hover:text-stone-900 font-semibold underline"
                    >
                      + New Dept
                    </button>
                  </div>
                  <select
                    value={newEmpDeptId}
                    onChange={(e) => setNewEmpDeptId(e.target.value)}
                    className="w-full px-3 py-2 border border-stone-200 rounded-lg bg-stone-50 text-stone-900 focus:outline-none focus:ring-1 focus:ring-stone-400"
                  >
                    <option value="">{departments.length === 0 ? "No depts yet (+ New Dept)" : "Select Department"}</option>
                    {departments.map((d) => (
                      <option key={d.department_id} value={d.department_id}>
                        {d.department_name}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="text-stone-600 font-medium">Designation</label>
                    <button
                      type="button"
                      onClick={() => setShowDesigModal(true)}
                      className="text-[10px] text-stone-700 hover:text-stone-900 font-semibold underline"
                    >
                      + New Desig
                    </button>
                  </div>
                  <select
                    value={newEmpDesigId}
                    onChange={(e) => setNewEmpDesigId(e.target.value)}
                    className="w-full px-3 py-2 border border-stone-200 rounded-lg bg-stone-50 text-stone-900 focus:outline-none focus:ring-1 focus:ring-stone-400"
                  >
                    <option value="">{designations.length === 0 ? "No roles yet (+ New Desig)" : "Select Designation"}</option>
                    {designations.map((d) => (
                      <option key={d.designation_id} value={d.designation_id}>
                        {d.designation_name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-stone-600 font-medium mb-1">Gender</label>
                  <select
                    value={newEmpGender}
                    onChange={(e) => setNewEmpGender(e.target.value)}
                    className="w-full px-3 py-2 border border-stone-200 rounded-lg bg-stone-50 text-stone-900 focus:outline-none focus:ring-1 focus:ring-stone-400"
                  >
                    <option value="MALE">Male</option>
                    <option value="FEMALE">Female</option>
                    <option value="OTHER">Other</option>
                  </select>
                </div>
                <div>
                  <label className="block text-stone-600 font-medium mb-1">Date of Joining</label>
                  <input
                    type="date"
                    value={newEmpDoj}
                    onChange={(e) => setNewEmpDoj(e.target.value)}
                    className="w-full px-3 py-2 border border-stone-200 rounded-lg bg-stone-50 text-stone-900 focus:outline-none focus:ring-1 focus:ring-stone-400"
                  />
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowEmpModal(false)}
                  className="px-4 py-2 border border-stone-200 hover:bg-stone-50 text-stone-700 rounded-lg transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-stone-900 hover:bg-stone-800 text-white rounded-lg transition"
                >
                  Create Record
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: New Department (Problem 2 Fix) */}
      {showDeptModal && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl border border-stone-200 shadow-xl max-w-sm w-full p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-stone-100 pb-3">
              <div>
                <h3 className="text-sm font-bold text-stone-900">Add Department</h3>
                <p className="text-xs text-stone-500 mt-0.5">Create corporate business unit or department</p>
              </div>
              <button onClick={() => setShowDeptModal(false)} className="text-stone-400 hover:text-stone-700">
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateDepartment} className="space-y-3 text-xs">
              <div>
                <label className="block text-stone-600 font-medium mb-1">Department Name</label>
                <input
                  type="text"
                  placeholder="e.g. Engineering, Sales, Operations"
                  value={newDeptName}
                  onChange={(e) => setNewDeptName(e.target.value)}
                  className="w-full px-3 py-2 border border-stone-200 rounded-lg bg-stone-50 text-stone-900 focus:outline-none focus:ring-1 focus:ring-stone-400"
                  required
                  autoFocus
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowDeptModal(false)}
                  className="px-3.5 py-1.5 border border-stone-200 hover:bg-stone-50 text-stone-700 rounded-lg transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-3.5 py-1.5 bg-stone-900 hover:bg-stone-800 text-white rounded-lg transition font-medium"
                >
                  Create Department
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: New Designation (Problem 2 Fix) */}
      {showDesigModal && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl border border-stone-200 shadow-xl max-w-sm w-full p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-stone-100 pb-3">
              <div>
                <h3 className="text-sm font-bold text-stone-900">Add Designation</h3>
                <p className="text-xs text-stone-500 mt-0.5">Register job title and functional responsibility</p>
              </div>
              <button onClick={() => setShowDesigModal(false)} className="text-stone-400 hover:text-stone-700">
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateDesignation} className="space-y-3 text-xs">
              <div>
                <label className="block text-stone-600 font-medium mb-1">Designation / Role Title</label>
                <input
                  type="text"
                  placeholder="e.g. Senior Software Engineer"
                  value={newDesigName}
                  onChange={(e) => setNewDesigName(e.target.value)}
                  className="w-full px-3 py-2 border border-stone-200 rounded-lg bg-stone-50 text-stone-900 focus:outline-none focus:ring-1 focus:ring-stone-400"
                  required
                  autoFocus
                />
              </div>

              <div>
                <label className="block text-stone-600 font-medium mb-1">Description (Optional)</label>
                <input
                  type="text"
                  placeholder="e.g. Lead engineering and architecture"
                  value={newDesigDesc}
                  onChange={(e) => setNewDesigDesc(e.target.value)}
                  className="w-full px-3 py-2 border border-stone-200 rounded-lg bg-stone-50 text-stone-900 focus:outline-none focus:ring-1 focus:ring-stone-400"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowDesigModal(false)}
                  className="px-3.5 py-1.5 border border-stone-200 hover:bg-stone-50 text-stone-700 rounded-lg transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-3.5 py-1.5 bg-stone-900 hover:bg-stone-800 text-white rounded-lg transition font-medium"
                >
                  Create Designation
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Start Onboarding (Problem 3 Fix) */}
      {showOnboardingModal && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl border border-stone-200 shadow-xl max-w-md w-full p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-stone-100 pb-3">
              <div>
                <h3 className="text-sm font-bold text-stone-900">Start Employee Onboarding</h3>
                <p className="text-xs text-stone-500 mt-0.5">Initialize checklist and readiness tracking</p>
              </div>
              <button onClick={() => setShowOnboardingModal(false)} className="text-stone-400 hover:text-stone-700">
                ✕
              </button>
            </div>

            <form onSubmit={handleStartOnboarding} className="space-y-3 text-xs">
              <div>
                <label className="block text-stone-600 font-medium mb-1">Employee</label>
                <select
                  value={onbEmpId}
                  onChange={(e) => setOnbEmpId(e.target.value)}
                  className="w-full px-3 py-2 border border-stone-200 rounded-lg bg-stone-50 text-stone-900 focus:outline-none focus:ring-1 focus:ring-stone-400"
                  required
                >
                  {employees.map((e) => (
                    <option key={e.employee_id} value={e.employee_id}>
                      {e.employee_code} — {e.first_name} {e.last_name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-stone-600 font-medium mb-1">Applicant / Candidate Name</label>
                <input
                  type="text"
                  placeholder="e.g. John Doe"
                  value={onbApplicantName}
                  onChange={(e) => setOnbApplicantName(e.target.value)}
                  className="w-full px-3 py-2 border border-stone-200 rounded-lg bg-stone-50 text-stone-900 focus:outline-none focus:ring-1 focus:ring-stone-400"
                />
              </div>

              <div>
                <label className="block text-stone-600 font-medium mb-1">Date of Joining</label>
                <input
                  type="date"
                  value={onbJoiningDate}
                  onChange={(e) => setOnbJoiningDate(e.target.value)}
                  className="w-full px-3 py-2 border border-stone-200 rounded-lg bg-stone-50 text-stone-900 focus:outline-none focus:ring-1 focus:ring-stone-400"
                  required
                />
              </div>

              <div>
                <label className="block text-stone-600 font-medium mb-1">
                  Onboarding Checklist Tasks (One per line)
                </label>
                <textarea
                  rows={4}
                  value={onbTaskInput}
                  onChange={(e) => setOnbTaskInput(e.target.value)}
                  className="w-full px-3 py-2 border border-stone-200 rounded-lg bg-stone-50 text-stone-900 focus:outline-none focus:ring-1 focus:ring-stone-400 font-mono text-[11px]"
                  required
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowOnboardingModal(false)}
                  className="px-4 py-2 border border-stone-200 hover:bg-stone-50 text-stone-700 rounded-lg transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-emerald-700 hover:bg-emerald-800 text-white rounded-lg transition font-medium"
                >
                  Initiate Onboarding
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Start Separation (Problem 3 Fix) */}
      {showSeparationModal && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl border border-stone-200 shadow-xl max-w-md w-full p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-stone-100 pb-3">
              <div>
                <h3 className="text-sm font-bold text-stone-900">Start Employee Separation</h3>
                <p className="text-xs text-stone-500 mt-0.5">Offboarding checklist, asset recovery, and exit clearance</p>
              </div>
              <button onClick={() => setShowSeparationModal(false)} className="text-stone-400 hover:text-stone-700">
                ✕
              </button>
            </div>

            <form onSubmit={handleStartSeparation} className="space-y-3 text-xs">
              <div>
                <label className="block text-stone-600 font-medium mb-1">Employee</label>
                <select
                  value={sepEmpId}
                  onChange={(e) => setSepEmpId(e.target.value)}
                  className="w-full px-3 py-2 border border-stone-200 rounded-lg bg-stone-50 text-stone-900 focus:outline-none focus:ring-1 focus:ring-stone-400"
                  required
                >
                  {employees.filter((e) => e.status === "ACTIVE").map((e) => (
                    <option key={e.employee_id} value={e.employee_id}>
                      {e.employee_code} — {e.first_name} {e.last_name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-stone-600 font-medium mb-1">Resignation Date</label>
                <input
                  type="date"
                  value={sepResignDate}
                  onChange={(e) => setSepResignDate(e.target.value)}
                  className="w-full px-3 py-2 border border-stone-200 rounded-lg bg-stone-50 text-stone-900 focus:outline-none focus:ring-1 focus:ring-stone-400"
                  required
                />
              </div>

              <div>
                <label className="block text-stone-600 font-medium mb-1">Exit Interview Notes</label>
                <textarea
                  rows={2}
                  value={sepNotes}
                  onChange={(e) => setSepNotes(e.target.value)}
                  className="w-full px-3 py-2 border border-stone-200 rounded-lg bg-stone-50 text-stone-900 focus:outline-none focus:ring-1 focus:ring-stone-400"
                  placeholder="Reason for resignation, feedback, handover notes..."
                />
              </div>

              <div>
                <label className="block text-stone-600 font-medium mb-1">
                  Clearance Checklist Tasks (One per line)
                </label>
                <textarea
                  rows={4}
                  value={sepTaskInput}
                  onChange={(e) => setSepTaskInput(e.target.value)}
                  className="w-full px-3 py-2 border border-stone-200 rounded-lg bg-stone-50 text-stone-900 focus:outline-none focus:ring-1 focus:ring-stone-400 font-mono text-[11px]"
                  required
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowSeparationModal(false)}
                  className="px-4 py-2 border border-stone-200 hover:bg-stone-50 text-stone-700 rounded-lg transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-stone-900 hover:bg-stone-800 text-white rounded-lg transition font-medium"
                >
                  Initiate Separation
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: New Leave Type */}
      {showLeaveTypeModal && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl border border-stone-200 shadow-xl max-w-sm w-full p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-stone-100 pb-3">
              <div>
                <h3 className="text-sm font-bold text-stone-900">Add New Leave Type</h3>
                <p className="text-xs text-stone-500 mt-0.5">Configure entitlement quota & policy</p>
              </div>
              <button onClick={() => setShowLeaveTypeModal(false)} className="text-stone-400 hover:text-stone-700">
                ✕
              </button>
            </div>

            {leaveModalError && (
              <div className="p-2.5 bg-rose-50 border border-rose-200 rounded-lg text-rose-700 text-xs flex items-start gap-2">
                <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                <span className="flex-1">{leaveModalError}</span>
              </div>
            )}

            <form onSubmit={handleCreateLeaveType} className="space-y-3 text-xs">
              <div>
                <label className="block text-stone-600 font-medium mb-1">Leave Type Name</label>
                <input
                  type="text"
                  placeholder="e.g. Parental Leave, Study Leave"
                  value={newLeaveTypeName}
                  onChange={(e) => setNewLeaveTypeName(e.target.value)}
                  className="w-full px-3 py-2 border border-stone-200 rounded-lg bg-stone-50 text-stone-900 focus:outline-none focus:ring-1 focus:ring-stone-400"
                  required
                  autoFocus
                />
              </div>

              <div>
                <label className="block text-stone-600 font-medium mb-1">Max Annual Days</label>
                <input
                  type="number"
                  min="0"
                  value={newLeaveTypeMaxDays}
                  onChange={(e) => setNewLeaveTypeMaxDays(e.target.value)}
                  className="w-full px-3 py-2 border border-stone-200 rounded-lg bg-stone-50 text-stone-900 focus:outline-none focus:ring-1 focus:ring-stone-400"
                  required
                />
              </div>

              <div className="space-y-2 pt-1">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={newLeaveTypeCarryForward}
                    onChange={(e) => setNewLeaveTypeCarryForward(e.target.checked)}
                    className="rounded border-stone-300 text-stone-900 focus:ring-stone-400"
                  />
                  <span className="text-stone-700">Allow Carry Forward to next year</span>
                </label>

                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={newLeaveTypeIsLwp}
                    onChange={(e) => setNewLeaveTypeIsLwp(e.target.checked)}
                    className="rounded border-stone-300 text-stone-900 focus:ring-stone-400"
                  />
                  <span className="text-stone-700">Leave Without Pay (LWP / Unpaid)</span>
                </label>
              </div>

              <div className="flex justify-end gap-2 pt-3">
                <button
                  type="button"
                  onClick={() => setShowLeaveTypeModal(false)}
                  className="px-3.5 py-1.5 border border-stone-200 hover:bg-stone-50 text-stone-700 rounded-lg transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-3.5 py-1.5 bg-stone-900 hover:bg-stone-800 text-white rounded-lg transition font-medium"
                >
                  Create Leave Type
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
