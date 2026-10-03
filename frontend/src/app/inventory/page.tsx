"use client";

import { useEffect, useState } from "react";
import {
  Layers,
  Plus,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  ArrowRightLeft,
  ClipboardCheck,
  Barcode,
  Truck,
  Package,
  Calendar,
  MapPin,
  Clock,
  ShieldCheck,
  Tag,
  ExternalLink,
  ChevronRight,
} from "lucide-react";
import { api } from "@/lib/api";

export default function InventoryPage() {
  const [activeTab, setActiveTab] = useState<
    "catalog" | "entries" | "reconciliation" | "serials_batches" | "fulfillment" | "delivery"
  >("catalog");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // Core Data
  const [items, setItems] = useState<any[]>([]);
  const [warehouses, setWarehouses] = useState<any[]>([]);
  const [stockEntries, setStockEntries] = useState<any[]>([]);
  const [reconciliations, setReconciliations] = useState<any[]>([]);
  const [batches, setBatches] = useState<any[]>([]);
  const [serials, setSerials] = useState<any[]>([]);
  const [pickLists, setPickLists] = useState<any[]>([]);
  const [packingSlips, setPackingSlips] = useState<any[]>([]);
  const [deliveryTrips, setDeliveryTrips] = useState<any[]>([]);
  const [customers, setCustomers] = useState<any[]>([]);

  // Modals
  const [showItemModal, setShowItemModal] = useState(false);
  const [showEntryModal, setShowEntryModal] = useState(false);
  const [showReconModal, setShowReconModal] = useState(false);
  const [showBatchModal, setShowBatchModal] = useState(false);
  const [showSerialModal, setShowSerialModal] = useState(false);
  const [showPickModal, setShowPickModal] = useState(false);
  const [showTripModal, setShowTripModal] = useState(false);
  const [showVariantModal, setShowVariantModal] = useState<any | null>(null);

  // Item Form
  const [itemCode, setItemCode] = useState("");
  const [itemName, setItemName] = useState("");
  const [stockUom, setStockUom] = useState("Nos");
  const [standardRate, setStandardRate] = useState("10.00");
  const [initialQty, setInitialQty] = useState("100");
  const [reorderLevel, setReorderLevel] = useState("50");

  // ROP State
  const [ropItemCode, setRopItemCode] = useState("");
  const [ropResult, setRopResult] = useState<any | null>(null);
  const [calculatingRop, setCalculatingRop] = useState(false);

  // Stock Entry Form
  const [entryType, setEntryType] = useState("MATERIAL_TRANSFER");
  const [fromWhId, setFromWhId] = useState("");
  const [toWhId, setToWhId] = useState("");
  const [entryItemId, setEntryItemId] = useState("");
  const [entryQty, setEntryQty] = useState("10");
  const [entryRate, setEntryRate] = useState("15.00");
  const [entryBatchNo, setEntryBatchNo] = useState("");
  const [entrySerialNo, setEntrySerialNo] = useState("");

  // Reconciliation Form
  const [reconWhId, setReconWhId] = useState("");
  const [reconItemId, setReconItemId] = useState("");
  const [reconPhysicalQty, setReconPhysicalQty] = useState("100");
  const [reconRate, setReconRate] = useState("15.00");

  // Batch / Serial Forms
  const [batchNo, setBatchNo] = useState("");
  const [batchItemId, setBatchItemId] = useState("");
  const [batchExpiryDays, setBatchExpiryDays] = useState("180");

  const [serialNo, setSerialNo] = useState("");
  const [serialItemId, setSerialItemId] = useState("");
  const [serialWhId, setSerialWhId] = useState("");

  // Pick List Form
  const [plCustomerId, setPlCustomerId] = useState("");
  const [plItemId, setPlItemId] = useState("");
  const [plWhId, setPlWhId] = useState("");
  const [plQty, setPlQty] = useState("50");

  // Delivery Trip Form
  const [tripDriver, setTripDriver] = useState("");
  const [tripVehicle, setTripVehicle] = useState("");
  const [tripAddress, setTripAddress] = useState("");
  const [tripDistance, setTripDistance] = useState("25");

  // Variant Form
  const [variantAttrKey, setVariantAttrKey] = useState("Size");
  const [variantAttrVal, setVariantAttrVal] = useState("Large");

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 4000);
  };

  const loadAll = async () => {
    setLoading(true);
    setError(null);
    try {
      const [itData, whData, seData, recData, batData, serData, plData, psData, dtData, custData] =
        await Promise.allSettled([
          api.getItems(),
          api.getWarehouses(),
          api.getStockEntries(),
          api.getStockReconciliations(),
          api.getBatches(),
          api.getSerials(),
          api.getPickLists(),
          api.getPackingSlips(),
          api.getDeliveryTrips(),
          api.getCustomers(),
        ]);

      if (itData.status === "fulfilled") setItems(itData.value || []);
      if (whData.status === "fulfilled") setWarehouses(whData.value || []);
      if (seData.status === "fulfilled") setStockEntries(seData.value || []);
      if (recData.status === "fulfilled") setReconciliations(recData.value || []);
      if (batData.status === "fulfilled") setBatches(batData.value || []);
      if (serData.status === "fulfilled") setSerials(serData.value || []);
      if (plData.status === "fulfilled") setPickLists(plData.value || []);
      if (psData.status === "fulfilled") setPackingSlips(psData.value || []);
      if (dtData.status === "fulfilled") setDeliveryTrips(dtData.value || []);
      if (custData.status === "fulfilled") setCustomers(custData.value || []);
    } catch (err: any) {
      setError(err.message || "Failed to load stock data.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAll();
  }, []);

  // --- Handlers ---

  const handleCreateItem = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.createItem({
        item_code: itemCode.trim().toUpperCase(),
        item_name: itemName.trim(),
        stock_uom: stockUom,
        standard_rate: parseFloat(standardRate),
        initial_qty: parseFloat(initialQty),
        reorder_level: parseFloat(reorderLevel),
      });
      setShowItemModal(false);
      setItemCode("");
      setItemName("");
      showToast("Master catalog item created successfully!");
      await loadAll();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleCreateStockEntry = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const entryNum = `STE-${Date.now().toString().slice(-6)}`;
      await api.createStockEntry({
        entry_number: entryNum,
        stock_entry_type: entryType,
        from_warehouse_id: fromWhId || undefined,
        to_warehouse_id: toWhId || undefined,
        items: [
          {
            item_id: entryItemId,
            s_warehouse_id: fromWhId || undefined,
            t_warehouse_id: toWhId || undefined,
            qty: parseFloat(entryQty),
            basic_rate: parseFloat(entryRate),
            batch_no: entryBatchNo || undefined,
            serial_no: entrySerialNo || undefined,
          },
        ],
      });
      setShowEntryModal(false);
      showToast(`Stock entry ${entryNum} drafted successfully!`);
      await loadAll();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleSubmitStockEntry = async (id: string) => {
    try {
      await api.submitStockEntry(id);
      showToast("Stock entry posted to ledger & GL!");
      await loadAll();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleCreateReconciliation = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const recNum = `REC-${Date.now().toString().slice(-6)}`;
      await api.createStockReconciliation({
        reconciliation_number: recNum,
        items: [
          {
            item_id: reconItemId,
            warehouse_id: reconWhId,
            reconciled_qty: parseFloat(reconPhysicalQty),
            reconciled_valuation_rate: parseFloat(reconRate),
          },
        ],
      });
      setShowReconModal(false);
      showToast(`Reconciliation ${recNum} drafted!`);
      await loadAll();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleSubmitReconciliation = async (id: string) => {
    try {
      await api.submitStockReconciliation(id);
      showToast("Physical count reconciliation committed to ledger!");
      await loadAll();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleCreateBatch = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const days = parseInt(batchExpiryDays, 10) || 180;
      const expiry = new Date();
      expiry.setDate(expiry.getDate() + days);

      await api.createBatch({
        batch_number: batchNo.trim().toUpperCase(),
        item_id: batchItemId,
        expiry_date: expiry.toISOString().split("T")[0],
        description: "Standard production lot",
      });
      setShowBatchModal(false);
      setBatchNo("");
      showToast("Batch lot registered!");
      await loadAll();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleCreateSerial = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.createSerial({
        serial_number: serialNo.trim().toUpperCase(),
        item_id: serialItemId,
        warehouse_id: serialWhId || undefined,
      });
      setShowSerialModal(false);
      setSerialNo("");
      showToast("Serial unit registered!");
      await loadAll();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleCreatePickList = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const plNum = `PL-${Date.now().toString().slice(-6)}`;
      await api.createPickList({
        pick_list_number: plNum,
        customer_id: plCustomerId || undefined,
        items: [
          {
            item_id: plItemId,
            warehouse_id: plWhId,
            qty_to_pick: parseFloat(plQty),
            picked_qty: 0,
          },
        ],
      });
      setShowPickModal(false);
      showToast(`Pick list ${plNum} generated!`);
      await loadAll();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handlePickLine = async (plId: string, pickItemId: string, qty: number) => {
    try {
      await api.updatePickedQty(plId, pickItemId, qty);
      showToast(`Picked ${qty} units!`);
      await loadAll();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleCompletePick = async (plId: string) => {
    try {
      await api.completePickList(plId);
      showToast("Pick list marked completed!");
      await loadAll();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleCreateTrip = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const tripNum = `TRIP-${Date.now().toString().slice(-6)}`;
      await api.createDeliveryTrip({
        trip_number: tripNum,
        driver_name: tripDriver,
        vehicle_number: tripVehicle,
        total_distance_km: parseFloat(tripDistance),
        stops: [
          {
            address: tripAddress || "Customer Warehouse Destination",
            stop_sequence: 1,
          },
        ],
      });
      setShowTripModal(false);
      showToast(`Delivery Trip ${tripNum} planned!`);
      await loadAll();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleDispatchTrip = async (tripId: string) => {
    try {
      await api.dispatchDeliveryTrip(tripId);
      showToast("Delivery vehicle dispatched (IN_TRANSIT)!");
      await loadAll();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleCompleteStop = async (tripId: string, stopId: string) => {
    try {
      await api.completeDeliveryStop(tripId, stopId, "CUSTOMER-CONFIRMED");
      showToast("Stop delivery confirmed!");
      await loadAll();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleGenerateVariants = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!showVariantModal) return;
    try {
      await api.generateItemVariants(showVariantModal.item_id, {
        variants: [
          {
            item_code: `${showVariantModal.item_code}-${variantAttrVal.toUpperCase().slice(0, 3)}`,
            item_name: `${showVariantModal.item_name} (${variantAttrVal})`,
            attributes: { [variantAttrKey]: variantAttrVal },
          },
        ],
      });
      setShowVariantModal(null);
      showToast("Item variant generated!");
      await loadAll();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleCalculateROP = async () => {
    if (!ropItemCode) return;
    setCalculatingRop(true);
    setError(null);
    try {
      const res = await api.calculateROP({
        item_code: ropItemCode,
        daily_demand_mean: 150,
        daily_demand_std: 25,
        lead_time_mean_days: 14,
        lead_time_std_days: 3,
      });
      setRopResult(res);
    } catch (err: any) {
      setError(err.message || "Failed to compute dynamic ROP.");
    } finally {
      setCalculatingRop(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Toast Alert */}
      {toastMessage && (
        <div className="fixed bottom-4 right-4 z-50 flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2.5 text-xs font-medium text-white shadow-lg animate-in fade-in slide-in-from-bottom-2">
          <CheckCircle2 className="h-4 w-4" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Header */}
      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between border-b border-cream-300 pb-5">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-cream-900">
            Stock, Warehousing & Fulfillment Logistics
          </h1>
          <p className="text-xs text-cream-700 mt-1">
            Universal Stock Movements, Physical Count Reconciliation, Serial/Batch Lifecycles, and Multi-Stop Route Dispatch.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={loadAll}
            disabled={loading}
            className="flex items-center gap-1.5 rounded-md border border-cream-300 bg-cream-100 px-3 py-1.5 text-xs font-medium text-cream-800 hover:bg-cream-200 transition-colors"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
            <span>Sync</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-rose-50 border border-rose-300 text-rose-800 text-xs">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Workspace Navigation Tabs */}
      <div className="flex border-b border-cream-300 gap-1 overflow-x-auto text-xs font-medium">
        <button
          onClick={() => setActiveTab("catalog")}
          className={`flex items-center gap-1.5 px-4 py-2.5 border-b-2 transition-colors whitespace-nowrap ${
            activeTab === "catalog"
              ? "border-cream-950 text-cream-950 font-semibold"
              : "border-transparent text-cream-600 hover:text-cream-900"
          }`}
        >
          <Layers className="h-3.5 w-3.5" />
          <span>Catalog & Stochastic ROP</span>
          <span className="ml-1 rounded-full bg-cream-200 px-1.5 py-0.2 text-[10px] text-cream-800">
            {items.length}
          </span>
        </button>

        <button
          onClick={() => setActiveTab("entries")}
          className={`flex items-center gap-1.5 px-4 py-2.5 border-b-2 transition-colors whitespace-nowrap ${
            activeTab === "entries"
              ? "border-cream-950 text-cream-950 font-semibold"
              : "border-transparent text-cream-600 hover:text-cream-900"
          }`}
        >
          <ArrowRightLeft className="h-3.5 w-3.5" />
          <span>Stock Movements</span>
          <span className="ml-1 rounded-full bg-cream-200 px-1.5 py-0.2 text-[10px] text-cream-800">
            {stockEntries.length}
          </span>
        </button>

        <button
          onClick={() => setActiveTab("reconciliation")}
          className={`flex items-center gap-1.5 px-4 py-2.5 border-b-2 transition-colors whitespace-nowrap ${
            activeTab === "reconciliation"
              ? "border-cream-950 text-cream-950 font-semibold"
              : "border-transparent text-cream-600 hover:text-cream-900"
          }`}
        >
          <ClipboardCheck className="h-3.5 w-3.5" />
          <span>Stock Reconciliation</span>
          <span className="ml-1 rounded-full bg-cream-200 px-1.5 py-0.2 text-[10px] text-cream-800">
            {reconciliations.length}
          </span>
        </button>

        <button
          onClick={() => setActiveTab("serials_batches")}
          className={`flex items-center gap-1.5 px-4 py-2.5 border-b-2 transition-colors whitespace-nowrap ${
            activeTab === "serials_batches"
              ? "border-cream-950 text-cream-950 font-semibold"
              : "border-transparent text-cream-600 hover:text-cream-900"
          }`}
        >
          <Barcode className="h-3.5 w-3.5" />
          <span>Serials & Batches</span>
          <span className="ml-1 rounded-full bg-cream-200 px-1.5 py-0.2 text-[10px] text-cream-800">
            {batches.length + serials.length}
          </span>
        </button>

        <button
          onClick={() => setActiveTab("fulfillment")}
          className={`flex items-center gap-1.5 px-4 py-2.5 border-b-2 transition-colors whitespace-nowrap ${
            activeTab === "fulfillment"
              ? "border-cream-950 text-cream-950 font-semibold"
              : "border-transparent text-cream-600 hover:text-cream-900"
          }`}
        >
          <Package className="h-3.5 w-3.5" />
          <span>Pick Lists & Packaging</span>
          <span className="ml-1 rounded-full bg-cream-200 px-1.5 py-0.2 text-[10px] text-cream-800">
            {pickLists.length}
          </span>
        </button>

        <button
          onClick={() => setActiveTab("delivery")}
          className={`flex items-center gap-1.5 px-4 py-2.5 border-b-2 transition-colors whitespace-nowrap ${
            activeTab === "delivery"
              ? "border-cream-950 text-cream-950 font-semibold"
              : "border-transparent text-cream-600 hover:text-cream-900"
          }`}
        >
          <Truck className="h-3.5 w-3.5" />
          <span>Delivery Logistics</span>
          <span className="ml-1 rounded-full bg-cream-200 px-1.5 py-0.2 text-[10px] text-cream-800">
            {deliveryTrips.length}
          </span>
        </button>
      </div>

      {/* ========================================================================= */}
      {/* TAB 1: CATALOG & STOCHASTIC ROP */}
      {/* ========================================================================= */}
      {activeTab === "catalog" && (
        <div className="space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-cream-900">Item Master & Stochastic Inventory</h2>
              <p className="text-[11px] text-cream-600">
                Multi-warehouse stock levels, reorder thresholds, and variant attributes.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setShowItemModal(true)}
                className="flex items-center gap-1.5 rounded-md bg-cream-900 px-3 py-1.5 text-xs font-medium text-cream-50 hover:bg-cream-800 transition-colors"
              >
                <Plus className="h-3.5 w-3.5" />
                <span>New Catalog Item</span>
              </button>
            </div>
          </div>

          {/* Stochastic ROP Banner */}
          {ropResult && (
            <div className="rounded-lg border border-emerald-300 bg-emerald-50/50 p-4 text-xs text-emerald-950 space-y-1">
              <div className="font-semibold flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                <span>Stochastic ROP Result for {ropResult.item_code} (Z=2.33 &bull; 99% Service Level)</span>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 pt-2 font-mono text-[11px]">
                <div>Lead Time Demand: <span className="font-bold">{ropResult.lead_time_demand_mean}</span></div>
                <div>Safety Buffer: <span className="font-bold">{ropResult.safety_stock}</span></div>
                <div>Dynamic ROP: <span className="font-bold">{ropResult.reorder_point}</span></div>
                <div>Optimal EOQ: <span className="font-bold">{ropResult.economic_order_quantity}</span></div>
              </div>
            </div>
          )}

          {/* Catalog Items Table */}
          <div className="rounded-xl border border-cream-300 bg-cream-100 overflow-hidden shadow-xs">
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-cream-300 bg-cream-200/50 text-cream-700 font-medium">
                    <th className="py-2.5 px-3">Item Code</th>
                    <th className="py-2.5 px-3">Item Name</th>
                    <th className="py-2.5 px-3">UOM</th>
                    <th className="py-2.5 px-3 text-right">On-Hand</th>
                    <th className="py-2.5 px-3 text-right">Reserved</th>
                    <th className="py-2.5 px-3 text-right">Available</th>
                    <th className="py-2.5 px-3 text-right">Valuation Rate</th>
                    <th className="py-2.5 px-3 text-right">Reorder Level</th>
                    <th className="py-2.5 px-3 text-center">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-cream-200">
                  {items.length === 0 ? (
                    <tr>
                      <td colSpan={9} className="py-8 text-center text-cream-600 text-xs">
                        No items registered in catalog.
                      </td>
                    </tr>
                  ) : (
                    items.map((it) => (
                      <tr key={it.item_id} className="hover:bg-cream-50/50 transition-colors">
                        <td className="py-2.5 px-3 font-mono font-medium text-cream-950">
                          {it.item_code}
                          {it.has_variants && (
                            <span className="ml-1.5 rounded bg-blue-100 px-1 py-0.2 text-[9px] font-semibold text-blue-700">
                              Template
                            </span>
                          )}
                          {it.variant_of && (
                            <span className="ml-1.5 rounded bg-purple-100 px-1 py-0.2 text-[9px] font-semibold text-purple-700">
                              Variant
                            </span>
                          )}
                        </td>
                        <td className="py-2.5 px-3 text-cream-800 max-w-[200px] truncate">{it.item_name}</td>
                        <td className="py-2.5 px-3 text-cream-600 font-mono text-[11px]">{it.stock_uom}</td>
                        <td className="py-2.5 px-3 text-right font-mono font-bold text-cream-950">
                          {parseFloat(it.current_qty || 0).toLocaleString()}
                        </td>
                        <td className="py-2.5 px-3 text-right font-mono text-amber-700">
                          {parseFloat(it.reserved_qty || 0).toLocaleString()}
                        </td>
                        <td className="py-2.5 px-3 text-right font-mono text-emerald-700 font-semibold">
                          {parseFloat(it.available_qty || it.current_qty || 0).toLocaleString()}
                        </td>
                        <td className="py-2.5 px-3 text-right font-mono text-cream-700">
                          ${parseFloat(it.valuation_rate || it.standard_rate || 0).toFixed(2)}
                        </td>
                        <td className="py-2.5 px-3 text-right font-mono text-cream-600">
                          {parseFloat(it.reorder_level || 0).toLocaleString()}
                        </td>
                        <td className="py-2.5 px-3 text-center">
                          <button
                            onClick={() => {
                              setRopItemCode(it.item_code);
                              handleCalculateROP();
                            }}
                            className="rounded bg-cream-200 px-2 py-1 text-[10px] font-medium text-cream-800 hover:bg-cream-300 transition-colors mr-1"
                          >
                            ROP
                          </button>
                          <button
                            onClick={() => setShowVariantModal(it)}
                            className="rounded bg-purple-100 px-2 py-1 text-[10px] font-medium text-purple-800 hover:bg-purple-200 transition-colors"
                          >
                            +Variant
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

      {/* ========================================================================= */}
      {/* TAB 2: STOCK MOVEMENTS (STOCK ENTRIES) */}
      {/* ========================================================================= */}
      {activeTab === "entries" && (
        <div className="space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-cream-900">Stock Entries & Material Movements</h2>
              <p className="text-[11px] text-cream-600">
                Universal material movements (Receipt, Issue, Transfer) with double-entry GL impacts.
              </p>
            </div>
            <button
              onClick={() => {
                if (items.length > 0) setEntryItemId(items[0].item_id);
                if (warehouses.length > 0) {
                  setFromWhId(warehouses[0].warehouse_id);
                  setToWhId(warehouses[1]?.warehouse_id || warehouses[0].warehouse_id);
                }
                setShowEntryModal(true);
              }}
              className="flex items-center gap-1.5 rounded-md bg-cream-900 px-3 py-1.5 text-xs font-medium text-cream-50 hover:bg-cream-800 transition-colors"
            >
              <Plus className="h-3.5 w-3.5" />
              <span>New Stock Movement</span>
            </button>
          </div>

          <div className="rounded-xl border border-cream-300 bg-cream-100 overflow-hidden shadow-xs">
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-cream-300 bg-cream-200/50 text-cream-700 font-medium">
                    <th className="py-2.5 px-3">Entry Number</th>
                    <th className="py-2.5 px-3">Type</th>
                    <th className="py-2.5 px-3">Date</th>
                    <th className="py-2.5 px-3">Source WH</th>
                    <th className="py-2.5 px-3">Target WH</th>
                    <th className="py-2.5 px-3 text-right">Total Amount</th>
                    <th className="py-2.5 px-3 text-center">Status</th>
                    <th className="py-2.5 px-3 text-center">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-cream-200">
                  {stockEntries.length === 0 ? (
                    <tr>
                      <td colSpan={8} className="py-8 text-center text-cream-600 text-xs">
                        No stock movement entries recorded. Click "New Stock Movement" to transfer or issue stock.
                      </td>
                    </tr>
                  ) : (
                    stockEntries.map((se) => (
                      <tr key={se.entry_id} className="hover:bg-cream-50/50 transition-colors">
                        <td className="py-2.5 px-3 font-mono font-medium text-cream-950">{se.entry_number}</td>
                        <td className="py-2.5 px-3">
                          <span
                            className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${
                              se.stock_entry_type === "MATERIAL_RECEIPT"
                                ? "bg-emerald-100 text-emerald-800"
                                : se.stock_entry_type === "MATERIAL_ISSUE"
                                ? "bg-rose-100 text-rose-800"
                                : "bg-blue-100 text-blue-800"
                            }`}
                          >
                            {se.stock_entry_type}
                          </span>
                        </td>
                        <td className="py-2.5 px-3 text-cream-700">{se.posting_date}</td>
                        <td className="py-2.5 px-3 text-cream-600 font-mono text-[11px]">
                          {se.from_warehouse?.warehouse_name || "-"}
                        </td>
                        <td className="py-2.5 px-3 text-cream-600 font-mono text-[11px]">
                          {se.to_warehouse?.warehouse_name || "-"}
                        </td>
                        <td className="py-2.5 px-3 text-right font-mono font-medium text-cream-950">
                          ${parseFloat(se.total_amount || 0).toFixed(2)}
                        </td>
                        <td className="py-2.5 px-3 text-center">
                          <span
                            className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${
                              se.status === "SUBMITTED"
                                ? "bg-emerald-100 text-emerald-800"
                                : "bg-amber-100 text-amber-800"
                            }`}
                          >
                            {se.status}
                          </span>
                        </td>
                        <td className="py-2.5 px-3 text-center">
                          {se.status === "DRAFT" && (
                            <button
                              onClick={() => handleSubmitStockEntry(se.entry_id)}
                              className="rounded bg-emerald-600 px-2 py-1 text-[10px] font-medium text-white hover:bg-emerald-700 transition-colors"
                            >
                              Submit & Post GL
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

      {/* ========================================================================= */}
      {/* TAB 3: STOCK RECONCILIATION */}
      {/* ========================================================================= */}
      {activeTab === "reconciliation" && (
        <div className="space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-cream-900">Physical Count Stock Reconciliation</h2>
              <p className="text-[11px] text-cream-600">
                Audit warehouse shelf inventory, calculate variances, and write adjusting stock ledger entries.
              </p>
            </div>
            <button
              onClick={() => {
                if (items.length > 0) setReconItemId(items[0].item_id);
                if (warehouses.length > 0) setReconWhId(warehouses[0].warehouse_id);
                setShowReconModal(true);
              }}
              className="flex items-center gap-1.5 rounded-md bg-cream-900 px-3 py-1.5 text-xs font-medium text-cream-50 hover:bg-cream-800 transition-colors"
            >
              <Plus className="h-3.5 w-3.5" />
              <span>New Count Audit</span>
            </button>
          </div>

          <div className="rounded-xl border border-cream-300 bg-cream-100 overflow-hidden shadow-xs">
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-cream-300 bg-cream-200/50 text-cream-700 font-medium">
                    <th className="py-2.5 px-3">Reconciliation Number</th>
                    <th className="py-2.5 px-3">Posting Date</th>
                    <th className="py-2.5 px-3">Item Lines</th>
                    <th className="py-2.5 px-3 text-right">Variance Value</th>
                    <th className="py-2.5 px-3 text-center">Status</th>
                    <th className="py-2.5 px-3 text-center">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-cream-200">
                  {reconciliations.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="py-8 text-center text-cream-600 text-xs">
                        No physical stock reconciliations recorded.
                      </td>
                    </tr>
                  ) : (
                    reconciliations.map((rec) => (
                      <tr key={rec.reconciliation_id} className="hover:bg-cream-50/50 transition-colors">
                        <td className="py-2.5 px-3 font-mono font-medium text-cream-950">
                          {rec.reconciliation_number}
                        </td>
                        <td className="py-2.5 px-3 text-cream-700">{rec.posting_date}</td>
                        <td className="py-2.5 px-3 text-cream-600 font-mono text-[11px]">
                          {rec.items?.length || 1} lines
                        </td>
                        <td
                          className={`py-2.5 px-3 text-right font-mono font-bold ${
                            parseFloat(rec.total_variance_value || 0) < 0
                              ? "text-rose-700"
                              : "text-emerald-700"
                          }`}
                        >
                          ${parseFloat(rec.total_variance_value || 0).toFixed(2)}
                        </td>
                        <td className="py-2.5 px-3 text-center">
                          <span
                            className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${
                              rec.status === "SUBMITTED"
                                ? "bg-emerald-100 text-emerald-800"
                                : "bg-amber-100 text-amber-800"
                            }`}
                          >
                            {rec.status}
                          </span>
                        </td>
                        <td className="py-2.5 px-3 text-center">
                          {rec.status === "DRAFT" && (
                            <button
                              onClick={() => handleSubmitReconciliation(rec.reconciliation_id)}
                              className="rounded bg-emerald-600 px-2 py-1 text-[10px] font-medium text-white hover:bg-emerald-700 transition-colors"
                            >
                              Submit Adjustment
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

      {/* ========================================================================= */}
      {/* TAB 4: SERIALS & BATCHES */}
      {/* ========================================================================= */}
      {activeTab === "serials_batches" && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Batches Column */}
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-semibold text-cream-900">Lot & Batch Tracking</h3>
                  <p className="text-[11px] text-cream-600">Production lots with expiration dates.</p>
                </div>
                <button
                  onClick={() => {
                    if (items.length > 0) setBatchItemId(items[0].item_id);
                    setShowBatchModal(true);
                  }}
                  className="flex items-center gap-1 rounded bg-cream-900 px-2.5 py-1 text-xs font-medium text-cream-50 hover:bg-cream-800 transition-colors"
                >
                  <Plus className="h-3.5 w-3.5" />
                  <span>New Batch</span>
                </button>
              </div>

              <div className="rounded-xl border border-cream-300 bg-cream-100 overflow-hidden shadow-xs">
                <table className="w-full text-left border-collapse text-xs">
                  <thead>
                    <tr className="border-b border-cream-300 bg-cream-200/50 text-cream-700 font-medium">
                      <th className="py-2 px-3">Batch No</th>
                      <th className="py-2 px-3">Item</th>
                      <th className="py-2 px-3">Expiry Date</th>
                      <th className="py-2 px-3 text-center">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-cream-200">
                    {batches.length === 0 ? (
                      <tr>
                        <td colSpan={4} className="py-6 text-center text-cream-600 text-xs">
                          No batches registered.
                        </td>
                      </tr>
                    ) : (
                      batches.map((b) => (
                        <tr key={b.batch_id} className="hover:bg-cream-50/50 transition-colors">
                          <td className="py-2 px-3 font-mono font-medium text-cream-950">{b.batch_number}</td>
                          <td className="py-2 px-3 text-cream-700 truncate max-w-[120px]">
                            {b.item?.item_code || "-"}
                          </td>
                          <td className="py-2 px-3 font-mono text-[11px] text-cream-600">{b.expiry_date || "N/A"}</td>
                          <td className="py-2 px-3 text-center">
                            <span
                              className={`rounded px-1.5 py-0.2 text-[9px] font-semibold ${
                                b.status === "ACTIVE"
                                  ? "bg-emerald-100 text-emerald-800"
                                  : "bg-rose-100 text-rose-800"
                              }`}
                            >
                              {b.status}
                            </span>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Serial Numbers Column */}
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-semibold text-cream-900">Unit Serial Numbers</h3>
                  <p className="text-[11px] text-cream-600">Individual unit lifecycle tracking.</p>
                </div>
                <button
                  onClick={() => {
                    if (items.length > 0) setSerialItemId(items[0].item_id);
                    if (warehouses.length > 0) setSerialWhId(warehouses[0].warehouse_id);
                    setShowSerialModal(true);
                  }}
                  className="flex items-center gap-1 rounded bg-cream-900 px-2.5 py-1 text-xs font-medium text-cream-50 hover:bg-cream-800 transition-colors"
                >
                  <Plus className="h-3.5 w-3.5" />
                  <span>Register Serial</span>
                </button>
              </div>

              <div className="rounded-xl border border-cream-300 bg-cream-100 overflow-hidden shadow-xs">
                <table className="w-full text-left border-collapse text-xs">
                  <thead>
                    <tr className="border-b border-cream-300 bg-cream-200/50 text-cream-700 font-medium">
                      <th className="py-2 px-3">Serial No</th>
                      <th className="py-2 px-3">Item</th>
                      <th className="py-2 px-3">Warehouse</th>
                      <th className="py-2 px-3 text-center">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-cream-200">
                    {serials.length === 0 ? (
                      <tr>
                        <td colSpan={4} className="py-6 text-center text-cream-600 text-xs">
                          No serial numbers registered.
                        </td>
                      </tr>
                    ) : (
                      serials.map((s) => (
                        <tr key={s.serial_id} className="hover:bg-cream-50/50 transition-colors">
                          <td className="py-2 px-3 font-mono font-medium text-cream-950">{s.serial_number}</td>
                          <td className="py-2 px-3 text-cream-700 truncate max-w-[120px]">
                            {s.item?.item_code || "-"}
                          </td>
                          <td className="py-2 px-3 text-cream-600 font-mono text-[11px]">
                            {s.warehouse?.warehouse_name || "Dispatched"}
                          </td>
                          <td className="py-2 px-3 text-center">
                            <span
                              className={`rounded px-1.5 py-0.2 text-[9px] font-semibold ${
                                s.status === "ACTIVE"
                                  ? "bg-emerald-100 text-emerald-800"
                                  : "bg-blue-100 text-blue-800"
                              }`}
                            >
                              {s.status}
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
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 5: FULFILLMENT & PICK LISTS */}
      {/* ========================================================================= */}
      {activeTab === "fulfillment" && (
        <div className="space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-cream-900">Warehouse Picking Lists & Packing Slips</h2>
              <p className="text-[11px] text-cream-600">
                Order fulfillment pick routes, picking status, and carton packing manifests.
              </p>
            </div>
            <button
              onClick={() => {
                if (items.length > 0) setPlItemId(items[0].item_id);
                if (warehouses.length > 0) setPlWhId(warehouses[0].warehouse_id);
                if (customers.length > 0) setPlCustomerId(customers[0].customer_id);
                setShowPickModal(true);
              }}
              className="flex items-center gap-1.5 rounded-md bg-cream-900 px-3 py-1.5 text-xs font-medium text-cream-50 hover:bg-cream-800 transition-colors"
            >
              <Plus className="h-3.5 w-3.5" />
              <span>New Pick List</span>
            </button>
          </div>

          <div className="rounded-xl border border-cream-300 bg-cream-100 overflow-hidden shadow-xs">
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-cream-300 bg-cream-200/50 text-cream-700 font-medium">
                    <th className="py-2.5 px-3">Pick List Number</th>
                    <th className="py-2.5 px-3">Customer</th>
                    <th className="py-2.5 px-3">Purpose</th>
                    <th className="py-2.5 px-3">Lines to Pick</th>
                    <th className="py-2.5 px-3 text-center">Status</th>
                    <th className="py-2.5 px-3 text-center">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-cream-200">
                  {pickLists.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="py-8 text-center text-cream-600 text-xs">
                        No pick lists generated. Click "New Pick List" to stage customer order picking.
                      </td>
                    </tr>
                  ) : (
                    pickLists.map((pl) => (
                      <tr key={pl.pick_list_id} className="hover:bg-cream-50/50 transition-colors">
                        <td className="py-2.5 px-3 font-mono font-medium text-cream-950">{pl.pick_list_number}</td>
                        <td className="py-2.5 px-3 text-cream-800">{pl.customer?.customer_name || "General Stock"}</td>
                        <td className="py-2.5 px-3 text-cream-600 font-mono text-[11px]">{pl.purpose}</td>
                        <td className="py-2.5 px-3 text-cream-700">
                          {pl.items?.map((it: any) => (
                            <div key={it.pick_item_id} className="font-mono text-[11px]">
                              {it.item?.item_code}: {it.picked_qty} / {it.qty_to_pick} picked
                            </div>
                          ))}
                        </td>
                        <td className="py-2.5 px-3 text-center">
                          <span
                            className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${
                              pl.status === "COMPLETED"
                                ? "bg-emerald-100 text-emerald-800"
                                : pl.status === "PICKING"
                                ? "bg-blue-100 text-blue-800"
                                : "bg-amber-100 text-amber-800"
                            }`}
                          >
                            {pl.status}
                          </span>
                        </td>
                        <td className="py-2.5 px-3 text-center">
                          {pl.status !== "COMPLETED" && (
                            <div className="flex items-center justify-center gap-1">
                              {pl.items?.[0] && (
                                <button
                                  onClick={() =>
                                    handlePickLine(
                                      pl.pick_list_id,
                                      pl.items[0].pick_item_id,
                                      parseFloat(pl.items[0].qty_to_pick)
                                    )
                                  }
                                  className="rounded bg-blue-600 px-2 py-1 text-[10px] font-medium text-white hover:bg-blue-700 transition-colors"
                                >
                                  Pick All
                                </button>
                              )}
                              <button
                                onClick={() => handleCompletePick(pl.pick_list_id)}
                                className="rounded bg-emerald-600 px-2 py-1 text-[10px] font-medium text-white hover:bg-emerald-700 transition-colors"
                              >
                                Complete
                              </button>
                            </div>
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

      {/* ========================================================================= */}
      {/* TAB 6: DELIVERY LOGISTICS */}
      {/* ========================================================================= */}
      {activeTab === "delivery" && (
        <div className="space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-cream-900">Multi-Stop Delivery Route Dispatch</h2>
              <p className="text-[11px] text-cream-600">
                Driver assignments, multi-stop tracking, and proof-of-delivery signatures.
              </p>
            </div>
            <button
              onClick={() => setShowTripModal(true)}
              className="flex items-center gap-1.5 rounded-md bg-cream-900 px-3 py-1.5 text-xs font-medium text-cream-50 hover:bg-cream-800 transition-colors"
            >
              <Plus className="h-3.5 w-3.5" />
              <span>Plan Delivery Route</span>
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {deliveryTrips.length === 0 ? (
              <div className="col-span-full rounded-xl border border-cream-300 bg-cream-100 p-8 text-center text-cream-600 text-xs">
                No active delivery routes scheduled. Click "Plan Delivery Route" to dispatch vehicles.
              </div>
            ) : (
              deliveryTrips.map((trip) => (
                <div
                  key={trip.trip_id}
                  className="rounded-xl border border-cream-300 bg-cream-100 p-4 space-y-3 shadow-xs"
                >
                  <div className="flex items-center justify-between border-b border-cream-200 pb-2">
                    <span className="font-mono font-bold text-cream-950 text-xs">{trip.trip_number}</span>
                    <span
                      className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${
                        trip.status === "COMPLETED"
                          ? "bg-emerald-100 text-emerald-800"
                          : trip.status === "IN_TRANSIT"
                          ? "bg-blue-100 text-blue-800"
                          : "bg-amber-100 text-amber-800"
                      }`}
                    >
                      {trip.status}
                    </span>
                  </div>

                  <div className="text-xs space-y-1 text-cream-800">
                    <div className="flex items-center gap-1.5">
                      <Truck className="h-3.5 w-3.5 text-cream-500" />
                      <span>{trip.vehicle_number} &bull; {trip.driver_name}</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <MapPin className="h-3.5 w-3.5 text-cream-500" />
                      <span>{trip.total_distance_km} km estimated</span>
                    </div>
                  </div>

                  {/* Stops list */}
                  <div className="pt-2 border-t border-cream-200 space-y-2">
                    <div className="text-[11px] font-semibold text-cream-700">Delivery Stops:</div>
                    {trip.stops?.map((stop: any) => (
                      <div
                        key={stop.stop_id}
                        className="flex items-center justify-between rounded bg-cream-200/50 p-2 text-[11px]"
                      >
                        <div className="truncate max-w-[180px]">
                          <span className="font-bold text-cream-900">#{stop.stop_sequence}: </span>
                          <span className="text-cream-700">{stop.address}</span>
                        </div>
                        {stop.status === "DELIVERED" ? (
                          <span className="text-emerald-700 font-bold flex items-center gap-1">
                            <CheckCircle2 className="h-3 w-3" /> Done
                          </span>
                        ) : (
                          <button
                            onClick={() => handleCompleteStop(trip.trip_id, stop.stop_id)}
                            className="rounded bg-emerald-600 px-2 py-0.5 text-[10px] font-medium text-white hover:bg-emerald-700 transition-colors"
                          >
                            Confirm Drop
                          </button>
                        )}
                      </div>
                    ))}
                  </div>

                  {/* Trip Actions */}
                  <div className="pt-2 flex items-center justify-end gap-2">
                    {trip.status === "DRAFT" && (
                      <button
                        onClick={() => handleDispatchTrip(trip.trip_id)}
                        className="rounded bg-blue-600 px-3 py-1 text-xs font-medium text-white hover:bg-blue-700 transition-colors"
                      >
                        Dispatch Vehicle
                      </button>
                    )}
                    {trip.status === "IN_TRANSIT" && (
                      <button
                        onClick={() => api.completeDeliveryTrip(trip.trip_id).then(loadAll)}
                        className="rounded bg-emerald-600 px-3 py-1 text-xs font-medium text-white hover:bg-emerald-700 transition-colors"
                      >
                        Complete Trip
                      </button>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* MODALS */}
      {/* ========================================================================= */}

      {/* New Item Modal */}
      {showItemModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="w-full max-w-md rounded-xl border border-cream-300 bg-cream-100 p-6 shadow-xl space-y-4">
            <h3 className="text-sm font-semibold text-cream-900">Create Catalog Item</h3>
            <form onSubmit={handleCreateItem} className="space-y-3 text-xs">
              <div>
                <label className="block text-cream-700 mb-1">Item Code</label>
                <input
                  type="text"
                  required
                  value={itemCode}
                  onChange={(e) => setItemCode(e.target.value)}
                  placeholder="e.g. COMP-MOTOR-500W"
                  className="w-full rounded border border-cream-300 bg-white px-2.5 py-1.5 font-mono text-xs"
                />
              </div>
              <div>
                <label className="block text-cream-700 mb-1">Item Name</label>
                <input
                  type="text"
                  required
                  value={itemName}
                  onChange={(e) => setItemName(e.target.value)}
                  placeholder="e.g. 500W Brushless DC Motor"
                  className="w-full rounded border border-cream-300 bg-white px-2.5 py-1.5 text-xs"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-cream-700 mb-1">Stock UOM</label>
                  <input
                    type="text"
                    value={stockUom}
                    onChange={(e) => setStockUom(e.target.value)}
                    className="w-full rounded border border-cream-300 bg-white px-2.5 py-1.5 text-xs"
                  />
                </div>
                <div>
                  <label className="block text-cream-700 mb-1">Standard Rate ($)</label>
                  <input
                    type="number"
                    step="0.01"
                    value={standardRate}
                    onChange={(e) => setStandardRate(e.target.value)}
                    className="w-full rounded border border-cream-300 bg-white px-2.5 py-1.5 text-xs"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-cream-700 mb-1">Initial Stock Qty</label>
                  <input
                    type="number"
                    value={initialQty}
                    onChange={(e) => setInitialQty(e.target.value)}
                    className="w-full rounded border border-cream-300 bg-white px-2.5 py-1.5 text-xs"
                  />
                </div>
                <div>
                  <label className="block text-cream-700 mb-1">Safety Reorder Level</label>
                  <input
                    type="number"
                    value={reorderLevel}
                    onChange={(e) => setReorderLevel(e.target.value)}
                    className="w-full rounded border border-cream-300 bg-white px-2.5 py-1.5 text-xs"
                  />
                </div>
              </div>
              <div className="flex justify-end gap-2 pt-3 border-t border-cream-200">
                <button
                  type="button"
                  onClick={() => setShowItemModal(false)}
                  className="rounded px-3 py-1.5 text-cream-700 hover:bg-cream-200 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="rounded bg-cream-900 px-4 py-1.5 font-medium text-cream-50 hover:bg-cream-800 transition-colors"
                >
                  Save Item
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* New Stock Entry Modal */}
      {showEntryModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="w-full max-w-md rounded-xl border border-cream-300 bg-cream-100 p-6 shadow-xl space-y-4">
            <h3 className="text-sm font-semibold text-cream-900">Record Stock Movement</h3>
            <form onSubmit={handleCreateStockEntry} className="space-y-3 text-xs">
              <div>
                <label className="block text-cream-700 mb-1">Movement Type</label>
                <select
                  value={entryType}
                  onChange={(e) => setEntryType(e.target.value)}
                  className="w-full rounded border border-cream-300 bg-white px-2.5 py-1.5 text-xs"
                >
                  <option value="MATERIAL_TRANSFER">Material Transfer (Warehouse to Warehouse)</option>
                  <option value="MATERIAL_RECEIPT">Material Receipt (Inbound Inventory)</option>
                  <option value="MATERIAL_ISSUE">Material Issue (Internal Write-Off / Scrap)</option>
                </select>
              </div>

              <div>
                <label className="block text-cream-700 mb-1">Select Item</label>
                <select
                  value={entryItemId}
                  onChange={(e) => setEntryItemId(e.target.value)}
                  className="w-full rounded border border-cream-300 bg-white px-2.5 py-1.5 text-xs font-mono"
                >
                  {items.map((it) => (
                    <option key={it.item_id} value={it.item_id}>
                      {it.item_code} - {it.item_name}
                    </option>
                  ))}
                </select>
              </div>

              {entryType !== "MATERIAL_RECEIPT" && (
                <div>
                  <label className="block text-cream-700 mb-1">Source Warehouse</label>
                  <select
                    value={fromWhId}
                    onChange={(e) => setFromWhId(e.target.value)}
                    className="w-full rounded border border-cream-300 bg-white px-2.5 py-1.5 text-xs"
                  >
                    {warehouses.map((w) => (
                      <option key={w.warehouse_id} value={w.warehouse_id}>
                        {w.warehouse_name} ({w.warehouse_code})
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {entryType !== "MATERIAL_ISSUE" && (
                <div>
                  <label className="block text-cream-700 mb-1">Target Warehouse</label>
                  <select
                    value={toWhId}
                    onChange={(e) => setToWhId(e.target.value)}
                    className="w-full rounded border border-cream-300 bg-white px-2.5 py-1.5 text-xs"
                  >
                    {warehouses.map((w) => (
                      <option key={w.warehouse_id} value={w.warehouse_id}>
                        {w.warehouse_name} ({w.warehouse_code})
                      </option>
                    ))}
                  </select>
                </div>
              )}

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-cream-700 mb-1">Quantity</label>
                  <input
                    type="number"
                    step="0.01"
                    required
                    value={entryQty}
                    onChange={(e) => setEntryQty(e.target.value)}
                    className="w-full rounded border border-cream-300 bg-white px-2.5 py-1.5 text-xs"
                  />
                </div>
                <div>
                  <label className="block text-cream-700 mb-1">Basic Rate ($)</label>
                  <input
                    type="number"
                    step="0.01"
                    value={entryRate}
                    onChange={(e) => setEntryRate(e.target.value)}
                    className="w-full rounded border border-cream-300 bg-white px-2.5 py-1.5 text-xs"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-cream-700 mb-1">Batch No (Optional)</label>
                  <input
                    type="text"
                    value={entryBatchNo}
                    onChange={(e) => setEntryBatchNo(e.target.value)}
                    placeholder="e.g. BAT-2026-X1"
                    className="w-full rounded border border-cream-300 bg-white px-2.5 py-1.5 text-xs font-mono"
                  />
                </div>
                <div>
                  <label className="block text-cream-700 mb-1">Serial No (Optional)</label>
                  <input
                    type="text"
                    value={entrySerialNo}
                    onChange={(e) => setEntrySerialNo(e.target.value)}
                    placeholder="e.g. SN-0981"
                    className="w-full rounded border border-cream-300 bg-white px-2.5 py-1.5 text-xs font-mono"
                  />
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-cream-200">
                <button
                  type="button"
                  onClick={() => setShowEntryModal(false)}
                  className="rounded px-3 py-1.5 text-cream-700 hover:bg-cream-200 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="rounded bg-cream-900 px-4 py-1.5 font-medium text-cream-50 hover:bg-cream-800 transition-colors"
                >
                  Draft Movement
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* New Reconciliation Modal */}
      {showReconModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="w-full max-w-md rounded-xl border border-cream-300 bg-cream-100 p-6 shadow-xl space-y-4">
            <h3 className="text-sm font-semibold text-cream-900">Physical Stock Count Audit</h3>
            <form onSubmit={handleCreateReconciliation} className="space-y-3 text-xs">
              <div>
                <label className="block text-cream-700 mb-1">Audited Warehouse</label>
                <select
                  value={reconWhId}
                  onChange={(e) => setReconWhId(e.target.value)}
                  className="w-full rounded border border-cream-300 bg-white px-2.5 py-1.5 text-xs"
                >
                  {warehouses.map((w) => (
                    <option key={w.warehouse_id} value={w.warehouse_id}>
                      {w.warehouse_name} ({w.warehouse_code})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-cream-700 mb-1">Item to Count</label>
                <select
                  value={reconItemId}
                  onChange={(e) => setReconItemId(e.target.value)}
                  className="w-full rounded border border-cream-300 bg-white px-2.5 py-1.5 text-xs font-mono"
                >
                  {items.map((it) => (
                    <option key={it.item_id} value={it.item_id}>
                      {it.item_code} - {it.item_name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-cream-700 mb-1">Actual Physical Count</label>
                  <input
                    type="number"
                    step="0.01"
                    required
                    value={reconPhysicalQty}
                    onChange={(e) => setReconPhysicalQty(e.target.value)}
                    className="w-full rounded border border-cream-300 bg-white px-2.5 py-1.5 text-xs font-bold font-mono"
                  />
                </div>
                <div>
                  <label className="block text-cream-700 mb-1">Valuation Rate ($)</label>
                  <input
                    type="number"
                    step="0.01"
                    value={reconRate}
                    onChange={(e) => setReconRate(e.target.value)}
                    className="w-full rounded border border-cream-300 bg-white px-2.5 py-1.5 text-xs font-mono"
                  />
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-cream-200">
                <button
                  type="button"
                  onClick={() => setShowReconModal(false)}
                  className="rounded px-3 py-1.5 text-cream-700 hover:bg-cream-200 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="rounded bg-cream-900 px-4 py-1.5 font-medium text-cream-50 hover:bg-cream-800 transition-colors"
                >
                  Draft Audit
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* New Batch Modal */}
      {showBatchModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="w-full max-w-sm rounded-xl border border-cream-300 bg-cream-100 p-6 shadow-xl space-y-4">
            <h3 className="text-sm font-semibold text-cream-900">Register Production Batch</h3>
            <form onSubmit={handleCreateBatch} className="space-y-3 text-xs">
              <div>
                <label className="block text-cream-700 mb-1">Batch Number</label>
                <input
                  type="text"
                  required
                  value={batchNo}
                  onChange={(e) => setBatchNo(e.target.value)}
                  placeholder="e.g. LOT-2026-B1"
                  className="w-full rounded border border-cream-300 bg-white px-2.5 py-1.5 text-xs font-mono"
                />
              </div>
              <div>
                <label className="block text-cream-700 mb-1">Item</label>
                <select
                  value={batchItemId}
                  onChange={(e) => setBatchItemId(e.target.value)}
                  className="w-full rounded border border-cream-300 bg-white px-2.5 py-1.5 text-xs font-mono"
                >
                  {items.map((it) => (
                    <option key={it.item_id} value={it.item_id}>
                      {it.item_code}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-cream-700 mb-1">Shelf Life (Days to Expiry)</label>
                <input
                  type="number"
                  value={batchExpiryDays}
                  onChange={(e) => setBatchExpiryDays(e.target.value)}
                  className="w-full rounded border border-cream-300 bg-white px-2.5 py-1.5 text-xs"
                />
              </div>
              <div className="flex justify-end gap-2 pt-3 border-t border-cream-200">
                <button
                  type="button"
                  onClick={() => setShowBatchModal(false)}
                  className="rounded px-3 py-1.5 text-cream-700 hover:bg-cream-200 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="rounded bg-cream-900 px-4 py-1.5 font-medium text-cream-50 hover:bg-cream-800 transition-colors"
                >
                  Save Batch
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* New Serial Modal */}
      {showSerialModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="w-full max-w-sm rounded-xl border border-cream-300 bg-cream-100 p-6 shadow-xl space-y-4">
            <h3 className="text-sm font-semibold text-cream-900">Register Serial Number</h3>
            <form onSubmit={handleCreateSerial} className="space-y-3 text-xs">
              <div>
                <label className="block text-cream-700 mb-1">Serial Number</label>
                <input
                  type="text"
                  required
                  value={serialNo}
                  onChange={(e) => setSerialNo(e.target.value)}
                  placeholder="e.g. SN-AERO-9901"
                  className="w-full rounded border border-cream-300 bg-white px-2.5 py-1.5 text-xs font-mono"
                />
              </div>
              <div>
                <label className="block text-cream-700 mb-1">Item</label>
                <select
                  value={serialItemId}
                  onChange={(e) => setSerialItemId(e.target.value)}
                  className="w-full rounded border border-cream-300 bg-white px-2.5 py-1.5 text-xs font-mono"
                >
                  {items.map((it) => (
                    <option key={it.item_id} value={it.item_id}>
                      {it.item_code}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-cream-700 mb-1">Storage Warehouse</label>
                <select
                  value={serialWhId}
                  onChange={(e) => setSerialWhId(e.target.value)}
                  className="w-full rounded border border-cream-300 bg-white px-2.5 py-1.5 text-xs"
                >
                  {warehouses.map((w) => (
                    <option key={w.warehouse_id} value={w.warehouse_id}>
                      {w.warehouse_name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex justify-end gap-2 pt-3 border-t border-cream-200">
                <button
                  type="button"
                  onClick={() => setShowSerialModal(false)}
                  className="rounded px-3 py-1.5 text-cream-700 hover:bg-cream-200 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="rounded bg-cream-900 px-4 py-1.5 font-medium text-cream-50 hover:bg-cream-800 transition-colors"
                >
                  Save Serial
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* New Pick List Modal */}
      {showPickModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="w-full max-w-md rounded-xl border border-cream-300 bg-cream-100 p-6 shadow-xl space-y-4">
            <h3 className="text-sm font-semibold text-cream-900">Create Warehouse Pick List</h3>
            <form onSubmit={handleCreatePickList} className="space-y-3 text-xs">
              <div>
                <label className="block text-cream-700 mb-1">Customer</label>
                <select
                  value={plCustomerId}
                  onChange={(e) => setPlCustomerId(e.target.value)}
                  className="w-full rounded border border-cream-300 bg-white px-2.5 py-1.5 text-xs"
                >
                  <option value="">General Demand</option>
                  {customers.map((c) => (
                    <option key={c.customer_id} value={c.customer_id}>
                      {c.customer_name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-cream-700 mb-1">Item to Pick</label>
                <select
                  value={plItemId}
                  onChange={(e) => setPlItemId(e.target.value)}
                  className="w-full rounded border border-cream-300 bg-white px-2.5 py-1.5 text-xs font-mono"
                >
                  {items.map((it) => (
                    <option key={it.item_id} value={it.item_id}>
                      {it.item_code} - {it.item_name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-cream-700 mb-1">Pick Location (Warehouse)</label>
                <select
                  value={plWhId}
                  onChange={(e) => setPlWhId(e.target.value)}
                  className="w-full rounded border border-cream-300 bg-white px-2.5 py-1.5 text-xs"
                >
                  {warehouses.map((w) => (
                    <option key={w.warehouse_id} value={w.warehouse_id}>
                      {w.warehouse_name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-cream-700 mb-1">Quantity to Pick</label>
                <input
                  type="number"
                  required
                  value={plQty}
                  onChange={(e) => setPlQty(e.target.value)}
                  className="w-full rounded border border-cream-300 bg-white px-2.5 py-1.5 text-xs font-mono"
                />
              </div>
              <div className="flex justify-end gap-2 pt-3 border-t border-cream-200">
                <button
                  type="button"
                  onClick={() => setShowPickModal(false)}
                  className="rounded px-3 py-1.5 text-cream-700 hover:bg-cream-200 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="rounded bg-cream-900 px-4 py-1.5 font-medium text-cream-50 hover:bg-cream-800 transition-colors"
                >
                  Generate Pick List
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* New Delivery Trip Modal */}
      {showTripModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="w-full max-w-md rounded-xl border border-cream-300 bg-cream-100 p-6 shadow-xl space-y-4">
            <h3 className="text-sm font-semibold text-cream-900">Plan Delivery Route</h3>
            <form onSubmit={handleCreateTrip} className="space-y-3 text-xs">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-cream-700 mb-1">Driver Name</label>
                  <input
                    type="text"
                    required
                    value={tripDriver}
                    onChange={(e) => setTripDriver(e.target.value)}
                    placeholder="e.g. Tariq Mansoor"
                    className="w-full rounded border border-cream-300 bg-white px-2.5 py-1.5 text-xs"
                  />
                </div>
                <div>
                  <label className="block text-cream-700 mb-1">Vehicle License</label>
                  <input
                    type="text"
                    required
                    value={tripVehicle}
                    onChange={(e) => setTripVehicle(e.target.value)}
                    placeholder="e.g. TRK-9821"
                    className="w-full rounded border border-cream-300 bg-white px-2.5 py-1.5 text-xs font-mono"
                  />
                </div>
              </div>
              <div>
                <label className="block text-cream-700 mb-1">Destination Address (Stop 1)</label>
                <input
                  type="text"
                  required
                  value={tripAddress}
                  onChange={(e) => setTripAddress(e.target.value)}
                  placeholder="e.g. Sector I-9 Industrial Area"
                  className="w-full rounded border border-cream-300 bg-white px-2.5 py-1.5 text-xs"
                />
              </div>
              <div>
                <label className="block text-cream-700 mb-1">Estimated Distance (km)</label>
                <input
                  type="number"
                  value={tripDistance}
                  onChange={(e) => setTripDistance(e.target.value)}
                  className="w-full rounded border border-cream-300 bg-white px-2.5 py-1.5 text-xs font-mono"
                />
              </div>
              <div className="flex justify-end gap-2 pt-3 border-t border-cream-200">
                <button
                  type="button"
                  onClick={() => setShowTripModal(false)}
                  className="rounded px-3 py-1.5 text-cream-700 hover:bg-cream-200 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="rounded bg-cream-900 px-4 py-1.5 font-medium text-cream-50 hover:bg-cream-800 transition-colors"
                >
                  Create Route
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Generate Variant Modal */}
      {showVariantModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="w-full max-w-sm rounded-xl border border-cream-300 bg-cream-100 p-6 shadow-xl space-y-4">
            <h3 className="text-sm font-semibold text-cream-900">
              Generate Variant for {showVariantModal.item_code}
            </h3>
            <form onSubmit={handleGenerateVariants} className="space-y-3 text-xs">
              <div>
                <label className="block text-cream-700 mb-1">Attribute Name</label>
                <input
                  type="text"
                  required
                  value={variantAttrKey}
                  onChange={(e) => setVariantAttrKey(e.target.value)}
                  placeholder="e.g. Size, Color, Grade"
                  className="w-full rounded border border-cream-300 bg-white px-2.5 py-1.5 text-xs"
                />
              </div>
              <div>
                <label className="block text-cream-700 mb-1">Attribute Value</label>
                <input
                  type="text"
                  required
                  value={variantAttrVal}
                  onChange={(e) => setVariantAttrVal(e.target.value)}
                  placeholder="e.g. Large, Red, Grade-A"
                  className="w-full rounded border border-cream-300 bg-white px-2.5 py-1.5 text-xs"
                />
              </div>
              <div className="flex justify-end gap-2 pt-3 border-t border-cream-200">
                <button
                  type="button"
                  onClick={() => setShowVariantModal(null)}
                  className="rounded px-3 py-1.5 text-cream-700 hover:bg-cream-200 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="rounded bg-purple-900 px-4 py-1.5 font-medium text-purple-50 hover:bg-purple-800 transition-colors"
                >
                  Generate SKU
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
