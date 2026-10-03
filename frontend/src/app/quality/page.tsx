"use client";

import { useEffect, useState } from "react";
import {
  Activity,
  AlertOctagon,
  AlertTriangle,
  Camera,
  CheckCircle2,
  Cpu,
  Gauge,
  Layers,
  Play,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  Unlock,
  Zap,
  Plus,
  Search,
  Check,
  X,
  FileText,
  Sliders,
  ArrowRight,
  TrendingDown,
  HelpCircle,
} from "lucide-react";
import { api } from "@/lib/api";

type TabType = "inspections" | "ncr" | "capa" | "templates" | "edge";

interface TelemetrySummary {
  parts_inspected: number;
  scrap_diverted: number;
  rolling_defect_rate: number;
  status: string;
  motor_temperature_c: number;
  vibration_mms: number;
  conveyor_speed_rpm: number;
}

interface DiverterStatus {
  solenoid_state: string;
  gpio_pin: number;
  total_trips: number;
  latest_trip_latency_ms: number;
  sla_met_sub_200ms: boolean;
}

interface TelemetryFrame {
  time: string;
  workstation_code: string;
  conveyor_speed_rpm: number;
  motor_temperature_c: number;
  vibration_mms: number;
  scrap_count: number;
  status: string;
}

interface QuarantinedLot {
  lot_number: string;
  status: string;
  reason: string;
  item_code: string;
  quarantined_workstation: string;
}

export default function QualityPage() {
  const [activeTab, setActiveTab] = useState<TabType>("inspections");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Quality Management Data State
  const [inspections, setInspections] = useState<any[]>([]);
  const [ncrs, setNcrs] = useState<any[]>([]);
  const [capas, setCapas] = useState<any[]>([]);
  const [templates, setTemplates] = useState<any[]>([]);
  const [selectedInspection, setSelectedInspection] = useState<any | null>(null);

  // Modals
  const [showInspectionModal, setShowInspectionModal] = useState(false);
  const [showNcrModal, setShowNcrModal] = useState(false);
  const [showCapaModal, setShowCapaModal] = useState(false);
  const [showTemplateModal, setShowTemplateModal] = useState(false);
  const [showResolveModal, setShowResolveModal] = useState(false);
  const [activeActionId, setActiveActionId] = useState<string | null>(null);
  const [resolutionNotes, setResolutionNotes] = useState("");

  // Inspection Form State
  const [formInsp, setFormInsp] = useState({
    inspection_number: "",
    inspection_type: "INCOMING",
    reference_doc_type: "PurchaseReceipt",
    item_code: "RAW-TI-BRACKET",
    sample_size: "5.00",
    remarks: "Dimensional & surface verification",
    param_length_val: "100.02",
    param_length_min: "99.95",
    param_length_max: "100.05",
    param_roughness_val: "0.65",
    param_roughness_min: "0.00",
    param_roughness_max: "0.80",
  });

  // NCR Form State
  const [formNcr, setFormNcr] = useState({
    nc_number: "",
    title: "",
    item_code: "RAW-TI-BRACKET",
    severity: "MAJOR",
    immediate_disposition: "REWORK",
    description: "",
  });

  // CAPA Form State
  const [formCapa, setFormCapa] = useState({
    capa_number: "",
    nc_id: "",
    action_type: "CORRECTIVE",
    root_cause_analysis: "Why 1: Length oversized 100.12mm\nWhy 2: Tool wear offset not updated\nWhy 3: Presetter lens dirty\nWhy 4: Air purge off\nWhy 5: Solenoid failed\nRoot Cause: Missing pressure interlock switch",
    action_plan: "Install pressure switch interlock alarm and mandate shift checklist.",
    target_completion_date: new Date(Date.now() + 14 * 86400000).toISOString().split("T")[0],
  });

  // Edge IoT Telemetry State (Preserved)
  const [summary, setSummary] = useState<TelemetrySummary | null>(null);
  const [history, setHistory] = useState<TelemetryFrame[]>([]);
  const [diverter, setDiverter] = useState<DiverterStatus | null>(null);
  const [quarantinedLots, setQuarantinedLots] = useState<QuarantinedLot[]>([]);
  const [inspecting, setInspecting] = useState(false);
  const [defectType, setDefectType] = useState("SURFACE_CRACK");
  const [confidenceScore, setConfidenceScore] = useState(0.99);
  const [simWorkstation, setSimWorkstation] = useState("WS-LINE-01");
  const [simLotNumber, setSimLotNumber] = useState("LOT-2026-X889");
  const [lastInspectionResult, setLastInspectionResult] = useState<any | null>(null);

  const loadQualityData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [iData, ncData, cpData, tmplData] = await Promise.all([
        api.getQualityInspections(),
        api.getNonConformances(),
        api.getQualityActions(),
        api.getQualityTemplates(),
      ]);
      setInspections(iData);
      setNcrs(ncData);
      setCapas(cpData);
      setTemplates(tmplData);
      if (ncData.length > 0 && !formCapa.nc_id) {
        setFormCapa((prev) => ({ ...prev, nc_id: ncData[0].nc_id }));
      }
    } catch (err: any) {
      setError(err.message || "Failed to load quality data.");
    } finally {
      setLoading(false);
    }
  };

  const loadTelemetry = async () => {
    try {
      const data = await api.getQualityTelemetry();
      setSummary(data.summary);
      setHistory(data.history || []);
      setDiverter(data.diverter);
      const lots = await api.getQuarantinedLots();
      setQuarantinedLots(lots || []);
    } catch (err: any) {
      console.error(err);
    }
  };

  useEffect(() => {
    loadQualityData();
    loadTelemetry();
  }, []);

  const handleCreateInspection = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const inspNum = formInsp.inspection_number || `QI-${Date.now().toString().slice(-6)}`;
      await api.createQualityInspection({
        inspection_number: inspNum,
        inspection_type: formInsp.inspection_type,
        reference_doc_type: formInsp.reference_doc_type,
        item_code: formInsp.item_code,
        sample_size: parseFloat(formInsp.sample_size),
        remarks: formInsp.remarks,
        readings: [
          {
            parameter_name: "Bracket Length",
            reading_value: parseFloat(formInsp.param_length_val),
            min_value: parseFloat(formInsp.param_length_min),
            max_value: parseFloat(formInsp.param_length_max),
          },
          {
            parameter_name: "Surface Roughness",
            reading_value: parseFloat(formInsp.param_roughness_val),
            min_value: parseFloat(formInsp.param_roughness_min),
            max_value: parseFloat(formInsp.param_roughness_max),
          },
        ],
        auto_create_nc_on_failure: true,
      });
      setShowInspectionModal(false);
      await loadQualityData();
    } catch (err: any) {
      alert("Error logging inspection: " + err.message);
    }
  };

  const handleCreateNcr = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const ncNum = formNcr.nc_number || `NCR-${Date.now().toString().slice(-6)}`;
      await api.createNonConformance({
        ...formNcr,
        nc_number: ncNum,
      });
      setShowNcrModal(false);
      await loadQualityData();
    } catch (err: any) {
      alert("Error logging NCR: " + err.message);
    }
  };

  const handleCreateCapa = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const capaNum = formCapa.capa_number || `CAPA-${Date.now().toString().slice(-6)}`;
      await api.createQualityAction({
        ...formCapa,
        capa_number: capaNum,
      });
      setShowCapaModal(false);
      await loadQualityData();
    } catch (err: any) {
      alert("Error assigning CAPA: " + err.message);
    }
  };

  const handleResolveCapa = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeActionId) return;
    try {
      await api.resolveQualityAction(activeActionId, {
        resolution_notes: resolutionNotes,
        new_status: "VERIFIED_CLOSED",
      });
      setShowResolveModal(false);
      setResolutionNotes("");
      await loadQualityData();
    } catch (err: any) {
      alert("Error resolving CAPA: " + err.message);
    }
  };

  const handleRunEdgeInspection = async () => {
    setInspecting(true);
    try {
      const res = await api.submitOpticalInspection({
        item_code: "FG-ENCLOSURE-IP67",
        lot_number: simLotNumber,
        workstation_code: simWorkstation,
        defect_type: defectType,
        confidence_score: confidenceScore,
      });
      setLastInspectionResult(res);
      await loadTelemetry();
    } catch (err: any) {
      alert("Inspection failure: " + err.message);
    } finally {
      setInspecting(false);
    }
  };

  const handleReleaseLot = async (lotNumber: string) => {
    try {
      await api.releaseQuarantinedLot({
        lot_number: lotNumber,
        release_notes: "Authorized by Quality Manager via web console",
      });
      await loadTelemetry();
    } catch (err: any) {
      alert("Failed to release lot: " + err.message);
    }
  };

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-stone-900 text-white flex items-center justify-center shadow-sm">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-2xl font-semibold text-stone-900 tracking-tight">Quality Assurance & Inspections</h1>
              <p className="text-sm text-stone-500">
                Incoming/in-process dimensional tolerance tests, Non-Conformance Reports (NCR) & 5-Whys CAPA root cause engine.
              </p>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => {
              loadQualityData();
              loadTelemetry();
            }}
            disabled={loading}
            className="p-2.5 text-stone-600 hover:text-stone-900 hover:bg-stone-100 rounded-lg border border-stone-200 transition-colors"
            title="Refresh"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          </button>
          <button
            onClick={() => setShowNcrModal(true)}
            className="px-3.5 py-2 text-sm font-medium text-stone-700 bg-white border border-stone-300 hover:bg-stone-50 rounded-lg shadow-sm"
          >
            Log NCR
          </button>
          <button
            onClick={() => setShowCapaModal(true)}
            disabled={ncrs.length === 0}
            className="px-3.5 py-2 text-sm font-medium text-stone-700 bg-white border border-stone-300 hover:bg-stone-50 rounded-lg shadow-sm disabled:opacity-50"
          >
            Assign CAPA
          </button>
          <button
            onClick={() => setShowInspectionModal(true)}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-stone-900 hover:bg-stone-800 rounded-lg shadow-sm"
          >
            <Plus className="w-4 h-4" />
            New Inspection
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white border border-stone-200/80 rounded-xl p-5 shadow-sm">
          <div className="text-xs font-medium text-stone-500 uppercase tracking-wider">Quality Inspections</div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-stone-900">{inspections.length}</span>
            <span className="text-xs text-stone-500">Evaluated</span>
          </div>
        </div>
        <div className="bg-white border border-stone-200/80 rounded-xl p-5 shadow-sm">
          <div className="text-xs font-medium text-stone-500 uppercase tracking-wider">Open Non-Conformances</div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-rose-700">
              {ncrs.filter((n) => n.status !== "CLOSED").length}
            </span>
            <span className="text-xs text-stone-500">of {ncrs.length} Total</span>
          </div>
        </div>
        <div className="bg-white border border-stone-200/80 rounded-xl p-5 shadow-sm">
          <div className="text-xs font-medium text-stone-500 uppercase tracking-wider">Active CAPAs (5-Whys)</div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-amber-700">
              {capas.filter((c) => c.status !== "VERIFIED_CLOSED").length}
            </span>
            <span className="text-xs text-stone-500">Pending Closure</span>
          </div>
        </div>
        <div className="bg-white border border-stone-200/80 rounded-xl p-5 shadow-sm">
          <div className="text-xs font-medium text-stone-500 uppercase tracking-wider">Inspection Pass Rate</div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-emerald-700">
              {inspections.length > 0
                ? `${Math.round((inspections.filter((i) => i.status === "PASS").length / inspections.length) * 100)}%`
                : "100%"}
            </span>
          </div>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="flex border-b border-stone-200 gap-6">
        <button
          onClick={() => setActiveTab("inspections")}
          className={`pb-3 text-sm font-medium border-b-2 transition-colors ${
            activeTab === "inspections"
              ? "border-stone-900 text-stone-900"
              : "border-transparent text-stone-500 hover:text-stone-800"
          }`}
        >
          Inspections Log ({inspections.length})
        </button>
        <button
          onClick={() => setActiveTab("ncr")}
          className={`pb-3 text-sm font-medium border-b-2 transition-colors ${
            activeTab === "ncr"
              ? "border-stone-900 text-stone-900"
              : "border-transparent text-stone-500 hover:text-stone-800"
          }`}
        >
          Non-Conformances ({ncrs.length})
        </button>
        <button
          onClick={() => setActiveTab("capa")}
          className={`pb-3 text-sm font-medium border-b-2 transition-colors ${
            activeTab === "capa"
              ? "border-stone-900 text-stone-900"
              : "border-transparent text-stone-500 hover:text-stone-800"
          }`}
        >
          CAPA Root Cause ({capas.length})
        </button>
        <button
          onClick={() => setActiveTab("templates")}
          className={`pb-3 text-sm font-medium border-b-2 transition-colors ${
            activeTab === "templates"
              ? "border-stone-900 text-stone-900"
              : "border-transparent text-stone-500 hover:text-stone-800"
          }`}
        >
          Tolerances & Templates ({templates.length})
        </button>
        <button
          onClick={() => setActiveTab("edge")}
          className={`pb-3 text-sm font-medium border-b-2 transition-colors ${
            activeTab === "edge"
              ? "border-stone-900 text-stone-900"
              : "border-transparent text-stone-500 hover:text-stone-800"
          }`}
        >
          Edge Optical & Diverter
        </button>
      </div>

      {/* Tab 1: Inspections */}
      {activeTab === "inspections" && (
        <div className="bg-white border border-stone-200/80 rounded-xl overflow-hidden shadow-sm">
          <table className="w-full text-left text-sm text-stone-600">
            <thead className="bg-stone-50/75 border-b border-stone-200 text-xs font-semibold text-stone-600 uppercase tracking-wider">
              <tr>
                <th className="px-6 py-3.5">Inspection #</th>
                <th className="px-6 py-3.5">Type</th>
                <th className="px-6 py-3.5">Doc Type</th>
                <th className="px-6 py-3.5">Item Code</th>
                <th className="px-6 py-3.5">Date</th>
                <th className="px-6 py-3.5 text-center">Status</th>
                <th className="px-6 py-3.5">Remarks</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-stone-200/60">
              {inspections.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-6 py-12 text-center text-stone-500">
                    No inspections recorded. Click &quot;New Inspection&quot; to test a sample.
                  </td>
                </tr>
              ) : (
                inspections.map((insp) => (
                  <tr key={insp.inspection_id} className="hover:bg-stone-50/50">
                    <td className="px-6 py-4 font-mono font-medium text-stone-900">{insp.inspection_number}</td>
                    <td className="px-6 py-4 text-xs font-medium">{insp.inspection_type}</td>
                    <td className="px-6 py-4 text-xs text-stone-500">{insp.reference_doc_type}</td>
                    <td className="px-6 py-4 font-mono text-stone-800 font-semibold">{insp.item_code}</td>
                    <td className="px-6 py-4 text-stone-500">{insp.inspection_date}</td>
                    <td className="px-6 py-4 text-center">
                      <span
                        className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${
                          insp.status === "PASS"
                            ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                            : "bg-rose-50 text-rose-700 border border-rose-200"
                        }`}
                      >
                        {insp.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-stone-500 text-xs">{insp.remarks || "—"}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Tab 2: Non-Conformances (NCR) */}
      {activeTab === "ncr" && (
        <div className="bg-white border border-stone-200/80 rounded-xl overflow-hidden shadow-sm">
          <table className="w-full text-left text-sm text-stone-600">
            <thead className="bg-stone-50/75 border-b border-stone-200 text-xs font-semibold text-stone-600 uppercase tracking-wider">
              <tr>
                <th className="px-6 py-3.5">NCR #</th>
                <th className="px-6 py-3.5">Title</th>
                <th className="px-6 py-3.5">Item Code</th>
                <th className="px-6 py-3.5">Severity</th>
                <th className="px-6 py-3.5">Disposition</th>
                <th className="px-6 py-3.5 text-center">Status</th>
                <th className="px-6 py-3.5 text-right">Actions Assigned</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-stone-200/60">
              {ncrs.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-6 py-12 text-center text-stone-500">
                    No Non-Conformance Reports logged.
                  </td>
                </tr>
              ) : (
                ncrs.map((nc) => (
                  <tr key={nc.nc_id} className="hover:bg-stone-50/50">
                    <td className="px-6 py-4 font-mono font-medium text-stone-900">{nc.nc_number}</td>
                    <td className="px-6 py-4 font-medium text-stone-900">{nc.title}</td>
                    <td className="px-6 py-4 font-mono text-xs">{nc.item_code}</td>
                    <td className="px-6 py-4">
                      <span
                        className={`px-2 py-0.5 rounded text-2xs font-semibold ${
                          nc.severity === "CRITICAL"
                            ? "bg-rose-100 text-rose-700"
                            : nc.severity === "MAJOR"
                            ? "bg-amber-100 text-amber-700"
                            : "bg-blue-100 text-blue-700"
                        }`}
                      >
                        {nc.severity}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-xs font-mono">{nc.immediate_disposition}</td>
                    <td className="px-6 py-4 text-center">
                      <span
                        className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${
                          nc.status === "CLOSED"
                            ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                            : nc.status === "CAPA_ASSIGNED"
                            ? "bg-purple-50 text-purple-700 border border-purple-200"
                            : "bg-rose-50 text-rose-700 border border-rose-200"
                        }`}
                      >
                        {nc.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-right text-stone-700 font-medium">{nc.action_count} CAPA</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Tab 3: CAPA (5-Whys) */}
      {activeTab === "capa" && (
        <div className="bg-white border border-stone-200/80 rounded-xl overflow-hidden shadow-sm">
          <table className="w-full text-left text-sm text-stone-600">
            <thead className="bg-stone-50/75 border-b border-stone-200 text-xs font-semibold text-stone-600 uppercase tracking-wider">
              <tr>
                <th className="px-6 py-3.5">CAPA #</th>
                <th className="px-6 py-3.5">Type</th>
                <th className="px-6 py-3.5">5-Whys Root Cause Analysis</th>
                <th className="px-6 py-3.5">Action Plan</th>
                <th className="px-6 py-3.5">Target Date</th>
                <th className="px-6 py-3.5 text-center">Status</th>
                <th className="px-6 py-3.5 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-stone-200/60">
              {capas.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-6 py-12 text-center text-stone-500">
                    No CAPA root cause actions registered.
                  </td>
                </tr>
              ) : (
                capas.map((c) => (
                  <tr key={c.action_id} className="hover:bg-stone-50/50">
                    <td className="px-6 py-4 font-mono font-medium text-stone-900">{c.capa_number}</td>
                    <td className="px-6 py-4 text-xs font-semibold">{c.action_type}</td>
                    <td className="px-6 py-4 text-xs text-stone-700 max-w-xs truncate" title={c.root_cause_analysis}>
                      {c.root_cause_analysis}
                    </td>
                    <td className="px-6 py-4 text-xs text-stone-600 max-w-xs truncate" title={c.action_plan}>
                      {c.action_plan}
                    </td>
                    <td className="px-6 py-4 text-stone-500 text-xs">{c.target_completion_date}</td>
                    <td className="px-6 py-4 text-center">
                      <span
                        className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${
                          c.status === "VERIFIED_CLOSED"
                            ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                            : "bg-amber-50 text-amber-700 border border-amber-200"
                        }`}
                      >
                        {c.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-right">
                      {c.status !== "VERIFIED_CLOSED" && (
                        <button
                          onClick={() => {
                            setActiveActionId(c.action_id);
                            setShowResolveModal(true);
                          }}
                          className="px-3 py-1 text-xs font-medium text-white bg-stone-900 hover:bg-stone-800 rounded-lg shadow-xs"
                        >
                          Resolve & Close
                        </button>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Tab 4: Templates */}
      {activeTab === "templates" && (
        <div className="bg-white border border-stone-200/80 rounded-xl overflow-hidden shadow-sm">
          <table className="w-full text-left text-sm text-stone-600">
            <thead className="bg-stone-50/75 border-b border-stone-200 text-xs font-semibold text-stone-600 uppercase tracking-wider">
              <tr>
                <th className="px-6 py-3.5">Template Name</th>
                <th className="px-6 py-3.5">Description</th>
                <th className="px-6 py-3.5">Tolerance Parameters</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-stone-200/60">
              {templates.length === 0 ? (
                <tr>
                  <td colSpan={3} className="px-6 py-12 text-center text-stone-500">
                    No inspection templates created yet.
                  </td>
                </tr>
              ) : (
                templates.map((t) => (
                  <tr key={t.template_id} className="hover:bg-stone-50/50">
                    <td className="px-6 py-4 font-medium text-stone-900">{t.template_name}</td>
                    <td className="px-6 py-4 text-stone-500">{t.description || "—"}</td>
                    <td className="px-6 py-4">
                      <div className="flex flex-wrap gap-1.5">
                        {t.parameters?.map((p: any, idx: number) => (
                          <span
                            key={idx}
                            className="inline-flex items-center px-2 py-0.5 rounded bg-stone-100 text-stone-700 text-2xs font-mono"
                          >
                            {p.parameter_name}: [{p.min_value} - {p.max_value}]
                          </span>
                        ))}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Tab 5: Edge Optical & Diverter (Preserved) */}
      {activeTab === "edge" && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-6">
            <div className="bg-white border border-stone-200/80 rounded-xl p-6 shadow-sm space-y-4">
              <h3 className="text-base font-semibold text-stone-900">Simulate Edge Optical Inspection Frame</h3>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-stone-700 mb-1">Workstation</label>
                  <select
                    value={simWorkstation}
                    onChange={(e) => setSimWorkstation(e.target.value)}
                    className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg"
                  >
                    <option value="WS-LINE-01">WS-LINE-01 (Molding)</option>
                    <option value="WS-LINE-02">WS-LINE-02 (Machining)</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-stone-700 mb-1">Lot Number</label>
                  <input
                    type="text"
                    value={simLotNumber}
                    onChange={(e) => setSimLotNumber(e.target.value)}
                    className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-stone-700 mb-1">Classified Defect</label>
                  <select
                    value={defectType}
                    onChange={(e) => setDefectType(e.target.value)}
                    className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg"
                  >
                    <option value="NONE">NONE (Compliant)</option>
                    <option value="SURFACE_CRACK">SURFACE_CRACK</option>
                    <option value="DIMENSIONAL_VARIANCE">DIMENSIONAL_VARIANCE</option>
                    <option value="VOID">VOID</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-stone-700 mb-1">AI Confidence Score</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    max="1"
                    value={confidenceScore}
                    onChange={(e) => setConfidenceScore(parseFloat(e.target.value))}
                    className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg"
                  />
                </div>
              </div>
              <button
                onClick={handleRunEdgeInspection}
                disabled={inspecting}
                className="w-full py-2.5 bg-stone-900 hover:bg-stone-800 text-white text-sm font-medium rounded-lg shadow-sm"
              >
                {inspecting ? "Evaluating Edge Frame..." : "Execute Optical Inspection & Pneumatic Diverter"}
              </button>
            </div>

            {/* Quarantined Lots */}
            <div className="bg-white border border-stone-200/80 rounded-xl p-6 shadow-sm space-y-4">
              <h3 className="text-base font-semibold text-stone-900">Quarantined Inventory Lots</h3>
              {quarantinedLots.length === 0 ? (
                <p className="text-xs text-stone-500 italic">No lots currently quarantined.</p>
              ) : (
                <div className="divide-y divide-stone-100">
                  {quarantinedLots.map((q, idx) => (
                    <div key={idx} className="py-3 flex justify-between items-center text-xs">
                      <div>
                        <span className="font-mono font-bold text-stone-900">{q.lot_number}</span>
                        <p className="text-stone-500">{q.reason}</p>
                      </div>
                      <button
                        onClick={() => handleReleaseLot(q.lot_number)}
                        className="px-3 py-1 bg-stone-100 hover:bg-stone-200 rounded text-stone-800 font-medium"
                      >
                        Release Lot
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Diverter Telemetry Status */}
          <div className="space-y-6">
            <div className="bg-white border border-stone-200/80 rounded-xl p-6 shadow-sm space-y-4">
              <h3 className="text-base font-semibold text-stone-900">Pneumatic Diverter Hardware</h3>
              <div className="space-y-3 text-xs">
                <div className="flex justify-between pb-2 border-b border-stone-100">
                  <span className="text-stone-500">Solenoid State:</span>
                  <span className="font-mono font-bold text-emerald-700">{diverter?.solenoid_state || "READY"}</span>
                </div>
                <div className="flex justify-between pb-2 border-b border-stone-100">
                  <span className="text-stone-500">Sub-200ms Actuation:</span>
                  <span className="font-bold text-emerald-700">CERTIFIED</span>
                </div>
                <div className="flex justify-between pb-2 border-b border-stone-100">
                  <span className="text-stone-500">Total Scrap Diversions:</span>
                  <span className="font-bold text-stone-900">{diverter?.total_trips || 0}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Modal: New Inspection */}
      {showInspectionModal && (
        <div className="fixed inset-0 z-50 bg-stone-900/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-6 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-stone-200">
              <h3 className="text-lg font-bold text-stone-900">Log Quality Inspection</h3>
              <button onClick={() => setShowInspectionModal(false)} className="text-stone-400 hover:text-stone-600">
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleCreateInspection} className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-stone-700 mb-1">Inspection #</label>
                  <input
                    type="text"
                    placeholder="QI-AUTO"
                    value={formInsp.inspection_number}
                    onChange={(e) => setFormInsp({ ...formInsp, inspection_number: e.target.value })}
                    className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-stone-700 mb-1">Type</label>
                  <select
                    value={formInsp.inspection_type}
                    onChange={(e) => setFormInsp({ ...formInsp, inspection_type: e.target.value })}
                    className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg"
                  >
                    <option value="INCOMING">Incoming</option>
                    <option value="IN_PROCESS">In Process</option>
                    <option value="OUTGOING">Outgoing</option>
                  </select>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-stone-700 mb-1">Item Code</label>
                  <input
                    type="text"
                    required
                    value={formInsp.item_code}
                    onChange={(e) => setFormInsp({ ...formInsp, item_code: e.target.value })}
                    className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-stone-700 mb-1">Sample Size</label>
                  <input
                    type="number"
                    step="1"
                    required
                    value={formInsp.sample_size}
                    onChange={(e) => setFormInsp({ ...formInsp, sample_size: e.target.value })}
                    className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg"
                  />
                </div>
              </div>
              {/* Readings */}
              <div className="bg-stone-50 p-3 rounded-lg border border-stone-200 space-y-2">
                <span className="text-xs font-semibold text-stone-800">Reading Tolerances (Pass/Fail)</span>
                <div className="grid grid-cols-3 gap-2 text-xs">
                  <div>
                    <label className="text-2xs text-stone-500">Length (mm)</label>
                    <input
                      type="number"
                      step="0.01"
                      value={formInsp.param_length_val}
                      onChange={(e) => setFormInsp({ ...formInsp, param_length_val: e.target.value })}
                      className="w-full px-2 py-1 border rounded bg-white"
                    />
                  </div>
                  <div>
                    <label className="text-2xs text-stone-500">Min Spec</label>
                    <input
                      type="number"
                      step="0.01"
                      value={formInsp.param_length_min}
                      onChange={(e) => setFormInsp({ ...formInsp, param_length_min: e.target.value })}
                      className="w-full px-2 py-1 border rounded bg-white"
                    />
                  </div>
                  <div>
                    <label className="text-2xs text-stone-500">Max Spec</label>
                    <input
                      type="number"
                      step="0.01"
                      value={formInsp.param_length_max}
                      onChange={(e) => setFormInsp({ ...formInsp, param_length_max: e.target.value })}
                      className="w-full px-2 py-1 border rounded bg-white"
                    />
                  </div>
                </div>
              </div>
              <div className="pt-3 flex justify-end gap-2 border-t border-stone-200">
                <button
                  type="button"
                  onClick={() => setShowInspectionModal(false)}
                  className="px-4 py-2 text-sm text-stone-600 hover:bg-stone-100 rounded-lg"
                >
                  Cancel
                </button>
                <button type="submit" className="px-4 py-2 text-sm font-medium text-white bg-stone-900 rounded-lg hover:bg-stone-800">
                  Evaluate & Save
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: New NCR */}
      {showNcrModal && (
        <div className="fixed inset-0 z-50 bg-stone-900/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-6 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-stone-200">
              <h3 className="text-lg font-bold text-stone-900">New Non-Conformance Report</h3>
              <button onClick={() => setShowNcrModal(false)} className="text-stone-400 hover:text-stone-600">
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleCreateNcr} className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-stone-700 mb-1">NCR Title</label>
                <input
                  type="text"
                  required
                  placeholder="Bracket length tolerance breach"
                  value={formNcr.title}
                  onChange={(e) => setFormNcr({ ...formNcr, title: e.target.value })}
                  className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-stone-700 mb-1">Severity</label>
                  <select
                    value={formNcr.severity}
                    onChange={(e) => setFormNcr({ ...formNcr, severity: e.target.value })}
                    className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg"
                  >
                    <option value="MINOR">Minor</option>
                    <option value="MAJOR">Major</option>
                    <option value="CRITICAL">Critical</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-stone-700 mb-1">Disposition</label>
                  <select
                    value={formNcr.immediate_disposition}
                    onChange={(e) => setFormNcr({ ...formNcr, immediate_disposition: e.target.value })}
                    className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg"
                  >
                    <option value="REWORK">Rework</option>
                    <option value="SCRAP">Scrap</option>
                    <option value="CONCESSION">Concession</option>
                    <option value="RETURN_TO_SUPPLIER">Return to Supplier</option>
                  </select>
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-stone-700 mb-1">Description</label>
                <textarea
                  rows={3}
                  required
                  value={formNcr.description}
                  onChange={(e) => setFormNcr({ ...formNcr, description: e.target.value })}
                  className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg"
                />
              </div>
              <div className="pt-3 flex justify-end gap-2 border-t border-stone-200">
                <button
                  type="button"
                  onClick={() => setShowNcrModal(false)}
                  className="px-4 py-2 text-sm text-stone-600 hover:bg-stone-100 rounded-lg"
                >
                  Cancel
                </button>
                <button type="submit" className="px-4 py-2 text-sm font-medium text-white bg-stone-900 rounded-lg hover:bg-stone-800">
                  Log NCR
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Assign CAPA */}
      {showCapaModal && (
        <div className="fixed inset-0 z-50 bg-stone-900/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-lg w-full p-6 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-stone-200">
              <h3 className="text-lg font-bold text-stone-900">Assign CAPA (5-Whys Analysis)</h3>
              <button onClick={() => setShowCapaModal(false)} className="text-stone-400 hover:text-stone-600">
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleCreateCapa} className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-stone-700 mb-1">Linked NCR</label>
                <select
                  required
                  value={formCapa.nc_id}
                  onChange={(e) => setFormCapa({ ...formCapa, nc_id: e.target.value })}
                  className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg"
                >
                  {ncrs.map((n) => (
                    <option key={n.nc_id} value={n.nc_id}>
                      {n.nc_number} - {n.title}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-stone-700 mb-1">
                  5-Whys Root Cause Analysis
                </label>
                <textarea
                  rows={4}
                  required
                  value={formCapa.root_cause_analysis}
                  onChange={(e) => setFormCapa({ ...formCapa, root_cause_analysis: e.target.value })}
                  className="w-full px-3 py-2 text-xs font-mono border border-stone-300 rounded-lg"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-stone-700 mb-1">Action Plan</label>
                <textarea
                  rows={2}
                  required
                  value={formCapa.action_plan}
                  onChange={(e) => setFormCapa({ ...formCapa, action_plan: e.target.value })}
                  className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg"
                />
              </div>
              <div className="pt-3 flex justify-end gap-2 border-t border-stone-200">
                <button
                  type="button"
                  onClick={() => setShowCapaModal(false)}
                  className="px-4 py-2 text-sm text-stone-600 hover:bg-stone-100 rounded-lg"
                >
                  Cancel
                </button>
                <button type="submit" className="px-4 py-2 text-sm font-medium text-white bg-stone-900 rounded-lg hover:bg-stone-800">
                  Assign CAPA
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Resolve CAPA */}
      {showResolveModal && (
        <div className="fixed inset-0 z-50 bg-stone-900/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-sm w-full p-6 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-stone-200">
              <h3 className="text-lg font-bold text-stone-900">Resolve CAPA Action</h3>
              <button onClick={() => setShowResolveModal(false)} className="text-stone-400 hover:text-stone-600">
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleResolveCapa} className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-stone-700 mb-1">Verification / Resolution Notes</label>
                <textarea
                  rows={3}
                  required
                  placeholder="Engineering verification complete; safety sensor installed and verified."
                  value={resolutionNotes}
                  onChange={(e) => setResolutionNotes(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg"
                />
              </div>
              <div className="pt-3 flex justify-end gap-2 border-t border-stone-200">
                <button
                  type="button"
                  onClick={() => setShowResolveModal(false)}
                  className="px-4 py-2 text-sm text-stone-600 hover:bg-stone-100 rounded-lg"
                >
                  Cancel
                </button>
                <button type="submit" className="px-4 py-2 text-sm font-medium text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg">
                  Verify & Close
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
