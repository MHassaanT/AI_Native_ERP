"use client";

import { useEffect, useState } from "react";
import {
  Truck,
  Plus,
  RefreshCw,
  Search,
  CheckCircle2,
  Clock,
  ArrowRight,
  Layers,
  Building2,
  X,
  FileCheck,
  AlertCircle,
  Package,
} from "lucide-react";
import { api } from "@/lib/api";

type TabType = "orders" | "receipts";

export default function SubcontractingPage() {
  const [activeTab, setActiveTab] = useState<TabType>("orders");
  const [orders, setOrders] = useState<any[]>([]);
  const [receipts, setReceipts] = useState<any[]>([]);
  const [suppliers, setSuppliers] = useState<any[]>([]);
  const [warehouses, setWarehouses] = useState<any[]>([]);
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Modals
  const [showOrderModal, setShowOrderModal] = useState(false);
  const [showTransferModal, setShowTransferModal] = useState(false);
  const [showReceiptModal, setShowReceiptModal] = useState(false);
  const [selectedOrder, setSelectedOrder] = useState<any | null>(null);

  // Transfer Form
  const [transferQty, setTransferQty] = useState("10");
  const [transferRawId, setTransferRawId] = useState("");
  const [transferSourceWh, setTransferSourceWh] = useState("");
  const [transferTargetWh, setTransferTargetWh] = useState("");

  // Receipt Form
  const [receiptScrNumber, setReceiptScrNumber] = useState("");
  const [receiptTargetWh, setReceiptTargetWh] = useState("");
  const [receiptQty, setReceiptQty] = useState("10");
  const [receiptServiceRate, setReceiptServiceRate] = useState("25.00");

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [ordList, recList, supList, whList, itList] = await Promise.all([
        api.getSubcontractingOrders(),
        api.getSubcontractingReceipts(),
        api.getSuppliers ? api.getSuppliers() : Promise.resolve([]),
        api.getWarehouses ? api.getWarehouses() : Promise.resolve([]),
        api.getItems ? api.getItems() : Promise.resolve([]),
      ]);
      setOrders(ordList || []);
      setReceipts(recList || []);
      setSuppliers(supList || []);
      setWarehouses(whList || []);
      setItems(itList || []);
    } catch (err: any) {
      console.error(err);
      setError(err.message || "Failed to load subcontracting records");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [activeTab]);

  const handleSubmitOrder = async (scoId: string) => {
    try {
      await api.submitSubcontractingOrder(scoId);
      await loadData();
    } catch (err: any) {
      alert("Error submitting order: " + err.message);
    }
  };

  const handleTransferMaterials = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedOrder) return;
    try {
      await api.transferSubcontractingMaterials(selectedOrder.sco_id, {
        transfers: [
          {
            raw_item_id: transferRawId,
            quantity: Number(transferQty),
            source_warehouse_id: transferSourceWh,
            supplier_warehouse_id: transferTargetWh,
          },
        ],
      });
      setShowTransferModal(false);
      await loadData();
    } catch (err: any) {
      alert("Transfer error: " + err.message);
    }
  };

  const handleCreateReceipt = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedOrder) return;
    try {
      const fgItem = selectedOrder.items?.[0];
      await api.createSubcontractingReceipt({
        scr_number: receiptScrNumber || `SCR-2026-${Math.floor(1000 + Math.random() * 9000)}`,
        sco_id: selectedOrder.sco_id,
        target_warehouse_id: receiptTargetWh,
        finished_items_received: [
          {
            item_id: fgItem?.item_id,
            quantity_received: Number(receiptQty),
            service_rate: Number(receiptServiceRate),
          },
        ],
      });
      setShowReceiptModal(false);
      await loadData();
    } catch (err: any) {
      alert("Receipt error: " + err.message);
    }
  };

  return (
    <div className="min-h-screen bg-[#FDFBF7] text-[#2D2A26] p-6 lg:p-10">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between pb-6 border-b border-[#E5E0D8] gap-4">
        <div className="flex items-center gap-3">
          <span className="p-2.5 rounded-xl bg-[#2D2A26] text-[#FDFBF7] shadow-sm">
            <Truck className="w-5 h-5" />
          </span>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-[#1A1816]">
              Subcontracting Operations Hub
            </h1>
            <p className="text-sm text-[#736B63] mt-0.5">
              Outsourced manufacturing, raw material issuance to vendor warehouses & finished goods valuation rollup
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={loadData}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-2 bg-white hover:bg-[#F7F4EE] border border-[#E5E0D8] rounded-xl text-xs font-medium transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 text-[#736B63] ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-2 mt-6 pb-2 border-b border-[#E5E0D8]">
        <button
          onClick={() => setActiveTab("orders")}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-medium transition-all ${
            activeTab === "orders"
              ? "bg-[#2D2A26] text-[#FDFBF7] shadow-sm"
              : "bg-white text-[#736B63] hover:text-[#2D2A26] border border-[#E5E0D8]"
          }`}
        >
          <Package className="w-3.5 h-3.5" />
          Subcontracting Orders ({orders.length})
        </button>
        <button
          onClick={() => setActiveTab("receipts")}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-medium transition-all ${
            activeTab === "receipts"
              ? "bg-[#2D2A26] text-[#FDFBF7] shadow-sm"
              : "bg-white text-[#736B63] hover:text-[#2D2A26] border border-[#E5E0D8]"
          }`}
        >
          <FileCheck className="w-3.5 h-3.5" />
          Finished Goods Receipts ({receipts.length})
        </button>
      </div>

      {/* Orders Tab */}
      {activeTab === "orders" && (
        <div className="mt-6 space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {orders.map((o) => (
              <div key={o.sco_id} className="bg-white rounded-2xl border border-[#E5E0D8] p-5 space-y-4 shadow-sm">
                <div className="flex justify-between items-start">
                  <div>
                    <span className="font-mono text-sm font-bold text-[#1A1816]">{o.sco_number}</span>
                    <p className="text-xs text-[#736B63] mt-0.5 font-medium">{o.supplier_name || "Supplier: " + o.supplier_id.slice(0, 8)}</p>
                  </div>
                  <span className={`px-2.5 py-1 rounded-full text-[10px] font-semibold tracking-wider ${
                    o.status === "COMPLETED"
                      ? "bg-emerald-100 text-emerald-800"
                      : o.status === "IN_PROCESS"
                      ? "bg-blue-100 text-blue-800"
                      : o.status === "SUBMITTED"
                      ? "bg-amber-100 text-amber-800"
                      : "bg-gray-100 text-gray-700"
                  }`}>
                    {o.status}
                  </span>
                </div>

                {/* Finished items */}
                <div className="space-y-1">
                  <span className="text-[10px] font-semibold text-[#736B63] uppercase tracking-wider">Finished Goods Line</span>
                  {o.items?.map((it: any, idx: number) => (
                    <div key={idx} className="flex justify-between text-xs py-1 border-b border-[#FAF7F0]">
                      <span className="font-mono text-[#1A1816]">{it.item_code || it.item_name || "FG Item"}</span>
                      <span className="font-bold text-[#1A1816]">{it.quantity} Nos @ ${it.unit_price}</span>
                    </div>
                  ))}
                </div>

                {/* Supplied Components Progress */}
                <div className="space-y-1">
                  <span className="text-[10px] font-semibold text-[#736B63] uppercase tracking-wider">Supplied Components</span>
                  <div className="space-y-1">
                    {o.supplied_items?.map((s: any, idx: number) => (
                      <div key={idx} className="text-xs flex justify-between text-[#736B63]">
                        <span>{s.raw_item_code || "Component"}</span>
                        <span>{Number(s.supplied_qty)} / {Number(s.required_qty)} Supplied ({Number(s.consumed_qty)} Consumed)</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Action Buttons */}
                <div className="pt-2 flex flex-wrap gap-2 border-t border-[#E5E0D8]">
                  {o.status === "DRAFT" && (
                    <button
                      onClick={() => handleSubmitOrder(o.sco_id)}
                      className="px-3 py-1.5 bg-[#2D2A26] text-[#FDFBF7] rounded-xl text-xs font-medium hover:bg-[#1A1816] transition-colors"
                    >
                      Submit Order
                    </button>
                  )}
                  {o.status === "SUBMITTED" && (
                    <button
                      onClick={() => {
                        setSelectedOrder(o);
                        setTransferRawId(o.supplied_items?.[0]?.raw_item_id || "");
                        setShowTransferModal(true);
                      }}
                      className="px-3 py-1.5 bg-blue-700 text-white rounded-xl text-xs font-medium hover:bg-blue-800 transition-colors"
                    >
                      Transfer Materials
                    </button>
                  )}
                  {o.status === "IN_PROCESS" && (
                    <button
                      onClick={() => {
                        setSelectedOrder(o);
                        setShowReceiptModal(true);
                      }}
                      className="px-3 py-1.5 bg-emerald-700 text-white rounded-xl text-xs font-medium hover:bg-emerald-800 transition-colors"
                    >
                      Receive Finished Goods
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Receipts Tab */}
      {activeTab === "receipts" && (
        <div className="mt-6 bg-white rounded-2xl border border-[#E5E0D8] overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-[#FAF7F0] border-b border-[#E5E0D8] text-[#736B63]">
                <tr>
                  <th className="py-3 px-4 font-semibold">Receipt #</th>
                  <th className="py-3 px-4 font-semibold">Supplier</th>
                  <th className="py-3 px-4 font-semibold">Target Warehouse</th>
                  <th className="py-3 px-4 font-semibold">Date</th>
                  <th className="py-3 px-4 font-semibold">Finished Goods Received</th>
                  <th className="py-3 px-4 font-semibold">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E5E0D8]">
                {receipts.map((r) => (
                  <tr key={r.scr_id} className="hover:bg-[#FAF7F0] transition-colors">
                    <td className="py-3 px-4 font-mono font-bold text-[#1A1816]">{r.scr_number}</td>
                    <td className="py-3 px-4">{r.supplier_name || r.supplier_id.slice(0, 8)}</td>
                    <td className="py-3 px-4 font-medium">{r.target_warehouse_name || "Stores"}</td>
                    <td className="py-3 px-4 text-[#736B63]">{r.posting_date}</td>
                    <td className="py-3 px-4">
                      {r.items?.map((it: any, idx: number) => (
                        <span key={idx} className="font-semibold text-[#1A1816]">
                          {it.quantity_received} Nos ({it.item_code || "FG"})
                        </span>
                      ))}
                    </td>
                    <td className="py-3 px-4">
                      <span className="px-2.5 py-0.5 bg-emerald-100 text-emerald-800 rounded-full font-semibold text-[10px]">
                        {r.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Transfer Material Modal */}
      {showTransferModal && selectedOrder && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <form onSubmit={handleTransferMaterials} className="bg-white rounded-2xl border border-[#E5E0D8] max-w-md w-full p-6 shadow-xl space-y-4">
            <h3 className="font-semibold text-base text-[#1A1816]">Transfer Components to Subcontractor</h3>
            <p className="text-xs text-[#736B63]">Order: {selectedOrder.sco_number}</p>
            <div>
              <label className="block text-xs font-medium text-[#736B63] mb-1">Raw Component</label>
              <select
                value={transferRawId}
                onChange={(e) => setTransferRawId(e.target.value)}
                className="w-full px-3 py-2 bg-[#FAF7F0] border border-[#E5E0D8] rounded-xl text-xs text-[#2D2A26]"
              >
                {selectedOrder.supplied_items?.map((s: any) => (
                  <option key={s.raw_item_id} value={s.raw_item_id}>
                    {s.raw_item_code || s.raw_item_id} (Req: {s.required_qty})
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-[#736B63] mb-1">Transfer Quantity</label>
              <input
                type="number"
                step="0.01"
                required
                value={transferQty}
                onChange={(e) => setTransferQty(e.target.value)}
                className="w-full px-3 py-2 bg-[#FAF7F0] border border-[#E5E0D8] rounded-xl text-xs text-[#2D2A26]"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-[#736B63] mb-1">Source Warehouse (Main Stores)</label>
              <select
                value={transferSourceWh}
                onChange={(e) => setTransferSourceWh(e.target.value)}
                className="w-full px-3 py-2 bg-[#FAF7F0] border border-[#E5E0D8] rounded-xl text-xs text-[#2D2A26]"
              >
                <option value="">Select Warehouse...</option>
                {warehouses.map((wh) => (
                  <option key={wh.warehouse_id} value={wh.warehouse_id}>
                    {wh.warehouse_name || wh.warehouse_code}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-[#736B63] mb-1">Subcontractor Vendor Warehouse</label>
              <select
                value={transferTargetWh}
                onChange={(e) => setTransferTargetWh(e.target.value)}
                className="w-full px-3 py-2 bg-[#FAF7F0] border border-[#E5E0D8] rounded-xl text-xs text-[#2D2A26]"
              >
                <option value="">Select Vendor Floor Warehouse...</option>
                {warehouses.map((wh) => (
                  <option key={wh.warehouse_id} value={wh.warehouse_id}>
                    {wh.warehouse_name || wh.warehouse_code}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setShowTransferModal(false)}
                className="px-3.5 py-2 bg-white hover:bg-[#F7F4EE] border border-[#E5E0D8] rounded-xl text-xs font-medium text-[#736B63]"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-4 py-2 bg-blue-700 hover:bg-blue-800 text-white rounded-xl text-xs font-semibold"
              >
                Dispatch Components
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Subcontracting Receipt Modal */}
      {showReceiptModal && selectedOrder && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <form onSubmit={handleCreateReceipt} className="bg-white rounded-2xl border border-[#E5E0D8] max-w-md w-full p-6 shadow-xl space-y-4">
            <h3 className="font-semibold text-base text-[#1A1816]">Receive Finished Goods</h3>
            <p className="text-xs text-[#736B63]">
              Order: {selectedOrder.sco_number}. Automatically consumes components from subcontractor warehouse and rolls up finished goods valuation.
            </p>
            <div>
              <label className="block text-xs font-medium text-[#736B63] mb-1">Target Warehouse (Finished Goods)</label>
              <select
                required
                value={receiptTargetWh}
                onChange={(e) => setReceiptTargetWh(e.target.value)}
                className="w-full px-3 py-2 bg-[#FAF7F0] border border-[#E5E0D8] rounded-xl text-xs text-[#2D2A26]"
              >
                <option value="">Select Warehouse...</option>
                {warehouses.map((wh) => (
                  <option key={wh.warehouse_id} value={wh.warehouse_id}>
                    {wh.warehouse_name || wh.warehouse_code}
                  </option>
                ))}
              </select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-[#736B63] mb-1">Quantity Received</label>
                <input
                  type="number"
                  step="0.01"
                  required
                  value={receiptQty}
                  onChange={(e) => setReceiptQty(e.target.value)}
                  className="w-full px-3 py-2 bg-[#FAF7F0] border border-[#E5E0D8] rounded-xl text-xs text-[#2D2A26]"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-[#736B63] mb-1">Service Fee ($/unit)</label>
                <input
                  type="number"
                  step="0.01"
                  required
                  value={receiptServiceRate}
                  onChange={(e) => setReceiptServiceRate(e.target.value)}
                  className="w-full px-3 py-2 bg-[#FAF7F0] border border-[#E5E0D8] rounded-xl text-xs text-[#2D2A26]"
                />
              </div>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setShowReceiptModal(false)}
                className="px-3.5 py-2 bg-white hover:bg-[#F7F4EE] border border-[#E5E0D8] rounded-xl text-xs font-medium text-[#736B63]"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-4 py-2 bg-emerald-700 hover:bg-emerald-800 text-white rounded-xl text-xs font-semibold"
              >
                Ingest & Consume
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
