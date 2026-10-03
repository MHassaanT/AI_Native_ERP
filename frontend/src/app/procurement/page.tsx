"use client";

import { useEffect, useState } from "react";
import {
  AlertCircle,
  ArrowRight,
  Award,
  BarChart3,
  Boxes,
  Building2,
  Calendar,
  CheckCircle2,
  ChevronRight,
  ClipboardList,
  Clock,
  DollarSign,
  FileCheck,
  FileSpreadsheet,
  FileText,
  Filter,
  Layers,
  Percent,
  Play,
  Plus,
  RefreshCw,
  Scale,
  Send,
  ShieldAlert,
  ShieldCheck,
  ShoppingBag,
  Sparkles,
  Tag,
  Trash2,
  TrendingDown,
  TrendingUp,
  Truck,
  Users,
  Wrench,
  X,
} from "lucide-react";
import { api } from "@/lib/api";

const formatMoney = (val: any) => {
  const num = Number(val);
  return isNaN(num) ? "0.00" : num.toFixed(2);
};

export default function ProcurementPage() {
  const [activeTab, setActiveTab] = useState<
    | "requisitions"
    | "sourcing"
    | "blanket-orders"
    | "landed-costs"
    | "scorecards"
    | "subcontracting"
  >("requisitions");

  // Shared master data
  const [items, setItems] = useState<any[]>([]);
  const [suppliers, setSuppliers] = useState<any[]>([]);
  const [warehouses, setWarehouses] = useState<any[]>([]);
  const [goodsReceipts, setGoodsReceipts] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [notification, setNotification] = useState<{ type: "success" | "error"; message: string } | null>(null);

  // Tab 1: Requisitions
  const [materialRequests, setMaterialRequests] = useState<any[]>([]);
  const [mrFilterStatus, setMrFilterStatus] = useState<string>("");
  const [showCreateMRModal, setShowCreateMRModal] = useState(false);
  const [showConvertMRModal, setShowConvertMRModal] = useState<any | null>(null);
  const [mrFormData, setMrFormData] = useState<any>({
    mr_number: "",
    material_request_type: "PURCHASE",
    schedule_date: "",
    notes: "",
    items: [{ item_id: "", quantity: 1, target_warehouse_id: "", uom: "Nos" }],
  });
  const [convertPOData, setConvertPOData] = useState<any>({
    po_number: "",
    supplier_id: "",
  });

  // Tab 2: Sourcing & RFQs
  const [rfqs, setRfqs] = useState<any[]>([]);
  const [supplierQuotations, setSupplierQuotations] = useState<any[]>([]);
  const [showCreateRFQModal, setShowCreateRFQModal] = useState(false);
  const [showCreateQuoteModal, setShowCreateQuoteModal] = useState(false);
  const [comparisonMatrix, setComparisonMatrix] = useState<any | null>(null);
  const [showAwardModal, setShowAwardModal] = useState<{ sq_id: string; quote_number: string; supplier_name: string } | null>(null);
  const [awardPoNumber, setAwardPoNumber] = useState("");
  const [rfqFormData, setRfqFormData] = useState<any>({
    rfq_number: "",
    notes: "",
    supplier_ids: [],
    items: [{ item_id: "", quantity: 10, required_date: "" }],
  });
  const [quoteFormData, setQuoteFormData] = useState<any>({
    quotation_number: "",
    supplier_id: "",
    rfq_id: "",
    currency: "USD",
    lead_time_days: 7,
    payment_terms: "Net 30",
    items: [{ item_id: "", quantity: 10, unit_price: 0, discount_pct: 0, lead_time_days: 7 }],
  });

  // Tab 3: Blanket Orders
  const [blanketOrders, setBlanketOrders] = useState<any[]>([]);
  const [showCreateBOModal, setShowCreateBOModal] = useState(false);
  const [showDrawdownModal, setShowDrawdownModal] = useState<any | null>(null);
  const [boFormData, setBoFormData] = useState<any>({
    order_number: "",
    supplier_id: "",
    from_date: "",
    to_date: "",
    items: [{ item_id: "", quantity: 100, unit_price: 0 }],
  });
  const [drawdownData, setDrawdownData] = useState<any>({
    po_number: "",
    items: [],
  });

  // Tab 4: Landed Cost Vouchers
  const [lcvs, setLcvs] = useState<any[]>([]);
  const [showCreateLCVModal, setShowCreateLCVModal] = useState(false);
  const [selectedLCVDetail, setSelectedLCVDetail] = useState<any | null>(null);
  const [lcvFormData, setLcvFormData] = useState<any>({
    voucher_number: "",
    distribute_charges_based_on: "VALUATION",
    posting_date: "",
    company: "Corporate",
    notes: "",
    grn_ids: [],
    taxes_and_charges: [
      { expense_account: "5100-FREIGHT-CUSTOMS-CLEARING", description: "Ocean Freight", amount: 500 },
      { expense_account: "5100-FREIGHT-CUSTOMS-CLEARING", description: "Import Duty & Tariff", amount: 250 },
    ],
  });

  // Tab 5: Scorecards & Leaderboard
  const [leaderboard, setLeaderboard] = useState<any[]>([]);
  const [scorecards, setScorecards] = useState<any[]>([]);
  const [showCalcScorecardModal, setShowCalcScorecardModal] = useState(false);
  const [scorecardDetail, setScorecardDetail] = useState<any | null>(null);
  const [scorecardFormData, setScorecardFormData] = useState<any>({
    supplier_id: "",
    period_start: "",
    period_end: "",
    evaluation_period: "MONTHLY",
  });

  // Tab 6: Subcontracting
  const [subconOrders, setSubconOrders] = useState<any[]>([]);
  const [subconReceipts, setSubconReceipts] = useState<any[]>([]);
  const [showCreateSCOModal, setShowCreateSCOModal] = useState(false);
  const [showTransferModal, setShowTransferModal] = useState<any | null>(null);
  const [showReceiveModal, setShowReceiveModal] = useState<any | null>(null);
  const [scoFormData, setScoFormData] = useState<any>({
    sco_number: "",
    supplier_id: "",
    service_cost: 0,
    notes: "",
    finished_items: [{ item_id: "", quantity: 10, unit_price: 0 }],
    supplied_items: [{ raw_item_id: "", required_qty: 20, source_warehouse_id: "", supplier_warehouse_id: "" }],
  });
  const [transferData, setTransferData] = useState<any>({
    transfers: [],
  });
  const [receiveData, setReceiveData] = useState<any>({
    scr_number: "",
    target_warehouse_id: "",
    finished_items: [],
  });

  // Notifications helper
  const showToast = (message: string, type: "success" | "error" = "success") => {
    setNotification({ message, type });
    setTimeout(() => setNotification(null), 5000);
  };

  // Initial Data Load
  useEffect(() => {
    loadMasterData();
  }, []);

  useEffect(() => {
    if (activeTab === "requisitions") loadRequisitions();
    if (activeTab === "sourcing") loadSourcing();
    if (activeTab === "blanket-orders") loadBlanketOrders();
    if (activeTab === "landed-costs") loadLandedCosts();
    if (activeTab === "scorecards") loadScorecards();
    if (activeTab === "subcontracting") loadSubcontracting();
  }, [activeTab, mrFilterStatus]);

  const loadMasterData = async () => {
    try {
      const [itms, supps, whs, grns] = await Promise.all([
        api.getItems().catch(() => []),
        api.getSuppliers().catch(() => []),
        api.getWarehouses().catch(() => []),
        api.getGoodsReceipts().catch(() => []),
      ]);
      setItems(itms || []);
      setSuppliers(supps || []);
      setWarehouses(whs || []);
      setGoodsReceipts(grns || []);
    } catch (err: any) {
      console.error("Failed to load master data", err);
    }
  };

  const loadRequisitions = async () => {
    setLoading(true);
    try {
      const res = await api.getMaterialRequests({ status: mrFilterStatus || undefined });
      setMaterialRequests(res || []);
    } catch (err: any) {
      showToast(err.message, "error");
    } finally {
      setLoading(false);
    }
  };

  const loadSourcing = async () => {
    setLoading(true);
    try {
      const [rfqList, quotes] = await Promise.all([
        api.getRFQs().catch(() => []),
        api.getSupplierQuotations().catch(() => []),
      ]);
      setRfqs(rfqList || []);
      setSupplierQuotations(quotes || []);
    } catch (err: any) {
      showToast(err.message, "error");
    } finally {
      setLoading(false);
    }
  };

  const loadBlanketOrders = async () => {
    setLoading(true);
    try {
      const res = await api.getBlanketOrders();
      setBlanketOrders(res || []);
    } catch (err: any) {
      showToast(err.message, "error");
    } finally {
      setLoading(false);
    }
  };

  const loadLandedCosts = async () => {
    setLoading(true);
    try {
      const res = await api.getLandedCostVouchers();
      setLcvs(res || []);
    } catch (err: any) {
      showToast(err.message, "error");
    } finally {
      setLoading(false);
    }
  };

  const loadScorecards = async () => {
    setLoading(true);
    try {
      const [board, cards] = await Promise.all([
        api.getSupplierLeaderboard().catch(() => []),
        api.getSupplierScorecards().catch(() => []),
      ]);
      setLeaderboard(board || []);
      setScorecards(cards || []);
    } catch (err: any) {
      showToast(err.message, "error");
    } finally {
      setLoading(false);
    }
  };

  const loadSubcontracting = async () => {
    setLoading(true);
    try {
      const [orders, receipts] = await Promise.all([
        api.getSubcontractingOrders().catch(() => []),
        api.getSubcontractingReceipts().catch(() => []),
      ]);
      setSubconOrders(orders || []);
      setSubconReceipts(receipts || []);
    } catch (err: any) {
      showToast(err.message, "error");
    } finally {
      setLoading(false);
    }
  };

  // -----------------------------------------------------------------------
  // Actions: Requisitions
  // -----------------------------------------------------------------------
  const handleCreateMR = async (e: React.FormEvent) => {
    e.preventDefault();
    setActionLoading(true);
    try {
      await api.createMaterialRequest({
        mr_number: mrFormData.mr_number || `MR-${Date.now().toString().slice(-6)}`,
        material_request_type: mrFormData.material_request_type,
        schedule_date: mrFormData.schedule_date || undefined,
        notes: mrFormData.notes || undefined,
        items: mrFormData.items.map((it: any) => ({
          item_id: it.item_id,
          quantity: Number(it.quantity),
          target_warehouse_id: it.target_warehouse_id || undefined,
          uom: it.uom || "Nos",
        })),
      });
      showToast("Material Request created in DRAFT successfully.");
      setShowCreateMRModal(false);
      loadRequisitions();
    } catch (err: any) {
      showToast(err.message, "error");
    } finally {
      setActionLoading(false);
    }
  };

  const handleSubmitMR = async (mrId: string) => {
    setActionLoading(true);
    try {
      await api.submitMaterialRequest(mrId);
      showToast("Material Request submitted for purchasing.");
      loadRequisitions();
    } catch (err: any) {
      showToast(err.message, "error");
    } finally {
      setActionLoading(false);
    }
  };

  const handleConvertMRToPO = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!showConvertMRModal) return;
    setActionLoading(true);
    try {
      const po = await api.convertMRToPO(showConvertMRModal.mr_id, {
        po_number: convertPOData.po_number || `PO-${Date.now().toString().slice(-6)}`,
        supplier_id: convertPOData.supplier_id,
      });
      showToast(`Generated Purchase Order ${po.po_number} successfully!`);
      setShowConvertMRModal(null);
      loadRequisitions();
    } catch (err: any) {
      showToast(err.message, "error");
    } finally {
      setActionLoading(false);
    }
  };

  const handleRunReplenishment = async () => {
    setActionLoading(true);
    try {
      const res = await api.checkReplenishment();
      showToast(res.message || "Replenishment scan completed.");
      loadRequisitions();
    } catch (err: any) {
      showToast(err.message, "error");
    } finally {
      setActionLoading(false);
    }
  };

  // -----------------------------------------------------------------------
  // Actions: Sourcing & RFQs
  // -----------------------------------------------------------------------
  const handleCreateRFQ = async (e: React.FormEvent) => {
    e.preventDefault();
    setActionLoading(true);
    try {
      await api.createRFQ({
        rfq_number: rfqFormData.rfq_number || `RFQ-${Date.now().toString().slice(-6)}`,
        notes: rfqFormData.notes || undefined,
        supplier_ids: rfqFormData.supplier_ids,
        items: rfqFormData.items.map((it: any) => ({
          item_id: it.item_id,
          quantity: Number(it.quantity),
          required_date: it.required_date || undefined,
        })),
      });
      showToast("RFQ created in DRAFT.");
      setShowCreateRFQModal(false);
      loadSourcing();
    } catch (err: any) {
      showToast(err.message, "error");
    } finally {
      setActionLoading(false);
    }
  };

  const handleSendRFQ = async (rfqId: string) => {
    setActionLoading(true);
    try {
      await api.sendRFQ(rfqId);
      showToast("RFQ dispatched to invited suppliers!");
      loadSourcing();
    } catch (err: any) {
      showToast(err.message, "error");
    } finally {
      setActionLoading(false);
    }
  };

  const handleViewComparisonMatrix = async (rfqId: string) => {
    setActionLoading(true);
    try {
      const mat = await api.getQuoteComparisonMatrix(rfqId);
      setComparisonMatrix(mat);
    } catch (err: any) {
      showToast(err.message, "error");
    } finally {
      setActionLoading(false);
    }
  };

  const handleAwardQuote = async () => {
    if (!showAwardModal) return;
    setActionLoading(true);
    try {
      const poNum = awardPoNumber || `PO-AWARD-${Date.now().toString().slice(-6)}`;
      const po = await api.awardSupplierQuotation(showAwardModal.sq_id, poNum);
      showToast(`Quote Awarded! Created Purchase Order ${po.po_number}.`);
      setShowAwardModal(null);
      setComparisonMatrix(null);
      loadSourcing();
    } catch (err: any) {
      showToast(err.message, "error");
    } finally {
      setActionLoading(false);
    }
  };

  const handleCreateSupplierQuote = async (e: React.FormEvent) => {
    e.preventDefault();
    setActionLoading(true);
    try {
      await api.createSupplierQuotation({
        quotation_number: quoteFormData.quotation_number || `SQ-${Date.now().toString().slice(-6)}`,
        supplier_id: quoteFormData.supplier_id,
        rfq_id: quoteFormData.rfq_id || undefined,
        currency: quoteFormData.currency,
        lead_time_days: Number(quoteFormData.lead_time_days),
        payment_terms: quoteFormData.payment_terms || undefined,
        items: quoteFormData.items.map((it: any) => ({
          item_id: it.item_id,
          quantity: Number(it.quantity),
          unit_price: Number(it.unit_price),
          discount_pct: Number(it.discount_pct || 0),
          lead_time_days: Number(it.lead_time_days || quoteFormData.lead_time_days),
        })),
      });
      showToast("Supplier Quotation bid submitted!");
      setShowCreateQuoteModal(false);
      loadSourcing();
    } catch (err: any) {
      showToast(err.message, "error");
    } finally {
      setActionLoading(false);
    }
  };

  // -----------------------------------------------------------------------
  // Actions: Blanket Orders
  // -----------------------------------------------------------------------
  const handleCreateBO = async (e: React.FormEvent) => {
    e.preventDefault();
    setActionLoading(true);
    try {
      await api.createBlanketOrder({
        order_number: boFormData.order_number || `BO-${Date.now().toString().slice(-6)}`,
        supplier_id: boFormData.supplier_id,
        from_date: boFormData.from_date,
        to_date: boFormData.to_date,
        items: boFormData.items.map((it: any) => ({
          item_id: it.item_id,
          quantity: Number(it.quantity),
          unit_price: Number(it.unit_price),
        })),
      });
      showToast("Blanket Order Contract activated!");
      setShowCreateBOModal(false);
      loadBlanketOrders();
    } catch (err: any) {
      showToast(err.message, "error");
    } finally {
      setActionLoading(false);
    }
  };

  const handleDrawdownBO = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!showDrawdownModal) return;
    setActionLoading(true);
    try {
      const poNum = drawdownData.po_number || `PO-REL-${Date.now().toString().slice(-6)}`;
      const po = await api.drawdownBlanketOrder(showDrawdownModal.blanket_order_id, {
        po_number: poNum,
        items: drawdownData.items.map((it: any) => ({
          item_id: it.item_id,
          quantity: Number(it.drawdown_qty),
        })),
      });
      showToast(`Drawdown successful! Purchase Order ${po.po_number} generated at locked rates.`);
      setShowDrawdownModal(null);
      loadBlanketOrders();
    } catch (err: any) {
      showToast(err.message, "error");
    } finally {
      setActionLoading(false);
    }
  };

  // -----------------------------------------------------------------------
  // Actions: Landed Cost Vouchers
  // -----------------------------------------------------------------------
  const handleCreateLCV = async (e: React.FormEvent) => {
    e.preventDefault();
    setActionLoading(true);
    try {
      await api.createLandedCostVoucher({
        voucher_number: lcvFormData.voucher_number || `LCV-${Date.now().toString().slice(-6)}`,
        distribute_charges_based_on: lcvFormData.distribute_charges_based_on,
        company: lcvFormData.company || "Corporate",
        notes: lcvFormData.notes || undefined,
        grn_ids: lcvFormData.grn_ids,
        taxes_and_charges: lcvFormData.taxes_and_charges.map((tc: any) => ({
          expense_account: tc.expense_account,
          description: tc.description,
          amount: Number(tc.amount),
        })),
      });
      showToast("Landed Cost Voucher created and charges apportioned!");
      setShowCreateLCVModal(false);
      loadLandedCosts();
    } catch (err: any) {
      showToast(err.message, "error");
    } finally {
      setActionLoading(false);
    }
  };

  const handleSubmitLCV = async (lcvId: string) => {
    setActionLoading(true);
    try {
      await api.submitLandedCostVoucher(lcvId);
      showToast("Landed Cost capitalized to inventory & posted to General Ledger!");
      loadLandedCosts();
    } catch (err: any) {
      showToast(err.message, "error");
    } finally {
      setActionLoading(false);
    }
  };

  // -----------------------------------------------------------------------
  // Actions: Scorecards
  // -----------------------------------------------------------------------
  const handleCalculateScorecard = async (e: React.FormEvent) => {
    e.preventDefault();
    setActionLoading(true);
    try {
      const sc = await api.calculateSupplierScorecard({
        supplier_id: scorecardFormData.supplier_id,
        period_start: scorecardFormData.period_start,
        period_end: scorecardFormData.period_end,
        evaluation_period: scorecardFormData.evaluation_period,
      });
      showToast(`Scorecard generated: Standing is ${sc.standing} (Score: ${sc.total_score}%)`);
      setShowCalcScorecardModal(false);
      loadScorecards();
    } catch (err: any) {
      showToast(err.message, "error");
    } finally {
      setActionLoading(false);
    }
  };

  // -----------------------------------------------------------------------
  // Actions: Subcontracting
  // -----------------------------------------------------------------------
  const handleCreateSCO = async (e: React.FormEvent) => {
    e.preventDefault();
    setActionLoading(true);
    try {
      await api.createSubcontractingOrder({
        sco_number: scoFormData.sco_number || `SCO-${Date.now().toString().slice(-6)}`,
        supplier_id: scoFormData.supplier_id,
        service_cost: Number(scoFormData.service_cost || 0),
        notes: scoFormData.notes || undefined,
        finished_items: scoFormData.finished_items.map((it: any) => ({
          item_id: it.item_id,
          quantity: Number(it.quantity),
          unit_price: Number(it.unit_price || 0),
        })),
        supplied_items: scoFormData.supplied_items.map((s: any) => ({
          raw_item_id: s.raw_item_id,
          required_qty: Number(s.required_qty),
          source_warehouse_id: s.source_warehouse_id || undefined,
          supplier_warehouse_id: s.supplier_warehouse_id || undefined,
        })),
      });
      showToast("Subcontracting Order created!");
      setShowCreateSCOModal(false);
      loadSubcontracting();
    } catch (err: any) {
      showToast(err.message, "error");
    } finally {
      setActionLoading(false);
    }
  };

  const handleSubmitSCO = async (scoId: string) => {
    setActionLoading(true);
    try {
      await api.submitSubcontractingOrder(scoId);
      showToast("Subcontracting Order submitted!");
      loadSubcontracting();
    } catch (err: any) {
      showToast(err.message, "error");
    } finally {
      setActionLoading(false);
    }
  };

  const handleTransferMaterials = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!showTransferModal) return;
    setActionLoading(true);
    try {
      await api.transferSubcontractingMaterials(showTransferModal.sco_id, transferData.transfers);
      showToast("Raw components issued to subcontractor warehouse!");
      setShowTransferModal(null);
      loadSubcontracting();
    } catch (err: any) {
      showToast(err.message, "error");
    } finally {
      setActionLoading(false);
    }
  };

  const handleReceiveSubcontractedGoods = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!showReceiveModal) return;
    setActionLoading(true);
    try {
      await api.createSubcontractingReceipt({
        scr_number: receiveData.scr_number || `SCR-${Date.now().toString().slice(-6)}`,
        sco_id: showReceiveModal.sco_id,
        target_warehouse_id: receiveData.target_warehouse_id,
        finished_items: receiveData.finished_items.map((it: any) => ({
          item_id: it.item_id,
          quantity_received: Number(it.quantity_received),
          service_rate: Number(it.service_rate || 0),
        })),
      });
      showToast("Finished goods stocked & components auto-consumed from vendor warehouse!");
      setShowReceiveModal(null);
      loadSubcontracting();
    } catch (err: any) {
      showToast(err.message, "error");
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div className="space-y-6 pb-16">
      {/* Toast Notification */}
      {notification && (
        <div
          className={`fixed top-4 right-4 z-50 flex items-center gap-3 px-4 py-3 rounded-lg shadow-lg border text-sm font-medium ${
            notification.type === "success"
              ? "bg-emerald-50 border-emerald-200 text-emerald-800"
              : "bg-rose-50 border-rose-200 text-rose-800"
          }`}
        >
          {notification.type === "success" ? (
            <CheckCircle2 className="w-5 h-5 text-emerald-600" />
          ) : (
            <AlertCircle className="w-5 h-5 text-rose-600" />
          )}
          <span>{notification.message}</span>
          <button onClick={() => setNotification(null)} className="ml-2 hover:opacity-75">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-cream-950 font-serif">
              Procurement & Strategic Buying
            </h1>
            <span className="text-xs bg-amber-100 text-amber-800 font-semibold px-2 py-0.5 rounded-full border border-amber-300">
              ERPNext Parity
            </span>
          </div>
          <p className="text-sm text-cream-700 mt-1">
            Requisitions, RFQ tender comparisons, long-term blanket contracts, landed cost capitalization, vendor scorecards, and outside subcontracting.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {activeTab === "requisitions" && (
            <>
              <button
                onClick={handleRunReplenishment}
                disabled={actionLoading}
                className="flex items-center gap-2 px-3 py-2 text-xs font-medium rounded-lg bg-amber-50 text-amber-900 border border-amber-200 hover:bg-amber-100 transition-colors shadow-sm"
              >
                <Sparkles className="w-4 h-4 text-amber-600" />
                <span>Auto-Replenish Scan</span>
              </button>
              <button
                onClick={() => {
                  setMrFormData({
                    mr_number: `MR-${Date.now().toString().slice(-6)}`,
                    material_request_type: "PURCHASE",
                    schedule_date: new Date(Date.now() + 7 * 86400000).toISOString().split("T")[0],
                    notes: "",
                    items: [{ item_id: items[0]?.item_id || "", quantity: 10, target_warehouse_id: warehouses[0]?.warehouse_id || "", uom: "Nos" }],
                  });
                  setShowCreateMRModal(true);
                }}
                className="flex items-center gap-2 px-3 py-2 text-xs font-medium rounded-lg bg-cream-900 text-cream-50 hover:bg-cream-800 transition-colors shadow-sm"
              >
                <Plus className="w-4 h-4" />
                <span>New Requisition</span>
              </button>
            </>
          )}

          {activeTab === "sourcing" && (
            <>
              <button
                onClick={() => {
                  setQuoteFormData({
                    quotation_number: `SQ-${Date.now().toString().slice(-6)}`,
                    supplier_id: suppliers[0]?.supplier_id || "",
                    rfq_id: rfqs[0]?.rfq_id || "",
                    currency: "USD",
                    lead_time_days: 7,
                    payment_terms: "Net 30",
                    items: [{ item_id: items[0]?.item_id || "", quantity: 10, unit_price: 25, discount_pct: 0, lead_time_days: 7 }],
                  });
                  setShowCreateQuoteModal(true);
                }}
                className="flex items-center gap-2 px-3 py-2 text-xs font-medium rounded-lg bg-cream-100 text-cream-900 border border-cream-300 hover:bg-cream-200 transition-colors"
              >
                <Tag className="w-4 h-4 text-cream-700" />
                <span>Submit Vendor Quote</span>
              </button>
              <button
                onClick={() => {
                  setRfqFormData({
                    rfq_number: `RFQ-${Date.now().toString().slice(-6)}`,
                    notes: "",
                    supplier_ids: suppliers.slice(0, 2).map((s) => s.supplier_id),
                    items: [{ item_id: items[0]?.item_id || "", quantity: 50, required_date: "" }],
                  });
                  setShowCreateRFQModal(true);
                }}
                className="flex items-center gap-2 px-3 py-2 text-xs font-medium rounded-lg bg-cream-900 text-cream-50 hover:bg-cream-800 transition-colors shadow-sm"
              >
                <Plus className="w-4 h-4" />
                <span>New RFQ Tender</span>
              </button>
            </>
          )}

          {activeTab === "blanket-orders" && (
            <button
              onClick={() => {
                setBoFormData({
                  order_number: `BO-${Date.now().toString().slice(-6)}`,
                  supplier_id: suppliers[0]?.supplier_id || "",
                  from_date: new Date().toISOString().split("T")[0],
                  to_date: new Date(Date.now() + 365 * 86400000).toISOString().split("T")[0],
                  items: [{ item_id: items[0]?.item_id || "", quantity: 500, unit_price: 20 }],
                });
                setShowCreateBOModal(true);
              }}
              className="flex items-center gap-2 px-3 py-2 text-xs font-medium rounded-lg bg-cream-900 text-cream-50 hover:bg-cream-800 transition-colors shadow-sm"
            >
              <Plus className="w-4 h-4" />
              <span>New Blanket Contract</span>
            </button>
          )}

          {activeTab === "landed-costs" && (
            <button
              onClick={() => {
                setLcvFormData({
                  voucher_number: `LCV-${Date.now().toString().slice(-6)}`,
                  distribute_charges_based_on: "VALUATION",
                  posting_date: new Date().toISOString().split("T")[0],
                  company: "Corporate",
                  notes: "",
                  grn_ids: goodsReceipts.slice(0, 1).map((g) => g.grn_id),
                  taxes_and_charges: [
                    { expense_account: "5100-FREIGHT-CUSTOMS-CLEARING", description: "Ocean Freight & Bunker Surcharge", amount: 450 },
                    { expense_account: "5100-FREIGHT-CUSTOMS-CLEARING", description: "Customs Import Duty", amount: 180 },
                  ],
                });
                setShowCreateLCVModal(true);
              }}
              className="flex items-center gap-2 px-3 py-2 text-xs font-medium rounded-lg bg-cream-900 text-cream-50 hover:bg-cream-800 transition-colors shadow-sm"
            >
              <Scale className="w-4 h-4" />
              <span>New Landed Cost Voucher</span>
            </button>
          )}

          {activeTab === "scorecards" && (
            <button
              onClick={() => {
                const now = new Date();
                const past = new Date(now.getTime() - 30 * 86400000);
                setScorecardFormData({
                  supplier_id: suppliers[0]?.supplier_id || "",
                  period_start: past.toISOString().split("T")[0],
                  period_end: now.toISOString().split("T")[0],
                  evaluation_period: "MONTHLY",
                });
                setShowCalcScorecardModal(true);
              }}
              className="flex items-center gap-2 px-3 py-2 text-xs font-medium rounded-lg bg-cream-900 text-cream-50 hover:bg-cream-800 transition-colors shadow-sm"
            >
              <BarChart3 className="w-4 h-4" />
              <span>Evaluate Supplier</span>
            </button>
          )}

          {activeTab === "subcontracting" && (
            <button
              onClick={() => {
                setScoFormData({
                  sco_number: `SCO-${Date.now().toString().slice(-6)}`,
                  supplier_id: suppliers[0]?.supplier_id || "",
                  service_cost: 500,
                  notes: "",
                  finished_items: [{ item_id: items[1]?.item_id || items[0]?.item_id || "", quantity: 10, unit_price: 150 }],
                  supplied_items: [
                    {
                      raw_item_id: items[0]?.item_id || "",
                      required_qty: 30,
                      source_warehouse_id: warehouses[0]?.warehouse_id || "",
                      supplier_warehouse_id: warehouses[1]?.warehouse_id || warehouses[0]?.warehouse_id || "",
                    },
                  ],
                });
                setShowCreateSCOModal(true);
              }}
              className="flex items-center gap-2 px-3 py-2 text-xs font-medium rounded-lg bg-cream-900 text-cream-50 hover:bg-cream-800 transition-colors shadow-sm"
            >
              <Plus className="w-4 h-4" />
              <span>New Subcontracting Order</span>
            </button>
          )}
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="border-b border-cream-200">
        <nav className="flex space-x-2 overflow-x-auto pb-1" aria-label="Tabs">
          {[
            { id: "requisitions", label: "Requisitions (Material Requests)", icon: ClipboardList },
            { id: "sourcing", label: "Strategic Sourcing & RFQs", icon: FileSpreadsheet },
            { id: "blanket-orders", label: "Blanket Orders (Contracts)", icon: FileCheck },
            { id: "landed-costs", label: "Landed Cost Vouchers", icon: Scale },
            { id: "scorecards", label: "Supplier Scorecards & Ranking", icon: Award },
            { id: "subcontracting", label: "Subcontracting & Issuance", icon: Wrench },
          ].map((tab) => {
            const Icon = tab.icon;
            const isCurrent = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`flex items-center gap-2 whitespace-nowrap py-2.5 px-3 border-b-2 font-medium text-xs rounded-t-lg transition-colors ${
                  isCurrent
                    ? "border-cream-900 text-cream-950 bg-cream-100/60 font-semibold"
                    : "border-transparent text-cream-600 hover:text-cream-900 hover:border-cream-300"
                }`}
              >
                <Icon className={`w-4 h-4 ${isCurrent ? "text-cream-900" : "text-cream-500"}`} />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </nav>
      </div>

      {/* ------------------------------------------------------------------ */}
      {/* TAB 1: REQUISITIONS (MATERIAL REQUESTS) */}
      {/* ------------------------------------------------------------------ */}
      {activeTab === "requisitions" && (
        <div className="space-y-6">
          {/* Quick Metrics */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-white p-4 rounded-xl border border-cream-200 shadow-sm">
              <span className="text-xs text-cream-600 font-medium">Total Requisitions</span>
              <p className="text-xl font-bold text-cream-900 mt-1">{materialRequests.length}</p>
            </div>
            <div className="bg-white p-4 rounded-xl border border-cream-200 shadow-sm">
              <span className="text-xs text-cream-600 font-medium">Pending Approvals</span>
              <p className="text-xl font-bold text-amber-700 mt-1">
                {materialRequests.filter((r) => r.status === "DRAFT" || r.status === "SUBMITTED").length}
              </p>
            </div>
            <div className="bg-white p-4 rounded-xl border border-cream-200 shadow-sm">
              <span className="text-xs text-cream-600 font-medium">Partially Ordered</span>
              <p className="text-xl font-bold text-blue-700 mt-1">
                {materialRequests.filter((r) => r.status === "PARTIALLY_ORDERED").length}
              </p>
            </div>
            <div className="bg-white p-4 rounded-xl border border-cream-200 shadow-sm">
              <span className="text-xs text-cream-600 font-medium">Fully Converted to PO</span>
              <p className="text-xl font-bold text-emerald-700 mt-1">
                {materialRequests.filter((r) => r.status === "ORDERED").length}
              </p>
            </div>
          </div>

          {/* Filter Bar */}
          <div className="flex items-center justify-between gap-4 bg-white p-3 rounded-lg border border-cream-200">
            <div className="flex items-center gap-2">
              <Filter className="w-4 h-4 text-cream-600" />
              <span className="text-xs font-semibold text-cream-800">Filter Status:</span>
              <div className="flex gap-1">
                {["", "DRAFT", "SUBMITTED", "PARTIALLY_ORDERED", "ORDERED", "CANCELLED"].map((st) => (
                  <button
                    key={st}
                    onClick={() => setMrFilterStatus(st)}
                    className={`px-2.5 py-1 text-xs rounded-md font-medium transition-colors ${
                      mrFilterStatus === st
                        ? "bg-cream-900 text-cream-50"
                        : "bg-cream-100 text-cream-700 hover:bg-cream-200"
                    }`}
                  >
                    {st || "All"}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Requisitions Table */}
          <div className="bg-white rounded-xl border border-cream-200 shadow-sm overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-cream-50/75 border-b border-cream-200 text-cream-700 font-semibold uppercase tracking-wider">
                  <tr>
                    <th className="py-3 px-4">Requisition #</th>
                    <th className="py-3 px-4">Type</th>
                    <th className="py-3 px-4">Target Date</th>
                    <th className="py-3 px-4">Items / Ordered Progress</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-cream-100">
                  {materialRequests.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="py-8 text-center text-cream-500">
                        No material requests found. Create a new requisition or trigger an automated replenishment scan.
                      </td>
                    </tr>
                  ) : (
                    materialRequests.map((mr) => (
                      <tr key={mr.mr_id} className="hover:bg-cream-50/50 transition-colors">
                        <td className="py-3.5 px-4 font-mono font-medium text-cream-950">
                          {mr.mr_number}
                          {mr.notes && <p className="text-[10px] text-cream-500 mt-0.5">{mr.notes}</p>}
                        </td>
                        <td className="py-3.5 px-4">
                          <span className="px-2 py-0.5 text-[10px] font-medium rounded-full bg-cream-100 text-cream-800 border border-cream-200">
                            {mr.material_request_type}
                          </span>
                        </td>
                        <td className="py-3.5 px-4 text-cream-700">{mr.schedule_date}</td>
                        <td className="py-3.5 px-4">
                          <div className="space-y-1">
                            {mr.items?.map((it: any) => (
                              <div key={it.mr_item_id} className="flex items-center gap-2 text-[11px]">
                                <span className="font-semibold text-cream-900">{it.item?.item_code || "SKU"}:</span>
                                <span className="text-cream-600">
                                  {Number(it.ordered_qty).toFixed(1)} / {Number(it.quantity).toFixed(1)} {it.uom}
                                </span>
                                <div className="w-16 bg-cream-200 h-1.5 rounded-full overflow-hidden">
                                  <div
                                    className="bg-emerald-600 h-full rounded-full"
                                    style={{
                                      width: `${Math.min(100, (Number(it.ordered_qty) / Number(it.quantity)) * 100)}%`,
                                    }}
                                  />
                                </div>
                              </div>
                            ))}
                          </div>
                        </td>
                        <td className="py-3.5 px-4">
                          <span
                            className={`px-2 py-0.5 text-[10px] font-semibold rounded-full border ${
                              mr.status === "ORDERED"
                                ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                                : mr.status === "PARTIALLY_ORDERED"
                                ? "bg-blue-50 text-blue-800 border-blue-200"
                                : mr.status === "SUBMITTED"
                                ? "bg-amber-50 text-amber-800 border-amber-200"
                                : mr.status === "CANCELLED"
                                ? "bg-rose-50 text-rose-800 border-rose-200"
                                : "bg-cream-100 text-cream-800 border-cream-200"
                            }`}
                          >
                            {mr.status}
                          </span>
                        </td>
                        <td className="py-3.5 px-4 text-right">
                          <div className="flex items-center justify-end gap-1.5">
                            {mr.status === "DRAFT" && (
                              <button
                                onClick={() => handleSubmitMR(mr.mr_id)}
                                disabled={actionLoading}
                                className="px-2 py-1 text-[11px] font-medium rounded bg-emerald-600 text-white hover:bg-emerald-700 transition-colors"
                              >
                                Submit
                              </button>
                            )}

                            {(mr.status === "SUBMITTED" || mr.status === "PARTIALLY_ORDERED") && (
                              <button
                                onClick={() => {
                                  setShowConvertMRModal(mr);
                                  setConvertPOData({
                                    po_number: `PO-MR-${Date.now().toString().slice(-6)}`,
                                    supplier_id: suppliers[0]?.supplier_id || "",
                                  });
                                }}
                                className="flex items-center gap-1 px-2.5 py-1 text-[11px] font-medium rounded bg-cream-900 text-cream-50 hover:bg-cream-800 transition-colors"
                              >
                                <ShoppingBag className="w-3 h-3" />
                                <span>Create PO</span>
                              </button>
                            )}
                          </div>
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

      {/* ------------------------------------------------------------------ */}
      {/* TAB 2: STRATEGIC SOURCING & RFQS */}
      {/* ------------------------------------------------------------------ */}
      {activeTab === "sourcing" && (
        <div className="space-y-6">
          {/* Quick Metrics */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="bg-white p-4 rounded-xl border border-cream-200 shadow-sm">
              <span className="text-xs text-cream-600 font-medium">Active RFQs</span>
              <p className="text-xl font-bold text-cream-900 mt-1">{rfqs.length}</p>
            </div>
            <div className="bg-white p-4 rounded-xl border border-cream-200 shadow-sm">
              <span className="text-xs text-cream-600 font-medium">Bids / Quotations Received</span>
              <p className="text-xl font-bold text-blue-700 mt-1">{supplierQuotations.length}</p>
            </div>
            <div className="bg-white p-4 rounded-xl border border-cream-200 shadow-sm">
              <span className="text-xs text-cream-600 font-medium">Contracts Awarded</span>
              <p className="text-xl font-bold text-emerald-700 mt-1">
                {supplierQuotations.filter((q) => q.status === "AWARDED").length}
              </p>
            </div>
          </div>

          {/* RFQ Tender List */}
          <div className="bg-white rounded-xl border border-cream-200 shadow-sm overflow-hidden">
            <div className="p-4 border-b border-cream-200 flex items-center justify-between">
              <div>
                <h2 className="text-sm font-bold text-cream-950">Requests for Quotations (RFQs)</h2>
                <p className="text-xs text-cream-600 mt-0.5">Competitive bidding matrix across suppliers</p>
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-cream-50/75 border-b border-cream-200 text-cream-700 font-semibold uppercase tracking-wider">
                  <tr>
                    <th className="py-3 px-4">RFQ #</th>
                    <th className="py-3 px-4">Date</th>
                    <th className="py-3 px-4">Invited Vendors</th>
                    <th className="py-3 px-4">Items Required</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4 text-right">Matrix / Award</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-cream-100">
                  {rfqs.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="py-8 text-center text-cream-500">
                        No RFQs found. Click "New RFQ Tender" to invite suppliers for bidding.
                      </td>
                    </tr>
                  ) : (
                    rfqs.map((rfq) => (
                      <tr key={rfq.rfq_id} className="hover:bg-cream-50/50 transition-colors">
                        <td className="py-3.5 px-4 font-mono font-medium text-cream-950">
                          {rfq.rfq_number}
                          {rfq.notes && <p className="text-[10px] text-cream-500">{rfq.notes}</p>}
                        </td>
                        <td className="py-3.5 px-4 text-cream-700">{rfq.transaction_date}</td>
                        <td className="py-3.5 px-4">
                          <div className="flex flex-wrap gap-1">
                            {rfq.suppliers?.map((s: any) => (
                              <span
                                key={s.rfq_supplier_id}
                                className={`px-2 py-0.5 text-[10px] rounded-full border ${
                                  s.quote_status === "SUBMITTED"
                                    ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                                    : "bg-cream-100 text-cream-700 border-cream-200"
                                }`}
                              >
                                {s.supplier?.supplier_name || "Vendor"} ({s.quote_status})
                              </span>
                            ))}
                          </div>
                        </td>
                        <td className="py-3.5 px-4 text-cream-800">
                          {rfq.items?.map((it: any) => (
                            <span key={it.rfq_item_id} className="block text-[11px]">
                              {it.item?.item_code}: {Number(it.quantity)} units
                            </span>
                          ))}
                        </td>
                        <td className="py-3.5 px-4">
                          <span
                            className={`px-2 py-0.5 text-[10px] font-semibold rounded-full border ${
                              rfq.status === "COMPLETED"
                                ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                                : rfq.status === "QUOTES_RECEIVED"
                                ? "bg-blue-50 text-blue-800 border-blue-200"
                                : rfq.status === "SENT"
                                ? "bg-amber-50 text-amber-800 border-amber-200"
                                : "bg-cream-100 text-cream-800 border-cream-200"
                            }`}
                          >
                            {rfq.status}
                          </span>
                        </td>
                        <td className="py-3.5 px-4 text-right">
                          <div className="flex items-center justify-end gap-1.5">
                            {rfq.status === "DRAFT" && (
                              <button
                                onClick={() => handleSendRFQ(rfq.rfq_id)}
                                disabled={actionLoading}
                                className="flex items-center gap-1 px-2.5 py-1 text-[11px] font-medium rounded bg-emerald-600 text-white hover:bg-emerald-700 transition-colors"
                              >
                                <Send className="w-3 h-3" />
                                <span>Send RFQ</span>
                              </button>
                            )}

                            <button
                              onClick={() => handleViewComparisonMatrix(rfq.rfq_id)}
                              className="flex items-center gap-1 px-2.5 py-1 text-[11px] font-medium rounded bg-cream-900 text-cream-50 hover:bg-cream-800 transition-colors"
                            >
                              <Scale className="w-3 h-3" />
                              <span>Quote Matrix</span>
                            </button>
                          </div>
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

      {/* ------------------------------------------------------------------ */}
      {/* TAB 3: BLANKET ORDERS (CONTRACT PURCHASING) */}
      {/* ------------------------------------------------------------------ */}
      {activeTab === "blanket-orders" && (
        <div className="space-y-6">
          {/* Quick Metrics */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="bg-white p-4 rounded-xl border border-cream-200 shadow-sm">
              <span className="text-xs text-cream-600 font-medium">Active Blanket Contracts</span>
              <p className="text-xl font-bold text-cream-900 mt-1">
                {blanketOrders.filter((b) => b.status === "ACTIVE").length}
              </p>
            </div>
            <div className="bg-white p-4 rounded-xl border border-cream-200 shadow-sm">
              <span className="text-xs text-cream-600 font-medium">Total Contract Value Committed</span>
              <p className="text-xl font-bold text-emerald-700 mt-1">
                $
                {formatMoney(
                  blanketOrders.reduce((acc, b) => acc + Number(b.total_amount || 0), 0)
                )}
              </p>
            </div>
            <div className="bg-white p-4 rounded-xl border border-cream-200 shadow-sm">
              <span className="text-xs text-cream-600 font-medium">Closed Contracts</span>
              <p className="text-xl font-bold text-cream-700 mt-1">
                {blanketOrders.filter((b) => b.status === "CLOSED").length}
              </p>
            </div>
          </div>

          {/* Blanket Orders Table */}
          <div className="bg-white rounded-xl border border-cream-200 shadow-sm overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-cream-50/75 border-b border-cream-200 text-cream-700 font-semibold uppercase tracking-wider">
                  <tr>
                    <th className="py-3 px-4">Contract #</th>
                    <th className="py-3 px-4">Vendor</th>
                    <th className="py-3 px-4">Validity Window</th>
                    <th className="py-3 px-4">Committed Value</th>
                    <th className="py-3 px-4">Drawdown Progress</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-cream-100">
                  {blanketOrders.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="py-8 text-center text-cream-500">
                        No blanket orders found. Create a long-term contract to lock in volume pricing.
                      </td>
                    </tr>
                  ) : (
                    blanketOrders.map((bo) => {
                      const totalQty = bo.items?.reduce((acc: number, it: any) => acc + Number(it.quantity), 0) || 1;
                      const drawnQty = bo.items?.reduce((acc: number, it: any) => acc + Number(it.ordered_qty), 0) || 0;
                      const pct = Math.min(100, Math.round((drawnQty / totalQty) * 100));

                      return (
                        <tr key={bo.blanket_order_id} className="hover:bg-cream-50/50 transition-colors">
                          <td className="py-3.5 px-4 font-mono font-medium text-cream-950">{bo.order_number}</td>
                          <td className="py-3.5 px-4 text-cream-900 font-medium">
                            {bo.supplier?.supplier_name || "Supplier"}
                          </td>
                          <td className="py-3.5 px-4 text-cream-700">
                            {bo.from_date} &rarr; {bo.to_date}
                          </td>
                          <td className="py-3.5 px-4 font-mono font-semibold text-cream-900">
                            ${formatMoney(bo.total_amount)}
                          </td>
                          <td className="py-3.5 px-4">
                            <div className="space-y-1">
                              <div className="flex justify-between text-[10px] text-cream-600 font-medium">
                                <span>{drawnQty} / {totalQty} units</span>
                                <span>{pct}%</span>
                              </div>
                              <div className="w-32 bg-cream-200 h-2 rounded-full overflow-hidden">
                                <div
                                  className="bg-emerald-600 h-full rounded-full"
                                  style={{ width: `${pct}%` }}
                                />
                              </div>
                            </div>
                          </td>
                          <td className="py-3.5 px-4">
                            <span
                              className={`px-2 py-0.5 text-[10px] font-semibold rounded-full border ${
                                bo.status === "ACTIVE"
                                  ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                                  : "bg-cream-100 text-cream-700 border-cream-200"
                              }`}
                            >
                              {bo.status}
                            </span>
                          </td>
                          <td className="py-3.5 px-4 text-right">
                            {bo.status === "ACTIVE" && (
                              <button
                                onClick={() => {
                                  setShowDrawdownModal(bo);
                                  setDrawdownData({
                                    po_number: `PO-BO-${Date.now().toString().slice(-6)}`,
                                    items: bo.items?.map((it: any) => ({
                                      item_id: it.item_id,
                                      item_code: it.item?.item_code,
                                      remaining: Number(it.quantity) - Number(it.ordered_qty),
                                      unit_price: Number(it.unit_price),
                                      drawdown_qty: Math.min(10, Number(it.quantity) - Number(it.ordered_qty)),
                                    })) || [],
                                  });
                                }}
                                className="px-2.5 py-1 text-[11px] font-medium rounded bg-cream-900 text-cream-50 hover:bg-cream-800 transition-colors"
                              >
                                Release PO
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
        </div>
      )}

      {/* ------------------------------------------------------------------ */}
      {/* TAB 4: LANDED COST VOUCHERS */}
      {/* ------------------------------------------------------------------ */}
      {activeTab === "landed-costs" && (
        <div className="space-y-6">
          {/* Quick Metrics */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="bg-white p-4 rounded-xl border border-cream-200 shadow-sm">
              <span className="text-xs text-cream-600 font-medium">Total Landed Vouchers</span>
              <p className="text-xl font-bold text-cream-900 mt-1">{lcvs.length}</p>
            </div>
            <div className="bg-white p-4 rounded-xl border border-cream-200 shadow-sm">
              <span className="text-xs text-cream-600 font-medium">Total Capitalized Charges</span>
              <p className="text-xl font-bold text-emerald-700 mt-1">
                $
                {formatMoney(
                  lcvs.reduce((acc, l) => acc + Number(l.total_charges || 0), 0)
                )}
              </p>
            </div>
            <div className="bg-white p-4 rounded-xl border border-cream-200 shadow-sm">
              <span className="text-xs text-cream-600 font-medium">Submitted & Posted to GL</span>
              <p className="text-xl font-bold text-cream-700 mt-1">
                {lcvs.filter((l) => l.status === "SUBMITTED").length}
              </p>
            </div>
          </div>

          {/* LCV Table */}
          <div className="bg-white rounded-xl border border-cream-200 shadow-sm overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-cream-50/75 border-b border-cream-200 text-cream-700 font-semibold uppercase tracking-wider">
                  <tr>
                    <th className="py-3 px-4">Voucher #</th>
                    <th className="py-3 px-4">Posting Date</th>
                    <th className="py-3 px-4">Apportionment Basis</th>
                    <th className="py-3 px-4">Allocated Charges</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-cream-100">
                  {lcvs.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="py-8 text-center text-cream-500">
                        No landed cost vouchers found. Create a voucher to capitalize freight and customs into inventory.
                      </td>
                    </tr>
                  ) : (
                    lcvs.map((lcv) => (
                      <tr key={lcv.lcv_id} className="hover:bg-cream-50/50 transition-colors">
                        <td className="py-3.5 px-4 font-mono font-medium text-cream-950">
                          {lcv.voucher_number}
                          {lcv.notes && <p className="text-[10px] text-cream-500">{lcv.notes}</p>}
                        </td>
                        <td className="py-3.5 px-4 text-cream-700">{lcv.posting_date}</td>
                        <td className="py-3.5 px-4">
                          <span className="px-2 py-0.5 text-[10px] font-medium rounded-full bg-cream-100 text-cream-800 border border-cream-200">
                            Based on {lcv.distribute_charges_based_on}
                          </span>
                        </td>
                        <td className="py-3.5 px-4 font-mono font-bold text-cream-900">
                          ${formatMoney(lcv.total_charges)}
                        </td>
                        <td className="py-3.5 px-4">
                          <span
                            className={`px-2 py-0.5 text-[10px] font-semibold rounded-full border ${
                              lcv.status === "SUBMITTED"
                                ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                                : "bg-amber-50 text-amber-800 border-amber-200"
                            }`}
                          >
                            {lcv.status}
                          </span>
                        </td>
                        <td className="py-3.5 px-4 text-right">
                          <div className="flex items-center justify-end gap-1.5">
                            {lcv.status === "DRAFT" && (
                              <button
                                onClick={() => handleSubmitLCV(lcv.lcv_id)}
                                disabled={actionLoading}
                                className="px-2.5 py-1 text-[11px] font-medium rounded bg-emerald-600 text-white hover:bg-emerald-700 transition-colors"
                              >
                                Submit & Post GL
                              </button>
                            )}
                          </div>
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

      {/* ------------------------------------------------------------------ */}
      {/* TAB 5: SUPPLIER PERFORMANCE SCORECARDS & LEADERBOARD */}
      {/* ------------------------------------------------------------------ */}
      {activeTab === "scorecards" && (
        <div className="space-y-6">
          {/* Quick Metrics */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="bg-white p-4 rounded-xl border border-cream-200 shadow-sm">
              <span className="text-xs text-cream-600 font-medium">Ranked Suppliers</span>
              <p className="text-xl font-bold text-cream-900 mt-1">{leaderboard.length}</p>
            </div>
            <div className="bg-white p-4 rounded-xl border border-cream-200 shadow-sm">
              <span className="text-xs text-cream-600 font-medium">Preferred Suppliers (Tier 1)</span>
              <p className="text-xl font-bold text-emerald-700 mt-1">
                {leaderboard.filter((s) => s.standing === "PREFERRED").length}
              </p>
            </div>
            <div className="bg-white p-4 rounded-xl border border-cream-200 shadow-sm">
              <span className="text-xs text-cream-600 font-medium">At-Risk or Blacklisted</span>
              <p className="text-xl font-bold text-rose-700 mt-1">
                {leaderboard.filter((s) => s.standing === "AT_RISK" || s.standing === "BLACKLISTED").length}
              </p>
            </div>
          </div>

          {/* Leaderboard Table */}
          <div className="bg-white rounded-xl border border-cream-200 shadow-sm overflow-hidden">
            <div className="p-4 border-b border-cream-200">
              <h2 className="text-sm font-bold text-cream-950">Supplier Performance Leaderboard</h2>
              <p className="text-xs text-cream-600 mt-0.5">
                Evaluates OTIF (40%), Quality Inspection (40%), and Price Variance (20%)
              </p>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-cream-50/75 border-b border-cream-200 text-cream-700 font-semibold uppercase tracking-wider">
                  <tr>
                    <th className="py-3 px-4">Rank</th>
                    <th className="py-3 px-4">Supplier</th>
                    <th className="py-3 px-4">OTIF Score</th>
                    <th className="py-3 px-4">Quality Acceptance</th>
                    <th className="py-3 px-4">Price Variance</th>
                    <th className="py-3 px-4">Total Score</th>
                    <th className="py-3 px-4">Standing Tier</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-cream-100">
                  {leaderboard.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="py-8 text-center text-cream-500">
                        No evaluated suppliers yet. Click "Evaluate Supplier" to calculate metrics.
                      </td>
                    </tr>
                  ) : (
                    leaderboard.map((sup) => (
                      <tr key={sup.supplier_id} className="hover:bg-cream-50/50 transition-colors">
                        <td className="py-3.5 px-4 font-mono font-bold text-cream-700">
                          #{sup.rank}
                        </td>
                        <td className="py-3.5 px-4">
                          <p className="font-semibold text-cream-900">{sup.supplier_name}</p>
                          <span className="font-mono text-[10px] text-cream-500">{sup.supplier_code}</span>
                        </td>
                        <td className="py-3.5 px-4 font-mono text-cream-800">
                          {Number(sup.otif_score).toFixed(1)}%
                        </td>
                        <td className="py-3.5 px-4 font-mono text-cream-800">
                          {Number(sup.quality_score).toFixed(1)}%
                        </td>
                        <td className="py-3.5 px-4 font-mono text-cream-800">
                          {Number(sup.pricing_score).toFixed(1)}%
                        </td>
                        <td className="py-3.5 px-4 font-mono font-bold text-cream-950 text-sm">
                          {Number(sup.total_score).toFixed(1)}%
                        </td>
                        <td className="py-3.5 px-4">
                          <span
                            className={`px-2.5 py-1 text-[10px] font-bold rounded-full border ${
                              sup.standing === "PREFERRED"
                                ? "bg-emerald-50 text-emerald-800 border-emerald-300"
                                : sup.standing === "STANDARD"
                                ? "bg-blue-50 text-blue-800 border-blue-300"
                                : sup.standing === "AT_RISK"
                                ? "bg-amber-50 text-amber-800 border-amber-300"
                                : "bg-rose-50 text-rose-800 border-rose-300"
                            }`}
                          >
                            {sup.standing}
                          </span>
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

      {/* ------------------------------------------------------------------ */}
      {/* TAB 6: SUBCONTRACTING & OUTSIDE PROCESSING */}
      {/* ------------------------------------------------------------------ */}
      {activeTab === "subcontracting" && (
        <div className="space-y-6">
          {/* Quick Metrics */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="bg-white p-4 rounded-xl border border-cream-200 shadow-sm">
              <span className="text-xs text-cream-600 font-medium">Subcontracting Orders</span>
              <p className="text-xl font-bold text-cream-900 mt-1">{subconOrders.length}</p>
            </div>
            <div className="bg-white p-4 rounded-xl border border-cream-200 shadow-sm">
              <span className="text-xs text-cream-600 font-medium">In Process (At Vendor WH)</span>
              <p className="text-xl font-bold text-amber-700 mt-1">
                {subconOrders.filter((s) => s.status === "IN_PROCESS").length}
              </p>
            </div>
            <div className="bg-white p-4 rounded-xl border border-cream-200 shadow-sm">
              <span className="text-xs text-cream-600 font-medium">Completed Receipts</span>
              <p className="text-xl font-bold text-emerald-700 mt-1">{subconReceipts.length}</p>
            </div>
          </div>

          {/* Subcontracting Orders Table */}
          <div className="bg-white rounded-xl border border-cream-200 shadow-sm overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-cream-50/75 border-b border-cream-200 text-cream-700 font-semibold uppercase tracking-wider">
                  <tr>
                    <th className="py-3 px-4">SCO #</th>
                    <th className="py-3 px-4">Subcontractor</th>
                    <th className="py-3 px-4">Finished Goods</th>
                    <th className="py-3 px-4">Raw Components Required</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-cream-100">
                  {subconOrders.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="py-8 text-center text-cream-500">
                        No subcontracting orders found. Create an outside processing order to transfer materials and track finished goods.
                      </td>
                    </tr>
                  ) : (
                    subconOrders.map((sco) => (
                      <tr key={sco.sco_id} className="hover:bg-cream-50/50 transition-colors">
                        <td className="py-3.5 px-4 font-mono font-medium text-cream-950">{sco.sco_number}</td>
                        <td className="py-3.5 px-4 text-cream-900 font-medium">
                          {sco.supplier?.supplier_name || "Vendor"}
                        </td>
                        <td className="py-3.5 px-4">
                          {sco.items?.map((it: any) => (
                            <span key={it.sco_item_id} className="block text-[11px] font-semibold text-cream-900">
                              {it.item?.item_code}: {Number(it.quantity)} units
                            </span>
                          ))}
                        </td>
                        <td className="py-3.5 px-4">
                          {sco.supplied_items?.map((s: any) => (
                            <span key={s.supplied_item_id} className="block text-[11px] text-cream-700">
                              {s.raw_item?.item_code}: {Number(s.supplied_qty)} / {Number(s.required_qty)} supplied (Consumed: {Number(s.consumed_qty)})
                            </span>
                          ))}
                        </td>
                        <td className="py-3.5 px-4">
                          <span
                            className={`px-2 py-0.5 text-[10px] font-semibold rounded-full border ${
                              sco.status === "COMPLETED"
                                ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                                : sco.status === "IN_PROCESS"
                                ? "bg-blue-50 text-blue-800 border-blue-200"
                                : sco.status === "SUBMITTED"
                                ? "bg-amber-50 text-amber-800 border-amber-200"
                                : "bg-cream-100 text-cream-800 border-cream-200"
                            }`}
                          >
                            {sco.status}
                          </span>
                        </td>
                        <td className="py-3.5 px-4 text-right">
                          <div className="flex items-center justify-end gap-1.5">
                            {sco.status === "DRAFT" && (
                              <button
                                onClick={() => handleSubmitSCO(sco.sco_id)}
                                disabled={actionLoading}
                                className="px-2.5 py-1 text-[11px] font-medium rounded bg-emerald-600 text-white hover:bg-emerald-700 transition-colors"
                              >
                                Submit
                              </button>
                            )}

                            {(sco.status === "SUBMITTED" || sco.status === "IN_PROCESS") && (
                              <button
                                onClick={() => {
                                  setShowTransferModal(sco);
                                  setTransferData({
                                    transfers: sco.supplied_items?.map((s: any) => ({
                                      raw_item_id: s.raw_item_id,
                                      raw_item_code: s.raw_item?.item_code,
                                      quantity: Math.max(0, Number(s.required_qty) - Number(s.supplied_qty)),
                                      source_warehouse_id: s.source_warehouse_id || warehouses[0]?.warehouse_id || "",
                                      supplier_warehouse_id: s.supplier_warehouse_id || warehouses[1]?.warehouse_id || warehouses[0]?.warehouse_id || "",
                                    })) || [],
                                  });
                                }}
                                className="px-2.5 py-1 text-[11px] font-medium rounded bg-amber-600 text-white hover:bg-amber-700 transition-colors"
                              >
                                Issue Materials
                              </button>
                            )}

                            {sco.status === "IN_PROCESS" && (
                              <button
                                onClick={() => {
                                  setShowReceiveModal(sco);
                                  setReceiveData({
                                    scr_number: `SCR-${Date.now().toString().slice(-6)}`,
                                    target_warehouse_id: warehouses[0]?.warehouse_id || "",
                                    finished_items: sco.items?.map((it: any) => ({
                                      item_id: it.item_id,
                                      item_code: it.item?.item_code,
                                      quantity_received: Number(it.quantity),
                                      service_rate: Number(it.unit_price || 0),
                                    })) || [],
                                  });
                                }}
                                className="px-2.5 py-1 text-[11px] font-medium rounded bg-emerald-800 text-white hover:bg-emerald-900 transition-colors"
                              >
                                Receive FG
                              </button>
                            )}
                          </div>
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

      {/* ================================================================= */}
      {/* MODALS */}
      {/* ================================================================= */}

      {/* 1. Create Material Request Modal */}
      {showCreateMRModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <div className="bg-white rounded-xl border border-cream-200 shadow-xl max-w-xl w-full p-6 space-y-4">
            <div className="flex justify-between items-center border-b border-cream-200 pb-3">
              <h3 className="text-base font-bold text-cream-950 font-serif">New Material Requisition</h3>
              <button onClick={() => setShowCreateMRModal(false)}>
                <X className="w-5 h-5 text-cream-500 hover:text-cream-800" />
              </button>
            </div>

            <form onSubmit={handleCreateMR} className="space-y-4 text-xs">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-cream-700 font-semibold mb-1">Requisition #</label>
                  <input
                    type="text"
                    required
                    value={mrFormData.mr_number}
                    onChange={(e) => setMrFormData({ ...mrFormData, mr_number: e.target.value })}
                    className="w-full px-3 py-2 border border-cream-300 rounded-lg bg-cream-50/50"
                  />
                </div>
                <div>
                  <label className="block text-cream-700 font-semibold mb-1">Requisition Type</label>
                  <select
                    value={mrFormData.material_request_type}
                    onChange={(e) => setMrFormData({ ...mrFormData, material_request_type: e.target.value })}
                    className="w-full px-3 py-2 border border-cream-300 rounded-lg bg-cream-50/50"
                  >
                    <option value="PURCHASE">Purchase Order Requisition</option>
                    <option value="MATERIAL_TRANSFER">Material Transfer</option>
                    <option value="MATERIAL_ISSUE">Material Issue</option>
                    <option value="MANUFACTURE">Manufacture</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-cream-700 font-semibold mb-1">Required By Date</label>
                  <input
                    type="date"
                    value={mrFormData.schedule_date}
                    onChange={(e) => setMrFormData({ ...mrFormData, schedule_date: e.target.value })}
                    className="w-full px-3 py-2 border border-cream-300 rounded-lg bg-cream-50/50"
                  />
                </div>
                <div>
                  <label className="block text-cream-700 font-semibold mb-1">Internal Notes</label>
                  <input
                    type="text"
                    placeholder="Department or project reference..."
                    value={mrFormData.notes}
                    onChange={(e) => setMrFormData({ ...mrFormData, notes: e.target.value })}
                    className="w-full px-3 py-2 border border-cream-300 rounded-lg bg-cream-50/50"
                  />
                </div>
              </div>

              {/* Items Section */}
              <div className="space-y-2 border-t border-cream-200 pt-3">
                <div className="flex justify-between items-center">
                  <span className="font-bold text-cream-900">Requested Items</span>
                  <button
                    type="button"
                    onClick={() =>
                      setMrFormData({
                        ...mrFormData,
                        items: [
                          ...mrFormData.items,
                          { item_id: items[0]?.item_id || "", quantity: 1, target_warehouse_id: warehouses[0]?.warehouse_id || "", uom: "Nos" },
                        ],
                      })
                    }
                    className="text-amber-800 font-medium hover:underline text-[11px]"
                  >
                    + Add Item Line
                  </button>
                </div>

                {mrFormData.items.map((it: any, idx: number) => (
                  <div key={idx} className="grid grid-cols-12 gap-2 items-center bg-cream-50/75 p-2 rounded-lg border border-cream-200">
                    <div className="col-span-5">
                      <select
                        value={it.item_id}
                        onChange={(e) => {
                          const updated = [...mrFormData.items];
                          updated[idx].item_id = e.target.value;
                          setMrFormData({ ...mrFormData, items: updated });
                        }}
                        className="w-full px-2 py-1.5 border border-cream-300 rounded bg-white text-[11px]"
                      >
                        {items.map((item) => (
                          <option key={item.item_id} value={item.item_id}>
                            {item.item_code} - {item.item_name}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div className="col-span-3">
                      <input
                        type="number"
                        min="0.01"
                        step="any"
                        placeholder="Qty"
                        value={it.quantity}
                        onChange={(e) => {
                          const updated = [...mrFormData.items];
                          updated[idx].quantity = e.target.value;
                          setMrFormData({ ...mrFormData, items: updated });
                        }}
                        className="w-full px-2 py-1.5 border border-cream-300 rounded bg-white text-[11px]"
                      />
                    </div>

                    <div className="col-span-3">
                      <select
                        value={it.target_warehouse_id}
                        onChange={(e) => {
                          const updated = [...mrFormData.items];
                          updated[idx].target_warehouse_id = e.target.value;
                          setMrFormData({ ...mrFormData, items: updated });
                        }}
                        className="w-full px-2 py-1.5 border border-cream-300 rounded bg-white text-[11px]"
                      >
                        {warehouses.map((wh) => (
                          <option key={wh.warehouse_id} value={wh.warehouse_id}>
                            {wh.warehouse_name}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div className="col-span-1 text-right">
                      {mrFormData.items.length > 1 && (
                        <button
                          type="button"
                          onClick={() => {
                            const updated = mrFormData.items.filter((_: any, i: number) => i !== idx);
                            setMrFormData({ ...mrFormData, items: updated });
                          }}
                          className="text-rose-600 hover:text-rose-800"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-cream-200">
                <button
                  type="button"
                  onClick={() => setShowCreateMRModal(false)}
                  className="px-4 py-2 border border-cream-300 rounded-lg text-cream-700 hover:bg-cream-100"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="px-4 py-2 bg-cream-900 text-cream-50 rounded-lg hover:bg-cream-800 font-semibold"
                >
                  {actionLoading ? "Creating..." : "Save Draft Requisition"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* 2. Convert Requisition to PO Modal */}
      {showConvertMRModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <div className="bg-white rounded-xl border border-cream-200 shadow-xl max-w-md w-full p-6 space-y-4">
            <div className="flex justify-between items-center border-b border-cream-200 pb-3">
              <div>
                <h3 className="text-base font-bold text-cream-950 font-serif">Generate Purchase Order</h3>
                <p className="text-xs text-cream-600 mt-0.5">From {showConvertMRModal.mr_number}</p>
              </div>
              <button onClick={() => setShowConvertMRModal(null)}>
                <X className="w-5 h-5 text-cream-500 hover:text-cream-800" />
              </button>
            </div>

            <form onSubmit={handleConvertMRToPO} className="space-y-4 text-xs">
              <div>
                <label className="block text-cream-700 font-semibold mb-1">Target Vendor / Supplier</label>
                <select
                  required
                  value={convertPOData.supplier_id}
                  onChange={(e) => setConvertPOData({ ...convertPOData, supplier_id: e.target.value })}
                  className="w-full px-3 py-2 border border-cream-300 rounded-lg bg-cream-50/50"
                >
                  <option value="">Select Supplier...</option>
                  {suppliers.map((s) => (
                    <option key={s.supplier_id} value={s.supplier_id}>
                      {s.supplier_name} ({s.supplier_code})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-cream-700 font-semibold mb-1">Purchase Order #</label>
                <input
                  type="text"
                  required
                  value={convertPOData.po_number}
                  onChange={(e) => setConvertPOData({ ...convertPOData, po_number: e.target.value })}
                  className="w-full px-3 py-2 border border-cream-300 rounded-lg bg-cream-50/50 font-mono"
                />
              </div>

              <div className="bg-cream-50 p-3 rounded-lg border border-cream-200 space-y-1">
                <span className="font-semibold text-cream-900 block">Pending Items to Order:</span>
                {showConvertMRModal.items?.map((it: any) => (
                  <p key={it.mr_item_id} className="text-cream-700 text-[11px]">
                    &bull; {it.item?.item_code}: {Number(it.quantity) - Number(it.ordered_qty)} {it.uom}
                  </p>
                ))}
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-cream-200">
                <button
                  type="button"
                  onClick={() => setShowConvertMRModal(null)}
                  className="px-4 py-2 border border-cream-300 rounded-lg text-cream-700 hover:bg-cream-100"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="px-4 py-2 bg-cream-900 text-cream-50 rounded-lg hover:bg-cream-800 font-semibold"
                >
                  {actionLoading ? "Converting..." : "1-Click Create PO"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* 3. Quote Comparison Matrix Modal */}
      {comparisonMatrix && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <div className="bg-white rounded-xl border border-cream-200 shadow-xl max-w-4xl w-full p-6 space-y-4 max-h-[90vh] overflow-y-auto">
            <div className="flex justify-between items-center border-b border-cream-200 pb-3">
              <div>
                <h3 className="text-base font-bold text-cream-950 font-serif">
                  Quote Comparison Matrix &mdash; {comparisonMatrix.rfq_number}
                </h3>
                <p className="text-xs text-cream-600 mt-0.5">
                  {comparisonMatrix.total_quotes_received} vendor bids tendered out of {comparisonMatrix.total_invited_suppliers} invited
                </p>
              </div>
              <button onClick={() => setComparisonMatrix(null)}>
                <X className="w-5 h-5 text-cream-500 hover:text-cream-800" />
              </button>
            </div>

            {/* Quotations Overview */}
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
              {comparisonMatrix.quotations?.map((q: any) => (
                <div key={q.sq_id} className="p-3 bg-cream-50/75 rounded-lg border border-cream-200 space-y-1 text-xs">
                  <div className="flex justify-between items-center">
                    <span className="font-bold text-cream-900">{q.supplier_name}</span>
                    <span
                      className={`px-1.5 py-0.5 text-[9px] font-bold rounded ${
                        q.status === "AWARDED"
                          ? "bg-emerald-100 text-emerald-800"
                          : q.status === "REJECTED"
                          ? "bg-rose-100 text-rose-800"
                          : "bg-blue-100 text-blue-800"
                      }`}
                    >
                      {q.status}
                    </span>
                  </div>
                  <p className="text-cream-600 text-[11px] font-mono">{q.quotation_number}</p>
                  <p className="text-cream-800 font-bold text-sm mt-1">${formatMoney(q.grand_total)}</p>
                  <div className="flex justify-between text-[10px] text-cream-600">
                    <span>Lead time: {q.lead_time_days} days</span>
                    <span>OTIF: {q.otif_score}%</span>
                  </div>

                  {q.status !== "AWARDED" && q.status !== "REJECTED" && (
                    <button
                      onClick={() => {
                        setShowAwardModal({
                          sq_id: q.sq_id,
                          quote_number: q.quotation_number,
                          supplier_name: q.supplier_name,
                        });
                        setAwardPoNumber(`PO-AWARD-${Date.now().toString().slice(-6)}`);
                      }}
                      className="w-full mt-2 py-1 text-[11px] font-semibold rounded bg-emerald-600 text-white hover:bg-emerald-700 transition-colors shadow-sm"
                    >
                      Award PO to Winner
                    </button>
                  )}
                </div>
              ))}
            </div>

            {/* Side-by-Side Item Matrix */}
            <div className="space-y-4 border-t border-cream-200 pt-4">
              <h4 className="text-xs font-bold text-cream-950 uppercase tracking-wider">Line Item Bidding Analysis</h4>
              {comparisonMatrix.items_matrix?.map((it: any) => (
                <div key={it.item_id} className="border border-cream-200 rounded-lg overflow-hidden">
                  <div className="bg-cream-100/50 p-2.5 flex justify-between items-center text-xs">
                    <div>
                      <span className="font-bold text-cream-900">{it.item_code}</span> &bull; {it.item_name}
                    </div>
                    <span className="font-semibold text-cream-700">Req Qty: {it.required_qty} units</span>
                  </div>

                  <table className="w-full text-left text-xs">
                    <thead className="bg-cream-50 text-cream-700 border-b border-cream-200 text-[11px]">
                      <tr>
                        <th className="py-2 px-3">Rank</th>
                        <th className="py-2 px-3">Supplier</th>
                        <th className="py-2 px-3">Unit Price</th>
                        <th className="py-2 px-3">Discount</th>
                        <th className="py-2 px-3">Line Total</th>
                        <th className="py-2 px-3">Lead Time</th>
                        <th className="py-2 px-3">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-cream-100">
                      {it.bids?.map((bid: any) => (
                        <tr key={bid.sq_id} className={bid.is_lowest_price ? "bg-emerald-50/40" : ""}>
                          <td className="py-2 px-3 font-bold font-mono">
                            #{bid.rank}
                            {bid.is_lowest_price && (
                              <span className="ml-1.5 text-[10px] bg-emerald-100 text-emerald-800 px-1.5 py-0.5 rounded font-sans">
                                Best Price
                              </span>
                            )}
                          </td>
                          <td className="py-2 px-3 font-medium text-cream-900">{bid.supplier_name}</td>
                          <td className="py-2 px-3 font-mono font-bold text-cream-900">${formatMoney(bid.unit_price)}</td>
                          <td className="py-2 px-3 font-mono text-cream-600">{bid.discount_pct}%</td>
                          <td className="py-2 px-3 font-mono font-bold text-cream-950">${formatMoney(bid.line_total)}</td>
                          <td className="py-2 px-3 text-cream-700">{bid.lead_time_days} days</td>
                          <td className="py-2 px-3">
                            <span className="text-[10px] text-cream-600 font-medium font-mono">{bid.quotation_number}</span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ))}
            </div>

            <div className="flex justify-end pt-3 border-t border-cream-200">
              <button
                type="button"
                onClick={() => setComparisonMatrix(null)}
                className="px-4 py-2 border border-cream-300 rounded-lg text-cream-700 hover:bg-cream-100 text-xs"
              >
                Close Matrix
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 4. Award PO Confirmation Modal */}
      {showAwardModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <div className="bg-white rounded-xl border border-cream-200 shadow-xl max-w-md w-full p-6 space-y-4">
            <div className="flex justify-between items-center border-b border-cream-200 pb-3">
              <h3 className="text-base font-bold text-cream-950 font-serif">Award Tender to Vendor</h3>
              <button onClick={() => setShowAwardModal(null)}>
                <X className="w-5 h-5 text-cream-500 hover:text-cream-800" />
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <p className="text-cream-700">
                You are awarding the winning quotation <strong className="text-cream-950 font-mono">{showAwardModal.quote_number}</strong> from{" "}
                <strong className="text-cream-950">{showAwardModal.supplier_name}</strong>.
              </p>
              <div className="bg-amber-50 p-3 rounded-lg border border-amber-200 text-amber-900 text-[11px] space-y-1">
                <p className="font-semibold">&bull; 1-Click Purchase Order Generation</p>
                <p>&bull; Marks other competing bids on this RFQ as REJECTED</p>
                <p>&bull; Closes the RFQ status to COMPLETED</p>
              </div>

              <div>
                <label className="block text-cream-700 font-semibold mb-1">New Purchase Order #</label>
                <input
                  type="text"
                  required
                  value={awardPoNumber}
                  onChange={(e) => setAwardPoNumber(e.target.value)}
                  className="w-full px-3 py-2 border border-cream-300 rounded-lg bg-cream-50/50 font-mono"
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-3 border-t border-cream-200 text-xs">
              <button
                type="button"
                onClick={() => setShowAwardModal(null)}
                className="px-4 py-2 border border-cream-300 rounded-lg text-cream-700 hover:bg-cream-100"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleAwardQuote}
                disabled={actionLoading}
                className="px-4 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 font-semibold shadow-sm"
              >
                {actionLoading ? "Awarding..." : "Confirm & Award PO"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 5. Create RFQ Modal */}
      {showCreateRFQModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <div className="bg-white rounded-xl border border-cream-200 shadow-xl max-w-xl w-full p-6 space-y-4">
            <div className="flex justify-between items-center border-b border-cream-200 pb-3">
              <h3 className="text-base font-bold text-cream-950 font-serif">Create Request for Quotation (RFQ)</h3>
              <button onClick={() => setShowCreateRFQModal(false)}>
                <X className="w-5 h-5 text-cream-500 hover:text-cream-800" />
              </button>
            </div>

            <form onSubmit={handleCreateRFQ} className="space-y-4 text-xs">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-cream-700 font-semibold mb-1">RFQ #</label>
                  <input
                    type="text"
                    required
                    value={rfqFormData.rfq_number}
                    onChange={(e) => setRfqFormData({ ...rfqFormData, rfq_number: e.target.value })}
                    className="w-full px-3 py-2 border border-cream-300 rounded-lg bg-cream-50/50 font-mono"
                  />
                </div>
                <div>
                  <label className="block text-cream-700 font-semibold mb-1">Notes / Terms</label>
                  <input
                    type="text"
                    placeholder="Tender terms..."
                    value={rfqFormData.notes}
                    onChange={(e) => setRfqFormData({ ...rfqFormData, notes: e.target.value })}
                    className="w-full px-3 py-2 border border-cream-300 rounded-lg bg-cream-50/50"
                  />
                </div>
              </div>

              <div>
                <label className="block text-cream-700 font-semibold mb-1">Invite Suppliers for Bidding</label>
                <div className="grid grid-cols-2 gap-2 bg-cream-50/50 p-2.5 rounded-lg border border-cream-200 max-h-32 overflow-y-auto">
                  {suppliers.map((s) => {
                    const checked = rfqFormData.supplier_ids.includes(s.supplier_id);
                    return (
                      <label key={s.supplier_id} className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setRfqFormData({
                                ...rfqFormData,
                                supplier_ids: [...rfqFormData.supplier_ids, s.supplier_id],
                              });
                            } else {
                              setRfqFormData({
                                ...rfqFormData,
                                supplier_ids: rfqFormData.supplier_ids.filter((id: string) => id !== s.supplier_id),
                              });
                            }
                          }}
                        />
                        <span className="text-[11px] text-cream-800">{s.supplier_name}</span>
                      </label>
                    );
                  })}
                </div>
              </div>

              {/* Items Section */}
              <div className="space-y-2 border-t border-cream-200 pt-3">
                <div className="flex justify-between items-center">
                  <span className="font-bold text-cream-900">Items to Quote</span>
                  <button
                    type="button"
                    onClick={() =>
                      setRfqFormData({
                        ...rfqFormData,
                        items: [...rfqFormData.items, { item_id: items[0]?.item_id || "", quantity: 10 }],
                      })
                    }
                    className="text-amber-800 font-medium hover:underline text-[11px]"
                  >
                    + Add Item
                  </button>
                </div>

                {rfqFormData.items.map((it: any, idx: number) => (
                  <div key={idx} className="grid grid-cols-12 gap-2 items-center bg-cream-50/75 p-2 rounded-lg border border-cream-200">
                    <div className="col-span-7">
                      <select
                        value={it.item_id}
                        onChange={(e) => {
                          const updated = [...rfqFormData.items];
                          updated[idx].item_id = e.target.value;
                          setRfqFormData({ ...rfqFormData, items: updated });
                        }}
                        className="w-full px-2 py-1.5 border border-cream-300 rounded bg-white text-[11px]"
                      >
                        {items.map((item) => (
                          <option key={item.item_id} value={item.item_id}>
                            {item.item_code} - {item.item_name}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div className="col-span-4">
                      <input
                        type="number"
                        min="1"
                        placeholder="Quantity"
                        value={it.quantity}
                        onChange={(e) => {
                          const updated = [...rfqFormData.items];
                          updated[idx].quantity = e.target.value;
                          setRfqFormData({ ...rfqFormData, items: updated });
                        }}
                        className="w-full px-2 py-1.5 border border-cream-300 rounded bg-white text-[11px]"
                      />
                    </div>

                    <div className="col-span-1 text-right">
                      {rfqFormData.items.length > 1 && (
                        <button
                          type="button"
                          onClick={() => {
                            const updated = rfqFormData.items.filter((_: any, i: number) => i !== idx);
                            setRfqFormData({ ...rfqFormData, items: updated });
                          }}
                          className="text-rose-600 hover:text-rose-800"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-cream-200">
                <button
                  type="button"
                  onClick={() => setShowCreateRFQModal(false)}
                  className="px-4 py-2 border border-cream-300 rounded-lg text-cream-700 hover:bg-cream-100"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="px-4 py-2 bg-cream-900 text-cream-50 rounded-lg hover:bg-cream-800 font-semibold"
                >
                  {actionLoading ? "Creating..." : "Save RFQ Draft"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* 6. Landed Cost Voucher Modal */}
      {showCreateLCVModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <div className="bg-white rounded-xl border border-cream-200 shadow-xl max-w-2xl w-full p-6 space-y-4 max-h-[90vh] overflow-y-auto">
            <div className="flex justify-between items-center border-b border-cream-200 pb-3">
              <div>
                <h3 className="text-base font-bold text-cream-950 font-serif">New Landed Cost Voucher</h3>
                <p className="text-xs text-cream-600 mt-0.5">Capitalize shipping, duties & customs into stock valuation</p>
              </div>
              <button onClick={() => setShowCreateLCVModal(false)}>
                <X className="w-5 h-5 text-cream-500 hover:text-cream-800" />
              </button>
            </div>

            <form onSubmit={handleCreateLCV} className="space-y-4 text-xs">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-cream-700 font-semibold mb-1">Voucher #</label>
                  <input
                    type="text"
                    required
                    value={lcvFormData.voucher_number}
                    onChange={(e) => setLcvFormData({ ...lcvFormData, voucher_number: e.target.value })}
                    className="w-full px-3 py-2 border border-cream-300 rounded-lg bg-cream-50/50 font-mono"
                  />
                </div>
                <div>
                  <label className="block text-cream-700 font-semibold mb-1">Apportionment Basis</label>
                  <select
                    value={lcvFormData.distribute_charges_based_on}
                    onChange={(e) => setLcvFormData({ ...lcvFormData, distribute_charges_based_on: e.target.value })}
                    className="w-full px-3 py-2 border border-cream-300 rounded-lg bg-cream-50/50"
                  >
                    <option value="VALUATION">By Item Purchase Valuation Amount</option>
                    <option value="QUANTITY">By Item Receipt Quantity</option>
                  </select>
                </div>
              </div>

              {/* Select GRNs */}
              <div>
                <label className="block text-cream-700 font-semibold mb-1">Select Goods Receipt Notes (GRNs)</label>
                <div className="bg-cream-50/50 p-2.5 rounded-lg border border-cream-200 max-h-32 overflow-y-auto space-y-1">
                  {goodsReceipts.map((grn) => {
                    const checked = lcvFormData.grn_ids.includes(grn.grn_id);
                    return (
                      <label key={grn.grn_id} className="flex items-center gap-2 cursor-pointer text-[11px]">
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setLcvFormData({ ...lcvFormData, grn_ids: [...lcvFormData.grn_ids, grn.grn_id] });
                            } else {
                              setLcvFormData({
                                ...lcvFormData,
                                grn_ids: lcvFormData.grn_ids.filter((id: string) => id !== grn.grn_id),
                              });
                            }
                          }}
                        />
                        <span className="font-mono font-medium text-cream-950">{grn.grn_number}</span>
                        <span className="text-cream-600">({grn.receipt_date})</span>
                      </label>
                    );
                  })}
                </div>
              </div>

              {/* Landed Taxes and Charges Table */}
              <div className="space-y-2 border-t border-cream-200 pt-3">
                <div className="flex justify-between items-center">
                  <span className="font-bold text-cream-900">Freight & Customs Charges to Capitalize</span>
                  <button
                    type="button"
                    onClick={() =>
                      setLcvFormData({
                        ...lcvFormData,
                        taxes_and_charges: [
                          ...lcvFormData.taxes_and_charges,
                          { expense_account: "5100-FREIGHT-CUSTOMS-CLEARING", description: "Handling Fee", amount: 100 },
                        ],
                      })
                    }
                    className="text-amber-800 font-medium hover:underline text-[11px]"
                  >
                    + Add Charge Line
                  </button>
                </div>

                {lcvFormData.taxes_and_charges.map((tc: any, idx: number) => (
                  <div key={idx} className="grid grid-cols-12 gap-2 items-center bg-cream-50/75 p-2 rounded-lg border border-cream-200">
                    <div className="col-span-6">
                      <input
                        type="text"
                        placeholder="Description (e.g. Ocean Freight)"
                        value={tc.description}
                        onChange={(e) => {
                          const updated = [...lcvFormData.taxes_and_charges];
                          updated[idx].description = e.target.value;
                          setLcvFormData({ ...lcvFormData, taxes_and_charges: updated });
                        }}
                        className="w-full px-2 py-1.5 border border-cream-300 rounded bg-white text-[11px]"
                      />
                    </div>
                    <div className="col-span-5">
                      <div className="flex items-center gap-1">
                        <span className="text-cream-500 font-mono">$</span>
                        <input
                          type="number"
                          min="0.01"
                          step="any"
                          placeholder="Amount"
                          value={tc.amount}
                          onChange={(e) => {
                            const updated = [...lcvFormData.taxes_and_charges];
                            updated[idx].amount = e.target.value;
                            setLcvFormData({ ...lcvFormData, taxes_and_charges: updated });
                          }}
                          className="w-full px-2 py-1.5 border border-cream-300 rounded bg-white text-[11px] font-mono"
                        />
                      </div>
                    </div>
                    <div className="col-span-1 text-right">
                      {lcvFormData.taxes_and_charges.length > 1 && (
                        <button
                          type="button"
                          onClick={() => {
                            const updated = lcvFormData.taxes_and_charges.filter((_: any, i: number) => i !== idx);
                            setLcvFormData({ ...lcvFormData, taxes_and_charges: updated });
                          }}
                          className="text-rose-600 hover:text-rose-800"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  </div>
                ))}

                <div className="text-right text-xs font-bold text-cream-900 pt-1">
                  Total Landed Charges: $
                  {formatMoney(
                    lcvFormData.taxes_and_charges.reduce((acc: number, c: any) => acc + Number(c.amount || 0), 0)
                  )}
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-cream-200">
                <button
                  type="button"
                  onClick={() => setShowCreateLCVModal(false)}
                  className="px-4 py-2 border border-cream-300 rounded-lg text-cream-700 hover:bg-cream-100"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading || lcvFormData.grn_ids.length === 0}
                  className="px-4 py-2 bg-cream-900 text-cream-50 rounded-lg hover:bg-cream-800 font-semibold"
                >
                  {actionLoading ? "Apportioning..." : "Create & Apportion"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* 7. Drawdown Blanket Order Modal */}
      {showDrawdownModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <div className="bg-white rounded-xl border border-cream-200 shadow-xl max-w-lg w-full p-6 space-y-4">
            <div className="flex justify-between items-center border-b border-cream-200 pb-3">
              <div>
                <h3 className="text-base font-bold text-cream-950 font-serif">Release PO from Contract</h3>
                <p className="text-xs text-cream-600 mt-0.5">
                  Drawdown against {showDrawdownModal.order_number} ({showDrawdownModal.supplier?.supplier_name})
                </p>
              </div>
              <button onClick={() => setShowDrawdownModal(null)}>
                <X className="w-5 h-5 text-cream-500 hover:text-cream-800" />
              </button>
            </div>

            <form onSubmit={handleDrawdownBO} className="space-y-4 text-xs">
              <div>
                <label className="block text-cream-700 font-semibold mb-1">Release Purchase Order #</label>
                <input
                  type="text"
                  required
                  value={drawdownData.po_number}
                  onChange={(e) => setDrawdownData({ ...drawdownData, po_number: e.target.value })}
                  className="w-full px-3 py-2 border border-cream-300 rounded-lg bg-cream-50/50 font-mono"
                />
              </div>

              <div className="space-y-2 border-t border-cream-200 pt-3">
                <span className="font-bold text-cream-900 block">Item Drawdowns</span>
                {drawdownData.items.map((it: any, idx: number) => (
                  <div key={it.item_id} className="p-2.5 bg-cream-50/75 rounded-lg border border-cream-200 space-y-1">
                    <div className="flex justify-between items-center">
                      <span className="font-bold text-cream-900">{it.item_code}</span>
                      <span className="text-emerald-700 font-mono font-semibold">${formatMoney(it.unit_price)}/unit</span>
                    </div>
                    <div className="flex justify-between items-center text-[11px] text-cream-600">
                      <span>Contract Balance: {it.remaining} units</span>
                      <div className="flex items-center gap-1">
                        <span>Drawdown Qty:</span>
                        <input
                          type="number"
                          min="1"
                          max={it.remaining}
                          value={it.drawdown_qty}
                          onChange={(e) => {
                            const updated = [...drawdownData.items];
                            updated[idx].drawdown_qty = e.target.value;
                            setDrawdownData({ ...drawdownData, items: updated });
                          }}
                          className="w-20 px-2 py-1 border border-cream-300 rounded bg-white font-mono"
                        />
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-cream-200">
                <button
                  type="button"
                  onClick={() => setShowDrawdownModal(null)}
                  className="px-4 py-2 border border-cream-300 rounded-lg text-cream-700 hover:bg-cream-100"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="px-4 py-2 bg-cream-900 text-cream-50 rounded-lg hover:bg-cream-800 font-semibold"
                >
                  {actionLoading ? "Releasing..." : "Release PO"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* 8. Evaluate Scorecard Modal */}
      {showCalcScorecardModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <div className="bg-white rounded-xl border border-cream-200 shadow-xl max-w-md w-full p-6 space-y-4">
            <div className="flex justify-between items-center border-b border-cream-200 pb-3">
              <h3 className="text-base font-bold text-cream-950 font-serif">Evaluate Supplier Performance</h3>
              <button onClick={() => setShowCalcScorecardModal(false)}>
                <X className="w-5 h-5 text-cream-500 hover:text-cream-800" />
              </button>
            </div>

            <form onSubmit={handleCalculateScorecard} className="space-y-4 text-xs">
              <div>
                <label className="block text-cream-700 font-semibold mb-1">Select Supplier</label>
                <select
                  required
                  value={scorecardFormData.supplier_id}
                  onChange={(e) => setScorecardFormData({ ...scorecardFormData, supplier_id: e.target.value })}
                  className="w-full px-3 py-2 border border-cream-300 rounded-lg bg-cream-50/50"
                >
                  <option value="">Select Vendor...</option>
                  {suppliers.map((s) => (
                    <option key={s.supplier_id} value={s.supplier_id}>
                      {s.supplier_name} ({s.supplier_code})
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-cream-700 font-semibold mb-1">Period Start</label>
                  <input
                    type="date"
                    required
                    value={scorecardFormData.period_start}
                    onChange={(e) => setScorecardFormData({ ...scorecardFormData, period_start: e.target.value })}
                    className="w-full px-3 py-2 border border-cream-300 rounded-lg bg-cream-50/50"
                  />
                </div>
                <div>
                  <label className="block text-cream-700 font-semibold mb-1">Period End</label>
                  <input
                    type="date"
                    required
                    value={scorecardFormData.period_end}
                    onChange={(e) => setScorecardFormData({ ...scorecardFormData, period_end: e.target.value })}
                    className="w-full px-3 py-2 border border-cream-300 rounded-lg bg-cream-50/50"
                  />
                </div>
              </div>

              <div>
                <label className="block text-cream-700 font-semibold mb-1">Evaluation Cycle</label>
                <select
                  value={scorecardFormData.evaluation_period}
                  onChange={(e) => setScorecardFormData({ ...scorecardFormData, evaluation_period: e.target.value })}
                  className="w-full px-3 py-2 border border-cream-300 rounded-lg bg-cream-50/50"
                >
                  <option value="MONTHLY">Monthly</option>
                  <option value="QUARTERLY">Quarterly</option>
                  <option value="ANNUAL">Annual</option>
                </select>
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-cream-200">
                <button
                  type="button"
                  onClick={() => setShowCalcScorecardModal(false)}
                  className="px-4 py-2 border border-cream-300 rounded-lg text-cream-700 hover:bg-cream-100"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="px-4 py-2 bg-cream-900 text-cream-50 rounded-lg hover:bg-cream-800 font-semibold"
                >
                  {actionLoading ? "Evaluating..." : "Run Evaluation"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* 9. Create Subcontracting Order Modal */}
      {showCreateSCOModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <div className="bg-white rounded-xl border border-cream-200 shadow-xl max-w-2xl w-full p-6 space-y-4 max-h-[90vh] overflow-y-auto">
            <div className="flex justify-between items-center border-b border-cream-200 pb-3">
              <div>
                <h3 className="text-base font-bold text-cream-950 font-serif">New Subcontracting Order</h3>
                <p className="text-xs text-cream-600 mt-0.5">Component supply & outsourced assembly</p>
              </div>
              <button onClick={() => setShowCreateSCOModal(false)}>
                <X className="w-5 h-5 text-cream-500 hover:text-cream-800" />
              </button>
            </div>

            <form onSubmit={handleCreateSCO} className="space-y-4 text-xs">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-cream-700 font-semibold mb-1">Order #</label>
                  <input
                    type="text"
                    required
                    value={scoFormData.sco_number}
                    onChange={(e) => setScoFormData({ ...scoFormData, sco_number: e.target.value })}
                    className="w-full px-3 py-2 border border-cream-300 rounded-lg bg-cream-50/50 font-mono"
                  />
                </div>
                <div>
                  <label className="block text-cream-700 font-semibold mb-1">Subcontractor (Vendor)</label>
                  <select
                    required
                    value={scoFormData.supplier_id}
                    onChange={(e) => setScoFormData({ ...scoFormData, supplier_id: e.target.value })}
                    className="w-full px-3 py-2 border border-cream-300 rounded-lg bg-cream-50/50"
                  >
                    <option value="">Select Subcontractor...</option>
                    {suppliers.map((s) => (
                      <option key={s.supplier_id} value={s.supplier_id}>
                        {s.supplier_name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Finished Good to produce */}
              <div className="border-t border-cream-200 pt-3 space-y-2">
                <span className="font-bold text-cream-900 block">Finished Goods to Produce</span>
                {scoFormData.finished_items.map((it: any, idx: number) => (
                  <div key={idx} className="grid grid-cols-12 gap-2 bg-cream-50/75 p-2 rounded-lg border border-cream-200">
                    <div className="col-span-8">
                      <select
                        value={it.item_id}
                        onChange={(e) => {
                          const updated = [...scoFormData.finished_items];
                          updated[idx].item_id = e.target.value;
                          setScoFormData({ ...scoFormData, finished_items: updated });
                        }}
                        className="w-full px-2 py-1.5 border border-cream-300 rounded bg-white text-[11px]"
                      >
                        {items.map((item) => (
                          <option key={item.item_id} value={item.item_id}>
                            {item.item_code} - {item.item_name}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="col-span-4">
                      <input
                        type="number"
                        min="1"
                        placeholder="Quantity"
                        value={it.quantity}
                        onChange={(e) => {
                          const updated = [...scoFormData.finished_items];
                          updated[idx].quantity = e.target.value;
                          setScoFormData({ ...scoFormData, finished_items: updated });
                        }}
                        className="w-full px-2 py-1.5 border border-cream-300 rounded bg-white text-[11px]"
                      />
                    </div>
                  </div>
                ))}
              </div>

              {/* Components to Supply */}
              <div className="border-t border-cream-200 pt-3 space-y-2">
                <span className="font-bold text-cream-900 block">Raw Materials / Components to Issue</span>
                {scoFormData.supplied_items.map((s: any, idx: number) => (
                  <div key={idx} className="grid grid-cols-12 gap-2 bg-cream-50/75 p-2 rounded-lg border border-cream-200">
                    <div className="col-span-4">
                      <select
                        value={s.raw_item_id}
                        onChange={(e) => {
                          const updated = [...scoFormData.supplied_items];
                          updated[idx].raw_item_id = e.target.value;
                          setScoFormData({ ...scoFormData, supplied_items: updated });
                        }}
                        className="w-full px-2 py-1.5 border border-cream-300 rounded bg-white text-[11px]"
                      >
                        {items.map((item) => (
                          <option key={item.item_id} value={item.item_id}>
                            {item.item_code}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="col-span-2">
                      <input
                        type="number"
                        min="1"
                        placeholder="Qty"
                        value={s.required_qty}
                        onChange={(e) => {
                          const updated = [...scoFormData.supplied_items];
                          updated[idx].required_qty = e.target.value;
                          setScoFormData({ ...scoFormData, supplied_items: updated });
                        }}
                        className="w-full px-2 py-1.5 border border-cream-300 rounded bg-white text-[11px]"
                      />
                    </div>
                    <div className="col-span-3">
                      <select
                        value={s.source_warehouse_id}
                        onChange={(e) => {
                          const updated = [...scoFormData.supplied_items];
                          updated[idx].source_warehouse_id = e.target.value;
                          setScoFormData({ ...scoFormData, supplied_items: updated });
                        }}
                        className="w-full px-2 py-1.5 border border-cream-300 rounded bg-white text-[11px]"
                      >
                        <option value="">Source WH...</option>
                        {warehouses.map((wh) => (
                          <option key={wh.warehouse_id} value={wh.warehouse_id}>
                            {wh.warehouse_name}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="col-span-3">
                      <select
                        value={s.supplier_warehouse_id}
                        onChange={(e) => {
                          const updated = [...scoFormData.supplied_items];
                          updated[idx].supplier_warehouse_id = e.target.value;
                          setScoFormData({ ...scoFormData, supplied_items: updated });
                        }}
                        className="w-full px-2 py-1.5 border border-cream-300 rounded bg-white text-[11px]"
                      >
                        <option value="">Vendor WH...</option>
                        {warehouses.map((wh) => (
                          <option key={wh.warehouse_id} value={wh.warehouse_id}>
                            {wh.warehouse_name}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>
                ))}
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-cream-200">
                <button
                  type="button"
                  onClick={() => setShowCreateSCOModal(false)}
                  className="px-4 py-2 border border-cream-300 rounded-lg text-cream-700 hover:bg-cream-100"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="px-4 py-2 bg-cream-900 text-cream-50 rounded-lg hover:bg-cream-800 font-semibold"
                >
                  {actionLoading ? "Creating..." : "Save Order"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* 10. Transfer Materials Modal */}
      {showTransferModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <div className="bg-white rounded-xl border border-cream-200 shadow-xl max-w-lg w-full p-6 space-y-4">
            <div className="flex justify-between items-center border-b border-cream-200 pb-3">
              <div>
                <h3 className="text-base font-bold text-cream-950 font-serif">Issue Components to Vendor WH</h3>
                <p className="text-xs text-cream-600 mt-0.5">Subcontracting Order: {showTransferModal.sco_number}</p>
              </div>
              <button onClick={() => setShowTransferModal(null)}>
                <X className="w-5 h-5 text-cream-500 hover:text-cream-800" />
              </button>
            </div>

            <form onSubmit={handleTransferMaterials} className="space-y-4 text-xs">
              <div className="space-y-3">
                {transferData.transfers.map((tr: any, idx: number) => (
                  <div key={idx} className="p-3 bg-cream-50/75 rounded-lg border border-cream-200 space-y-2">
                    <div className="flex justify-between items-center font-bold text-cream-900">
                      <span>{tr.raw_item_code}</span>
                      <div className="flex items-center gap-1 font-mono">
                        <span>Transfer Qty:</span>
                        <input
                          type="number"
                          min="1"
                          value={tr.quantity}
                          onChange={(e) => {
                            const updated = [...transferData.transfers];
                            updated[idx].quantity = e.target.value;
                            setTransferData({ ...transferData, transfers: updated });
                          }}
                          className="w-20 px-2 py-1 border border-cream-300 rounded bg-white"
                        />
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-2 text-[11px]">
                      <div>
                        <label className="text-cream-600 block mb-0.5">Source WH (Issue from):</label>
                        <select
                          value={tr.source_warehouse_id}
                          onChange={(e) => {
                            const updated = [...transferData.transfers];
                            updated[idx].source_warehouse_id = e.target.value;
                            setTransferData({ ...transferData, transfers: updated });
                          }}
                          className="w-full px-2 py-1 border border-cream-300 rounded bg-white text-[11px]"
                        >
                          {warehouses.map((wh) => (
                            <option key={wh.warehouse_id} value={wh.warehouse_id}>
                              {wh.warehouse_name}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className="text-cream-600 block mb-0.5">Vendor WH (Receive at):</label>
                        <select
                          value={tr.supplier_warehouse_id}
                          onChange={(e) => {
                            const updated = [...transferData.transfers];
                            updated[idx].supplier_warehouse_id = e.target.value;
                            setTransferData({ ...transferData, transfers: updated });
                          }}
                          className="w-full px-2 py-1 border border-cream-300 rounded bg-white text-[11px]"
                        >
                          {warehouses.map((wh) => (
                            <option key={wh.warehouse_id} value={wh.warehouse_id}>
                              {wh.warehouse_name}
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-cream-200">
                <button
                  type="button"
                  onClick={() => setShowTransferModal(null)}
                  className="px-4 py-2 border border-cream-300 rounded-lg text-cream-700 hover:bg-cream-100"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="px-4 py-2 bg-cream-900 text-cream-50 rounded-lg hover:bg-cream-800 font-semibold"
                >
                  {actionLoading ? "Transferring..." : "Confirm Material Transfer"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* 11. Receive Finished Assembly Modal */}
      {showReceiveModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <div className="bg-white rounded-xl border border-cream-200 shadow-xl max-w-lg w-full p-6 space-y-4">
            <div className="flex justify-between items-center border-b border-cream-200 pb-3">
              <div>
                <h3 className="text-base font-bold text-cream-950 font-serif">Receive Subcontracted Finished Goods</h3>
                <p className="text-xs text-cream-600 mt-0.5">Auto-consumes components from vendor warehouse</p>
              </div>
              <button onClick={() => setShowReceiveModal(null)}>
                <X className="w-5 h-5 text-cream-500 hover:text-cream-800" />
              </button>
            </div>

            <form onSubmit={handleReceiveSubcontractedGoods} className="space-y-4 text-xs">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-cream-700 font-semibold mb-1">Receipt #</label>
                  <input
                    type="text"
                    required
                    value={receiveData.scr_number}
                    onChange={(e) => setReceiveData({ ...receiveData, scr_number: e.target.value })}
                    className="w-full px-3 py-2 border border-cream-300 rounded-lg bg-cream-50/50 font-mono"
                  />
                </div>
                <div>
                  <label className="block text-cream-700 font-semibold mb-1">Target Receiving Warehouse</label>
                  <select
                    required
                    value={receiveData.target_warehouse_id}
                    onChange={(e) => setReceiveData({ ...receiveData, target_warehouse_id: e.target.value })}
                    className="w-full px-3 py-2 border border-cream-300 rounded-lg bg-cream-50/50"
                  >
                    <option value="">Select Warehouse...</option>
                    {warehouses.map((wh) => (
                      <option key={wh.warehouse_id} value={wh.warehouse_id}>
                        {wh.warehouse_name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="space-y-2 border-t border-cream-200 pt-3">
                <span className="font-bold text-cream-900 block">Received Finished Goods</span>
                {receiveData.finished_items.map((it: any, idx: number) => (
                  <div key={idx} className="p-2.5 bg-cream-50/75 rounded-lg border border-cream-200 flex justify-between items-center">
                    <span className="font-bold text-cream-900">{it.item_code}</span>
                    <div className="flex items-center gap-1 font-mono">
                      <span>Qty Received:</span>
                      <input
                        type="number"
                        min="1"
                        value={it.quantity_received}
                        onChange={(e) => {
                          const updated = [...receiveData.finished_items];
                          updated[idx].quantity_received = e.target.value;
                          setReceiveData({ ...receiveData, finished_items: updated });
                        }}
                        className="w-20 px-2 py-1 border border-cream-300 rounded bg-white"
                      />
                    </div>
                  </div>
                ))}
              </div>

              <div className="bg-emerald-50 p-2.5 rounded-lg border border-emerald-200 text-emerald-900 text-[11px]">
                &bull; System will increment Finished Goods in target warehouse.
                <br />
                &bull; Proportional raw materials will be automatically deducted from vendor warehouse.
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-cream-200">
                <button
                  type="button"
                  onClick={() => setShowReceiveModal(null)}
                  className="px-4 py-2 border border-cream-300 rounded-lg text-cream-700 hover:bg-cream-100"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="px-4 py-2 bg-cream-900 text-cream-50 rounded-lg hover:bg-cream-800 font-semibold"
                >
                  {actionLoading ? "Receiving..." : "Confirm Goods Receipt"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
