"use client";

import { useEffect, useState } from "react";
import { Layers, Plus, RefreshCw, AlertCircle, Sparkles, CheckCircle2, ArrowUpDown } from "lucide-react";
import { api } from "@/lib/api";

export default function InventoryPage() {
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // New Item Modal
  const [showModal, setShowModal] = useState(false);
  const [itemCode, setItemCode] = useState("");
  const [itemName, setItemName] = useState("");
  const [stockUom, setStockUom] = useState("Kg");
  const [standardRate, setStandardRate] = useState("10.00");
  const [initialQty, setInitialQty] = useState("500");
  const [reorderLevel, setReorderLevel] = useState("100");
  const [creating, setCreating] = useState(false);

  // ROP Modal / State
  const [ropItemCode, setRopItemCode] = useState("RAW-RESIN-HDPE");
  const [ropResult, setRopResult] = useState<any | null>(null);
  const [calculatingRop, setCalculatingRop] = useState(false);

  // Replenishment Action State
  const [replenishingId, setReplenishingId] = useState<string | null>(null);
  const [replenishResult, setReplenishResult] = useState<any | null>(null);

  const loadItems = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getItems();
      setItems(data);
    } catch (err: any) {
      setError(err.message || "Failed to load inventory items from database.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadItems();
  }, []);

  const handleCreateItem = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreating(true);
    try {
      await api.createItem({
        item_code: itemCode.trim().toUpperCase(),
        item_name: itemName.trim(),
        stock_uom: stockUom,
        standard_rate: parseFloat(standardRate),
        initial_qty: parseFloat(initialQty),
        reorder_level: parseFloat(reorderLevel),
      });

      setShowModal(false);
      setItemCode("");
      setItemName("");
      await loadItems();
    } catch (err: any) {
      setError(err.message || "Failed to create catalog item.");
    } finally {
      setCreating(false);
    }
  };

  const handleCalculateROP = async () => {
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

  const handleTriggerReplenishment = async (itemId: string) => {
    setReplenishingId(itemId);
    setError(null);
    try {
      const res = await api.triggerReplenishment(itemId);
      setReplenishResult(res);
      await loadItems();
    } catch (err: any) {
      setError(err.message || "Replenishment trigger failed.");
    } finally {
      setReplenishingId(null);
    }
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between border-b border-cream-300 pb-5">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-cream-900">
            Dynamic Inventory & Stochastic ROP Replenishment
          </h1>
          <p className="text-xs text-cream-700 mt-1">
            Real-time stock ledger, safety stock buffers with 99.0% service availability, and autonomous procurement.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={loadItems}
            disabled={loading}
            className="flex items-center gap-1.5 rounded-md border border-cream-300 bg-cream-100 px-3 py-1.5 text-xs font-medium text-cream-800 hover:bg-cream-200 transition-colors"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
            <span>Refresh</span>
          </button>
          <button
            onClick={() => setShowModal(true)}
            className="flex items-center gap-1.5 rounded-md border border-cream-400 bg-cream-900 px-3 py-1.5 text-xs font-medium text-cream-50 hover:bg-cream-800 transition-colors"
          >
            <Plus className="h-3.5 w-3.5" />
            <span>Add Catalog Item</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-terracotta-50 border border-terracotta-500/30 text-terracotta-700 text-xs">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* ROP Simulation Result Banner */}
      {ropResult && (
        <div className="rounded-lg border border-sage-500/30 bg-sage-50 p-4 text-xs text-sage-900 space-y-1">
          <div className="font-semibold flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-sage-600" />
            <span>Stochastic ROP Result for {ropResult.item_code} (Z=2.33 &bull; 99% SL)</span>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 pt-2 font-mono text-[11px]">
            <div>Lead Time Demand: <span className="font-bold">{ropResult.lead_time_demand_mean}</span></div>
            <div>Safety Buffer: <span className="font-bold">{ropResult.safety_stock}</span></div>
            <div>Dynamic ROP: <span className="font-bold">{ropResult.reorder_point}</span></div>
            <div>Recommended EOQ: <span className="font-bold">{ropResult.economic_order_quantity}</span></div>
          </div>
        </div>
      )}

      {/* Replenish Trigger Banner */}
      {replenishResult && (
        <div className="rounded-lg border border-cream-300 bg-cream-100 p-4 text-xs space-y-1">
          <div className="font-semibold text-cream-900">Replenishment Evaluation:</div>
          <p className="text-[11px] text-cream-700 font-mono">
            On-Hand: {replenishResult.current_on_hand} &bull; ROP: {replenishResult.reorder_point} &bull;{" "}
            {replenishResult.replenishment_triggered ? (
              <span className="text-sage-700 font-bold">Autonomous Purchase Order Generated ({replenishResult.purchase_order_number})</span>
            ) : (
              <span className="text-cream-600">Stock above ROP threshold. No procurement required.</span>
            )}
          </p>
        </div>
      )}

      {/* Stock Items Table */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-cream-900">Factory Floor & Warehouse Master Catalog</h2>
          <div className="flex items-center gap-2">
            <span className="text-xs text-cream-600 font-mono">{items.length} items</span>
            <button
              onClick={handleCalculateROP}
              disabled={calculatingRop}
              className="rounded border border-cream-300 bg-cream-200 px-2.5 py-1 text-[11px] font-medium text-cream-800 hover:bg-cream-300 transition-colors"
            >
              {calculatingRop ? "Calculating..." : "Compute Stochastic ROP (Z=2.33)"}
            </button>
          </div>
        </div>

        {items.length === 0 ? (
          <div className="rounded-xl border border-cream-300 bg-cream-100 p-8 text-center space-y-3">
            <Layers className="h-8 w-8 text-cream-400 mx-auto" />
            <div className="text-xs text-cream-800 font-medium">No items in warehouse catalog</div>
            <p className="text-[11px] text-cream-600 max-w-sm mx-auto">
              Add your raw materials, components, and finished goods to manage stock levels.
            </p>
          </div>
        ) : (
          <div className="rounded-xl border border-cream-300 bg-cream-100 overflow-hidden shadow-xs">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-cream-300 bg-cream-200/60 text-cream-800 font-medium text-[11px]">
                  <th className="py-2.5 px-4">SKU Code</th>
                  <th className="py-2.5 px-4">Item Name</th>
                  <th className="py-2.5 px-4">UOM</th>
                  <th className="py-2.5 px-4">Std Rate</th>
                  <th className="py-2.5 px-4">On-Hand Qty</th>
                  <th className="py-2.5 px-4">Available</th>
                  <th className="py-2.5 px-4">Reorder Point</th>
                  <th className="py-2.5 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-cream-200">
                {items.map((item) => (
                  <tr key={item.item_id} className="hover:bg-cream-50/50 transition-colors">
                    <td className="py-3 px-4 font-mono font-medium text-cream-900">{item.item_code}</td>
                    <td className="py-3 px-4 text-cream-800">{item.item_name}</td>
                    <td className="py-3 px-4 font-mono text-cream-600 text-[11px]">{item.stock_uom}</td>
                    <td className="py-3 px-4 font-mono text-cream-900">
                      ${parseFloat(item.standard_rate).toFixed(2)}
                    </td>
                    <td className="py-3 px-4 font-mono font-bold text-cream-900">
                      {parseFloat(item.current_qty).toFixed(0)} {item.stock_uom}
                    </td>
                    <td className="py-3 px-4 font-mono text-cream-700">
                      {parseFloat(item.available_qty).toFixed(0)}
                    </td>
                    <td className="py-3 px-4 font-mono text-cream-700">
                      {parseFloat(item.reorder_level).toFixed(0)}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <button
                        onClick={() => handleTriggerReplenishment(item.item_id)}
                        disabled={replenishingId === item.item_id}
                        className="rounded border border-cream-300 bg-cream-200 px-2.5 py-1 text-[11px] font-medium text-cream-800 hover:bg-cream-300 transition-colors disabled:opacity-50"
                      >
                        {replenishingId === item.item_id ? "Evaluating..." : "Evaluate ROP"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Modal: Add Catalog Item */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="w-full max-w-md rounded-xl border border-cream-300 bg-cream-100 p-6 shadow-lg space-y-4">
            <div className="flex items-center justify-between border-b border-cream-300 pb-3">
              <h3 className="font-semibold text-sm text-cream-900">Add Inventory Catalog Item</h3>
              <button onClick={() => setShowModal(false)} className="text-cream-600 hover:text-cream-900 text-xs">
                Cancel
              </button>
            </div>

            <form onSubmit={handleCreateItem} className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-cream-900 mb-1">Item Code (SKU)</label>
                <input
                  type="text"
                  required
                  value={itemCode}
                  onChange={(e) => setItemCode(e.target.value)}
                  placeholder="e.g. RAW-RESIN-PP"
                  className="w-full rounded-lg border border-cream-300 bg-cream-50 px-3 py-1.5 text-xs text-cream-900 font-mono"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-cream-900 mb-1">Item Name</label>
                <input
                  type="text"
                  required
                  value={itemName}
                  onChange={(e) => setItemName(e.target.value)}
                  placeholder="e.g. Polypropylene Pellets"
                  className="w-full rounded-lg border border-cream-300 bg-cream-50 px-3 py-1.5 text-xs text-cream-900"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-cream-900 mb-1">Stock UOM</label>
                  <input
                    type="text"
                    required
                    value={stockUom}
                    onChange={(e) => setStockUom(e.target.value)}
                    className="w-full rounded-lg border border-cream-300 bg-cream-50 px-3 py-1.5 text-xs text-cream-900 font-mono"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-cream-900 mb-1">Std Rate ($)</label>
                  <input
                    type="number"
                    step="0.01"
                    required
                    value={standardRate}
                    onChange={(e) => setStandardRate(e.target.value)}
                    className="w-full rounded-lg border border-cream-300 bg-cream-50 px-3 py-1.5 text-xs text-cream-900 font-mono"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-cream-900 mb-1">Initial Opening Qty</label>
                  <input
                    type="number"
                    required
                    value={initialQty}
                    onChange={(e) => setInitialQty(e.target.value)}
                    className="w-full rounded-lg border border-cream-300 bg-cream-50 px-3 py-1.5 text-xs text-cream-900 font-mono"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-cream-900 mb-1">Reorder Point (ROP)</label>
                  <input
                    type="number"
                    required
                    value={reorderLevel}
                    onChange={(e) => setReorderLevel(e.target.value)}
                    className="w-full rounded-lg border border-cream-300 bg-cream-50 px-3 py-1.5 text-xs text-cream-900 font-mono"
                  />
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-cream-300">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="rounded-lg border border-cream-300 bg-cream-200 px-3 py-1.5 text-xs font-medium text-cream-800"
                >
                  Close
                </button>
                <button
                  type="submit"
                  disabled={creating}
                  className="rounded-lg border border-cream-400 bg-cream-900 px-3 py-1.5 text-xs font-medium text-cream-50 hover:bg-cream-800 disabled:opacity-50"
                >
                  {creating ? "Saving..." : "Create Item"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
