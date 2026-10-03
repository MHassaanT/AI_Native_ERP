"use client";

import { useEffect, useState, useRef } from "react";
import {
  Activity,
  Plus,
  RefreshCw,
  AlertCircle,
  Play,
  Pause,
  CheckCircle2,
  Clock,
  Wrench,
  Cpu,
  Layers,
  FileSpreadsheet,
  Gauge,
  Calendar,
  AlertTriangle,
  ChevronRight,
  ChevronDown,
  ArrowRight,
  ShieldAlert,
  Zap,
  Check,
  User,
  Trash2,
} from "lucide-react";
import { api } from "@/lib/api";

type TabType = "boms" | "mrp" | "workorders" | "mes" | "oee" | "scheduler";

export default function ProductionPage() {
  const [activeTab, setActiveTab] = useState<TabType>("boms");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Data states
  const [workstations, setWorkstations] = useState<any[]>([]);
  const [operations, setOperations] = useState<any[]>([]);
  const [routings, setRoutings] = useState<any[]>([]);
  const [boms, setBoms] = useState<any[]>([]);
  const [selectedBomId, setSelectedBomId] = useState<string | null>(null);
  const [bomTree, setBomTree] = useState<any | null>(null);
  const [loadingTree, setLoadingTree] = useState(false);

  const [productionPlans, setProductionPlans] = useState<any[]>([]);
  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null);
  const [shortageReport, setShortageReport] = useState<any | null>(null);
  const [loadingShortage, setLoadingShortage] = useState(false);

  const [workOrders, setWorkOrders] = useState<any[]>([]);
  const [jobCards, setJobCards] = useState<any[]>([]);
  const [downtimes, setDowntimes] = useState<any[]>([]);
  const [selectedOeeWsId, setSelectedOeeWsId] = useState<string | null>(null);
  const [oeeMetrics, setOeeMetrics] = useState<any | null>(null);

  // Common catalog references
  const [items, setItems] = useState<any[]>([]);
  const [employees, setEmployees] = useState<any[]>([]);

  // MES Operator Console State
  const [mesOperatorId, setMesOperatorId] = useState<string>("");
  const [mesFilterWsId, setMesFilterWsId] = useState<string>("");
  const [activeTimerTicker, setActiveTimerTicker] = useState<number>(0);

  // Scheduler state
  const [scheduleResult, setScheduleResult] = useState<any | null>(null);
  const [solving, setSolving] = useState(false);
  const [faultingCode, setFaultingCode] = useState<string | null>(null);
  const [faultResult, setFaultResult] = useState<any | null>(null);

  // Modals
  const [showWsModal, setShowWsModal] = useState(false);
  const [wsCode, setWsCode] = useState("");
  const [wsName, setWsName] = useState("");
  const [wsType, setWsType] = useState("GENERAL");
  const [wsRate, setWsRate] = useState("45.00");
  const [wsCap, setWsCap] = useState("1.0");

  const [showOpModal, setShowOpModal] = useState(false);
  const [opName, setOpName] = useState("");
  const [opDesc, setOpDesc] = useState("");
  const [opWsId, setOpWsId] = useState("");

  const [showRoutingModal, setShowRoutingModal] = useState(false);
  const [routeName, setRouteName] = useState("");
  const [routeDesc, setRouteDesc] = useState("");
  const [routeOps, setRouteOps] = useState<any[]>([
    { operation_id: "", workstation_id: "", time_in_mins: "15", hourly_rate: "45", batch_size: "1" }
  ]);

  const [showBomModal, setShowBomModal] = useState(false);
  const [bomNumber, setBomNumber] = useState("");
  const [bomItemId, setBomItemId] = useState("");
  const [bomQty, setBomQty] = useState("1.0");
  const [bomRoutingId, setBomRoutingId] = useState("");
  const [bomWithOps, setBomWithOps] = useState(true);
  const [bomComponents, setBomComponents] = useState<any[]>([
    { item_id: "", quantity: "1.0", rate: "10.0", scrap_percentage: "0.0" }
  ]);

  const [showPlanModal, setShowPlanModal] = useState(false);
  const [planNumber, setPlanNumber] = useState("");
  const [planItems, setPlanItems] = useState<any[]>([
    { item_id: "", planned_qty: "10.0" }
  ]);

  const [showWoModal, setShowWoModal] = useState(false);
  const [woNumber, setWoNumber] = useState("");
  const [woItemId, setWoItemId] = useState("");
  const [woBomId, setWoBomId] = useState("");
  const [woQty, setWoQty] = useState("5.0");

  const [showDowntimeModal, setShowDowntimeModal] = useState(false);
  const [dtNumber, setDtNumber] = useState("");
  const [dtWsId, setDtWsId] = useState("");
  const [dtReason, setDtReason] = useState("MECHANICAL_BREAKDOWN");
  const [dtCode, setDtCode] = useState("");
  const [dtNotes, setDtNotes] = useState("");

  const [showScrapModal, setShowScrapModal] = useState(false);
  const [scrapTargetJc, setScrapTargetJc] = useState<any | null>(null);
  const [scrapActionType, setScrapActionType] = useState<"pause" | "complete">("complete");
  const [scrapCompletedQty, setScrapCompletedQty] = useState("1.0");
  const [scrapDefectQty, setScrapDefectQty] = useState("0.0");

  // Timer ticker for running MES Job Cards
  useEffect(() => {
    const timer = setInterval(() => {
      setActiveTimerTicker((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  const loadAll = async () => {
    setLoading(true);
    setError(null);
    try {
      const [wsList, opsList, routList, bomList, plansList, woList, jcList, dtList, itList, empList] =
        await Promise.all([
          api.getWorkstations(),
          api.getOperations().catch(() => []),
          api.getRoutings().catch(() => []),
          api.getBoms().catch(() => []),
          api.getProductionPlans().catch(() => []),
          api.getWorkOrders().catch(() => []),
          api.getJobCards().catch(() => []),
          api.getDowntimes().catch(() => []),
          api.getItems().catch(() => []),
          api.getEmployees().catch(() => []),
        ]);

      setWorkstations(wsList || []);
      setOperations(opsList || []);
      setRoutings(routList || []);
      setBoms(bomList || []);
      setProductionPlans(plansList || []);
      setWorkOrders(woList || []);
      setJobCards(jcList || []);
      setDowntimes(dtList || []);
      setItems(itList || []);
      setEmployees(empList || []);

      if (wsList && wsList.length > 0 && !selectedOeeWsId) {
        setSelectedOeeWsId(wsList[0].workstation_id);
      }
      if (bomList && bomList.length > 0 && !selectedBomId) {
        setSelectedBomId(bomList[0].bom_id);
      }
    } catch (err: any) {
      setError(err.message || "Failed to load manufacturing shop floor data.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAll();
  }, []);

  // Load Tree when selected BOM changes
  useEffect(() => {
    if (selectedBomId) {
      setLoadingTree(true);
      api
        .getBomTree(selectedBomId)
        .then((tree) => setBomTree(tree))
        .catch(() => setBomTree(null))
        .finally(() => setLoadingTree(false));
    } else {
      setBomTree(null);
    }
  }, [selectedBomId]);

  // Load OEE when selected WS changes
  useEffect(() => {
    if (selectedOeeWsId) {
      api
        .getWorkstationOEE(selectedOeeWsId)
        .then((res) => setOeeMetrics(res))
        .catch(() => setOeeMetrics(null));
    }
  }, [selectedOeeWsId]);

  // Actions
  const handleCreateWorkstation = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    try {
      await api.createWorkstation({
        workstation_code: wsCode.trim().toUpperCase(),
        workstation_name: wsName.trim(),
        workstation_type: wsType,
        hourly_rate: parseFloat(wsRate),
        production_capacity: parseFloat(wsCap),
        status: "OPERATIONAL",
      });
      setShowWsModal(false);
      setWsCode("");
      setWsName("");
      setSuccess("Workstation registered successfully.");
      await loadAll();
    } catch (err: any) {
      setError(err.message || "Failed to create workstation.");
    }
  };

  const handleCreateOperation = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    try {
      await api.createOperation({
        operation_name: opName.trim(),
        description: opDesc.trim() || undefined,
        default_workstation_id: opWsId || undefined,
      });
      setShowOpModal(false);
      setOpName("");
      setOpDesc("");
      setSuccess("Operation created in standard catalog.");
      await loadAll();
    } catch (err: any) {
      setError(err.message || "Failed to create operation.");
    }
  };

  const handleCreateRouting = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    try {
      const validOps = routeOps
        .filter((o) => o.operation_id)
        .map((o, idx) => ({
          operation_id: o.operation_id,
          workstation_id: o.workstation_id || undefined,
          sequence_id: idx + 1,
          time_in_mins: parseFloat(o.time_in_mins || "15"),
          hourly_rate: parseFloat(o.hourly_rate || "0"),
          batch_size: parseFloat(o.batch_size || "1"),
        }));

      await api.createRouting({
        routing_name: routeName.trim(),
        description: routeDesc.trim() || undefined,
        operations: validOps,
      });
      setShowRoutingModal(false);
      setRouteName("");
      setSuccess("Production routing sequence created.");
      await loadAll();
    } catch (err: any) {
      setError(err.message || "Failed to create routing.");
    }
  };

  const handleCreateBom = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    try {
      const validComps = bomComponents
        .filter((c) => c.item_id)
        .map((c) => ({
          item_id: c.item_id,
          quantity: parseFloat(c.quantity || "1"),
          rate: parseFloat(c.rate || "0"),
          scrap_percentage: parseFloat(c.scrap_percentage || "0"),
        }));

      await api.createBom({
        bom_number: bomNumber.trim().toUpperCase(),
        item_id: bomItemId,
        quantity: parseFloat(bomQty || "1"),
        routing_id: bomRoutingId || undefined,
        with_operations: bomWithOps,
        is_default: true,
        items: validComps,
        operations: [],
        scrap_items: [],
      });
      setShowBomModal(false);
      setBomNumber("");
      setSuccess("Bill of Materials created with unit cost rollup.");
      await loadAll();
    } catch (err: any) {
      setError(err.message || "Failed to create BOM.");
    }
  };

  const handleCreatePlan = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    try {
      const validItems = planItems
        .filter((it) => it.item_id)
        .map((it) => ({
          item_id: it.item_id,
          planned_qty: parseFloat(it.planned_qty || "1"),
        }));

      await api.createProductionPlan({
        plan_number: planNumber.trim().toUpperCase(),
        items: validItems,
      });
      setShowPlanModal(false);
      setPlanNumber("");
      setSuccess("Production Plan initialized.");
      await loadAll();
    } catch (err: any) {
      setError(err.message || "Failed to create Production Plan.");
    }
  };

  const handleExplodeShortages = async (planId: string) => {
    setSelectedPlanId(planId);
    setLoadingShortage(true);
    setError(null);
    try {
      const rep = await api.getPlanShortages(planId);
      setShortageReport(rep);
    } catch (err: any) {
      setError(err.message || "Failed to compute material explosion.");
    } finally {
      setLoadingShortage(false);
    }
  };

  const handleGenerateWorkOrders = async (planId: string) => {
    setError(null);
    setSuccess(null);
    try {
      const wos = await api.createWorkOrdersFromPlan(planId);
      setSuccess(`Generated ${wos.length} Work Orders and shop floor travelers!`);
      await loadAll();
    } catch (err: any) {
      setError(err.message || "Failed to generate work orders.");
    }
  };

  const handleCreateWorkOrder = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    try {
      await api.createWorkOrder({
        work_order_number: woNumber.trim().toUpperCase(),
        item_id: woItemId,
        bom_id: woBomId || undefined,
        planned_quantity: parseFloat(woQty || "1"),
      });
      setShowWoModal(false);
      setWoNumber("");
      setSuccess("Work Order created and Job Cards dispatched.");
      await loadAll();
    } catch (err: any) {
      setError(err.message || "Failed to create Work Order.");
    }
  };

  const handleStageMaterials = async (woId: string) => {
    setError(null);
    setSuccess(null);
    try {
      const res = await api.stageWorkOrderMaterials(woId);
      setSuccess(
        `Materials staged to WIP! Posted Stock Entry ${res.stock_entry_number} (${res.items_staged_count} items transferred).`
      );
      await loadAll();
    } catch (err: any) {
      if (err.message && err.message.includes("No Bill of Materials")) {
        setError(
          "Cannot stage materials: This Work Order target item has no Bill of Materials configured. Create a BOM first to specify which raw components to transfer from Stores to WIP."
        );
      } else {
        setError(err.message || "Material staging failed.");
      }
    }
  };

  const handleCompleteWorkOrder = async (woId: string) => {
    setError(null);
    setSuccess(null);
    try {
      const res = await api.completeWorkOrder(woId);
      setSuccess(
        `Manufacture complete! Produced ${res.produced_quantity} units. Backflushed stock entry ${res.stock_entry_number} and posted $${res.valuation_transferred} GL valuation.`
      );
      await loadAll();
    } catch (err: any) {
      setError(err.message || "Work Order completion failed.");
    }
  };

  // MES Actions
  const handleStartJobCard = async (jcId: string) => {
    setError(null);
    setSuccess(null);
    try {
      await api.startJobCard(jcId, { employee_id: mesOperatorId || undefined });
      setSuccess("Punch IN recorded. Execution timer running.");
      await loadAll();
    } catch (err: any) {
      setError(err.message || "Failed to start Job Card.");
    }
  };

  const handleOpenScrapModal = (jc: any, action: "pause" | "complete") => {
    setScrapTargetJc(jc);
    setScrapActionType(action);
    setScrapCompletedQty(String(jc.for_quantity - jc.total_completed_qty > 0 ? jc.for_quantity - jc.total_completed_qty : 1));
    setScrapDefectQty("0");
    setShowScrapModal(true);
  };

  const handleSubmitScrapModal = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!scrapTargetJc) return;
    setError(null);
    setSuccess(null);
    try {
      const payload = {
        employee_id: mesOperatorId || undefined,
        completed_qty: parseFloat(scrapCompletedQty || "0"),
        scrap_qty: parseFloat(scrapDefectQty || "0"),
      };
      if (scrapActionType === "pause") {
        await api.pauseJobCard(scrapTargetJc.job_card_id, payload);
        setSuccess("Punch session paused. Time log saved.");
      } else {
        await api.completeJobCard(scrapTargetJc.job_card_id, payload);
        setSuccess("Operation completed! Machine freed for next traveler.");
      }
      setShowScrapModal(false);
      await loadAll();
    } catch (err: any) {
      setError(err.message || "Failed to process traveler operation.");
    }
  };

  const handleRecordDowntime = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    try {
      await api.recordDowntime({
        downtime_number: dtNumber.trim().toUpperCase(),
        workstation_id: dtWsId,
        reason: dtReason,
        fault_code: dtCode.trim() || undefined,
        notes: dtNotes.trim() || undefined,
      });
      setShowDowntimeModal(false);
      setDtNumber("");
      setSuccess("Machine stoppage logged! Machine placed under lock.");
      await loadAll();
    } catch (err: any) {
      setError(err.message || "Failed to record downtime.");
    }
  };

  const handleResolveDowntime = async (downtimeId: string) => {
    setError(null);
    setSuccess(null);
    try {
      await api.resolveDowntime(downtimeId);
      setSuccess("Breakdown resolved! Workstation restored to OPERATIONAL.");
      await loadAll();
    } catch (err: any) {
      setError(err.message || "Failed to resolve downtime.");
    }
  };

  const handleSolveSchedule = async () => {
    setSolving(true);
    setError(null);
    try {
      const res = await api.solveSchedule();
      setScheduleResult(res);
      setSuccess("CP-SAT Job-Shop schedule optimized!");
    } catch (err: any) {
      setError(err.message || "CP-SAT optimization failed.");
    } finally {
      setSolving(false);
    }
  };

  const handleSimulateFault = async (code: string) => {
    setFaultingCode(code);
    setError(null);
    try {
      const res = await api.simulateFaultReroute(code);
      setFaultResult(res);
      setSuccess(`Dynamic rerouting completed for faulted machine ${code}.`);
      await loadAll();
    } catch (err: any) {
      setError(err.message || "Fault simulation failed.");
    } finally {
      setFaultingCode(null);
    }
  };

  const formatSeconds = (dtString: string | null) => {
    if (!dtString) return "00:00";
    const start = new Date(dtString).getTime();
    const now = Date.now();
    const diffSec = Math.max(0, Math.floor((now - start) / 1000));
    const mins = Math.floor(diffSec / 60);
    const secs = diffSec % 60;
    return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
  };

  return (
    <div className="space-y-6 pb-20">
      {/* Top Header */}
      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between border-b border-stone-200 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 text-[11px] font-semibold tracking-wide uppercase bg-emerald-100 text-emerald-800 rounded">
              Phase 5
            </span>
            <h1 className="text-xl font-bold tracking-tight text-stone-900">
              Manufacturing & MES Execution Suite
            </h1>
          </div>
          <p className="text-xs text-stone-500 mt-1">
            ERPNext Parity: Multi-Level BOMs, MRP Planning, Shop Floor Punch Timers, OEE Telemetry & CP-SAT Scheduling
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            onClick={loadAll}
            disabled={loading}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-stone-100 hover:bg-stone-200 text-stone-700 rounded-lg transition"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Alert Banners */}
      {error && (
        <div className="p-3 text-xs bg-red-50 text-red-700 border border-red-200 rounded-lg flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
          <button onClick={() => setError(null)} className="text-xs font-bold px-1.5 hover:bg-red-100 rounded">
            ×
          </button>
        </div>
      )}
      {success && (
        <div className="p-3 text-xs bg-emerald-50 text-emerald-800 border border-emerald-200 rounded-lg flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 shrink-0" />
            <span>{success}</span>
          </div>
          <button onClick={() => setSuccess(null)} className="text-xs font-bold px-1.5 hover:bg-emerald-100 rounded">
            ×
          </button>
        </div>
      )}

      {/* 6-Tab Navigation */}
      <div className="flex overflow-x-auto gap-2 border-b border-stone-200 pb-2 scrollbar-none">
        {[
          { id: "boms", label: "BOM & Routings", icon: Layers, count: boms.length },
          { id: "mrp", label: "Production Plan (MRP)", icon: FileSpreadsheet, count: productionPlans.length },
          { id: "workorders", label: "Work Orders & Staging", icon: CheckCircle2, count: workOrders.length },
          { id: "mes", label: "Operator Console (MES)", icon: Clock, count: jobCards.filter((j) => j.status === "WORK_IN_PROGRESS").length },
          { id: "oee", label: "Workstations & OEE", icon: Gauge, count: workstations.length },
          { id: "scheduler", label: "CP-SAT Scheduler", icon: Cpu },
        ].map((tab) => {
          const Icon = tab.icon;
          const active = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as TabType)}
              className={`inline-flex items-center gap-2 px-3 py-2 text-xs font-medium rounded-lg transition whitespace-nowrap ${
                active
                  ? "bg-stone-900 text-white shadow-sm"
                  : "bg-white hover:bg-stone-100 text-stone-600 border border-stone-200"
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              <span>{tab.label}</span>
              {tab.count !== undefined && (
                <span
                  className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                    active ? "bg-stone-700 text-stone-200" : "bg-stone-100 text-stone-600"
                  }`}
                >
                  {tab.count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* --- TAB 1: BOM & ROUTINGS --- */}
      {activeTab === "boms" && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold text-stone-900">Multi-Level Bill of Materials & Routings</h2>
              <p className="text-xs text-stone-500">Recursive component hierarchy, scrap allowances, and unit cost rollup</p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => setShowOpModal(true)}
                className="px-3 py-1.5 text-xs font-medium bg-stone-100 hover:bg-stone-200 text-stone-800 rounded-lg border border-stone-200"
              >
                + New Operation
              </button>
              <button
                onClick={() => setShowRoutingModal(true)}
                className="px-3 py-1.5 text-xs font-medium bg-stone-100 hover:bg-stone-200 text-stone-800 rounded-lg border border-stone-200"
              >
                + New Routing
              </button>
              <button
                onClick={() => setShowBomModal(true)}
                className="px-3.5 py-1.5 text-xs font-medium bg-stone-900 hover:bg-stone-800 text-white rounded-lg shadow-sm"
              >
                + New BOM
              </button>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* BOM List */}
            <div className="bg-white border border-stone-200 rounded-xl p-4 space-y-3">
              <div className="text-xs font-semibold text-stone-700 uppercase tracking-wider">BOM Registry</div>
              <div className="space-y-2 max-h-[500px] overflow-y-auto pr-1">
                {boms.length === 0 ? (
                  <p className="text-xs text-stone-400 py-4 text-center">No BOMs created yet.</p>
                ) : (
                  boms.map((b) => (
                    <div
                      key={b.bom_id}
                      onClick={() => setSelectedBomId(b.bom_id)}
                      className={`p-3 rounded-lg border cursor-pointer transition ${
                        selectedBomId === b.bom_id
                          ? "border-stone-900 bg-stone-50"
                          : "border-stone-200 hover:border-stone-300"
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-stone-900">{b.bom_number}</span>
                        <span className="text-[11px] font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded">
                          ${parseFloat(b.total_cost || "0").toFixed(2)}/ea
                        </span>
                      </div>
                      <div className="text-[11px] text-stone-500 mt-1">
                        Qty: {parseFloat(b.quantity || "1")} | Components: {b.items?.length || 0} | Ops: {b.operations?.length || 0}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Multi-Level Visual Tree Explorer */}
            <div className="lg:col-span-2 bg-white border border-stone-200 rounded-xl p-5 space-y-4">
              <div className="flex items-center justify-between border-b border-stone-100 pb-3">
                <span className="text-xs font-semibold text-stone-800 uppercase tracking-wider">
                  Visual Multi-Level Exploded Tree
                </span>
                {bomTree && (
                  <div className="flex gap-3 text-xs text-stone-600">
                    <span>Raw Material: <strong>${bomTree.raw_material_cost.toFixed(2)}</strong></span>
                    <span>Operating: <strong>${bomTree.operating_cost.toFixed(2)}</strong></span>
                    <span className="text-emerald-700 font-bold">Total: ${bomTree.total_cost.toFixed(2)}</span>
                  </div>
                )}
              </div>

              {loadingTree ? (
                <div className="py-12 text-center text-xs text-stone-400">Loading BOM hierarchy...</div>
              ) : !bomTree ? (
                <div className="py-12 text-center text-xs text-stone-400">Select a BOM to inspect its component tree.</div>
              ) : (
                <div className="space-y-3">
                  <div className="p-3 bg-stone-100 border border-stone-300 rounded-lg flex items-center justify-between">
                    <div>
                      <span className="text-xs font-bold text-stone-900">{bomTree.item_name}</span>
                      <span className="ml-2 text-[10px] text-stone-500">[{bomTree.item_code}]</span>
                      <div className="text-[11px] text-stone-500">Top-Level Finished Product (Qty: {bomTree.quantity})</div>
                    </div>
                    <span className="text-xs font-bold text-stone-900">${bomTree.total_cost.toFixed(2)}</span>
                  </div>

                  {/* Components */}
                  <div className="pl-4 border-l-2 border-stone-200 space-y-2">
                    {bomTree.components.length === 0 ? (
                      <p className="text-xs text-stone-400 italic">No component items attached.</p>
                    ) : (
                      bomTree.components.map((c: any, idx: number) => (
                        <div key={idx} className="space-y-2">
                          <div className="p-2.5 bg-white border border-stone-200 rounded-lg flex items-center justify-between text-xs">
                            <div className="flex items-center gap-2">
                              <span className="w-1.5 h-1.5 rounded-full bg-stone-400"></span>
                              <span className="font-medium text-stone-800">{c.item_name}</span>
                              <span className="text-stone-400 text-[10px]">[{c.item_code}]</span>
                              <span className="text-[11px] text-stone-500">
                                × {c.quantity} @ ${c.rate.toFixed(2)}
                              </span>
                              {c.scrap_percentage > 0 && (
                                <span className="text-[10px] px-1.5 py-0.2 bg-amber-50 text-amber-700 rounded">
                                  +{c.scrap_percentage}% Scrap
                                </span>
                              )}
                            </div>
                            <span className="font-semibold text-stone-900">${c.amount.toFixed(2)}</span>
                          </div>

                          {/* Sub-assembly recursion */}
                          {c.sub_assembly && (
                            <div className="pl-5 border-l-2 border-emerald-300 space-y-1.5">
                              <div className="text-[11px] font-semibold text-emerald-800">
                                ↳ Sub-Assembly: {c.sub_assembly.item_name} (BOM: {c.sub_assembly.bom_number})
                              </div>
                              {c.sub_assembly.components.map((subC: any, subIdx: number) => (
                                <div
                                  key={subIdx}
                                  className="p-2 bg-emerald-50/50 border border-emerald-200 rounded text-[11px] flex justify-between"
                                >
                                  <span>{subC.item_name} (× {subC.quantity})</span>
                                  <span className="font-medium text-stone-700">${subC.amount.toFixed(2)}</span>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      ))
                    )}
                  </div>

                  {/* Operations sequence */}
                  {bomTree.operations.length > 0 && (
                    <div className="mt-4 pt-4 border-t border-stone-100">
                      <div className="text-xs font-semibold text-stone-700 mb-2">Attached Routing Operations</div>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                        {bomTree.operations.map((op: any, idx: number) => (
                          <div key={idx} className="p-2 bg-stone-50 border border-stone-200 rounded text-xs flex justify-between">
                            <div>
                              <span className="font-semibold text-stone-900">{op.sequence_id}. {op.operation_name}</span>
                              <div className="text-[10px] text-stone-500">Machine: {op.workstation_code} | {op.time_in_mins} mins</div>
                            </div>
                            <span className="font-medium text-stone-700">${op.operating_cost.toFixed(2)}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* --- TAB 2: PRODUCTION PLAN (MRP) --- */}
      {activeTab === "mrp" && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold text-stone-900">Material Requirements Planning (MRP)</h2>
              <p className="text-xs text-stone-500">Explode demand, check stock shortages across stores, and bulk-generate work orders</p>
            </div>
            <button
              onClick={() => setShowPlanModal(true)}
              className="px-3.5 py-1.5 text-xs font-medium bg-stone-900 hover:bg-stone-800 text-white rounded-lg shadow-sm"
            >
              + New Production Plan
            </button>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Plans List */}
            <div className="bg-white border border-stone-200 rounded-xl p-4 space-y-3">
              <div className="text-xs font-semibold text-stone-700 uppercase tracking-wider">Active Plans</div>
              <div className="space-y-2">
                {productionPlans.length === 0 ? (
                  <p className="text-xs text-stone-400 py-4 text-center">No production plans found.</p>
                ) : (
                  productionPlans.map((p) => (
                    <div
                      key={p.plan_id}
                      onClick={() => handleExplodeShortages(p.plan_id)}
                      className={`p-3 rounded-lg border cursor-pointer transition ${
                        selectedPlanId === p.plan_id
                          ? "border-stone-900 bg-stone-50"
                          : "border-stone-200 hover:border-stone-300"
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-stone-900">{p.plan_number}</span>
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${
                          p.status === "COMPLETED"
                            ? "bg-emerald-100 text-emerald-800"
                            : p.status === "IN_PROCESS"
                            ? "bg-blue-100 text-blue-800"
                            : "bg-stone-100 text-stone-700"
                        }`}>
                          {p.status}
                        </span>
                      </div>
                      <div className="text-[11px] text-stone-500 mt-1 flex justify-between">
                        <span>Planned Qty: {parseFloat(p.total_planned_qty || "0")}</span>
                        <span>Items: {p.items?.length || 0}</span>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Shortage & Work Order Generation Panel */}
            <div className="lg:col-span-2 bg-white border border-stone-200 rounded-xl p-5 space-y-4">
              <div className="flex items-center justify-between border-b border-stone-100 pb-3">
                <span className="text-xs font-semibold text-stone-800 uppercase tracking-wider">
                  Material Requirements Explosion & Shortages
                </span>
                {selectedPlanId && (
                  <button
                    onClick={() => handleGenerateWorkOrders(selectedPlanId)}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg shadow-sm"
                  >
                    <Zap className="w-3.5 h-3.5" />
                    Generate Work Orders
                  </button>
                )}
              </div>

              {loadingShortage ? (
                <div className="py-12 text-center text-xs text-stone-400">Computing BOM requirements explosion...</div>
              ) : !shortageReport ? (
                <div className="py-12 text-center text-xs text-stone-400">Select a Production Plan to view material requirements.</div>
              ) : (
                <div className="space-y-4">
                  {/* Warning banner for planned items without BOM */}
                  {shortageReport.items_without_bom && shortageReport.items_without_bom.length > 0 && (
                    <div className="p-3.5 bg-amber-50 border border-amber-200 rounded-lg text-xs space-y-1.5">
                      <div className="flex items-center gap-1.5 font-bold text-amber-900">
                        <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
                        <span>Planned Items Without Bill of Materials ({shortageReport.items_without_bom.length})</span>
                      </div>
                      <p className="text-[11px] text-amber-800 leading-relaxed">
                        The following items in this production plan do not have an active Bill of Materials configured. Component requirements cannot be exploded for items without a BOM:
                      </p>
                      <div className="flex flex-wrap gap-1.5 pt-0.5">
                        {shortageReport.items_without_bom.map((nobom: any, i: number) => (
                          <span
                            key={i}
                            className="px-2 py-0.5 bg-white border border-amber-300 rounded text-[11px] font-semibold text-amber-900 shadow-sm"
                          >
                            {nobom.item_name} ({nobom.item_code})
                          </span>
                        ))}
                      </div>
                      <p className="text-[10px] text-amber-700 pt-1">
                        💡 <strong>Next step:</strong> Go to the <strong>Bill of Materials</strong> tab to create a BOM for these finished items, or plan finished products instead of purchased raw materials.
                      </p>
                    </div>
                  )}

                  {/* Requirements Table or Explanatory Empty State */}
                  {shortageReport.exploded_requirements.length === 0 ? (
                    <div className="py-10 text-center bg-stone-50 rounded-xl border border-dashed border-stone-200 p-6 space-y-2">
                      <Layers className="w-8 h-8 text-stone-400 mx-auto" />
                      <div className="text-xs font-semibold text-stone-700">No Raw Material Requirements Exploded</div>
                      <p className="text-[11px] text-stone-500 max-w-md mx-auto">
                        None of the items in production plan <strong>{shortageReport.plan_number}</strong> have an active Bill of Materials (BOM) defining component raw materials.
                      </p>
                      <div className="text-[10px] text-stone-400">
                        To compute component requirements, create a BOM for the finished good and add it to this production plan.
                      </div>
                    </div>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-xs">
                        <thead className="bg-stone-50 border-b border-stone-200 text-stone-600">
                          <tr>
                            <th className="py-2.5 px-3">Item / Component</th>
                            <th className="py-2.5 px-3">Gross Required</th>
                            <th className="py-2.5 px-3">In Stock</th>
                            <th className="py-2.5 px-3">Available</th>
                            <th className="py-2.5 px-3">Shortage</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-stone-100">
                          {shortageReport.exploded_requirements.map((req: any, idx: number) => {
                            const hasShortage = req.shortage_qty > 0;
                            return (
                              <tr key={idx} className="hover:bg-stone-50/50">
                                <td className="py-2.5 px-3 font-medium text-stone-900">
                                  {req.item_name}
                                  <span className="ml-1 text-[10px] text-stone-400">({req.item_code})</span>
                                </td>
                                <td className="py-2.5 px-3 font-bold text-stone-900">
                                  {req.gross_required_qty} {req.uom}
                                </td>
                                <td className="py-2.5 px-3 text-stone-600">{req.current_stock_qty}</td>
                                <td className="py-2.5 px-3 text-stone-600">{req.available_stock_qty}</td>
                                <td className="py-2.5 px-3">
                                  {hasShortage ? (
                                    <span className="inline-flex items-center gap-1 text-[11px] font-bold text-red-700 bg-red-50 px-2 py-0.5 rounded border border-red-200">
                                      <AlertTriangle className="w-3 h-3" />
                                      Short {req.shortage_qty} {req.uom}
                                    </span>
                                  ) : (
                                    <span className="text-[11px] font-medium text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded">
                                      Sufficient
                                    </span>
                                  )}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* --- TAB 3: WORK ORDERS & STAGING --- */}
      {activeTab === "workorders" && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold text-stone-900">Work Orders & Inventory Staging</h2>
              <p className="text-xs text-stone-500">1-click Material Transfer to WIP (ST-MAT-TRANSFER) and Backflush Manufacture (ST-MANUFACTURE)</p>
            </div>
            <button
              onClick={() => setShowWoModal(true)}
              className="px-3.5 py-1.5 text-xs font-medium bg-stone-900 hover:bg-stone-800 text-white rounded-lg shadow-sm"
            >
              + New Work Order
            </button>
          </div>

          <div className="bg-white border border-stone-200 rounded-xl overflow-hidden shadow-sm">
            <table className="w-full text-left text-xs">
              <thead className="bg-stone-50 border-b border-stone-200 text-stone-600">
                <tr>
                  <th className="py-3 px-3">WO Number</th>
                  <th className="py-3 px-3">Target Item</th>
                  <th className="py-3 px-3">BOM Status</th>
                  <th className="py-3 px-3">Planned Qty</th>
                  <th className="py-3 px-3">Produced Qty</th>
                  <th className="py-3 px-3">Material Staging</th>
                  <th className="py-3 px-3">Status</th>
                  <th className="py-3 px-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-stone-100">
                {workOrders.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="py-8 text-center text-stone-400">
                      No work orders in queue.
                    </td>
                  </tr>
                ) : (
                  workOrders.map((wo) => {
                    const isStaged = wo.material_transferred_for_mfg;
                    const isCompleted = wo.status === "COMPLETED";
                    const attachedBom = boms.find((b) => b.bom_id === wo.bom_id || b.item_id === wo.item_id);
                    const hasBom = Boolean(wo.bom_id || attachedBom);

                    return (
                      <tr key={wo.work_order_id} className="hover:bg-stone-50/50">
                        <td className="py-3 px-3 font-bold text-stone-900">{wo.work_order_number}</td>
                        <td className="py-3 px-3 text-stone-800">
                          {items.find((i) => i.item_id === wo.item_id)?.item_name || wo.item_id}
                        </td>
                        <td className="py-3 px-3">
                          {hasBom ? (
                            <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-800 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                              <Check className="w-3 h-3 text-emerald-600" />
                              {attachedBom?.bom_number || "BOM Attached"}
                            </span>
                          ) : (
                            <span
                              className="inline-flex items-center gap-1 text-[11px] font-medium text-amber-800 bg-amber-50 px-2 py-0.5 rounded border border-amber-200"
                              title="No Bill of Materials configured for this item"
                            >
                              <AlertCircle className="w-3 h-3 text-amber-600" />
                              No BOM
                            </span>
                          )}
                        </td>
                        <td className="py-3 px-3 font-semibold text-stone-900">{parseFloat(wo.planned_quantity)}</td>
                        <td className="py-3 px-3 text-emerald-700 font-bold">{parseFloat(wo.produced_quantity || "0")}</td>
                        <td className="py-3 px-3">
                          {isStaged ? (
                            <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                              <Check className="w-3 h-3" />
                              Staged to WIP
                            </span>
                          ) : (
                            <span className="text-[11px] text-amber-700 bg-amber-50 px-2 py-0.5 rounded border border-amber-200">
                              Not Staged
                            </span>
                          )}
                        </td>
                        <td className="py-3 px-3">
                          <span
                            className={`text-[10px] font-bold px-2 py-0.5 rounded ${
                              isCompleted
                                ? "bg-emerald-100 text-emerald-800"
                                : wo.status === "IN_PROCESS"
                                ? "bg-blue-100 text-blue-800"
                                : "bg-stone-100 text-stone-700"
                            }`}
                          >
                            {wo.status}
                          </span>
                        </td>
                        <td className="py-3 px-3 text-right space-x-2">
                          {!isStaged && !isCompleted && (
                            hasBom ? (
                              <button
                                onClick={() => handleStageMaterials(wo.work_order_id)}
                                className="px-2.5 py-1 text-[11px] font-medium bg-amber-600 hover:bg-amber-700 text-white rounded transition shadow-sm"
                              >
                                Stage to WIP
                              </button>
                            ) : (
                              <button
                                disabled
                                title="Cannot stage to WIP: Item has no Bill of Materials configured"
                                className="px-2.5 py-1 text-[11px] font-medium bg-stone-100 text-stone-400 border border-stone-200 rounded cursor-not-allowed"
                              >
                                Stage to WIP
                              </button>
                            )
                          )}
                          {!isCompleted && (
                            <button
                              onClick={() => handleCompleteWorkOrder(wo.work_order_id)}
                              className="px-2.5 py-1 text-[11px] font-medium bg-emerald-600 hover:bg-emerald-700 text-white rounded transition shadow-sm"
                            >
                              Complete & Backflush
                            </button>
                          )}
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* --- TAB 4: OPERATOR CONSOLE (MES) --- */}
      {activeTab === "mes" && (
        <div className="space-y-6">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-stone-900 text-white p-4 rounded-xl shadow">
            <div>
              <div className="flex items-center gap-2">
                <Clock className="w-4 h-4 text-emerald-400 animate-pulse" />
                <h2 className="text-sm font-bold tracking-tight">Shop Floor Operator Console (MES)</h2>
              </div>
              <p className="text-xs text-stone-400 mt-0.5">Punch clock traveler execution, active timers, and scrap defect logging</p>
            </div>

            <div className="flex items-center gap-3">
              {/* Operator Badge Selector */}
              <div className="flex items-center gap-2 bg-stone-800 px-3 py-1.5 rounded-lg border border-stone-700">
                <User className="w-3.5 h-3.5 text-stone-400" />
                <select
                  value={mesOperatorId}
                  onChange={(e) => setMesOperatorId(e.target.value)}
                  className="bg-transparent text-xs text-white outline-none cursor-pointer"
                >
                  <option value="" className="bg-stone-900 text-white">Select Operator Badge...</option>
                  {employees.map((emp) => (
                    <option key={emp.employee_id} value={emp.employee_id} className="bg-stone-900 text-white">
                      {emp.first_name} {emp.last_name} ({emp.employee_code})
                    </option>
                  ))}
                </select>
              </div>

              {/* Machine Filter */}
              <div className="flex items-center gap-2 bg-stone-800 px-3 py-1.5 rounded-lg border border-stone-700">
                <Cpu className="w-3.5 h-3.5 text-stone-400" />
                <select
                  value={mesFilterWsId}
                  onChange={(e) => setMesFilterWsId(e.target.value)}
                  className="bg-transparent text-xs text-white outline-none cursor-pointer"
                >
                  <option value="" className="bg-stone-900 text-white">All Machines</option>
                  {workstations.map((ws) => (
                    <option key={ws.workstation_id} value={ws.workstation_id} className="bg-stone-900 text-white">
                      {ws.workstation_code} - {ws.workstation_name}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          {/* Dispatched Job Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {jobCards
              .filter((jc) => (!mesFilterWsId || jc.workstation_id === mesFilterWsId))
              .map((jc) => {
                const isRunning = jc.status === "WORK_IN_PROGRESS";
                const isCompleted = jc.status === "COMPLETED";

                return (
                  <div
                    key={jc.job_card_id}
                    className={`bg-white border rounded-xl p-4 space-y-3 transition shadow-sm ${
                      isRunning ? "border-emerald-500 ring-2 ring-emerald-500/20" : "border-stone-200"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-stone-900">{jc.job_card_number}</span>
                      <span
                        className={`text-[10px] font-bold px-2 py-0.5 rounded ${
                          isRunning
                            ? "bg-emerald-100 text-emerald-800 animate-pulse"
                            : isCompleted
                            ? "bg-stone-100 text-stone-600"
                            : "bg-blue-100 text-blue-800"
                        }`}
                      >
                        {jc.status}
                      </span>
                    </div>

                    <div className="space-y-1">
                      <div className="text-xs font-semibold text-stone-800">
                        {jc.operation?.operation_name || "Manufacturing Step"}
                      </div>
                      <div className="text-[11px] text-stone-500">
                        Machine: <strong>{jc.workstation?.workstation_code || "Any Machine"}</strong>
                      </div>
                      <div className="text-[11px] text-stone-500">
                        Target Qty: <strong>{parseFloat(jc.for_quantity)}</strong> | Produced:{" "}
                        <strong className="text-emerald-700">{parseFloat(jc.total_completed_qty || "0")}</strong>
                      </div>
                    </div>

                    {/* Timer Box */}
                    <div className="p-3 bg-stone-50 border border-stone-200 rounded-lg flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Clock className={`w-4 h-4 ${isRunning ? "text-emerald-600 animate-spin" : "text-stone-400"}`} />
                        <span className="text-sm font-mono font-bold text-stone-800">
                          {isRunning ? formatSeconds(jc.current_timer_started_at) : `${parseFloat(jc.total_time_in_mins || "0").toFixed(1)}m`}
                        </span>
                      </div>
                      <span className="text-[10px] text-stone-400 uppercase tracking-wider font-semibold">
                        {isRunning ? "Active Clock" : "Total Time"}
                      </span>
                    </div>

                    {/* Touchscreen Button Controls */}
                    <div className="grid grid-cols-2 gap-2 pt-1">
                      {!isRunning && !isCompleted && (
                        <button
                          onClick={() => handleStartJobCard(jc.job_card_id)}
                          className="col-span-2 py-2 text-xs font-bold bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg shadow flex items-center justify-center gap-1.5 transition active:scale-95"
                        >
                          <Play className="w-3.5 h-3.5" />
                          Punch IN (Start)
                        </button>
                      )}

                      {isRunning && (
                        <>
                          <button
                            onClick={() => handleOpenScrapModal(jc, "pause")}
                            className="py-2 text-xs font-bold bg-amber-500 hover:bg-amber-600 text-white rounded-lg shadow flex items-center justify-center gap-1 transition active:scale-95"
                          >
                            <Pause className="w-3.5 h-3.5" />
                            Pause
                          </button>
                          <button
                            onClick={() => handleOpenScrapModal(jc, "complete")}
                            className="py-2 text-xs font-bold bg-stone-900 hover:bg-stone-800 text-white rounded-lg shadow flex items-center justify-center gap-1 transition active:scale-95"
                          >
                            <Check className="w-3.5 h-3.5" />
                            Complete
                          </button>
                        </>
                      )}

                      {isCompleted && (
                        <div className="col-span-2 py-1.5 text-center text-xs font-semibold text-emerald-700 bg-emerald-50 rounded-lg">
                          Operation Finished
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
          </div>
        </div>
      )}

      {/* --- TAB 5: WORKSTATIONS, DOWNTIME & OEE --- */}
      {activeTab === "oee" && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold text-stone-900">Workstations, Downtime & OEE Telemetry</h2>
              <p className="text-xs text-stone-500">Live Availability, Performance, Quality, and overall equipment effectiveness (OEE)</p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => setShowDowntimeModal(true)}
                className="px-3 py-1.5 text-xs font-medium bg-red-50 hover:bg-red-100 text-red-700 rounded-lg border border-red-200"
              >
                + Log Stoppage / Downtime
              </button>
              <button
                onClick={() => setShowWsModal(true)}
                className="px-3.5 py-1.5 text-xs font-medium bg-stone-900 hover:bg-stone-800 text-white rounded-lg shadow-sm"
              >
                + New Workstation
              </button>
            </div>
          </div>

          {/* OEE Gauges Banner */}
          {oeeMetrics && (
            <div className="bg-gradient-to-r from-stone-900 via-stone-800 to-stone-900 text-white p-5 rounded-xl shadow space-y-4">
              <div className="flex items-center justify-between border-b border-stone-700 pb-3">
                <div>
                  <span className="text-xs font-semibold text-stone-400 uppercase tracking-wider">
                    Machine Telemetry & OEE Rating
                  </span>
                  <div className="text-base font-bold text-white mt-0.5">
                    {oeeMetrics.workstation_code} - {oeeMetrics.workstation_name}
                  </div>
                </div>
                <div className="text-right">
                  <span className="text-2xl font-black text-emerald-400">{oeeMetrics.oee_percentage}%</span>
                  <div className="text-[10px] text-stone-400 uppercase tracking-wider font-semibold">Composite OEE</div>
                </div>
              </div>

              <div className="grid grid-cols-3 gap-4">
                <div className="p-3 bg-stone-800/80 rounded-lg border border-stone-700 text-center">
                  <div className="text-lg font-bold text-white">{(oeeMetrics.availability * 100).toFixed(1)}%</div>
                  <div className="text-[10px] text-stone-400 font-semibold uppercase mt-0.5">Availability</div>
                  <div className="text-[10px] text-stone-500 mt-1">Downtime: {oeeMetrics.downtime_minutes}m</div>
                </div>
                <div className="p-3 bg-stone-800/80 rounded-lg border border-stone-700 text-center">
                  <div className="text-lg font-bold text-white">{(oeeMetrics.performance * 100).toFixed(1)}%</div>
                  <div className="text-[10px] text-stone-400 font-semibold uppercase mt-0.5">Performance</div>
                  <div className="text-[10px] text-stone-500 mt-1">Operating: {oeeMetrics.operating_time_minutes}m</div>
                </div>
                <div className="p-3 bg-stone-800/80 rounded-lg border border-stone-700 text-center">
                  <div className="text-lg font-bold text-white">{(oeeMetrics.quality * 100).toFixed(1)}%</div>
                  <div className="text-[10px] text-stone-400 font-semibold uppercase mt-0.5">Quality</div>
                  <div className="text-[10px] text-stone-500 mt-1">Scrap: {oeeMetrics.total_scrap_qty}</div>
                </div>
              </div>
            </div>
          )}

          {/* Workstation Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {workstations.map((ws) => {
              const isFault = ws.status === "FAULT" || ws.status === "MAINTENANCE";
              return (
                <div
                  key={ws.workstation_id}
                  onClick={() => setSelectedOeeWsId(ws.workstation_id)}
                  className={`bg-white border rounded-xl p-4 space-y-3 cursor-pointer transition ${
                    selectedOeeWsId === ws.workstation_id ? "ring-2 ring-stone-900 border-stone-900" : "border-stone-200"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <span className="text-xs font-bold text-stone-900">{ws.workstation_code}</span>
                      <span className="ml-2 text-[10px] font-semibold text-stone-500">({ws.workstation_type})</span>
                    </div>
                    <span
                      className={`text-[10px] font-bold px-2 py-0.5 rounded ${
                        isFault
                          ? "bg-red-100 text-red-800 animate-pulse"
                          : ws.status === "IN_USE"
                          ? "bg-blue-100 text-blue-800"
                          : "bg-emerald-100 text-emerald-800"
                      }`}
                    >
                      {ws.status}
                    </span>
                  </div>

                  <div className="text-xs text-stone-600">{ws.workstation_name}</div>

                  <div className="flex items-center justify-between text-[11px] text-stone-500 pt-2 border-t border-stone-100">
                    <span>Rate: ${parseFloat(ws.hourly_rate)}/hr</span>
                    <span>Health: {parseFloat(ws.health_score || "100")}%</span>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Machine Downtime Log Table */}
          <div className="bg-white border border-stone-200 rounded-xl p-5 space-y-3">
            <span className="text-xs font-semibold text-stone-800 uppercase tracking-wider">
              Recent Downtime & Breakdown Events
            </span>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-stone-50 border-b border-stone-200 text-stone-600">
                  <tr>
                    <th className="py-2.5 px-3">Event Number</th>
                    <th className="py-2.5 px-3">Reason</th>
                    <th className="py-2.5 px-3">Fault Code</th>
                    <th className="py-2.5 px-3">Duration (mins)</th>
                    <th className="py-2.5 px-3">Status</th>
                    <th className="py-2.5 px-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-100">
                  {downtimes.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="py-6 text-center text-stone-400">
                        Zero machine stoppages recorded.
                      </td>
                    </tr>
                  ) : (
                    downtimes.map((dt) => (
                      <tr key={dt.downtime_id}>
                        <td className="py-2.5 px-3 font-medium text-stone-900">{dt.downtime_number}</td>
                        <td className="py-2.5 px-3 text-stone-700">{dt.reason}</td>
                        <td className="py-2.5 px-3 text-stone-500">{dt.fault_code || "—"}</td>
                        <td className="py-2.5 px-3 font-semibold text-stone-900">{parseFloat(dt.duration_mins || "0").toFixed(1)}</td>
                        <td className="py-2.5 px-3">
                          <span
                            className={`text-[10px] font-bold px-2 py-0.5 rounded ${
                              dt.status === "RESOLVED"
                                ? "bg-emerald-100 text-emerald-800"
                                : "bg-red-100 text-red-800"
                            }`}
                          >
                            {dt.status}
                          </span>
                        </td>
                        <td className="py-2.5 px-3 text-right">
                          {dt.status === "OPEN" && (
                            <button
                              onClick={() => handleResolveDowntime(dt.downtime_id)}
                              className="px-2.5 py-1 text-[11px] font-medium bg-emerald-600 hover:bg-emerald-700 text-white rounded transition shadow-sm"
                            >
                              Resolve
                            </button>
                          )}
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

      {/* --- TAB 6: CP-SAT SCHEDULER --- */}
      {activeTab === "scheduler" && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold text-stone-900">CP-SAT Autonomous Job-Shop Scheduler</h2>
              <p className="text-xs text-stone-500">Google OR-Tools solver minimizing makespan and resolving dynamic edge machine failures</p>
            </div>
            <button
              onClick={handleSolveSchedule}
              disabled={solving}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-medium bg-stone-900 hover:bg-stone-800 text-white rounded-lg shadow-sm"
            >
              <Cpu className={`w-3.5 h-3.5 ${solving ? "animate-spin" : ""}`} />
              {solving ? "Solving..." : "Run CP-SAT Optimizer"}
            </button>
          </div>

          {/* Fault Simulation Bar */}
          <div className="p-4 bg-amber-50 border border-amber-200 rounded-xl flex items-center justify-between">
            <div className="flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-amber-700" />
              <div>
                <span className="text-xs font-bold text-amber-900">Dynamic Re-Routing Simulation</span>
                <p className="text-[11px] text-amber-700">Simulate machine breakdown to test automated CP-SAT rerouting</p>
              </div>
            </div>
            <div className="flex gap-2">
              {workstations.slice(0, 3).map((ws) => (
                <button
                  key={ws.workstation_id}
                  onClick={() => handleSimulateFault(ws.workstation_code)}
                  disabled={faultingCode === ws.workstation_code}
                  className="px-2.5 py-1 text-xs font-medium bg-white hover:bg-amber-100 text-amber-800 border border-amber-300 rounded shadow-sm"
                >
                  Break {ws.workstation_code}
                </button>
              ))}
            </div>
          </div>

          {/* Gantt Timeline View */}
          {scheduleResult && (
            <div className="bg-white border border-stone-200 rounded-xl p-5 space-y-4">
              <div className="flex items-center justify-between border-b border-stone-100 pb-3">
                <span className="text-xs font-semibold text-stone-800 uppercase tracking-wider">
                  Optimal Gantt Schedule Timeline
                </span>
                <div className="text-xs text-stone-600 flex gap-4">
                  <span>Status: <strong className="text-emerald-700">{scheduleResult.solver_status}</strong></span>
                  <span>Total Makespan: <strong>{scheduleResult.makespan_minutes} mins</strong></span>
                  <span>Solve Time: <strong>{scheduleResult.solve_time_seconds}s</strong></span>
                </div>
              </div>

              <div className="space-y-3">
                {Object.entries(scheduleResult.workstation_schedules || {}).map(([wsCode, ops]: any) => (
                  <div key={wsCode} className="space-y-1">
                    <div className="text-xs font-bold text-stone-700">{wsCode}</div>
                    <div className="h-8 bg-stone-100 rounded-lg relative overflow-hidden flex items-center">
                      {ops.map((op: any, idx: number) => {
                        const totalMins = scheduleResult.makespan_minutes || 100;
                        const leftPct = (op.start_minute / totalMins) * 100;
                        const widthPct = Math.max(5, (op.duration_minutes / totalMins) * 100);

                        return (
                          <div
                            key={idx}
                            style={{ left: `${leftPct}%`, width: `${widthPct}%` }}
                            className="absolute h-6 bg-stone-800 text-white rounded text-[10px] flex items-center justify-center font-medium px-1 truncate shadow"
                            title={`${op.operation_name} (${op.start_minute}m - ${op.end_minute}m)`}
                          >
                            {op.job_id} ({op.duration_minutes}m)
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* --- MODAL: NEW WORKSTATION --- */}
      {showWsModal && (
        <div className="fixed inset-0 bg-stone-900/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl border border-stone-200 shadow-xl max-w-md w-full p-5 space-y-4">
            <h3 className="text-sm font-bold text-stone-900">Register Factory Workstation</h3>
            <form onSubmit={handleCreateWorkstation} className="space-y-3">
              <div>
                <label className="text-[11px] font-semibold text-stone-600">Workstation Code</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. WS-CNC-03"
                  value={wsCode}
                  onChange={(e) => setWsCode(e.target.value)}
                  className="w-full text-xs p-2 border border-stone-300 rounded-lg uppercase"
                />
              </div>
              <div>
                <label className="text-[11px] font-semibold text-stone-600">Workstation Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. 5-Axis Precision Mill"
                  value={wsName}
                  onChange={(e) => setWsName(e.target.value)}
                  className="w-full text-xs p-2 border border-stone-300 rounded-lg"
                />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-[11px] font-semibold text-stone-600">Type</label>
                  <select
                    value={wsType}
                    onChange={(e) => setWsType(e.target.value)}
                    className="w-full text-xs p-2 border border-stone-300 rounded-lg"
                  >
                    <option value="GENERAL">General</option>
                    <option value="CNC">CNC</option>
                    <option value="LATHE">Lathe</option>
                    <option value="ASSEMBLY">Assembly</option>
                    <option value="PACKAGING">Packaging</option>
                    <option value="QC">Quality Control</option>
                  </select>
                </div>
                <div>
                  <label className="text-[11px] font-semibold text-stone-600">Hourly Rate ($)</label>
                  <input
                    type="number"
                    step="0.01"
                    required
                    value={wsRate}
                    onChange={(e) => setWsRate(e.target.value)}
                    className="w-full text-xs p-2 border border-stone-300 rounded-lg"
                  />
                </div>
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowWsModal(false)}
                  className="px-3 py-1.5 text-xs text-stone-600 hover:bg-stone-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-3.5 py-1.5 text-xs font-medium bg-stone-900 hover:bg-stone-800 text-white rounded-lg"
                >
                  Register Machine
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* --- MODAL: NEW OPERATION --- */}
      {showOpModal && (
        <div className="fixed inset-0 bg-stone-900/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl border border-stone-200 shadow-xl max-w-md w-full p-5 space-y-4">
            <h3 className="text-sm font-bold text-stone-900">Create Manufacturing Operation</h3>
            <form onSubmit={handleCreateOperation} className="space-y-3">
              <div>
                <label className="text-[11px] font-semibold text-stone-600">Operation Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. CNC Milling, Sub-Assembly"
                  value={opName}
                  onChange={(e) => setOpName(e.target.value)}
                  className="w-full text-xs p-2 border border-stone-300 rounded-lg"
                />
              </div>
              <div>
                <label className="text-[11px] font-semibold text-stone-600">Default Workstation (Optional)</label>
                <select
                  value={opWsId}
                  onChange={(e) => setOpWsId(e.target.value)}
                  className="w-full text-xs p-2 border border-stone-300 rounded-lg"
                >
                  <option value="">Any Qualified Machine</option>
                  {workstations.map((ws) => (
                    <option key={ws.workstation_id} value={ws.workstation_id}>
                      {ws.workstation_code} - {ws.workstation_name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-[11px] font-semibold text-stone-600">Description</label>
                <textarea
                  rows={2}
                  value={opDesc}
                  onChange={(e) => setOpDesc(e.target.value)}
                  className="w-full text-xs p-2 border border-stone-300 rounded-lg"
                />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowOpModal(false)}
                  className="px-3 py-1.5 text-xs text-stone-600 hover:bg-stone-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-3.5 py-1.5 text-xs font-medium bg-stone-900 hover:bg-stone-800 text-white rounded-lg"
                >
                  Save Operation
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* --- MODAL: NEW ROUTING --- */}
      {showRoutingModal && (
        <div className="fixed inset-0 bg-stone-900/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl border border-stone-200 shadow-xl max-w-lg w-full p-5 space-y-4">
            <h3 className="text-sm font-bold text-stone-900">Define Production Routing Sequence</h3>
            <form onSubmit={handleCreateRouting} className="space-y-3">
              <div>
                <label className="text-[11px] font-semibold text-stone-600">Routing Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Standard 3-Step Assembly"
                  value={routeName}
                  onChange={(e) => setRouteName(e.target.value)}
                  className="w-full text-xs p-2 border border-stone-300 rounded-lg"
                />
              </div>

              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <span className="text-[11px] font-semibold text-stone-700">Operational Steps</span>
                  <button
                    type="button"
                    onClick={() =>
                      setRouteOps([
                        ...routeOps,
                        { operation_id: "", workstation_id: "", time_in_mins: "15", hourly_rate: "45", batch_size: "1" }
                      ])
                    }
                    className="text-[10px] text-emerald-700 hover:underline"
                  >
                    + Add Step
                  </button>
                </div>

                {routeOps.map((ro, idx) => (
                  <div key={idx} className="p-3 border border-stone-200 rounded-lg bg-stone-50 space-y-2">
                    <div className="flex items-center justify-between pb-1">
                      <span className="text-[10px] font-bold text-stone-700 uppercase tracking-wider">Step #{idx + 1}</span>
                      {routeOps.length > 1 && (
                        <button
                          type="button"
                          onClick={() => setRouteOps(routeOps.filter((_, i) => i !== idx))}
                          className="text-[10px] text-red-600 hover:text-red-700 flex items-center gap-1 font-medium"
                        >
                          <Trash2 className="w-3 h-3" />
                          <span>Remove</span>
                        </button>
                      )}
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="block text-[10px] font-medium text-stone-600 mb-0.5">Operation</label>
                        <select
                          required
                          value={ro.operation_id}
                          onChange={(e) => {
                            const updated = [...routeOps];
                            updated[idx].operation_id = e.target.value;
                            setRouteOps(updated);
                          }}
                          className="w-full text-xs p-1.5 border border-stone-300 rounded bg-white"
                        >
                          <option value="">Select Operation...</option>
                          {operations.map((op) => (
                            <option key={op.operation_id} value={op.operation_id}>
                              {op.operation_name}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className="block text-[10px] font-medium text-stone-600 mb-0.5">Workstation / Machine</label>
                        <select
                          value={ro.workstation_id}
                          onChange={(e) => {
                            const updated = [...routeOps];
                            updated[idx].workstation_id = e.target.value;
                            setRouteOps(updated);
                          }}
                          className="w-full text-xs p-1.5 border border-stone-300 rounded bg-white"
                        >
                          <option value="">Any Machine</option>
                          {workstations.map((ws) => (
                            <option key={ws.workstation_id} value={ws.workstation_id}>
                              {ws.workstation_code}
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="block text-[10px] font-medium text-stone-600 mb-0.5">Cycle Time (Mins)</label>
                        <input
                          type="number"
                          step="0.1"
                          placeholder="e.g. 15"
                          value={ro.time_in_mins}
                          onChange={(e) => {
                            const updated = [...routeOps];
                            updated[idx].time_in_mins = e.target.value;
                            setRouteOps(updated);
                          }}
                          className="w-full text-xs p-1.5 border border-stone-300 rounded bg-white"
                        />
                      </div>
                      <div>
                        <label className="block text-[10px] font-medium text-stone-600 mb-0.5">Hourly Cost Rate ($)</label>
                        <input
                          type="number"
                          step="0.01"
                          placeholder="e.g. 45.00"
                          value={ro.hourly_rate}
                          onChange={(e) => {
                            const updated = [...routeOps];
                            updated[idx].hourly_rate = e.target.value;
                            setRouteOps(updated);
                          }}
                          className="w-full text-xs p-1.5 border border-stone-300 rounded bg-white"
                        />
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowRoutingModal(false)}
                  className="px-3 py-1.5 text-xs text-stone-600 hover:bg-stone-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-3.5 py-1.5 text-xs font-medium bg-stone-900 hover:bg-stone-800 text-white rounded-lg"
                >
                  Save Routing
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* --- MODAL: NEW BOM --- */}
      {showBomModal && (
        <div className="fixed inset-0 bg-stone-900/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl border border-stone-200 shadow-xl max-w-lg w-full p-5 space-y-4 max-h-[90vh] overflow-y-auto">
            <h3 className="text-sm font-bold text-stone-900">Create Bill of Materials (BOM)</h3>
            <form onSubmit={handleCreateBom} className="space-y-3">
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-[11px] font-semibold text-stone-600">BOM Number</label>
                  <input
                    type="text"
                    required
                    placeholder="BOM-PROD-01"
                    value={bomNumber}
                    onChange={(e) => setBomNumber(e.target.value)}
                    className="w-full text-xs p-2 border border-stone-300 rounded-lg uppercase"
                  />
                </div>
                <div>
                  <label className="text-[11px] font-semibold text-stone-600">Output Quantity (Units to Produce)</label>
                  <input
                    type="number"
                    step="0.01"
                    required
                    value={bomQty}
                    onChange={(e) => setBomQty(e.target.value)}
                    className="w-full text-xs p-2 border border-stone-300 rounded-lg"
                  />
                </div>
              </div>

              <div>
                <label className="text-[11px] font-semibold text-stone-600">Finished Good / Target Assembly</label>
                <select
                  required
                  value={bomItemId}
                  onChange={(e) => setBomItemId(e.target.value)}
                  className="w-full text-xs p-2 border border-stone-300 rounded-lg"
                >
                  <option value="">Select Item...</option>
                  {items.map((it) => (
                    <option key={it.item_id} value={it.item_id}>
                      {it.item_name} ({it.item_code})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="text-[11px] font-semibold text-stone-600">Routing (Optional)</label>
                <select
                  value={bomRoutingId}
                  onChange={(e) => setBomRoutingId(e.target.value)}
                  className="w-full text-xs p-2 border border-stone-300 rounded-lg"
                >
                  <option value="">No Routing Sequence</option>
                  {routings.map((rt) => (
                    <option key={rt.routing_id} value={rt.routing_id}>
                      {rt.routing_name} ({rt.operations?.length || 0} steps)
                    </option>
                  ))}
                </select>
              </div>

              {/* Component Items */}
              <div className="space-y-2 pt-2 border-t border-stone-100">
                <div className="flex justify-between items-center">
                  <span className="text-[11px] font-semibold text-stone-700">Raw Material Components</span>
                  <button
                    type="button"
                    onClick={() =>
                      setBomComponents([
                        ...bomComponents,
                        { item_id: "", quantity: "1.0", rate: "10.0", scrap_percentage: "0.0" }
                      ])
                    }
                    className="text-[10px] text-emerald-700 hover:underline"
                  >
                    + Add Item
                  </button>
                </div>

                {bomComponents.map((c, idx) => (
                  <div key={idx} className="p-3 border border-stone-200 rounded-lg bg-stone-50 space-y-2">
                    <div className="flex items-center justify-between pb-1">
                      <span className="text-[10px] font-bold text-stone-700 uppercase tracking-wider">
                        Component Item #{idx + 1}
                      </span>
                      {bomComponents.length > 1 && (
                        <button
                          type="button"
                          onClick={() => setBomComponents(bomComponents.filter((_, i) => i !== idx))}
                          className="text-[10px] text-red-600 hover:text-red-700 flex items-center gap-1 font-medium"
                        >
                          <Trash2 className="w-3 h-3" />
                          <span>Remove</span>
                        </button>
                      )}
                    </div>

                    <div>
                      <label className="block text-[10px] font-medium text-stone-600 mb-0.5">Component / Raw Material</label>
                      <select
                        required
                        value={c.item_id}
                        onChange={(e) => {
                          const updated = [...bomComponents];
                          updated[idx].item_id = e.target.value;
                          setBomComponents(updated);
                        }}
                        className="w-full text-xs p-1.5 border border-stone-300 rounded bg-white"
                      >
                        <option value="">Select Component...</option>
                        {items.map((it) => (
                          <option key={it.item_id} value={it.item_id}>
                            {it.item_name} ({it.item_code})
                          </option>
                        ))}
                      </select>
                    </div>

                    <div className="grid grid-cols-3 gap-2">
                      <div>
                        <label className="block text-[10px] font-medium text-stone-600 mb-0.5">Quantity</label>
                        <input
                          type="number"
                          step="0.01"
                          required
                          placeholder="e.g. 1.0"
                          value={c.quantity}
                          onChange={(e) => {
                            const updated = [...bomComponents];
                            updated[idx].quantity = e.target.value;
                            setBomComponents(updated);
                          }}
                          className="w-full text-xs p-1.5 border border-stone-300 rounded bg-white"
                        />
                      </div>
                      <div>
                        <label className="block text-[10px] font-medium text-stone-600 mb-0.5">Unit Rate ($)</label>
                        <input
                          type="number"
                          step="0.01"
                          required
                          placeholder="e.g. 10.00"
                          value={c.rate}
                          onChange={(e) => {
                            const updated = [...bomComponents];
                            updated[idx].rate = e.target.value;
                            setBomComponents(updated);
                          }}
                          className="w-full text-xs p-1.5 border border-stone-300 rounded bg-white"
                        />
                      </div>
                      <div>
                        <label className="block text-[10px] font-medium text-stone-600 mb-0.5">Scrap (%)</label>
                        <input
                          type="number"
                          step="0.1"
                          placeholder="e.g. 0.0"
                          value={c.scrap_percentage}
                          onChange={(e) => {
                            const updated = [...bomComponents];
                            updated[idx].scrap_percentage = e.target.value;
                            setBomComponents(updated);
                          }}
                          className="w-full text-xs p-1.5 border border-stone-300 rounded bg-white"
                        />
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              <div className="flex justify-end gap-2 pt-3">
                <button
                  type="button"
                  onClick={() => setShowBomModal(false)}
                  className="px-3 py-1.5 text-xs text-stone-600 hover:bg-stone-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-3.5 py-1.5 text-xs font-medium bg-stone-900 hover:bg-stone-800 text-white rounded-lg"
                >
                  Create BOM
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* --- MODAL: NEW PRODUCTION PLAN --- */}
      {showPlanModal && (
        <div className="fixed inset-0 bg-stone-900/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl border border-stone-200 shadow-xl max-w-lg w-full p-5 space-y-4 max-h-[90vh] overflow-y-auto">
            <div>
              <h3 className="text-sm font-bold text-stone-900">Create Production Plan (MRP)</h3>
              <p className="text-[11px] text-stone-500 mt-0.5">
                Plan manufactured items. MRP will explode their active Bills of Materials to calculate gross component demand and warehouse shortages.
              </p>
            </div>
            <form onSubmit={handleCreatePlan} className="space-y-3">
              <div>
                <label className="text-[11px] font-semibold text-stone-600">Plan Number</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. PLAN-2026-001"
                  value={planNumber}
                  onChange={(e) => setPlanNumber(e.target.value)}
                  className="w-full text-xs p-2 border border-stone-300 rounded-lg uppercase"
                />
              </div>

              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <span className="text-[11px] font-semibold text-stone-700">Finished Items to Plan</span>
                  <button
                    type="button"
                    onClick={() => setPlanItems([...planItems, { item_id: "", planned_qty: "10.0" }])}
                    className="text-[10px] text-emerald-700 hover:underline"
                  >
                    + Add Item
                  </button>
                </div>

                {planItems.map((pi, idx) => {
                  const hasBom = pi.item_id ? boms.some((b) => b.item_id === pi.item_id) : true;
                  return (
                    <div key={idx} className="p-3 border border-stone-200 rounded-lg bg-stone-50 space-y-2">
                      <div className="flex items-center justify-between pb-1">
                        <span className="text-[10px] font-bold text-stone-700 uppercase tracking-wider">
                          Planned Item #{idx + 1}
                        </span>
                        {planItems.length > 1 && (
                          <button
                            type="button"
                            onClick={() => setPlanItems(planItems.filter((_, i) => i !== idx))}
                            className="text-[10px] text-red-600 hover:text-red-700 flex items-center gap-1 font-medium"
                          >
                            <Trash2 className="w-3 h-3" />
                            <span>Remove</span>
                          </button>
                        )}
                      </div>

                      <div className="grid grid-cols-3 gap-2">
                        <div className="col-span-2">
                          <label className="block text-[10px] font-medium text-stone-600 mb-0.5">
                            Target Manufactured Item
                          </label>
                          <select
                            required
                            value={pi.item_id}
                            onChange={(e) => {
                              const updated = [...planItems];
                              updated[idx].item_id = e.target.value;
                              setPlanItems(updated);
                            }}
                            className="w-full text-xs p-1.5 border border-stone-300 rounded bg-white"
                          >
                            <option value="">Select Item...</option>
                            {items.map((it) => {
                              const itemHasBom = boms.some((b) => b.item_id === it.item_id);
                              return (
                                <option key={it.item_id} value={it.item_id}>
                                  {it.item_name} ({it.item_code}) {itemHasBom ? "✓ [Has BOM]" : "⚠ [No BOM]"}
                                </option>
                              );
                            })}
                          </select>
                        </div>
                        <div>
                          <label className="block text-[10px] font-medium text-stone-600 mb-0.5">
                            Planned Output Qty
                          </label>
                          <input
                            type="number"
                            step="0.01"
                            required
                            placeholder="e.g. 10.0"
                            value={pi.planned_qty}
                            onChange={(e) => {
                              const updated = [...planItems];
                              updated[idx].planned_qty = e.target.value;
                              setPlanItems(updated);
                            }}
                            className="w-full text-xs p-1.5 border border-stone-300 rounded bg-white"
                          />
                        </div>
                      </div>

                      {pi.item_id && !hasBom && (
                        <div className="p-2 bg-amber-50 border border-amber-200 rounded text-[11px] text-amber-800 flex items-center gap-1.5">
                          <AlertTriangle className="w-3.5 h-3.5 text-amber-600 shrink-0" />
                          <span>
                            This item has no Bill of Materials. Component requirements cannot be exploded for items without a BOM.
                          </span>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowPlanModal(false)}
                  className="px-3 py-1.5 text-xs text-stone-600 hover:bg-stone-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-3.5 py-1.5 text-xs font-medium bg-stone-900 hover:bg-stone-800 text-white rounded-lg"
                >
                  Create Plan
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* --- MODAL: NEW WORK ORDER --- */}
      {showWoModal && (
        <div className="fixed inset-0 bg-stone-900/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl border border-stone-200 shadow-xl max-w-md w-full p-5 space-y-4">
            <h3 className="text-sm font-bold text-stone-900">Create Production Work Order</h3>
            <form onSubmit={handleCreateWorkOrder} className="space-y-3">
              <div>
                <label className="text-[11px] font-semibold text-stone-600">Work Order Number</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. WO-BATCH-001"
                  value={woNumber}
                  onChange={(e) => setWoNumber(e.target.value)}
                  className="w-full text-xs p-2 border border-stone-300 rounded-lg uppercase"
                />
              </div>

              <div>
                <label className="text-[11px] font-semibold text-stone-600">Finished Product Item</label>
                <select
                  required
                  value={woItemId}
                  onChange={(e) => setWoItemId(e.target.value)}
                  className="w-full text-xs p-2 border border-stone-300 rounded-lg"
                >
                  <option value="">Select Item...</option>
                  {items.map((it) => {
                    const itemHasBom = boms.some((b) => b.item_id === it.item_id);
                    return (
                      <option key={it.item_id} value={it.item_id}>
                        {it.item_name} ({it.item_code}) {itemHasBom ? "✓ [Has BOM]" : "⚠ [No BOM]"}
                      </option>
                    );
                  })}
                </select>
                {woItemId && !boms.some((b) => b.item_id === woItemId) && (
                  <div className="p-2 mt-1.5 bg-amber-50 border border-amber-200 rounded text-[11px] text-amber-800 flex items-center gap-1.5">
                    <AlertTriangle className="w-3.5 h-3.5 text-amber-600 shrink-0" />
                    <span>No BOM found for this item. Raw materials cannot be staged to WIP without an active BOM.</span>
                  </div>
                )}
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-[11px] font-semibold text-stone-600">BOM Reference (Optional)</label>
                  <select
                    value={woBomId}
                    onChange={(e) => setWoBomId(e.target.value)}
                    className="w-full text-xs p-2 border border-stone-300 rounded-lg"
                  >
                    <option value="">Default Active BOM</option>
                    {boms.map((b) => (
                      <option key={b.bom_id} value={b.bom_id}>
                        {b.bom_number} {b.item_id === woItemId ? "★ [Matches Item]" : ""}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="text-[11px] font-semibold text-stone-600">Planned Quantity</label>
                  <input
                    type="number"
                    step="0.01"
                    required
                    placeholder="e.g. 5.0"
                    value={woQty}
                    onChange={(e) => setWoQty(e.target.value)}
                    className="w-full text-xs p-2 border border-stone-300 rounded-lg"
                  />
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowWoModal(false)}
                  className="px-3 py-1.5 text-xs text-stone-600 hover:bg-stone-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-3.5 py-1.5 text-xs font-medium bg-stone-900 hover:bg-stone-800 text-white rounded-lg"
                >
                  Create Work Order
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* --- MODAL: RECORD DOWNTIME --- */}
      {showDowntimeModal && (
        <div className="fixed inset-0 bg-stone-900/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl border border-stone-200 shadow-xl max-w-md w-full p-5 space-y-4">
            <h3 className="text-sm font-bold text-stone-900">Record Machine Breakdown / Stoppage</h3>
            <form onSubmit={handleRecordDowntime} className="space-y-3">
              <div>
                <label className="text-[11px] font-semibold text-stone-600">Downtime Ticket #</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. DT-2026-001"
                  value={dtNumber}
                  onChange={(e) => setDtNumber(e.target.value)}
                  className="w-full text-xs p-2 border border-stone-300 rounded-lg uppercase"
                />
              </div>

              <div>
                <label className="text-[11px] font-semibold text-stone-600">Faulted Workstation</label>
                <select
                  required
                  value={dtWsId}
                  onChange={(e) => setDtWsId(e.target.value)}
                  className="w-full text-xs p-2 border border-stone-300 rounded-lg"
                >
                  <option value="">Select Machine...</option>
                  {workstations.map((ws) => (
                    <option key={ws.workstation_id} value={ws.workstation_id}>
                      {ws.workstation_code} - {ws.workstation_name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-[11px] font-semibold text-stone-600">Reason</label>
                  <select
                    value={dtReason}
                    onChange={(e) => setDtReason(e.target.value)}
                    className="w-full text-xs p-2 border border-stone-300 rounded-lg"
                  >
                    <option value="MECHANICAL_BREAKDOWN">Mechanical Breakdown</option>
                    <option value="ELECTRICAL_FAULT">Electrical Fault</option>
                    <option value="TOOL_WEAR">Tool Wear / Breakage</option>
                    <option value="SETUP_CHANGEOVER">Setup & Changeover</option>
                    <option value="MATERIAL_STARVATION">Material Starvation</option>
                    <option value="OPERATOR_UNAVAILABLE">Operator Unavailable</option>
                  </select>
                </div>
                <div>
                  <label className="text-[11px] font-semibold text-stone-600">Fault Code (Optional)</label>
                  <input
                    type="text"
                    placeholder="e.g. ERR-MOTOR-OVERHEAT"
                    value={dtCode}
                    onChange={(e) => setDtCode(e.target.value)}
                    className="w-full text-xs p-2 border border-stone-300 rounded-lg uppercase"
                  />
                </div>
              </div>

              <div>
                <label className="text-[11px] font-semibold text-stone-600">Notes & Observations</label>
                <textarea
                  rows={2}
                  value={dtNotes}
                  onChange={(e) => setDtNotes(e.target.value)}
                  className="w-full text-xs p-2 border border-stone-300 rounded-lg"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowDowntimeModal(false)}
                  className="px-3 py-1.5 text-xs text-stone-600 hover:bg-stone-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-3.5 py-1.5 text-xs font-medium bg-red-600 hover:bg-red-700 text-white rounded-lg shadow-sm"
                >
                  Lock Machine & Log Stoppage
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* --- MODAL: SCRAP & DEFECT LOGGING --- */}
      {showScrapModal && scrapTargetJc && (
        <div className="fixed inset-0 bg-stone-900/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl border border-stone-200 shadow-xl max-w-sm w-full p-5 space-y-4">
            <div>
              <h3 className="text-sm font-bold text-stone-900">
                {scrapActionType === "complete" ? "Complete Operation Traveler" : "Pause Session"}
              </h3>
              <p className="text-xs text-stone-500 mt-0.5">{scrapTargetJc.job_card_number} — {scrapTargetJc.operation?.operation_name}</p>
            </div>

            <form onSubmit={handleSubmitScrapModal} className="space-y-3">
              <div>
                <label className="text-[11px] font-semibold text-stone-700">Good Completed Quantity</label>
                <input
                  type="number"
                  step="0.01"
                  required
                  value={scrapCompletedQty}
                  onChange={(e) => setScrapCompletedQty(e.target.value)}
                  className="w-full text-sm font-bold p-2 border border-stone-300 rounded-lg"
                />
              </div>

              <div>
                <label className="text-[11px] font-semibold text-stone-700">Defect / Scrap Quantity</label>
                <input
                  type="number"
                  step="0.01"
                  required
                  value={scrapDefectQty}
                  onChange={(e) => setScrapDefectQty(e.target.value)}
                  className="w-full text-sm font-bold p-2 border border-red-300 bg-red-50/50 rounded-lg text-red-900"
                />
                <p className="text-[10px] text-stone-400 mt-1">Defective parts are credited to scrap warehouse and tracked in Quality KPI</p>
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowScrapModal(false)}
                  className="px-3 py-1.5 text-xs text-stone-600 hover:bg-stone-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-3.5 py-1.5 text-xs font-bold bg-stone-900 hover:bg-stone-800 text-white rounded-lg shadow-sm"
                >
                  Submit & Confirm
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
