"use client";

import { useEffect, useState } from "react";
import {
  Briefcase,
  Plus,
  RefreshCw,
  Search,
  CheckCircle2,
  Clock,
  DollarSign,
  Users,
  CheckSquare,
  ArrowRight,
  TrendingUp,
  X,
  Calendar,
  AlertCircle,
  FolderKanban,
} from "lucide-react";
import { api } from "@/lib/api";

type TabType = "projects" | "timesheets";

export default function ProjectsPage() {
  const [activeTab, setActiveTab] = useState<TabType>("projects");
  const [projects, setProjects] = useState<any[]>([]);
  const [timesheets, setTimesheets] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  // Detailed Project View Drawer
  const [selectedProject, setSelectedProject] = useState<any | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  // Modals
  const [showProjectModal, setShowProjectModal] = useState(false);
  const [showTaskModal, setShowTaskModal] = useState(false);
  const [showTimesheetModal, setShowTimesheetModal] = useState(false);

  // Form states
  const [formProj, setFormProj] = useState({
    project_code: "",
    project_name: "",
    customer_name: "",
    start_date: new Date().toISOString().split("T")[0],
    estimated_cost: "50000.00",
    notes: "",
  });

  const [formTask, setFormTask] = useState({
    task_title: "",
    task_description: "",
    priority: "MEDIUM",
    estimated_hours: "20.00",
    assigned_to_name: "Sarah Chen (Lead Engineer)",
  });

  const [formTimesheet, setFormTimesheet] = useState({
    timesheet_number: "",
    employee_name: "Sarah Chen",
    activity_type: "ENGINEERING",
    work_date: new Date().toISOString().split("T")[0],
    hours: "8.00",
    billing_rate: "150.00",
    costing_rate: "75.00",
    is_billable: true,
    task_id: "",
    notes: "",
  });

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [pData, tData] = await Promise.all([
        api.getProjects(),
        api.getProjectTimesheets(),
      ]);
      setProjects(pData);
      setTimesheets(tData);
    } catch (err: any) {
      setError(err.message || "Failed to load projects data.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const openProjectDetail = async (projectId: string) => {
    setLoadingDetail(true);
    try {
      const data = await api.getProject(projectId);
      setSelectedProject(data);
    } catch (err: any) {
      alert("Failed to load project details: " + err.message);
    } finally {
      setLoadingDetail(false);
    }
  };

  const handleCreateProject = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.createProject({
        ...formProj,
        estimated_cost: parseFloat(formProj.estimated_cost),
      });
      setShowProjectModal(false);
      setFormProj({
        project_code: "",
        project_name: "",
        customer_name: "",
        start_date: new Date().toISOString().split("T")[0],
        estimated_cost: "50000.00",
        notes: "",
      });
      await loadData();
    } catch (err: any) {
      alert("Error creating project: " + err.message);
    }
  };

  const handleCreateTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedProject) return;
    try {
      await api.createProjectTask(selectedProject.project_id, {
        ...formTask,
        estimated_hours: parseFloat(formTask.estimated_hours),
      });
      setShowTaskModal(false);
      setFormTask({
        task_title: "",
        task_description: "",
        priority: "MEDIUM",
        estimated_hours: "20.00",
        assigned_to_name: "Sarah Chen (Lead Engineer)",
      });
      await openProjectDetail(selectedProject.project_id);
      await loadData();
    } catch (err: any) {
      alert("Error creating task: " + err.message);
    }
  };

  const handleCompleteTask = async (taskId: string) => {
    try {
      await api.updateProjectTask(taskId, { status: "COMPLETED" });
      if (selectedProject) {
        await openProjectDetail(selectedProject.project_id);
      }
      await loadData();
    } catch (err: any) {
      alert("Error completing task: " + err.message);
    }
  };

  const handleLogTimesheet = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedProject) return;
    try {
      // Mock random employee ID for testing
      const empId = "00000000-0000-0000-0000-000000000001";
      const tsNum = formTimesheet.timesheet_number || `TS-${Date.now().toString().slice(-6)}`;
      await api.logProjectTimesheet(selectedProject.project_id, {
        timesheet_number: tsNum,
        employee_id: empId,
        employee_name: formTimesheet.employee_name,
        activity_type: formTimesheet.activity_type,
        work_date: formTimesheet.work_date,
        hours: parseFloat(formTimesheet.hours),
        billing_rate: parseFloat(formTimesheet.billing_rate),
        costing_rate: parseFloat(formTimesheet.costing_rate),
        is_billable: formTimesheet.is_billable,
        task_id: formTimesheet.task_id || undefined,
        notes: formTimesheet.notes,
      });
      setShowTimesheetModal(false);
      await openProjectDetail(selectedProject.project_id);
      await loadData();
    } catch (err: any) {
      alert("Error logging timesheet: " + err.message);
    }
  };

  // Metrics
  const totalProjects = projects.length;
  const totalEstimated = projects.reduce((acc, p) => acc + (p.estimated_cost || 0), 0);
  const totalActual = projects.reduce((acc, p) => acc + (p.actual_cost || 0), 0);
  const totalBilled = projects.reduce((acc, p) => acc + (p.total_billed_amount || 0), 0);
  const totalHours = timesheets.reduce((acc, t) => acc + (t.hours || 0), 0);

  const filteredProjects = projects.filter(
    (p) =>
      p.project_code.toLowerCase().includes(search.toLowerCase()) ||
      p.project_name.toLowerCase().includes(search.toLowerCase()) ||
      (p.customer_name && p.customer_name.toLowerCase().includes(search.toLowerCase()))
  );

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-stone-900 text-white flex items-center justify-center shadow-sm">
              <Briefcase className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-2xl font-semibold text-stone-900 tracking-tight">Projects & Timesheets</h1>
              <p className="text-sm text-stone-500">
                Project delivery tracking, work breakdowns, discrete tasks & billable labor cost rollups.
              </p>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={loadData}
            disabled={loading}
            className="p-2.5 text-stone-600 hover:text-stone-900 hover:bg-stone-100 rounded-lg border border-stone-200 transition-colors"
            title="Refresh"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          </button>
          <button
            onClick={() => setShowProjectModal(true)}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-stone-900 hover:bg-stone-800 rounded-lg shadow-sm"
          >
            <Plus className="w-4 h-4" />
            New Project
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white border border-stone-200/80 rounded-xl p-5 shadow-sm">
          <div className="text-xs font-medium text-stone-500 uppercase tracking-wider">Active Projects</div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-stone-900">{totalProjects}</span>
            <span className="text-xs text-stone-500">Engagements</span>
          </div>
        </div>
        <div className="bg-white border border-stone-200/80 rounded-xl p-5 shadow-sm">
          <div className="text-xs font-medium text-stone-500 uppercase tracking-wider">Estimated Budget</div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-stone-900">${totalEstimated.toLocaleString("en-US", { minimumFractionDigits: 2 })}</span>
          </div>
        </div>
        <div className="bg-white border border-stone-200/80 rounded-xl p-5 shadow-sm">
          <div className="text-xs font-medium text-stone-500 uppercase tracking-wider">Actual Labor Cost</div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-amber-700">${totalActual.toLocaleString("en-US", { minimumFractionDigits: 2 })}</span>
          </div>
        </div>
        <div className="bg-white border border-stone-200/80 rounded-xl p-5 shadow-sm">
          <div className="text-xs font-medium text-stone-500 uppercase tracking-wider">Total Billed & Hours</div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-emerald-700">${totalBilled.toLocaleString("en-US", { minimumFractionDigits: 2 })}</span>
            <span className="text-xs text-stone-500">({totalHours}h)</span>
          </div>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="flex border-b border-stone-200 gap-6">
        <button
          onClick={() => setActiveTab("projects")}
          className={`pb-3 text-sm font-medium border-b-2 transition-colors ${
            activeTab === "projects"
              ? "border-stone-900 text-stone-900"
              : "border-transparent text-stone-500 hover:text-stone-800"
          }`}
        >
          Projects Master ({projects.length})
        </button>
        <button
          onClick={() => setActiveTab("timesheets")}
          className={`pb-3 text-sm font-medium border-b-2 transition-colors ${
            activeTab === "timesheets"
              ? "border-stone-900 text-stone-900"
              : "border-transparent text-stone-500 hover:text-stone-800"
          }`}
        >
          Timesheets ({timesheets.length})
        </button>
      </div>

      {/* Tab 1: Projects Master */}
      {activeTab === "projects" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between gap-4">
            <div className="relative flex-1 max-w-sm">
              <Search className="absolute left-3 top-2.5 w-4 h-4 text-stone-400" />
              <input
                type="text"
                placeholder="Search projects by code, title, customer..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full pl-9 pr-4 py-2 text-sm bg-white border border-stone-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-stone-400"
              />
            </div>
          </div>

          <div className="bg-white border border-stone-200/80 rounded-xl overflow-hidden shadow-sm">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm text-stone-600">
                <thead className="bg-stone-50/75 border-b border-stone-200 text-xs font-semibold text-stone-600 uppercase tracking-wider">
                  <tr>
                    <th className="px-6 py-3.5">Code</th>
                    <th className="px-6 py-3.5">Project Title</th>
                    <th className="px-6 py-3.5">Customer</th>
                    <th className="px-6 py-3.5 text-center">Progress</th>
                    <th className="px-6 py-3.5 text-right">Estimated</th>
                    <th className="px-6 py-3.5 text-right">Actual Cost</th>
                    <th className="px-6 py-3.5 text-right">Billed</th>
                    <th className="px-6 py-3.5 text-center">Status</th>
                    <th className="px-6 py-3.5 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-200/60">
                  {filteredProjects.length === 0 ? (
                    <tr>
                      <td colSpan={9} className="px-6 py-12 text-center text-stone-500">
                        No projects found. Click &quot;New Project&quot; to begin.
                      </td>
                    </tr>
                  ) : (
                    filteredProjects.map((proj) => (
                      <tr key={proj.project_id} className="hover:bg-stone-50/50 transition-colors">
                        <td className="px-6 py-4 font-mono font-medium text-stone-900">{proj.project_code}</td>
                        <td className="px-6 py-4 font-medium text-stone-900">{proj.project_name}</td>
                        <td className="px-6 py-4 text-stone-600">{proj.customer_name || "Internal"}</td>
                        <td className="px-6 py-4">
                          <div className="w-32 mx-auto space-y-1">
                            <div className="flex justify-between text-2xs font-medium text-stone-600">
                              <span>{proj.percent_complete}%</span>
                              <span>{proj.task_count} tasks</span>
                            </div>
                            <div className="w-full bg-stone-100 rounded-full h-1.5 overflow-hidden">
                              <div
                                className={`h-full rounded-full ${
                                  proj.percent_complete >= 100
                                    ? "bg-emerald-500"
                                    : proj.percent_complete > 50
                                    ? "bg-blue-500"
                                    : "bg-amber-500"
                                }`}
                                style={{ width: `${Math.min(100, proj.percent_complete)}%` }}
                              />
                            </div>
                          </div>
                        </td>
                        <td className="px-6 py-4 text-right font-medium text-stone-900">
                          ${proj.estimated_cost?.toLocaleString("en-US", { minimumFractionDigits: 2 })}
                        </td>
                        <td className="px-6 py-4 text-right font-medium text-amber-700">
                          ${proj.actual_cost?.toLocaleString("en-US", { minimumFractionDigits: 2 })}
                        </td>
                        <td className="px-6 py-4 text-right font-medium text-emerald-700">
                          ${proj.total_billed_amount?.toLocaleString("en-US", { minimumFractionDigits: 2 })}
                        </td>
                        <td className="px-6 py-4 text-center">
                          <span
                            className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${
                              proj.status === "COMPLETED"
                                ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                                : "bg-blue-50 text-blue-700 border border-blue-200"
                            }`}
                          >
                            {proj.status}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-right">
                          <button
                            onClick={() => openProjectDetail(proj.project_id)}
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-stone-700 bg-stone-100 hover:bg-stone-200 rounded-lg transition-colors"
                          >
                            Work Items & Tasks
                            <ArrowRight className="w-3.5 h-3.5" />
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Tab 2: Timesheets */}
      {activeTab === "timesheets" && (
        <div className="bg-white border border-stone-200/80 rounded-xl overflow-hidden shadow-sm">
          <table className="w-full text-left text-sm text-stone-600">
            <thead className="bg-stone-50/75 border-b border-stone-200 text-xs font-semibold text-stone-600 uppercase tracking-wider">
              <tr>
                <th className="px-6 py-3.5">Timesheet #</th>
                <th className="px-6 py-3.5">Employee</th>
                <th className="px-6 py-3.5">Date</th>
                <th className="px-6 py-3.5">Activity</th>
                <th className="px-6 py-3.5 text-right">Hours</th>
                <th className="px-6 py-3.5 text-right">Cost Amount</th>
                <th className="px-6 py-3.5 text-right">Billing Amount</th>
                <th className="px-6 py-3.5 text-center">Billable</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-stone-200/60">
              {timesheets.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-6 py-12 text-center text-stone-500">
                    No labor timesheets logged yet.
                  </td>
                </tr>
              ) : (
                timesheets.map((ts) => (
                  <tr key={ts.timesheet_id} className="hover:bg-stone-50/50">
                    <td className="px-6 py-4 font-mono font-medium text-stone-900">{ts.timesheet_number}</td>
                    <td className="px-6 py-4 font-medium text-stone-900">{ts.employee_name || "—"}</td>
                    <td className="px-6 py-4 text-stone-500">{ts.work_date}</td>
                    <td className="px-6 py-4 font-mono text-xs">{ts.activity_type}</td>
                    <td className="px-6 py-4 text-right font-medium text-stone-900">{ts.hours}h</td>
                    <td className="px-6 py-4 text-right text-stone-700">
                      ${ts.costing_amount?.toLocaleString("en-US", { minimumFractionDigits: 2 })}
                    </td>
                    <td className="px-6 py-4 text-right font-medium text-emerald-700">
                      ${ts.billing_amount?.toLocaleString("en-US", { minimumFractionDigits: 2 })}
                    </td>
                    <td className="px-6 py-4 text-center">
                      {ts.is_billable ? (
                        <span className="text-emerald-700 font-semibold text-xs">YES</span>
                      ) : (
                        <span className="text-stone-400 text-xs">NO</span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Project Details Drawer */}
      {selectedProject && (
        <div className="fixed inset-0 z-50 bg-stone-900/40 backdrop-blur-sm flex justify-end">
          <div className="bg-white w-full max-w-2xl h-full shadow-2xl p-6 overflow-y-auto space-y-6">
            <div className="flex items-center justify-between pb-4 border-b border-stone-200">
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs px-2 py-0.5 rounded bg-stone-100 text-stone-700 font-semibold">
                    {selectedProject.project_code}
                  </span>
                  <span
                    className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${
                      selectedProject.status === "COMPLETED"
                        ? "bg-emerald-50 text-emerald-700"
                        : "bg-blue-50 text-blue-700"
                    }`}
                  >
                    {selectedProject.status}
                  </span>
                </div>
                <h2 className="text-xl font-bold text-stone-900 mt-1">{selectedProject.project_name}</h2>
                <p className="text-xs text-stone-500 mt-0.5">Customer: {selectedProject.customer_name || "Internal"}</p>
              </div>
              <button
                onClick={() => setSelectedProject(null)}
                className="p-2 text-stone-400 hover:text-stone-600 rounded-lg hover:bg-stone-100"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Quick Actions */}
            <div className="flex gap-2.5">
              <button
                onClick={() => setShowTaskModal(true)}
                className="flex-1 py-2 text-xs font-medium text-stone-700 bg-stone-50 border border-stone-200 hover:bg-stone-100 rounded-lg flex items-center justify-center gap-1.5"
              >
                <Plus className="w-3.5 h-3.5" />
                Add Discrete Task
              </button>
              <button
                onClick={() => setShowTimesheetModal(true)}
                className="flex-1 py-2 text-xs font-medium text-stone-700 bg-stone-50 border border-stone-200 hover:bg-stone-100 rounded-lg flex items-center justify-center gap-1.5"
              >
                <Clock className="w-3.5 h-3.5" />
                Log Labor Hours
              </button>
            </div>

            {/* Progress & Financial Bar */}
            <div className="bg-stone-50 rounded-xl p-4 border border-stone-200 space-y-3">
              <div className="flex justify-between items-baseline">
                <span className="text-xs font-medium text-stone-700">Project Completion</span>
                <span className="text-sm font-bold text-stone-900">{selectedProject.percent_complete}%</span>
              </div>
              <div className="w-full bg-stone-200 rounded-full h-2 overflow-hidden">
                <div
                  className="bg-emerald-600 h-full rounded-full transition-all"
                  style={{ width: `${Math.min(100, selectedProject.percent_complete)}%` }}
                />
              </div>
              <div className="grid grid-cols-3 gap-2 pt-2 border-t border-stone-200 text-xs">
                <div>
                  <span className="text-stone-500">Estimated Cost:</span>
                  <p className="font-semibold text-stone-900">${selectedProject.estimated_cost?.toLocaleString("en-US", { minimumFractionDigits: 2 })}</p>
                </div>
                <div>
                  <span className="text-stone-500">Actual Labor Cost:</span>
                  <p className="font-semibold text-amber-700">${selectedProject.actual_cost?.toLocaleString("en-US", { minimumFractionDigits: 2 })}</p>
                </div>
                <div>
                  <span className="text-stone-500">Total Billed:</span>
                  <p className="font-semibold text-emerald-700">${selectedProject.total_billed_amount?.toLocaleString("en-US", { minimumFractionDigits: 2 })}</p>
                </div>
              </div>
            </div>

            {/* Tasks Work Items */}
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <h3 className="text-sm font-semibold text-stone-900">Discrete Tasks ({selectedProject.tasks?.length || 0})</h3>
              </div>
              {selectedProject.tasks?.length === 0 ? (
                <p className="text-xs text-stone-500 italic">No tasks created yet.</p>
              ) : (
                <div className="space-y-2">
                  {selectedProject.tasks?.map((t: any) => (
                    <div
                      key={t.task_id}
                      className="border border-stone-200 rounded-lg p-3 text-xs flex items-center justify-between hover:bg-stone-50"
                    >
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span
                            className={`px-1.5 py-0.5 rounded text-2xs font-semibold ${
                              t.priority === "URGENT"
                                ? "bg-rose-100 text-rose-700"
                                : t.priority === "HIGH"
                                ? "bg-amber-100 text-amber-700"
                                : "bg-stone-100 text-stone-700"
                            }`}
                          >
                            {t.priority}
                          </span>
                          <span className="font-medium text-stone-900">{t.task_title}</span>
                        </div>
                        <div className="text-stone-500 flex gap-3 text-2xs">
                          <span>Assigned: {t.assigned_to_name || "Unassigned"}</span>
                          <span>Est: {t.estimated_hours}h / Act: {t.actual_hours}h</span>
                        </div>
                      </div>
                      <div>
                        {t.status === "COMPLETED" ? (
                          <span className="inline-flex items-center gap-1 text-emerald-700 font-semibold text-2xs">
                            <CheckCircle2 className="w-3.5 h-3.5" /> DONE
                          </span>
                        ) : (
                          <button
                            onClick={() => handleCompleteTask(t.task_id)}
                            className="px-2.5 py-1 text-2xs font-medium text-stone-700 bg-stone-100 hover:bg-emerald-50 hover:text-emerald-700 rounded border border-stone-200 transition-colors"
                          >
                            Mark Done
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Project Timesheets */}
            <div className="space-y-3">
              <h3 className="text-sm font-semibold text-stone-900">Logged Labor Timesheets ({selectedProject.timesheets?.length || 0})</h3>
              {selectedProject.timesheets?.length === 0 ? (
                <p className="text-xs text-stone-500 italic">No timesheets logged.</p>
              ) : (
                <div className="divide-y divide-stone-100 border border-stone-200 rounded-lg max-h-48 overflow-y-auto">
                  {selectedProject.timesheets?.map((ts: any) => (
                    <div key={ts.timesheet_id} className="p-3 text-xs flex justify-between items-center">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-mono font-medium text-stone-900">{ts.timesheet_number}</span>
                          <span className="text-stone-500">{ts.employee_name}</span>
                        </div>
                        <span className="text-2xs text-stone-400">{ts.work_date} • {ts.activity_type}</span>
                      </div>
                      <div className="text-right">
                        <span className="font-bold text-stone-900">{ts.hours}h</span>
                        <span className="block text-2xs text-emerald-700 font-medium">Billed: ${ts.billing_amount}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Modal: Create Project */}
      {showProjectModal && (
        <div className="fixed inset-0 z-50 bg-stone-900/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-6 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-stone-200">
              <h3 className="text-lg font-bold text-stone-900">Create New Project</h3>
              <button onClick={() => setShowProjectModal(false)} className="text-stone-400 hover:text-stone-600">
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleCreateProject} className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-stone-700 mb-1">Project Code</label>
                  <input
                    type="text"
                    required
                    placeholder="PRJ-AERO-01"
                    value={formProj.project_code}
                    onChange={(e) => setFormProj({ ...formProj, project_code: e.target.value })}
                    className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-stone-700 mb-1">Customer Name</label>
                  <input
                    type="text"
                    placeholder="Lockheed Martin"
                    value={formProj.customer_name}
                    onChange={(e) => setFormProj({ ...formProj, customer_name: e.target.value })}
                    className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg"
                  />
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-stone-700 mb-1">Project Title</label>
                <input
                  type="text"
                  required
                  placeholder="Titanium Aerospace Bracket Line"
                  value={formProj.project_name}
                  onChange={(e) => setFormProj({ ...formProj, project_name: e.target.value })}
                  className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-stone-700 mb-1">Estimated Cost ($)</label>
                  <input
                    type="number"
                    step="0.01"
                    required
                    value={formProj.estimated_cost}
                    onChange={(e) => setFormProj({ ...formProj, estimated_cost: e.target.value })}
                    className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-stone-700 mb-1">Start Date</label>
                  <input
                    type="date"
                    required
                    value={formProj.start_date}
                    onChange={(e) => setFormProj({ ...formProj, start_date: e.target.value })}
                    className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg"
                  />
                </div>
              </div>
              <div className="pt-3 flex justify-end gap-2 border-t border-stone-200">
                <button
                  type="button"
                  onClick={() => setShowProjectModal(false)}
                  className="px-4 py-2 text-sm text-stone-600 hover:bg-stone-100 rounded-lg"
                >
                  Cancel
                </button>
                <button type="submit" className="px-4 py-2 text-sm font-medium text-white bg-stone-900 rounded-lg hover:bg-stone-800">
                  Create Project
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Add Task */}
      {showTaskModal && (
        <div className="fixed inset-0 z-50 bg-stone-900/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-sm w-full p-6 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-stone-200">
              <h3 className="text-lg font-bold text-stone-900">Add Task Work Item</h3>
              <button onClick={() => setShowTaskModal(false)} className="text-stone-400 hover:text-stone-600">
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleCreateTask} className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-stone-700 mb-1">Task Title</label>
                <input
                  type="text"
                  required
                  placeholder="CAD / CAM Toolpath Simulation"
                  value={formTask.task_title}
                  onChange={(e) => setFormTask({ ...formTask, task_title: e.target.value })}
                  className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-stone-700 mb-1">Priority</label>
                  <select
                    value={formTask.priority}
                    onChange={(e) => setFormTask({ ...formTask, priority: e.target.value })}
                    className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg"
                  >
                    <option value="LOW">Low</option>
                    <option value="MEDIUM">Medium</option>
                    <option value="HIGH">High</option>
                    <option value="URGENT">Urgent</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-stone-700 mb-1">Est. Hours</label>
                  <input
                    type="number"
                    step="0.5"
                    required
                    value={formTask.estimated_hours}
                    onChange={(e) => setFormTask({ ...formTask, estimated_hours: e.target.value })}
                    className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg"
                  />
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-stone-700 mb-1">Assignee</label>
                <input
                  type="text"
                  value={formTask.assigned_to_name}
                  onChange={(e) => setFormTask({ ...formTask, assigned_to_name: e.target.value })}
                  className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg"
                />
              </div>
              <div className="pt-3 flex justify-end gap-2 border-t border-stone-200">
                <button
                  type="button"
                  onClick={() => setShowTaskModal(false)}
                  className="px-4 py-2 text-sm text-stone-600 hover:bg-stone-100 rounded-lg"
                >
                  Cancel
                </button>
                <button type="submit" className="px-4 py-2 text-sm font-medium text-white bg-stone-900 rounded-lg hover:bg-stone-800">
                  Save Task
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Log Timesheet */}
      {showTimesheetModal && (
        <div className="fixed inset-0 z-50 bg-stone-900/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-sm w-full p-6 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-stone-200">
              <h3 className="text-lg font-bold text-stone-900">Log Labor Timesheet</h3>
              <button onClick={() => setShowTimesheetModal(false)} className="text-stone-400 hover:text-stone-600">
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleLogTimesheet} className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-stone-700 mb-1">Employee Name</label>
                <input
                  type="text"
                  required
                  value={formTimesheet.employee_name}
                  onChange={(e) => setFormTimesheet({ ...formTimesheet, employee_name: e.target.value })}
                  className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-stone-700 mb-1">Activity Type</label>
                  <select
                    value={formTimesheet.activity_type}
                    onChange={(e) => setFormTimesheet({ ...formTimesheet, activity_type: e.target.value })}
                    className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg"
                  >
                    <option value="ENGINEERING">Engineering</option>
                    <option value="FABRICATION">Fabrication</option>
                    <option value="CONSULTING">Consulting</option>
                    <option value="SUPPORT">Support</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-stone-700 mb-1">Hours Worked</label>
                  <input
                    type="number"
                    step="0.25"
                    required
                    value={formTimesheet.hours}
                    onChange={(e) => setFormTimesheet({ ...formTimesheet, hours: e.target.value })}
                    className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-stone-700 mb-1">Billing Rate ($/h)</label>
                  <input
                    type="number"
                    step="0.01"
                    required
                    value={formTimesheet.billing_rate}
                    onChange={(e) => setFormTimesheet({ ...formTimesheet, billing_rate: e.target.value })}
                    className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-stone-700 mb-1">Costing Rate ($/h)</label>
                  <input
                    type="number"
                    step="0.01"
                    required
                    value={formTimesheet.costing_rate}
                    onChange={(e) => setFormTimesheet({ ...formTimesheet, costing_rate: e.target.value })}
                    className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg"
                  />
                </div>
              </div>
              <div className="pt-3 flex justify-end gap-2 border-t border-stone-200">
                <button
                  type="button"
                  onClick={() => setShowTimesheetModal(false)}
                  className="px-4 py-2 text-sm text-stone-600 hover:bg-stone-100 rounded-lg"
                >
                  Cancel
                </button>
                <button type="submit" className="px-4 py-2 text-sm font-medium text-white bg-stone-900 rounded-lg hover:bg-stone-800">
                  Log Hours & Rollup Cost
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
