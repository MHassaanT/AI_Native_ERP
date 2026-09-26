"use client";

import { useEffect, useState } from "react";
import {
  CheckCircle2,
  ShieldAlert,
  Plus,
  RefreshCw,
  FileText,
  AlertCircle,
  Truck,
  ShoppingCart,
  ArrowRight,
  Sparkles,
  Layers,
  Check,
  Building2,
} from "lucide-react";
import { api } from "@/lib/api";

export default function AccountsPayablePage() {
  const [invoices, setInvoices] = useState<any[]>([]);
  const [purchaseOrders, setPurchaseOrders] = useState<any[]>([]);
  const [goodsReceipts, setGoodsReceipts] = useState<any[]>([]);
  const [suppliers, setSuppliers] = useState<any[]>([]);
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"invoices" | "pos" | "grns" | "suppliers">("invoices");

  const [matchingId, setMatchingId] = useState<string | null>(null);
  const [matchResult, setMatchResult] = useState<any | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [seeding, setSeeding] = useState(false);

  // Modal States
  const [showCreateInvoiceModal, setShowCreateInvoiceModal] = useState(false);
  const [newInvNumber, setNewInvNumber] = useState("");
  const [newSubtotal, setNewSubtotal] = useState("");
  const [selectedPoId, setSelectedPoId] = useState("");
  const [creatingInvoice, setCreatingInvoice] = useState(false);
  const [invoiceModalError, setInvoiceModalError] = useState<string | null>(null);

  const [showCreatePoModal, setShowCreatePoModal] = useState(false);
  const [newPoNumber, setNewPoNumber] = useState("");
  const [selectedSupplierId, setSelectedSupplierId] = useState("");
  const [selectedItemId, setSelectedItemId] = useState("");
  const [poQty, setPoQty] = useState("100");
  const [poUnitPrice, setPoUnitPrice] = useState("147.00");
  const [creatingPo, setCreatingPo] = useState(false);

  const [showCreateGrnModal, setShowCreateGrnModal] = useState(false);
  const [newGrnNumber, setNewGrnNumber] = useState("");
  const [selectedGrnPoId, setSelectedGrnPoId] = useState("");
  const [creatingGrn, setCreatingGrn] = useState(false);

  const [showCreateSupplierModal, setShowCreateSupplierModal] = useState(false);
  const [newSupplierCode, setNewSupplierCode] = useState("");
  const [newSupplierName, setNewSupplierName] = useState("");
  const [newSupplierTaxId, setNewSupplierTaxId] = useState("");
  const [newSupplierCurrency, setNewSupplierCurrency] = useState("USD");
  const [newSupplierTerms, setNewSupplierTerms] = useState("30");
  const [creatingSupplier, setCreatingSupplier] = useState(false);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [invs, pos, grns, sups, itms] = await Promise.all([
        api.getInvoices().catch(() => []),
        api.getPurchaseOrders().catch(() => []),
        api.getGoodsReceipts().catch(() => []),
        api.getSuppliers().catch(() => []),
        api.getItems().catch(() => []),
      ]);
      setInvoices(invs || []);
      setPurchaseOrders(pos || []);
      setGoodsReceipts(grns || []);
      setSuppliers(sups || []);
      setItems(itms || []);

      if (pos && pos.length > 0 && !selectedPoId) {
        setSelectedPoId(pos[0].po_id);
      }
      if (sups && sups.length > 0 && !selectedSupplierId) {
        setSelectedSupplierId(sups[0].supplier_id);
      }
      if (itms && itms.length > 0 && !selectedItemId) {
        setSelectedItemId(itms[0].item_id);
      }
    } catch (err: any) {
      setError(err.message || "Failed to load accounts payable records from database.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleMatch = async (invoiceId: string, humanApproved: boolean = false) => {
    setMatchingId(invoiceId);
    setError(null);
    setMatchResult(null);
    try {
      const result = await api.matchInvoice(invoiceId, humanApproved);
      setMatchResult(result);
      await loadData();
    } catch (err: any) {
      setError(err.message || "3-Way match evaluation failed.");
    } finally {
      setMatchingId(null);
    }
  };

  // 1-Click Provisioning of full P2P Lifecycle (Supplier -> Item -> PO -> GRN)
  const handleSeedSampleP2P = async () => {
    setSeeding(true);
    setError(null);
    setSuccessMsg(null);
    try {
      // 1. Ensure a supplier exists
      let currentSuppliers = suppliers;
      if (!currentSuppliers || currentSuppliers.length === 0) {
        const newSup = await api.createSupplier({
          supplier_code: "SUP-AERO-01",
          supplier_name: "Apex Aerospace Materials LLC",
          currency: "USD",
          payment_terms_days: 30,
        });
        currentSuppliers = [newSup];
      }
      const supplierId = currentSuppliers[0].supplier_id;

      // 2. Ensure an item exists
      let currentItems = items;
      if (!currentItems || currentItems.length === 0) {
        const newItm = await api.createItem({
          item_code: "RAW-TITANIUM-BILLET",
          item_name: "Grade 5 Titanium Billet (6Al-4V)",
          standard_rate: 147.0,
          stock_uom: "Kg",
          initial_qty: 0,
        });
        currentItems = [newItm];
      }
      const itemId = currentItems[0].item_id;

      // 3. Create Sample Purchase Order
      const today = new Date().toISOString().split("T")[0];
      const randomSuffix = Math.floor(1000 + Math.random() * 9000);
      const poNum = `PO-${new Date().getFullYear()}-${randomSuffix}`;
      const po = await api.createPurchaseOrder({
        po_number: poNum,
        supplier_id: supplierId,
        order_date: today,
        currency: "USD",
        items: [
          {
            item_id: itemId,
            quantity: 100,
            unit_price: 147.0,
          },
        ],
      });

      // 4. Create Sample Goods Receipt Note (GRN)
      const grnNum = `GRN-${new Date().getFullYear()}-${randomSuffix}`;
      await api.createGoodsReceipt({
        grn_number: grnNum,
        supplier_id: supplierId,
        po_id: po.po_id,
        receipt_date: today,
        items: [
          {
            item_id: itemId,
            quantity_received: 100,
            unit_price: 147.0,
          },
        ],
      });

      await loadData();
      setSelectedPoId(po.po_id);
      setNewInvNumber(`INV-APEX-${randomSuffix}`);
      setNewSubtotal("14700.00");
      setSuccessMsg(`Successfully provisioned ${poNum} and ${grnNum}! You can now register and match vendor invoices.`);
    } catch (err: any) {
      setError(err?.message || "Failed to seed sample P2P records.");
    } finally {
      setSeeding(false);
    }
  };

  const handleCreateInvoice = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedPoId) {
      setInvoiceModalError("Please select an active Purchase Order to match against.");
      return;
    }
    setCreatingInvoice(true);
    setInvoiceModalError(null);
    setError(null);
    try {
      const po = purchaseOrders.find((p) => p.po_id === selectedPoId);
      if (!po) throw new Error("Selected PO not found.");

      const matchingGrn = goodsReceipts.find((g) => g.po_id === selectedPoId);

      await api.createInvoice({
        invoice_number: newInvNumber.trim(),
        supplier_id: po.supplier_id,
        po_id: po.po_id,
        grn_id: matchingGrn ? matchingGrn.grn_id : null,
        invoice_date: new Date().toISOString().split("T")[0],
        subtotal: parseFloat(newSubtotal),
        tax_amount: 0,
      });

      setShowCreateInvoiceModal(false);
      setNewInvNumber("");
      setNewSubtotal("");
      setInvoiceModalError(null);
      setActiveTab("invoices");
      await loadData();
    } catch (err: any) {
      setInvoiceModalError(err.message || "Failed to create invoice.");
    } finally {
      setCreatingInvoice(false);
    }
  };

  const handleCreatePo = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedSupplierId || !selectedItemId) {
      setError("Please select both a supplier and an item for the purchase order.");
      return;
    }
    setCreatingPo(true);
    setError(null);
    try {
      const poNum = newPoNumber.trim() || `PO-${new Date().getFullYear()}-${Math.floor(1000 + Math.random() * 9000)}`;
      await api.createPurchaseOrder({
        po_number: poNum,
        supplier_id: selectedSupplierId,
        order_date: new Date().toISOString().split("T")[0],
        currency: "USD",
        items: [
          {
            item_id: selectedItemId,
            quantity: parseFloat(poQty),
            unit_price: parseFloat(poUnitPrice),
          },
        ],
      });

      setShowCreatePoModal(false);
      setNewPoNumber("");
      setActiveTab("pos");
      await loadData();
    } catch (err: any) {
      setError(err.message || "Failed to create purchase order.");
    } finally {
      setCreatingPo(false);
    }
  };

  const handleCreateGrn = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedGrnPoId) {
      setError("Please select a Purchase Order to receive.");
      return;
    }
    setCreatingGrn(true);
    setError(null);
    try {
      const po = purchaseOrders.find((p) => p.po_id === selectedGrnPoId);
      if (!po) throw new Error("Selected PO not found.");

      const grnNum = newGrnNumber.trim() || `GRN-${new Date().getFullYear()}-${Math.floor(1000 + Math.random() * 9000)}`;
      await api.createGoodsReceipt({
        grn_number: grnNum,
        supplier_id: po.supplier_id,
        po_id: po.po_id,
        receipt_date: new Date().toISOString().split("T")[0],
      });

      setShowCreateGrnModal(false);
      setNewGrnNumber("");
      setActiveTab("grns");
      await loadData();
    } catch (err: any) {
      setError(err.message || "Failed to record goods receipt.");
    } finally {
      setCreatingGrn(false);
    }
  };

  const handleCreateSupplier = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newSupplierCode.trim() || !newSupplierName.trim()) {
      setError("Supplier code and supplier name are required.");
      return;
    }
    setCreatingSupplier(true);
    setError(null);
    try {
      const created = await api.createSupplier({
        supplier_code: newSupplierCode.trim().toUpperCase(),
        supplier_name: newSupplierName.trim(),
        tax_id: newSupplierTaxId.trim() || null,
        currency: newSupplierCurrency || "USD",
        payment_terms_days: parseInt(newSupplierTerms, 10) || 30,
        otif_score: 100.0,
      });

      setShowCreateSupplierModal(false);
      setNewSupplierCode("");
      setNewSupplierName("");
      setNewSupplierTaxId("");
      setSuccessMsg(`Supplier "${created.supplier_name}" (${created.supplier_code}) registered successfully.`);
      setSelectedSupplierId(created.supplier_id);
      setActiveTab("suppliers");
      await loadData();
    } catch (err: any) {
      setError(err.message || "Failed to create supplier.");
    } finally {
      setCreatingSupplier(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between border-b border-cream-300 pb-5">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-cream-900 flex items-center gap-2">
            <span>Accounts Payable &bull; Automated 3-Way Matching</span>
            <span className="inline-flex items-center gap-1 rounded bg-cream-200 border border-cream-300 px-2 py-0.5 text-[11px] font-mono font-medium text-cream-800">
              P2P Pipeline
            </span>
          </h1>
          <p className="text-xs text-cream-700 mt-1">
            Tripartite tolerance verification across Purchase Orders, Goods Receipt Notes (GRN), and Supplier Invoices.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={loadData}
            disabled={loading}
            className="flex items-center gap-1.5 rounded-md border border-cream-300 bg-cream-100 px-3 py-1.5 text-xs font-medium text-cream-800 hover:bg-cream-200 transition-colors"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
            <span>Refresh</span>
          </button>
          <button
            onClick={handleSeedSampleP2P}
            disabled={seeding}
            className="flex items-center gap-1.5 rounded-md border border-sage-400 bg-sage-50 px-3 py-1.5 text-xs font-medium text-sage-900 hover:bg-sage-100 transition-colors disabled:opacity-50"
            title="Creates a sample Supplier, PO (100 units @ $147), and GRN to test matching immediately"
          >
            <Sparkles className="h-3.5 w-3.5 text-sage-700" />
            <span>{seeding ? "Provisioning..." : "Seed Sample P2P Flow"}</span>
          </button>
          <button
            onClick={() => {
              setNewSupplierCode(`SUP-${Math.floor(100 + Math.random() * 900)}`);
              setNewSupplierName("");
              setNewSupplierTaxId("");
              setShowCreateSupplierModal(true);
            }}
            className="flex items-center gap-1.5 rounded-md border border-cream-300 bg-cream-100 px-3 py-1.5 text-xs font-medium text-cream-900 hover:bg-cream-200 transition-colors"
          >
            <Plus className="h-3.5 w-3.5" />
            <span>New Supplier</span>
          </button>
          <button
            onClick={() => {
              setNewPoNumber(`PO-${new Date().getFullYear()}-${Math.floor(1000 + Math.random() * 9000)}`);
              setShowCreatePoModal(true);
            }}
            className="flex items-center gap-1.5 rounded-md border border-cream-300 bg-cream-100 px-3 py-1.5 text-xs font-medium text-cream-900 hover:bg-cream-200 transition-colors"
          >
            <Plus className="h-3.5 w-3.5" />
            <span>Create PO</span>
          </button>
          <button
            onClick={() => {
              setInvoiceModalError(null);
              setNewInvNumber(`INV-${new Date().getFullYear()}-${Math.floor(1000 + Math.random() * 9000)}`);
              setShowCreateInvoiceModal(true);
            }}
            className="flex items-center gap-1.5 rounded-md border border-cream-400 bg-cream-900 px-3 py-1.5 text-xs font-medium text-cream-50 hover:bg-cream-800 transition-colors"
          >
            <Plus className="h-3.5 w-3.5" />
            <span>New Vendor Invoice</span>
          </button>
        </div>
      </div>

      {/* Notifications */}
      {error && (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-terracotta-50 border border-terracotta-500/30 text-terracotta-800 text-xs">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {successMsg && (
        <div className="flex items-center justify-between p-3 rounded-lg bg-sage-50 border border-sage-500/30 text-sage-900 text-xs">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 shrink-0 text-sage-700" />
            <span>{successMsg}</span>
          </div>
          <button onClick={() => setSuccessMsg(null)} className="text-sage-700 font-bold hover:underline">
            &times;
          </button>
        </div>
      )}

      {/* Triad Flow Explainer Card */}
      <div className="rounded-xl border border-cream-300 bg-cream-100 p-4">
        <div className="flex items-center justify-between pb-3 border-b border-cream-200">
          <div className="flex items-center gap-2">
            <Layers className="h-4 w-4 text-cream-800" />
            <h2 className="text-xs font-semibold text-cream-900 uppercase tracking-wider">
              Procure-to-Pay (P2P) Tripartite Verification Architecture
            </h2>
          </div>
          <span className="text-[11px] font-mono text-cream-600">Invariant: Tolerance &le; 1.0% Price, 0% Qty</span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mt-3 text-xs">
          <div className="p-3 rounded-lg bg-cream-50 border border-cream-200 space-y-1">
            <div className="flex items-center justify-between text-cream-600 text-[11px]">
              <span className="font-semibold text-cream-900">1. Purchase Order</span>
              <ShoppingCart className="h-3.5 w-3.5 text-cream-700" />
            </div>
            <p className="text-[11px] text-cream-700">Contracted quantities and agreed unit rate with supplier.</p>
            <div className="pt-1 font-mono text-[10px] text-cream-600">{purchaseOrders.length} POs on record</div>
          </div>

          <div className="p-3 rounded-lg bg-cream-50 border border-cream-200 space-y-1">
            <div className="flex items-center justify-between text-cream-600 text-[11px]">
              <span className="font-semibold text-cream-900">2. Goods Receipt (GRN)</span>
              <Truck className="h-3.5 w-3.5 text-cream-700" />
            </div>
            <p className="text-[11px] text-cream-700">Dock receipt proving physical delivery into warehouse inventory.</p>
            <div className="pt-1 font-mono text-[10px] text-cream-600">{goodsReceipts.length} GRNs logged</div>
          </div>

          <div className="p-3 rounded-lg bg-cream-50 border border-cream-200 space-y-1">
            <div className="flex items-center justify-between text-cream-600 text-[11px]">
              <span className="font-semibold text-cream-900">3. Vendor Invoice</span>
              <FileText className="h-3.5 w-3.5 text-cream-700" />
            </div>
            <p className="text-[11px] text-cream-700">Billing statement submitted by vendor requesting cash settlement.</p>
            <div className="pt-1 font-mono text-[10px] text-cream-600">{invoices.length} invoices registered</div>
          </div>

          <div className="p-3 rounded-lg bg-sage-50 border border-sage-300 space-y-1">
            <div className="flex items-center justify-between text-sage-800 text-[11px]">
              <span className="font-bold text-sage-900">4. 3-Way Engine</span>
              <CheckCircle2 className="h-3.5 w-3.5 text-sage-700" />
            </div>
            <p className="text-[11px] text-sage-800">
              Tripartite reconciliation. On match: posts GL <code className="font-mono text-[10px]">Dr 1300 / Cr 2100</code>.
            </p>
            <div className="pt-1 font-mono text-[10px] text-sage-700">Autonomous Ledger Engine</div>
          </div>
        </div>
      </div>

      {/* Match Result Banner */}
      {matchResult && (
        <div
          className={`rounded-lg border p-4 text-xs space-y-2 ${
            matchResult.matching_status === "MATCHED"
              ? "border-sage-500/30 bg-sage-50 text-sage-900"
              : matchResult.matching_status === "STAGED"
              ? "border-amber-500/40 bg-amber-50 text-amber-950"
              : "border-terracotta-500/30 bg-terracotta-50 text-terracotta-900"
          }`}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5 font-semibold text-sm">
              {matchResult.matching_status === "MATCHED" ? (
                <CheckCircle2 className="h-5 w-5 text-sage-700" />
              ) : matchResult.matching_status === "STAGED" ? (
                <ShieldAlert className="h-5 w-5 text-amber-700" />
              ) : (
                <ShieldAlert className="h-5 w-5 text-terracotta-700" />
              )}
              <span>
                Invoice {matchResult.invoice_number}: {matchResult.matching_status === "STAGED" ? "STAGED (APPROVAL REQUIRED)" : matchResult.matching_status}
              </span>
            </div>
            <span className="font-mono text-[11px] px-2.5 py-0.5 rounded bg-cream-100 border border-cream-300 font-semibold text-cream-800">
              Total Variance: {matchResult.tolerance_summary?.overall_variance_percentage || "0.00"}%
            </span>
          </div>

          {matchResult.tolerance_summary && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-[11px] font-mono pt-1">
              <div>
                Qty Variance:{" "}
                <span className="font-bold">
                  {matchResult.tolerance_summary.quantity_variance_percentage ?? "0.00"}%
                </span>
              </div>
              <div>
                Price Variance:{" "}
                <span className="font-bold">
                  {matchResult.tolerance_summary.price_variance_percentage ?? "0.00"}%
                </span>
              </div>
              <div>
                Threshold: <span className="font-bold">&le; 1.00%</span>
              </div>
              <div>
                Outcome:{" "}
                <span
                  className={
                    matchResult.matching_status === "MATCHED"
                      ? "text-sage-700 font-bold"
                      : matchResult.matching_status === "STAGED"
                      ? "text-amber-800 font-bold"
                      : "text-terracotta-700 font-bold"
                  }
                >
                  {matchResult.matching_status === "MATCHED"
                    ? "PASSED TOLERANCE"
                    : matchResult.matching_status === "STAGED"
                    ? "PASSED TOLERANCE (STAGED)"
                    : "BLOCKED FOR DISPUTE"}
                </span>
              </div>
            </div>
          )}

          {matchResult.matching_status === "STAGED" && (
            <div className="bg-white/90 p-3.5 rounded border border-amber-300 text-[11px] font-mono text-amber-950 space-y-2">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                <div className="font-bold text-xs flex items-center gap-1.5 text-amber-900">
                  <ShieldAlert className="h-4 w-4 text-amber-700" />
                  <span>Tier 3 Financial Ceiling Exceeded (&gt; $25,000.00)</span>
                </div>
                <button
                  type="button"
                  onClick={() => handleMatch(matchResult.invoice_id, true)}
                  disabled={matchingId === matchResult.invoice_id}
                  className="rounded bg-amber-600 hover:bg-amber-700 text-white font-sans text-xs font-semibold px-3 py-1.5 shadow-xs transition-colors disabled:opacity-50 flex items-center gap-1.5 justify-center"
                >
                  <CheckCircle2 className="h-3.5 w-3.5" />
                  <span>{matchingId === matchResult.invoice_id ? "Authorizing..." : "Authorize & Post to GL Now"}</span>
                </button>
              </div>
              <p>&bull; 3-Way Reconciliation: Quantities and unit pricing are 100% compliant with Purchase Order and GRN.</p>
              <p>&bull; Financial Governance: Per statutory ledger ceilings, transactions exceeding $25,000.00 require human supervisor sign-off before General Ledger commitment.</p>
            </div>
          )}

          {matchResult.dispute_notice && (
            <div className="bg-white/80 p-3 rounded border border-terracotta-300 text-[11px] font-mono text-terracotta-900 space-y-1">
              <div className="font-bold">Vendor Dispute Notice Generated:</div>
              <p>
                &bull; Reason:{" "}
                {matchResult.dispute_notice.dispute_reason ||
                  (matchResult.dispute_notice.discrepancy_details && matchResult.dispute_notice.discrepancy_details.join("; ")) ||
                  (matchResult.tolerance_summary?.discrepancies && matchResult.tolerance_summary.discrepancies.join("; ")) ||
                  "Variance exceeded allowable tolerance threshold"}
              </p>
              <p>
                &bull; Recommended Action:{" "}
                {matchResult.dispute_notice.action_recommended ||
                  matchResult.dispute_notice.resolution_instructions ||
                  "Record Goods Receipt Note (GRN) or resolve unit pricing discrepancy with vendor."}
              </p>
              <p className="text-[10px] text-cream-600 mt-1 italic">
                General Ledger posting held to prevent unauthorized cash leakage.
              </p>
            </div>
          )}

          {matchResult.ledger_result && (
            <div className="bg-white/80 p-3 rounded border border-sage-300 text-[11px] font-mono text-sage-900 space-y-1">
              <div className="font-bold">General Ledger Automated Posting Committed:</div>
              <p>&bull; Debit: <code className="bg-cream-100 px-1 py-0.5 rounded">1300-RAW-MATERIALS</code> (Inventory Asset)</p>
              <p>&bull; Credit: <code className="bg-cream-100 px-1 py-0.5 rounded">2100-AP-VENDORS</code> (Trade Payables)</p>
              <p>&bull; Transaction Ref: TXN-{matchResult.ledger_result.transaction_id.slice(0, 8)}</p>
            </div>
          )}
        </div>
      )}

      {/* Navigation Tabs */}
      <div className="flex border-b border-cream-300 text-xs font-medium text-cream-700 gap-6">
        <button
          onClick={() => setActiveTab("invoices")}
          className={`pb-3 flex items-center gap-2 border-b-2 transition-colors ${
            activeTab === "invoices"
              ? "border-cream-900 text-cream-900 font-semibold"
              : "border-transparent hover:text-cream-900"
          }`}
        >
          <FileText className="h-4 w-4" />
          <span>Supplier Invoices ({invoices.length})</span>
        </button>
        <button
          onClick={() => setActiveTab("pos")}
          className={`pb-3 flex items-center gap-2 border-b-2 transition-colors ${
            activeTab === "pos"
              ? "border-cream-900 text-cream-900 font-semibold"
              : "border-transparent hover:text-cream-900"
          }`}
        >
          <ShoppingCart className="h-4 w-4" />
          <span>Purchase Orders ({purchaseOrders.length})</span>
        </button>
        <button
          onClick={() => setActiveTab("grns")}
          className={`pb-3 flex items-center gap-2 border-b-2 transition-colors ${
            activeTab === "grns"
              ? "border-cream-900 text-cream-900 font-semibold"
              : "border-transparent hover:text-cream-900"
          }`}
        >
          <Truck className="h-4 w-4" />
          <span>Goods Receipts ({goodsReceipts.length})</span>
        </button>
        <button
          onClick={() => setActiveTab("suppliers")}
          className={`pb-3 flex items-center gap-2 border-b-2 transition-colors ${
            activeTab === "suppliers"
              ? "border-cream-900 text-cream-900 font-semibold"
              : "border-transparent hover:text-cream-900"
          }`}
        >
          <Building2 className="h-4 w-4" />
          <span>Suppliers ({suppliers.length})</span>
        </button>
      </div>

      {/* Tab 1: Supplier Invoices */}
      {activeTab === "invoices" && (
        <div className="space-y-4">
          {invoices.length === 0 ? (
            <div className="rounded-xl border border-cream-300 bg-cream-100 p-8 text-center space-y-3">
              <FileText className="h-8 w-8 text-cream-400 mx-auto" />
              <div className="text-xs text-cream-800 font-medium">No supplier invoices found in database</div>
              <p className="text-[11px] text-cream-600 max-w-md mx-auto">
                {purchaseOrders.length === 0
                  ? "To run 3-Way Matching, first seed or create a Purchase Order (PO). Invoices must link to an authorized PO."
                  : "Active Purchase Orders are available! Create an invoice to evaluate tripartite matching."}
              </p>
              <div className="flex justify-center gap-2 pt-2">
                {purchaseOrders.length === 0 && (
                  <button
                    onClick={handleSeedSampleP2P}
                    disabled={seeding}
                    className="inline-flex items-center gap-1.5 rounded-md border border-sage-500 bg-sage-50 px-3 py-1.5 text-xs font-medium text-sage-900 hover:bg-sage-100"
                  >
                    <Sparkles className="h-3.5 w-3.5 text-sage-700" />
                    <span>{seeding ? "Seeding..." : "Seed Sample P2P Flow"}</span>
                  </button>
                )}
                <button
                  onClick={() => {
                    setInvoiceModalError(null);
                    setNewInvNumber(`INV-${new Date().getFullYear()}-${Math.floor(1000 + Math.random() * 9000)}`);
                    setShowCreateInvoiceModal(true);
                  }}
                  className="inline-flex items-center gap-1.5 rounded-md border border-cream-400 bg-cream-900 px-3 py-1.5 text-xs font-medium text-cream-50 hover:bg-cream-800"
                >
                  <Plus className="h-3.5 w-3.5" />
                  <span>Create First Invoice</span>
                </button>
              </div>
            </div>
          ) : (
            <div className="rounded-xl border border-cream-300 bg-cream-100 overflow-hidden shadow-xs">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-cream-300 bg-cream-200/60 text-cream-800 font-medium text-[11px]">
                    <th className="py-2.5 px-4">Invoice #</th>
                    <th className="py-2.5 px-4">Date</th>
                    <th className="py-2.5 px-4">Amount</th>
                    <th className="py-2.5 px-4">Linked PO</th>
                    <th className="py-2.5 px-4">Match Status</th>
                    <th className="py-2.5 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-cream-200">
                  {invoices.map((inv) => (
                    <tr key={inv.invoice_id} className="hover:bg-cream-50/50 transition-colors">
                      <td className="py-3 px-4 font-mono font-medium text-cream-900">
                        <div>{inv.invoice_number}</div>
                        {inv.matching_status === "DISPUTED" && inv.dispute_reason && (
                          <div className="text-[10px] text-terracotta-700 font-sans mt-0.5 max-w-xs truncate" title={inv.dispute_reason}>
                            &bull; {inv.dispute_reason}
                          </div>
                        )}
                        {inv.matching_status === "STAGED" && (
                          <div className="text-[10px] text-amber-800 font-sans mt-0.5 max-w-xs truncate" title={inv.dispute_reason || "Amount > $25,000: Human authorization required"}>
                            &bull; {inv.dispute_reason || "Amount > $25,000: Human authorization required"}
                          </div>
                        )}
                      </td>
                      <td className="py-3 px-4 text-cream-700">{inv.invoice_date}</td>
                      <td className="py-3 px-4 font-mono font-bold text-cream-900">
                        ${parseFloat(inv.total_amount).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </td>
                      <td className="py-3 px-4 text-[11px] font-mono text-cream-600">
                        {inv.po_id ? `PO: ${inv.po_id.slice(0, 8)}...` : "Direct Bill"}
                      </td>
                      <td className="py-3 px-4">
                        <span
                          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold font-mono ${
                            inv.matching_status === "MATCHED"
                              ? "bg-sage-100 text-sage-800 border border-sage-500/30"
                              : inv.matching_status === "STAGED"
                              ? "bg-amber-100 text-amber-900 border border-amber-500/40"
                              : inv.matching_status === "DISPUTED"
                              ? "bg-terracotta-100 text-terracotta-800 border border-terracotta-500/30"
                              : "bg-cream-200 text-cream-800 border border-cream-300"
                          }`}
                        >
                          {inv.matching_status === "STAGED" ? "STAGED (APPROVAL REQ)" : inv.matching_status}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-right">
                        {inv.matching_status === "UNMATCHED" ? (
                          <button
                            onClick={() => handleMatch(inv.invoice_id)}
                            disabled={matchingId === inv.invoice_id}
                            className="rounded border border-cream-400 bg-cream-900 px-2.5 py-1 text-[11px] font-medium text-cream-50 hover:bg-cream-800 transition-colors disabled:opacity-50"
                          >
                            {matchingId === inv.invoice_id ? "Evaluating Match..." : "Execute 3-Way Match"}
                          </button>
                        ) : inv.matching_status === "STAGED" ? (
                          <button
                            onClick={() => handleMatch(inv.invoice_id, true)}
                            disabled={matchingId === inv.invoice_id}
                            className="inline-flex items-center gap-1.5 rounded border border-amber-500 bg-amber-50 px-2.5 py-1 text-[11px] font-semibold text-amber-900 hover:bg-amber-100 transition-colors disabled:opacity-50 shadow-2xs"
                            title="Tolerances matched 100%. Authorize transaction (> $25,000) to commit to General Ledger."
                          >
                            <CheckCircle2 className={`h-3 w-3 text-amber-700 ${matchingId === inv.invoice_id ? "animate-spin" : ""}`} />
                            <span>{matchingId === inv.invoice_id ? "Posting..." : "Authorize & Post to GL"}</span>
                          </button>
                        ) : inv.matching_status === "DISPUTED" ? (
                          <button
                            onClick={() => handleMatch(inv.invoice_id)}
                            disabled={matchingId === inv.invoice_id}
                            className="inline-flex items-center gap-1.5 rounded border border-terracotta-400 bg-terracotta-50 px-2.5 py-1 text-[11px] font-medium text-terracotta-900 hover:bg-terracotta-100 transition-colors disabled:opacity-50 shadow-2xs"
                            title="Re-run 3-way match after recording GRN or resolving dispute"
                          >
                            <RefreshCw className={`h-3 w-3 text-terracotta-700 ${matchingId === inv.invoice_id ? "animate-spin" : ""}`} />
                            <span>{matchingId === inv.invoice_id ? "Re-evaluating..." : "Re-evaluate Match"}</span>
                          </button>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-[11px] text-sage-800 font-mono font-medium">
                            <CheckCircle2 className="h-3.5 w-3.5 text-sage-600" />
                            <span>Matched &amp; Posted</span>
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Tab 2: Purchase Orders */}
      {activeTab === "pos" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-xs text-cream-700">Contractual purchase commitments approved by procurement.</p>
            <button
              onClick={() => {
                setNewPoNumber(`PO-${new Date().getFullYear()}-${Math.floor(1000 + Math.random() * 9000)}`);
                setShowCreatePoModal(true);
              }}
              className="flex items-center gap-1.5 rounded-md border border-cream-400 bg-cream-900 px-3 py-1.5 text-xs font-medium text-cream-50 hover:bg-cream-800"
            >
              <Plus className="h-3.5 w-3.5" />
              <span>Create Purchase Order</span>
            </button>
          </div>

          {purchaseOrders.length === 0 ? (
            <div className="rounded-xl border border-cream-300 bg-cream-100 p-8 text-center space-y-3">
              <ShoppingCart className="h-8 w-8 text-cream-400 mx-auto" />
              <div className="text-xs text-cream-800 font-medium">No purchase orders found in database</div>
              <p className="text-[11px] text-cream-600 max-w-sm mx-auto">
                Generate a sample purchase order or create a new one to establish baseline procurement terms.
              </p>
              <button
                onClick={handleSeedSampleP2P}
                disabled={seeding}
                className="inline-flex items-center gap-1.5 rounded-md border border-sage-500 bg-sage-50 px-3 py-1.5 text-xs font-medium text-sage-900 hover:bg-sage-100"
              >
                <Sparkles className="h-3.5 w-3.5 text-sage-700" />
                <span>{seeding ? "Provisioning..." : "Seed Sample P2P Flow"}</span>
              </button>
            </div>
          ) : (
            <div className="rounded-xl border border-cream-300 bg-cream-100 overflow-hidden shadow-xs">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-cream-300 bg-cream-200/60 text-cream-800 font-medium text-[11px]">
                    <th className="py-2.5 px-4">PO Number</th>
                    <th className="py-2.5 px-4">Order Date</th>
                    <th className="py-2.5 px-4">Total Amount</th>
                    <th className="py-2.5 px-4">Status</th>
                    <th className="py-2.5 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-cream-200">
                  {purchaseOrders.map((po) => (
                    <tr key={po.po_id} className="hover:bg-cream-50/50 transition-colors">
                      <td className="py-3 px-4 font-mono font-medium text-cream-900">{po.po_number}</td>
                      <td className="py-3 px-4 text-cream-700">{po.order_date}</td>
                      <td className="py-3 px-4 font-mono font-bold text-cream-900">
                        ${parseFloat(po.total_amount).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </td>
                      <td className="py-3 px-4">
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold font-mono bg-sage-100 text-sage-800 border border-sage-500/30">
                          {po.status}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-right space-x-2">
                        <button
                          onClick={() => {
                            setSelectedGrnPoId(po.po_id);
                            setNewGrnNumber(`GRN-${new Date().getFullYear()}-${Math.floor(1000 + Math.random() * 9000)}`);
                            setShowCreateGrnModal(true);
                          }}
                          className="text-[11px] font-medium text-cream-800 hover:text-cream-900 underline"
                        >
                          Receive (GRN)
                        </button>
                        <button
                          onClick={() => {
                            setSelectedPoId(po.po_id);
                            setNewInvNumber(`INV-${po.po_number.replace("PO-", "")}`);
                            setNewSubtotal(parseFloat(po.total_amount).toFixed(2));
                            setShowCreateInvoiceModal(true);
                          }}
                          className="text-[11px] font-medium text-cream-900 font-semibold underline"
                        >
                          Create Invoice
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Tab 3: Goods Receipts */}
      {activeTab === "grns" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-xs text-cream-700">Dock inspection receipts confirming physical receipt into warehouse stock.</p>
          </div>

          {goodsReceipts.length === 0 ? (
            <div className="rounded-xl border border-cream-300 bg-cream-100 p-8 text-center space-y-3">
              <Truck className="h-8 w-8 text-cream-400 mx-auto" />
              <div className="text-xs text-cream-800 font-medium">No goods receipt notes logged in database</div>
              <p className="text-[11px] text-cream-600 max-w-sm mx-auto">
                Goods receipts prove physical receipt. Link a receipt to a Purchase Order to verify shipments.
              </p>
            </div>
          ) : (
            <div className="rounded-xl border border-cream-300 bg-cream-100 overflow-hidden shadow-xs">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-cream-300 bg-cream-200/60 text-cream-800 font-medium text-[11px]">
                    <th className="py-2.5 px-4">GRN Number</th>
                    <th className="py-2.5 px-4">Receipt Date</th>
                    <th className="py-2.5 px-4">Linked PO</th>
                    <th className="py-2.5 px-4">Warehouse Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-cream-200">
                  {goodsReceipts.map((grn) => (
                    <tr key={grn.grn_id} className="hover:bg-cream-50/50 transition-colors">
                      <td className="py-3 px-4 font-mono font-medium text-cream-900">{grn.grn_number}</td>
                      <td className="py-3 px-4 text-cream-700">{grn.receipt_date}</td>
                      <td className="py-3 px-4 font-mono text-[11px] text-cream-600">
                        {grn.po_id ? `PO: ${grn.po_id.slice(0, 8)}...` : "Direct Receipt"}
                      </td>
                      <td className="py-3 px-4">
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold font-mono bg-sage-100 text-sage-800 border border-sage-500/30">
                          {grn.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Tab 4: Suppliers Directory */}
      {activeTab === "suppliers" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-xs text-cream-700">Vendor master directory with automated on-time in-full (OTIF) scoring.</p>
            <button
              onClick={() => {
                setNewSupplierCode(`SUP-${Math.floor(100 + Math.random() * 900)}`);
                setNewSupplierName("");
                setNewSupplierTaxId("");
                setShowCreateSupplierModal(true);
              }}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-cream-900 text-cream-50 text-xs font-medium hover:bg-cream-800 transition-colors"
            >
              <Plus className="h-3.5 w-3.5" />
              <span>Add Supplier</span>
            </button>
          </div>

          {suppliers.length === 0 ? (
            <div className="rounded-xl border border-cream-300 bg-cream-100 p-8 text-center space-y-3">
              <Building2 className="h-8 w-8 text-cream-400 mx-auto" />
              <div className="text-xs text-cream-800 font-medium">No suppliers registered in master directory</div>
              <p className="text-[11px] text-cream-600 max-w-sm mx-auto">
                Suppliers allow you to issue Purchase Orders, receive dock shipments (GRN), and verify vendor invoices.
              </p>
              <button
                onClick={() => {
                  setNewSupplierCode(`SUP-${Math.floor(100 + Math.random() * 900)}`);
                  setNewSupplierName("");
                  setNewSupplierTaxId("");
                  setShowCreateSupplierModal(true);
                }}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-cream-900 text-cream-50 text-xs font-medium hover:bg-cream-800 transition-colors"
              >
                <Plus className="h-3.5 w-3.5" />
                <span>Register First Supplier</span>
              </button>
            </div>
          ) : (
            <div className="rounded-xl border border-cream-300 bg-cream-100 overflow-hidden shadow-xs">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-cream-300 bg-cream-200/60 text-cream-800 font-medium text-[11px]">
                    <th className="py-2.5 px-4">Supplier Code</th>
                    <th className="py-2.5 px-4">Supplier Name</th>
                    <th className="py-2.5 px-4">Tax / VAT ID</th>
                    <th className="py-2.5 px-4">Currency</th>
                    <th className="py-2.5 px-4">Payment Terms</th>
                    <th className="py-2.5 px-4">OTIF Score</th>
                    <th className="py-2.5 px-4">Status</th>
                    <th className="py-2.5 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-cream-200">
                  {suppliers.map((s) => (
                    <tr key={s.supplier_id} className="hover:bg-cream-50/50 transition-colors">
                      <td className="py-3 px-4 font-mono font-medium text-cream-900">{s.supplier_code}</td>
                      <td className="py-3 px-4 font-medium text-cream-900">{s.supplier_name}</td>
                      <td className="py-3 px-4 text-cream-600 font-mono text-[11px]">{s.tax_id || "—"}</td>
                      <td className="py-3 px-4 text-cream-700 font-mono">{s.currency}</td>
                      <td className="py-3 px-4 text-cream-700">{s.payment_terms_days} days</td>
                      <td className="py-3 px-4 font-mono">
                        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-sage-100 text-sage-800 border border-sage-500/30">
                          {parseFloat(s.otif_score).toFixed(1)}%
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold font-mono bg-cream-200 text-cream-800">
                          {s.is_active ? "Active" : "Inactive"}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-right">
                        <button
                          onClick={() => {
                            setSelectedSupplierId(s.supplier_id);
                            setNewPoNumber(`PO-${new Date().getFullYear()}-${Math.floor(1000 + Math.random() * 9000)}`);
                            setShowCreatePoModal(true);
                          }}
                          className="px-2.5 py-1 text-[11px] font-medium rounded-md border border-cream-300 bg-cream-50 text-cream-900 hover:bg-cream-200 transition-colors"
                        >
                          + Create PO
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Modal 1: Create Vendor Invoice */}
      {showCreateInvoiceModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="w-full max-w-md rounded-xl border border-cream-300 bg-cream-100 p-6 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b border-cream-300 pb-3">
              <h3 className="font-semibold text-sm text-cream-900">Register Vendor Invoice</h3>
              <button
                onClick={() => setShowCreateInvoiceModal(false)}
                className="text-cream-600 hover:text-cream-900 text-sm font-semibold"
              >
                &times;
              </button>
            </div>

            {purchaseOrders.length === 0 ? (
              <div className="rounded-lg border border-amber-300 bg-amber-50 p-4 space-y-3 text-xs text-amber-900">
                <div className="font-semibold flex items-center gap-2">
                  <AlertCircle className="h-4 w-4 text-amber-700" />
                  <span>No Purchase Orders (PO) in Database</span>
                </div>
                <p className="text-[11px] leading-relaxed">
                  In enterprise accounting, a vendor invoice cannot be entered without an authorized Purchase Order (PO).
                  Click below to generate a sample PO and Goods Receipt Note (GRN) in one click!
                </p>
                <button
                  type="button"
                  onClick={async () => {
                    await handleSeedSampleP2P();
                  }}
                  disabled={seeding}
                  className="w-full flex items-center justify-center gap-2 rounded-lg border border-sage-500 bg-sage-600 px-3 py-2 text-xs font-semibold text-white hover:bg-sage-700 disabled:opacity-50"
                >
                  <Sparkles className="h-3.5 w-3.5" />
                  <span>{seeding ? "Provisioning..." : "Provision Sample PO & GRN Now"}</span>
                </button>
              </div>
            ) : (
              <form onSubmit={handleCreateInvoice} className="space-y-4 text-xs">
                {invoiceModalError && (
                  <div className="flex items-start gap-2 p-3 rounded-lg bg-terracotta-50 border border-terracotta-300 text-terracotta-900 text-xs">
                    <AlertCircle className="h-4 w-4 shrink-0 text-terracotta-700 mt-0.5" />
                    <div className="space-y-0.5">
                      <div className="font-semibold text-terracotta-900">Registration Error</div>
                      <p className="text-[11px] leading-relaxed text-terracotta-800">{invoiceModalError}</p>
                    </div>
                  </div>
                )}
                <div>
                  <label className="block font-medium text-cream-900 mb-1">Invoice Reference #</label>
                  <input
                    type="text"
                    required
                    value={newInvNumber}
                    onChange={(e) => setNewInvNumber(e.target.value)}
                    placeholder="e.g. INV-2026-9901"
                    className="w-full rounded-lg border border-cream-300 bg-cream-50 px-3 py-1.5 text-cream-900 font-mono"
                  />
                </div>

                <div>
                  <label className="block font-medium text-cream-900 mb-1">Purchase Order (PO to Match)</label>
                  <select
                    required
                    value={selectedPoId}
                    onChange={(e) => {
                      setSelectedPoId(e.target.value);
                      const po = purchaseOrders.find((p) => p.po_id === e.target.value);
                      if (po) setNewSubtotal(parseFloat(po.total_amount).toFixed(2));
                    }}
                    className="w-full rounded-lg border border-cream-300 bg-cream-50 px-3 py-1.5 text-cream-900 font-mono"
                  >
                    <option value="">Select PO to match...</option>
                    {purchaseOrders.map((p) => (
                      <option key={p.po_id} value={p.po_id}>
                        {p.po_number} (${parseFloat(p.total_amount).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })})
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block font-medium text-cream-900 mb-1">Billed Invoice Amount ($)</label>
                  <input
                    type="number"
                    step="0.01"
                    required
                    value={newSubtotal}
                    onChange={(e) => setNewSubtotal(e.target.value)}
                    placeholder="e.g. 14700.00"
                    className="w-full rounded-lg border border-cream-300 bg-cream-50 px-3 py-1.5 text-cream-900 font-mono"
                  />
                </div>

                {/* Preset Test Scenarios */}
                <div className="pt-2 border-t border-cream-200">
                  <span className="text-[11px] text-cream-600 block mb-1.5">3-Way Test Presets:</span>
                  <div className="grid grid-cols-2 gap-2 text-[10px]">
                    <button
                      type="button"
                      onClick={() => {
                        const po = purchaseOrders.find((p) => p.po_id === selectedPoId) || purchaseOrders[0];
                        if (po) setNewSubtotal(parseFloat(po.total_amount).toFixed(2));
                      }}
                      className="px-2 py-1 rounded bg-cream-200 hover:bg-cream-300 text-cream-900 font-mono text-left"
                    >
                      &bull; Exact Match (0.0% variance)
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        const po = purchaseOrders.find((p) => p.po_id === selectedPoId) || purchaseOrders[0];
                        if (po) setNewSubtotal((parseFloat(po.total_amount) * 1.15).toFixed(2));
                      }}
                      className="px-2 py-1 rounded bg-terracotta-100 hover:bg-terracotta-200 text-terracotta-800 font-mono text-left"
                    >
                      &bull; 15% Price Hike (Dispute)
                    </button>
                  </div>
                </div>

                <div className="flex justify-end gap-2 pt-3 border-t border-cream-300">
                  <button
                    type="button"
                    onClick={() => setShowCreateInvoiceModal(false)}
                    className="rounded-lg border border-cream-300 bg-cream-200 px-3 py-1.5 text-cream-800"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={creatingInvoice}
                    className="rounded-lg border border-cream-400 bg-cream-900 px-4 py-1.5 font-medium text-cream-50 hover:bg-cream-800 disabled:opacity-50"
                  >
                    {creatingInvoice ? "Saving..." : "Register Invoice"}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}

      {/* Modal 2: Create Purchase Order */}
      {showCreatePoModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="w-full max-w-md rounded-xl border border-cream-300 bg-cream-100 p-6 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b border-cream-300 pb-3">
              <h3 className="font-semibold text-sm text-cream-900">Issue Purchase Order (PO)</h3>
              <button onClick={() => setShowCreatePoModal(false)} className="text-cream-600 hover:text-cream-900">&times;</button>
            </div>

            <form onSubmit={handleCreatePo} className="space-y-3 text-xs">
              <div>
                <label className="block font-medium text-cream-900 mb-1">PO Number</label>
                <input
                  type="text"
                  required
                  value={newPoNumber}
                  onChange={(e) => setNewPoNumber(e.target.value)}
                  className="w-full rounded border border-cream-300 bg-cream-50 px-3 py-1.5 font-mono text-cream-900"
                />
              </div>

              <div>
                <label className="block font-medium text-cream-900 mb-1">Supplier</label>
                {suppliers.length > 0 ? (
                  <select
                    required
                    value={selectedSupplierId}
                    onChange={(e) => setSelectedSupplierId(e.target.value)}
                    className="w-full rounded border border-cream-300 bg-cream-50 px-3 py-1.5 text-cream-900"
                  >
                    {suppliers.map((s) => (
                      <option key={s.supplier_id} value={s.supplier_id}>
                        {s.supplier_name} ({s.supplier_code})
                      </option>
                    ))}
                  </select>
                ) : (
                  <div className="flex items-center justify-between p-2 rounded bg-terracotta-50 border border-terracotta-200 text-[11px] text-terracotta-800">
                    <span>No suppliers registered.</span>
                    <button
                      type="button"
                      onClick={() => {
                        setShowCreatePoModal(false);
                        setNewSupplierCode(`SUP-${Math.floor(100 + Math.random() * 900)}`);
                        setNewSupplierName("");
                        setNewSupplierTaxId("");
                        setShowCreateSupplierModal(true);
                      }}
                      className="text-cream-950 font-semibold underline ml-2 hover:text-cream-800"
                    >
                      + Add Supplier Now
                    </button>
                  </div>
                )}
              </div>

              <div>
                <label className="block font-medium text-cream-900 mb-1">Raw Material Component</label>
                {items.length > 0 ? (
                  <select
                    required
                    value={selectedItemId}
                    onChange={(e) => {
                      setSelectedItemId(e.target.value);
                      const itm = items.find((i) => i.item_id === e.target.value);
                      if (itm && itm.standard_rate) setPoUnitPrice(parseFloat(itm.standard_rate).toFixed(2));
                    }}
                    className="w-full rounded border border-cream-300 bg-cream-50 px-3 py-1.5 text-cream-900 font-mono"
                  >
                    {items.map((i) => (
                      <option key={i.item_id} value={i.item_id}>
                        {i.item_code} - {i.item_name}
                      </option>
                    ))}
                  </select>
                ) : (
                  <div className="text-[11px] text-terracotta-700 italic">No items. Use &quot;Seed Sample P2P Flow&quot; to auto-create.</div>
                )}
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-medium text-cream-900 mb-1">Quantity</label>
                  <input
                    type="number"
                    step="1"
                    required
                    value={poQty}
                    onChange={(e) => setPoQty(e.target.value)}
                    className="w-full rounded border border-cream-300 bg-cream-50 px-3 py-1.5 font-mono text-cream-900"
                  />
                </div>
                <div>
                  <label className="block font-medium text-cream-900 mb-1">Unit Price ($)</label>
                  <input
                    type="number"
                    step="0.01"
                    required
                    value={poUnitPrice}
                    onChange={(e) => setPoUnitPrice(e.target.value)}
                    className="w-full rounded border border-cream-300 bg-cream-50 px-3 py-1.5 font-mono text-cream-900"
                  />
                </div>
              </div>

              <div className="p-2.5 rounded bg-cream-200/60 font-mono text-xs flex justify-between">
                <span>Calculated Total:</span>
                <span className="font-bold text-cream-900">
                  ${(parseFloat(poQty || "0") * parseFloat(poUnitPrice || "0")).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </span>
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-cream-300">
                <button
                  type="button"
                  onClick={() => setShowCreatePoModal(false)}
                  className="rounded px-3 py-1.5 text-cream-800"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creatingPo}
                  className="rounded bg-cream-900 px-4 py-1.5 font-medium text-cream-50 hover:bg-cream-800 disabled:opacity-50"
                >
                  {creatingPo ? "Issuing..." : "Submit PO"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal 3: Create Goods Receipt (GRN) */}
      {showCreateGrnModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="w-full max-w-md rounded-xl border border-cream-300 bg-cream-100 p-6 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b border-cream-300 pb-3">
              <h3 className="font-semibold text-sm text-cream-900">Log Goods Receipt Note (GRN)</h3>
              <button onClick={() => setShowCreateGrnModal(false)} className="text-cream-600 hover:text-cream-900">&times;</button>
            </div>

            <form onSubmit={handleCreateGrn} className="space-y-3 text-xs">
              <div>
                <label className="block font-medium text-cream-900 mb-1">GRN Number</label>
                <input
                  type="text"
                  required
                  value={newGrnNumber}
                  onChange={(e) => setNewGrnNumber(e.target.value)}
                  className="w-full rounded border border-cream-300 bg-cream-50 px-3 py-1.5 font-mono text-cream-900"
                />
              </div>

              <div>
                <label className="block font-medium text-cream-900 mb-1">Purchase Order to Receive</label>
                <select
                  required
                  value={selectedGrnPoId}
                  onChange={(e) => setSelectedGrnPoId(e.target.value)}
                  className="w-full rounded border border-cream-300 bg-cream-50 px-3 py-1.5 font-mono text-cream-900"
                >
                  <option value="">Select PO...</option>
                  {purchaseOrders.map((p) => (
                    <option key={p.po_id} value={p.po_id}>
                      {p.po_number} (${parseFloat(p.total_amount).toFixed(2)})
                    </option>
                  ))}
                </select>
              </div>

              <div className="p-2.5 rounded bg-cream-200/60 text-[11px] text-cream-700">
                Logging a Goods Receipt automatically increments warehouse on-hand inventory and posts an audited Stock Ledger Entry (SLE).
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-cream-300">
                <button
                  type="button"
                  onClick={() => setShowCreateGrnModal(false)}
                  className="rounded px-3 py-1.5 text-cream-800"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creatingGrn}
                  className="rounded bg-cream-900 px-4 py-1.5 font-medium text-cream-50 hover:bg-cream-800 disabled:opacity-50"
                >
                  {creatingGrn ? "Recording..." : "Record GRN"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal 4: Register New Supplier */}
      {showCreateSupplierModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="w-full max-w-md rounded-xl border border-cream-300 bg-cream-100 p-6 shadow-xl space-y-4 animate-in fade-in zoom-in-95 duration-100">
            <div className="flex items-center justify-between border-b border-cream-300 pb-3">
              <div className="flex items-center gap-2">
                <Building2 className="h-4 w-4 text-cream-800" />
                <h3 className="font-semibold text-sm text-cream-950">Register New Supplier</h3>
              </div>
              <button
                onClick={() => setShowCreateSupplierModal(false)}
                className="text-cream-600 hover:text-cream-900 text-sm font-semibold"
              >
                &times;
              </button>
            </div>

            <form onSubmit={handleCreateSupplier} className="space-y-3.5 text-xs">
              <div>
                <label className="block font-medium text-cream-900 mb-1">Supplier Code</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. SUP-AERO-01"
                  value={newSupplierCode}
                  onChange={(e) => setNewSupplierCode(e.target.value.toUpperCase())}
                  className="w-full rounded border border-cream-300 bg-cream-50 px-3 py-1.5 font-mono text-cream-900 focus:border-cream-900 focus:outline-hidden"
                />
              </div>

              <div>
                <label className="block font-medium text-cream-900 mb-1">Supplier / Vendor Legal Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Apex Aerospace Materials LLC"
                  value={newSupplierName}
                  onChange={(e) => setNewSupplierName(e.target.value)}
                  className="w-full rounded border border-cream-300 bg-cream-50 px-3 py-1.5 text-cream-900 focus:border-cream-900 focus:outline-hidden"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-medium text-cream-900 mb-1">Tax / VAT ID</label>
                  <input
                    type="text"
                    placeholder="e.g. US-882910"
                    value={newSupplierTaxId}
                    onChange={(e) => setNewSupplierTaxId(e.target.value)}
                    className="w-full rounded border border-cream-300 bg-cream-50 px-3 py-1.5 font-mono text-cream-900 focus:border-cream-900 focus:outline-hidden"
                  />
                </div>
                <div>
                  <label className="block font-medium text-cream-900 mb-1">Operating Currency</label>
                  <select
                    value={newSupplierCurrency}
                    onChange={(e) => setNewSupplierCurrency(e.target.value)}
                    className="w-full rounded border border-cream-300 bg-cream-50 px-3 py-1.5 text-cream-900 focus:border-cream-900 focus:outline-hidden"
                  >
                    <option value="USD">USD ($)</option>
                    <option value="EUR">EUR (€)</option>
                    <option value="GBP">GBP (£)</option>
                    <option value="CAD">CAD ($)</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block font-medium text-cream-900 mb-1">Payment Terms (Days)</label>
                <input
                  type="number"
                  min="0"
                  max="365"
                  value={newSupplierTerms}
                  onChange={(e) => setNewSupplierTerms(e.target.value)}
                  className="w-full rounded border border-cream-300 bg-cream-50 px-3 py-1.5 text-cream-900 focus:border-cream-900 focus:outline-hidden"
                />
                <span className="text-[10px] text-cream-600">Standard vendor credit period (e.g. Net 30, Net 60).</span>
              </div>

              <div className="p-2.5 rounded bg-cream-200/60 text-[11px] text-cream-700">
                Registering a supplier assigns an initial 100.0% OTIF (On-Time In-Full) rating and enables immediate Purchase Order generation.
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-cream-300">
                <button
                  type="button"
                  onClick={() => setShowCreateSupplierModal(false)}
                  className="rounded px-3 py-1.5 text-cream-800"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creatingSupplier}
                  className="flex items-center gap-1.5 rounded bg-cream-900 px-4 py-1.5 font-medium text-cream-50 hover:bg-cream-800 disabled:opacity-50"
                >
                  <Plus className="h-3.5 w-3.5" />
                  <span>{creatingSupplier ? "Saving..." : "Create Supplier"}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

