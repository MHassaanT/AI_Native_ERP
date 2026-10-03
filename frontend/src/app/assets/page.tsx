"use client";

import { useEffect, useState } from "react";
import {
  Building2,
  Plus,
  RefreshCw,
  Search,
  Filter,
  ArrowRight,
  TrendingDown,
  CheckCircle2,
  AlertCircle,
  Clock,
  Layers,
  Wrench,
  Truck,
  Trash2,
  DollarSign,
  Calendar,
  X,
  FileText,
} from "lucide-react";
import { api } from "@/lib/api";

type TabType = "registry" | "categories" | "locations";

export default function AssetsPage() {
  const [activeTab, setActiveTab] = useState<TabType>("registry");
  const [assets, setAssets] = useState<any[]>([]);
  const [categories, setCategories] = useState<any[]>([]);
  const [locations, setLocations] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  // Detailed Asset View Drawer/Modal
  const [selectedAsset, setSelectedAsset] = useState<any | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  // Modals
  const [showAssetModal, setShowAssetModal] = useState(false);
  const [showCategoryModal, setShowCategoryModal] = useState(false);
  const [showLocationModal, setShowLocationModal] = useState(false);
  const [showMovementModal, setShowMovementModal] = useState(false);
  const [showRepairModal, setShowRepairModal] = useState(false);

  // Form states
  const [formAsset, setFormAsset] = useState({
    asset_code: "",
    asset_name: "",
    asset_category_id: "",
    purchase_date: new Date().toISOString().split("T")[0],
    available_for_use_date: new Date().toISOString().split("T")[0],
    gross_purchase_amount: "50000.00",
    salvage_value: "5000.00",
    location_id: "",
    notes: "",
  });

  const [formCat, setFormCat] = useState({
    category_name: "",
    depreciation_method: "STRAIGHT_LINE",
    total_number_of_depreciations: 24,
    frequency_in_months: 1,
    fixed_asset_account: "1500-FIXED-ASSETS",
    accumulated_depreciation_account: "1550-ACCUMULATED-DEPRECIATION",
    depreciation_expense_account: "5200-DEP-MACHINERY",
  });

  const [formLoc, setFormLoc] = useState({
    location_name: "",
  });

  const [formMove, setFormMove] = useState({
    to_location_id: "",
    purpose: "",
  });

  const [formRepair, setFormRepair] = useState({
    repair_cost: "1200.00",
    repair_description: "Precision spindle alignment & calibration",
    is_capitalized: false,
  });

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [aData, cData, lData] = await Promise.all([
        api.getAssets(),
        api.getAssetCategories(),
        api.getAssetLocations(),
      ]);
      setAssets(aData);
      setCategories(cData);
      setLocations(lData);
      if (cData.length > 0 && !formAsset.asset_category_id) {
        setFormAsset((prev) => ({ ...prev, asset_category_id: cData[0].category_id }));
      }
    } catch (err: any) {
      setError(err.message || "Failed to load assets data.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const openAssetDetail = async (assetId: string) => {
    setLoadingDetail(true);
    try {
      const data = await api.getAsset(assetId);
      setSelectedAsset(data);
    } catch (err: any) {
      alert("Failed to load asset details: " + err.message);
    } finally {
      setLoadingDetail(false);
    }
  };

  const handlePostDepreciation = async (scheduleId: string) => {
    try {
      await api.postAssetDepreciation(scheduleId);
      if (selectedAsset) {
        await openAssetDetail(selectedAsset.asset_id);
      }
      await loadData();
    } catch (err: any) {
      alert("Failed to post depreciation: " + err.message);
    }
  };

  const handleCreateAsset = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.createAsset({
        ...formAsset,
        gross_purchase_amount: parseFloat(formAsset.gross_purchase_amount),
        salvage_value: parseFloat(formAsset.salvage_value),
        location_id: formAsset.location_id || undefined,
      });
      setShowAssetModal(false);
      setFormAsset({
        asset_code: "",
        asset_name: "",
        asset_category_id: categories[0]?.category_id || "",
        purchase_date: new Date().toISOString().split("T")[0],
        available_for_use_date: new Date().toISOString().split("T")[0],
        gross_purchase_amount: "50000.00",
        salvage_value: "5000.00",
        location_id: "",
        notes: "",
      });
      await loadData();
    } catch (err: any) {
      alert("Error registering asset: " + err.message);
    }
  };

  const handleCreateCategory = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.createAssetCategory({
        ...formCat,
        total_number_of_depreciations: parseInt(formCat.total_number_of_depreciations.toString()),
        frequency_in_months: parseInt(formCat.frequency_in_months.toString()),
      });
      setShowCategoryModal(false);
      await loadData();
    } catch (err: any) {
      alert("Error creating category: " + err.message);
    }
  };

  const handleCreateLocation = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.createAssetLocation(formLoc);
      setShowLocationModal(false);
      setFormLoc({ location_name: "" });
      await loadData();
    } catch (err: any) {
      alert("Error creating location: " + err.message);
    }
  };

  const handleRecordMovement = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedAsset) return;
    try {
      await api.moveAsset(selectedAsset.asset_id, {
        to_location_id: formMove.to_location_id || undefined,
        purpose: formMove.purpose,
      });
      setShowMovementModal(false);
      await openAssetDetail(selectedAsset.asset_id);
      await loadData();
    } catch (err: any) {
      alert("Error recording movement: " + err.message);
    }
  };

  const handleRecordRepair = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedAsset) return;
    try {
      await api.repairAsset(selectedAsset.asset_id, {
        repair_cost: parseFloat(formRepair.repair_cost),
        repair_description: formRepair.repair_description,
        is_capitalized: formRepair.is_capitalized,
      });
      setShowRepairModal(false);
      await openAssetDetail(selectedAsset.asset_id);
      await loadData();
    } catch (err: any) {
      alert("Error recording repair: " + err.message);
    }
  };

  const handleScrapAsset = async () => {
    if (!selectedAsset) return;
    if (!confirm(`Are you sure you want to decommission and scrap asset ${selectedAsset.asset_code}? This writes off remaining book value to General Ledger loss on disposal.`)) return;
    try {
      await api.scrapAsset(selectedAsset.asset_id, { notes: "Decommissioned via web console" });
      await openAssetDetail(selectedAsset.asset_id);
      await loadData();
    } catch (err: any) {
      alert("Error scrapping asset: " + err.message);
    }
  };

  // Metrics
  const totalAssetsCount = assets.length;
  const totalGrossValue = assets.reduce((acc, a) => acc + (a.gross_purchase_amount || 0), 0);
  const totalBookValue = assets.reduce((acc, a) => acc + (a.current_book_value || 0), 0);
  const totalAccumDep = assets.reduce((acc, a) => acc + (a.accumulated_depreciation || 0), 0);

  const filteredAssets = assets.filter(
    (a) =>
      a.asset_code.toLowerCase().includes(search.toLowerCase()) ||
      a.asset_name.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-stone-900 text-white flex items-center justify-center shadow-sm">
              <Building2 className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-2xl font-semibold text-stone-900 tracking-tight">Fixed Assets & Depreciation</h1>
              <p className="text-sm text-stone-500">
                Asset register, multi-method amortization schedules, GL postings, transfers & repair capitalization.
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
            onClick={() => setShowCategoryModal(true)}
            className="px-3.5 py-2 text-sm font-medium text-stone-700 bg-white border border-stone-300 hover:bg-stone-50 rounded-lg shadow-sm"
          >
            New Category
          </button>
          <button
            onClick={() => setShowLocationModal(true)}
            className="px-3.5 py-2 text-sm font-medium text-stone-700 bg-white border border-stone-300 hover:bg-stone-50 rounded-lg shadow-sm"
          >
            New Location
          </button>
          <button
            onClick={() => setShowAssetModal(true)}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-stone-900 hover:bg-stone-800 rounded-lg shadow-sm"
          >
            <Plus className="w-4 h-4" />
            Register Asset
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white border border-stone-200/80 rounded-xl p-5 shadow-sm">
          <div className="text-xs font-medium text-stone-500 uppercase tracking-wider">Registered Assets</div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-stone-900">{totalAssetsCount}</span>
            <span className="text-xs text-stone-500">Units in Registry</span>
          </div>
        </div>
        <div className="bg-white border border-stone-200/80 rounded-xl p-5 shadow-sm">
          <div className="text-xs font-medium text-stone-500 uppercase tracking-wider">Total Gross Value</div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-stone-900">${totalGrossValue.toLocaleString("en-US", { minimumFractionDigits: 2 })}</span>
          </div>
        </div>
        <div className="bg-white border border-stone-200/80 rounded-xl p-5 shadow-sm">
          <div className="text-xs font-medium text-stone-500 uppercase tracking-wider">Net Book Value</div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-emerald-700">${totalBookValue.toLocaleString("en-US", { minimumFractionDigits: 2 })}</span>
          </div>
        </div>
        <div className="bg-white border border-stone-200/80 rounded-xl p-5 shadow-sm">
          <div className="text-xs font-medium text-stone-500 uppercase tracking-wider">Accumulated Depreciation</div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-amber-700">${totalAccumDep.toLocaleString("en-US", { minimumFractionDigits: 2 })}</span>
          </div>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="flex border-b border-stone-200 gap-6">
        <button
          onClick={() => setActiveTab("registry")}
          className={`pb-3 text-sm font-medium border-b-2 transition-colors ${
            activeTab === "registry"
              ? "border-stone-900 text-stone-900"
              : "border-transparent text-stone-500 hover:text-stone-800"
          }`}
        >
          Asset Registry ({assets.length})
        </button>
        <button
          onClick={() => setActiveTab("categories")}
          className={`pb-3 text-sm font-medium border-b-2 transition-colors ${
            activeTab === "categories"
              ? "border-stone-900 text-stone-900"
              : "border-transparent text-stone-500 hover:text-stone-800"
          }`}
        >
          Categories ({categories.length})
        </button>
        <button
          onClick={() => setActiveTab("locations")}
          className={`pb-3 text-sm font-medium border-b-2 transition-colors ${
            activeTab === "locations"
              ? "border-stone-900 text-stone-900"
              : "border-transparent text-stone-500 hover:text-stone-800"
          }`}
        >
          Locations ({locations.length})
        </button>
      </div>

      {/* Tab 1: Asset Registry */}
      {activeTab === "registry" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between gap-4">
            <div className="relative flex-1 max-w-sm">
              <Search className="absolute left-3 top-2.5 w-4 h-4 text-stone-400" />
              <input
                type="text"
                placeholder="Search assets by code or name..."
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
                    <th className="px-6 py-3.5">Asset Code</th>
                    <th className="px-6 py-3.5">Asset Name</th>
                    <th className="px-6 py-3.5">Category</th>
                    <th className="px-6 py-3.5">Purchase Date</th>
                    <th className="px-6 py-3.5 text-right">Gross Cost</th>
                    <th className="px-6 py-3.5 text-right">Book Value</th>
                    <th className="px-6 py-3.5 text-center">Status</th>
                    <th className="px-6 py-3.5 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-200/60">
                  {filteredAssets.length === 0 ? (
                    <tr>
                      <td colSpan={8} className="px-6 py-12 text-center text-stone-500">
                        No assets registered yet. Click &quot;Register Asset&quot; to begin.
                      </td>
                    </tr>
                  ) : (
                    filteredAssets.map((asset) => (
                      <tr key={asset.asset_id} className="hover:bg-stone-50/50 transition-colors">
                        <td className="px-6 py-4 font-mono font-medium text-stone-900">{asset.asset_code}</td>
                        <td className="px-6 py-4 font-medium text-stone-900">{asset.asset_name}</td>
                        <td className="px-6 py-4 text-stone-600">{asset.category_name || "—"}</td>
                        <td className="px-6 py-4 text-stone-500">{asset.purchase_date}</td>
                        <td className="px-6 py-4 text-right font-medium text-stone-900">
                          ${asset.gross_purchase_amount?.toLocaleString("en-US", { minimumFractionDigits: 2 })}
                        </td>
                        <td className="px-6 py-4 text-right font-medium text-emerald-700">
                          ${asset.current_book_value?.toLocaleString("en-US", { minimumFractionDigits: 2 })}
                        </td>
                        <td className="px-6 py-4 text-center">
                          <span
                            className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${
                              asset.status === "IN_USE"
                                ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                                : asset.status === "SUBMITTED"
                                ? "bg-blue-50 text-blue-700 border border-blue-200"
                                : asset.status === "SCRAPPED"
                                ? "bg-stone-100 text-stone-600 border border-stone-300"
                                : "bg-amber-50 text-amber-700 border border-amber-200"
                            }`}
                          >
                            {asset.status}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-right">
                          <button
                            onClick={() => openAssetDetail(asset.asset_id)}
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-stone-700 bg-stone-100 hover:bg-stone-200 rounded-lg transition-colors"
                          >
                            View Lifecycle
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

      {/* Tab 2: Categories */}
      {activeTab === "categories" && (
        <div className="bg-white border border-stone-200/80 rounded-xl overflow-hidden shadow-sm">
          <table className="w-full text-left text-sm text-stone-600">
            <thead className="bg-stone-50/75 border-b border-stone-200 text-xs font-semibold text-stone-600 uppercase tracking-wider">
              <tr>
                <th className="px-6 py-3.5">Category Name</th>
                <th className="px-6 py-3.5">Method</th>
                <th className="px-6 py-3.5">Total Periods</th>
                <th className="px-6 py-3.5">Asset Account</th>
                <th className="px-6 py-3.5">Accumulated Dep. Account</th>
                <th className="px-6 py-3.5">Expense Account</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-stone-200/60">
              {categories.map((c) => (
                <tr key={c.category_id} className="hover:bg-stone-50/50">
                  <td className="px-6 py-4 font-medium text-stone-900">{c.category_name}</td>
                  <td className="px-6 py-4 font-mono text-xs">{c.depreciation_method}</td>
                  <td className="px-6 py-4">{c.total_number_of_depreciations} months</td>
                  <td className="px-6 py-4 font-mono text-xs text-stone-500">{c.fixed_asset_account}</td>
                  <td className="px-6 py-4 font-mono text-xs text-stone-500">{c.accumulated_depreciation_account}</td>
                  <td className="px-6 py-4 font-mono text-xs text-stone-500">{c.depreciation_expense_account}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Tab 3: Locations */}
      {activeTab === "locations" && (
        <div className="bg-white border border-stone-200/80 rounded-xl overflow-hidden shadow-sm">
          <table className="w-full text-left text-sm text-stone-600">
            <thead className="bg-stone-50/75 border-b border-stone-200 text-xs font-semibold text-stone-600 uppercase tracking-wider">
              <tr>
                <th className="px-6 py-3.5">Location Name</th>
                <th className="px-6 py-3.5">Location ID</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-stone-200/60">
              {locations.map((l) => (
                <tr key={l.location_id} className="hover:bg-stone-50/50">
                  <td className="px-6 py-4 font-medium text-stone-900">{l.location_name}</td>
                  <td className="px-6 py-4 font-mono text-xs text-stone-400">{l.location_id}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Asset Lifecycle Detail Drawer */}
      {selectedAsset && (
        <div className="fixed inset-0 z-50 bg-stone-900/40 backdrop-blur-sm flex justify-end">
          <div className="bg-white w-full max-w-2xl h-full shadow-2xl p-6 overflow-y-auto space-y-6">
            <div className="flex items-center justify-between pb-4 border-b border-stone-200">
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs px-2 py-0.5 rounded bg-stone-100 text-stone-700 font-semibold">
                    {selectedAsset.asset_code}
                  </span>
                  <span
                    className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${
                      selectedAsset.status === "IN_USE"
                        ? "bg-emerald-50 text-emerald-700"
                        : selectedAsset.status === "SCRAPPED"
                        ? "bg-stone-100 text-stone-600"
                        : "bg-blue-50 text-blue-700"
                    }`}
                  >
                    {selectedAsset.status}
                  </span>
                </div>
                <h2 className="text-xl font-bold text-stone-900 mt-1">{selectedAsset.asset_name}</h2>
              </div>
              <button
                onClick={() => setSelectedAsset(null)}
                className="p-2 text-stone-400 hover:text-stone-600 rounded-lg hover:bg-stone-100"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Quick Actions */}
            <div className="flex gap-2.5">
              <button
                onClick={() => setShowMovementModal(true)}
                disabled={selectedAsset.status === "SCRAPPED"}
                className="flex-1 py-2 text-xs font-medium text-stone-700 bg-stone-50 border border-stone-200 hover:bg-stone-100 rounded-lg flex items-center justify-center gap-1.5"
              >
                <Truck className="w-3.5 h-3.5" />
                Transfer Bay
              </button>
              <button
                onClick={() => setShowRepairModal(true)}
                disabled={selectedAsset.status === "SCRAPPED"}
                className="flex-1 py-2 text-xs font-medium text-stone-700 bg-stone-50 border border-stone-200 hover:bg-stone-100 rounded-lg flex items-center justify-center gap-1.5"
              >
                <Wrench className="w-3.5 h-3.5" />
                Record Repair
              </button>
              <button
                onClick={handleScrapAsset}
                disabled={selectedAsset.status === "SCRAPPED"}
                className="py-2 px-3 text-xs font-medium text-rose-700 bg-rose-50 border border-rose-200 hover:bg-rose-100 rounded-lg flex items-center justify-center gap-1.5"
              >
                <Trash2 className="w-3.5 h-3.5" />
                Scrap
              </button>
            </div>

            {/* Financial Summary */}
            <div className="grid grid-cols-3 gap-3 bg-stone-50 rounded-xl p-4 border border-stone-200">
              <div>
                <span className="text-xs text-stone-500">Gross Value</span>
                <p className="text-base font-bold text-stone-900 mt-0.5">
                  ${selectedAsset.gross_purchase_amount?.toLocaleString("en-US", { minimumFractionDigits: 2 })}
                </p>
              </div>
              <div>
                <span className="text-xs text-stone-500">Book Value</span>
                <p className="text-base font-bold text-emerald-700 mt-0.5">
                  ${selectedAsset.current_book_value?.toLocaleString("en-US", { minimumFractionDigits: 2 })}
                </p>
              </div>
              <div>
                <span className="text-xs text-stone-500">Accumulated Dep.</span>
                <p className="text-base font-bold text-amber-700 mt-0.5">
                  ${selectedAsset.accumulated_depreciation?.toLocaleString("en-US", { minimumFractionDigits: 2 })}
                </p>
              </div>
            </div>

            {/* Depreciation Schedule */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold text-stone-900">Depreciation Schedule</h3>
                <span className="text-xs text-stone-500">{selectedAsset.schedules?.length || 0} Periods</span>
              </div>
              <div className="border border-stone-200 rounded-lg overflow-hidden max-h-64 overflow-y-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-stone-50 border-b border-stone-200 text-stone-600 font-semibold sticky top-0">
                    <tr>
                      <th className="px-3 py-2">Schedule Date</th>
                      <th className="px-3 py-2 text-right">Depreciation</th>
                      <th className="px-3 py-2 text-right">Book Value</th>
                      <th className="px-3 py-2 text-center">Status</th>
                      <th className="px-3 py-2 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-stone-100">
                    {selectedAsset.schedules?.map((s: any) => (
                      <tr key={s.schedule_id} className="hover:bg-stone-50">
                        <td className="px-3 py-2 font-mono text-stone-700">{s.schedule_date}</td>
                        <td className="px-3 py-2 text-right font-medium text-stone-900">
                          ${s.depreciation_amount?.toLocaleString("en-US", { minimumFractionDigits: 2 })}
                        </td>
                        <td className="px-3 py-2 text-right text-stone-600">
                          ${s.book_value_after_depreciation?.toLocaleString("en-US", { minimumFractionDigits: 2 })}
                        </td>
                        <td className="px-3 py-2 text-center">
                          {s.is_posted ? (
                            <span className="inline-flex items-center gap-1 text-emerald-700 text-2xs font-semibold">
                              <CheckCircle2 className="w-3 h-3" /> POSTED
                            </span>
                          ) : (
                            <span className="text-stone-400 text-2xs">UNPOSTED</span>
                          )}
                        </td>
                        <td className="px-3 py-2 text-right">
                          {!s.is_posted && (
                            <button
                              onClick={() => handlePostDepreciation(s.schedule_id)}
                              className="px-2 py-0.5 text-2xs font-medium text-white bg-stone-900 hover:bg-stone-800 rounded shadow-xs"
                            >
                              Post to GL
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Movements History */}
            <div className="space-y-3">
              <h3 className="text-sm font-semibold text-stone-900">Movement & Transfer History</h3>
              {selectedAsset.movements?.length === 0 ? (
                <p className="text-xs text-stone-500 italic">No transfers recorded.</p>
              ) : (
                <div className="divide-y divide-stone-100 border border-stone-200 rounded-lg p-3 space-y-2">
                  {selectedAsset.movements?.map((m: any) => (
                    <div key={m.movement_id} className="pt-2 first:pt-0 text-xs">
                      <div className="flex justify-between font-medium text-stone-800">
                        <span>Transfer Date: {m.movement_date}</span>
                      </div>
                      <p className="text-stone-500 mt-0.5">Purpose: {m.purpose || "Operational rebalance"}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Repairs History */}
            <div className="space-y-3">
              <h3 className="text-sm font-semibold text-stone-900">Maintenance & Capitalized Repairs</h3>
              {selectedAsset.repairs?.length === 0 ? (
                <p className="text-xs text-stone-500 italic">No repairs recorded.</p>
              ) : (
                <div className="divide-y divide-stone-100 border border-stone-200 rounded-lg p-3 space-y-2">
                  {selectedAsset.repairs?.map((r: any) => (
                    <div key={r.repair_id} className="pt-2 first:pt-0 text-xs flex justify-between items-center">
                      <div>
                        <p className="font-medium text-stone-900">{r.repair_description}</p>
                        <span className="text-stone-500">{r.repair_date}</span>
                      </div>
                      <div className="text-right">
                        <span className="font-bold text-stone-900">${r.repair_cost?.toLocaleString("en-US", { minimumFractionDigits: 2 })}</span>
                        {r.is_capitalized && (
                          <span className="block text-2xs text-emerald-700 font-semibold">CAPITALIZED</span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Modal: Register Asset */}
      {showAssetModal && (
        <div className="fixed inset-0 z-50 bg-stone-900/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-lg w-full p-6 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-stone-200">
              <h3 className="text-lg font-bold text-stone-900">Register Fixed Asset</h3>
              <button onClick={() => setShowAssetModal(false)} className="text-stone-400 hover:text-stone-600">
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleCreateAsset} className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-stone-700 mb-1">Asset Code</label>
                  <input
                    type="text"
                    required
                    placeholder="AST-CNC-001"
                    value={formAsset.asset_code}
                    onChange={(e) => setFormAsset({ ...formAsset, asset_code: e.target.value })}
                    className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-stone-700 mb-1">Category</label>
                  <select
                    required
                    value={formAsset.asset_category_id}
                    onChange={(e) => setFormAsset({ ...formAsset, asset_category_id: e.target.value })}
                    className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg"
                  >
                    {categories.map((c) => (
                      <option key={c.category_id} value={c.category_id}>
                        {c.category_name} ({c.depreciation_method})
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-stone-700 mb-1">Asset Name</label>
                <input
                  type="text"
                  required
                  placeholder="5-Axis CNC Machining Center"
                  value={formAsset.asset_name}
                  onChange={(e) => setFormAsset({ ...formAsset, asset_name: e.target.value })}
                  className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-stone-700 mb-1">Gross Purchase Cost ($)</label>
                  <input
                    type="number"
                    step="0.01"
                    required
                    value={formAsset.gross_purchase_amount}
                    onChange={(e) => setFormAsset({ ...formAsset, gross_purchase_amount: e.target.value })}
                    className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-stone-700 mb-1">Salvage Value ($)</label>
                  <input
                    type="number"
                    step="0.01"
                    required
                    value={formAsset.salvage_value}
                    onChange={(e) => setFormAsset({ ...formAsset, salvage_value: e.target.value })}
                    className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-stone-700 mb-1">Purchase Date</label>
                  <input
                    type="date"
                    required
                    value={formAsset.purchase_date}
                    onChange={(e) => setFormAsset({ ...formAsset, purchase_date: e.target.value })}
                    className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-stone-700 mb-1">Available for Use Date</label>
                  <input
                    type="date"
                    required
                    value={formAsset.available_for_use_date}
                    onChange={(e) => setFormAsset({ ...formAsset, available_for_use_date: e.target.value })}
                    className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg"
                  />
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-stone-700 mb-1">Location Bay</label>
                <select
                  value={formAsset.location_id}
                  onChange={(e) => setFormAsset({ ...formAsset, location_id: e.target.value })}
                  className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg"
                >
                  <option value="">Unassigned Location</option>
                  {locations.map((l) => (
                    <option key={l.location_id} value={l.location_id}>
                      {l.location_name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="pt-3 flex justify-end gap-2 border-t border-stone-200">
                <button
                  type="button"
                  onClick={() => setShowAssetModal(false)}
                  className="px-4 py-2 text-sm text-stone-600 hover:bg-stone-100 rounded-lg"
                >
                  Cancel
                </button>
                <button type="submit" className="px-4 py-2 text-sm font-medium text-white bg-stone-900 rounded-lg hover:bg-stone-800">
                  Register & Generate Schedule
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: New Category */}
      {showCategoryModal && (
        <div className="fixed inset-0 z-50 bg-stone-900/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-6 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-stone-200">
              <h3 className="text-lg font-bold text-stone-900">New Asset Category</h3>
              <button onClick={() => setShowCategoryModal(false)} className="text-stone-400 hover:text-stone-600">
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleCreateCategory} className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-stone-700 mb-1">Category Name</label>
                <input
                  type="text"
                  required
                  placeholder="Heavy Machinery & Tooling"
                  value={formCat.category_name}
                  onChange={(e) => setFormCat({ ...formCat, category_name: e.target.value })}
                  className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-stone-700 mb-1">Depreciation Method</label>
                  <select
                    value={formCat.depreciation_method}
                    onChange={(e) => setFormCat({ ...formCat, depreciation_method: e.target.value })}
                    className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg"
                  >
                    <option value="STRAIGHT_LINE">Straight Line</option>
                    <option value="DOUBLE_DECLINING">Double Declining</option>
                    <option value="WRITTEN_DOWN_VALUE">Written Down Value</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-stone-700 mb-1">Total Periods (Months)</label>
                  <input
                    type="number"
                    required
                    value={formCat.total_number_of_depreciations}
                    onChange={(e) => setFormCat({ ...formCat, total_number_of_depreciations: parseInt(e.target.value) || 12 })}
                    className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg"
                  />
                </div>
              </div>
              <div className="pt-3 flex justify-end gap-2 border-t border-stone-200">
                <button
                  type="button"
                  onClick={() => setShowCategoryModal(false)}
                  className="px-4 py-2 text-sm text-stone-600 hover:bg-stone-100 rounded-lg"
                >
                  Cancel
                </button>
                <button type="submit" className="px-4 py-2 text-sm font-medium text-white bg-stone-900 rounded-lg hover:bg-stone-800">
                  Save Category
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: New Location */}
      {showLocationModal && (
        <div className="fixed inset-0 z-50 bg-stone-900/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-sm w-full p-6 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-stone-200">
              <h3 className="text-lg font-bold text-stone-900">Add Location Bay</h3>
              <button onClick={() => setShowLocationModal(false)} className="text-stone-400 hover:text-stone-600">
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleCreateLocation} className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-stone-700 mb-1">Location Name</label>
                <input
                  type="text"
                  required
                  placeholder="Plant 1 - Machining Bay B"
                  value={formLoc.location_name}
                  onChange={(e) => setFormLoc({ location_name: e.target.value })}
                  className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg"
                />
              </div>
              <div className="pt-3 flex justify-end gap-2 border-t border-stone-200">
                <button
                  type="button"
                  onClick={() => setShowLocationModal(false)}
                  className="px-4 py-2 text-sm text-stone-600 hover:bg-stone-100 rounded-lg"
                >
                  Cancel
                </button>
                <button type="submit" className="px-4 py-2 text-sm font-medium text-white bg-stone-900 rounded-lg hover:bg-stone-800">
                  Save Location
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Record Transfer Movement */}
      {showMovementModal && (
        <div className="fixed inset-0 z-50 bg-stone-900/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-sm w-full p-6 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-stone-200">
              <h3 className="text-lg font-bold text-stone-900">Transfer Asset</h3>
              <button onClick={() => setShowMovementModal(false)} className="text-stone-400 hover:text-stone-600">
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleRecordMovement} className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-stone-700 mb-1">Destination Bay</label>
                <select
                  required
                  value={formMove.to_location_id}
                  onChange={(e) => setFormMove({ ...formMove, to_location_id: e.target.value })}
                  className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg"
                >
                  <option value="">Select Location</option>
                  {locations.map((l) => (
                    <option key={l.location_id} value={l.location_id}>
                      {l.location_name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-stone-700 mb-1">Transfer Reason</label>
                <input
                  type="text"
                  placeholder="Line rebalancing for aerospace order"
                  value={formMove.purpose}
                  onChange={(e) => setFormMove({ ...formMove, purpose: e.target.value })}
                  className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg"
                />
              </div>
              <div className="pt-3 flex justify-end gap-2 border-t border-stone-200">
                <button
                  type="button"
                  onClick={() => setShowMovementModal(false)}
                  className="px-4 py-2 text-sm text-stone-600 hover:bg-stone-100 rounded-lg"
                >
                  Cancel
                </button>
                <button type="submit" className="px-4 py-2 text-sm font-medium text-white bg-stone-900 rounded-lg hover:bg-stone-800">
                  Log Transfer
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Record Repair */}
      {showRepairModal && (
        <div className="fixed inset-0 z-50 bg-stone-900/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-sm w-full p-6 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-stone-200">
              <h3 className="text-lg font-bold text-stone-900">Record Asset Repair</h3>
              <button onClick={() => setShowRepairModal(false)} className="text-stone-400 hover:text-stone-600">
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleRecordRepair} className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-stone-700 mb-1">Repair Cost ($)</label>
                <input
                  type="number"
                  step="0.01"
                  required
                  value={formRepair.repair_cost}
                  onChange={(e) => setFormRepair({ ...formRepair, repair_cost: e.target.value })}
                  className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-stone-700 mb-1">Repair Description</label>
                <textarea
                  required
                  rows={3}
                  value={formRepair.repair_description}
                  onChange={(e) => setFormRepair({ ...formRepair, repair_description: e.target.value })}
                  className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg"
                />
              </div>
              <div className="flex items-center gap-2 pt-1">
                <input
                  type="checkbox"
                  id="is_capitalized"
                  checked={formRepair.is_capitalized}
                  onChange={(e) => setFormRepair({ ...formRepair, is_capitalized: e.target.checked })}
                  className="w-4 h-4 rounded text-stone-900"
                />
                <label htmlFor="is_capitalized" className="text-xs text-stone-700 font-medium">
                  Capitalize cost into Asset Book Value
                </label>
              </div>
              <div className="pt-3 flex justify-end gap-2 border-t border-stone-200">
                <button
                  type="button"
                  onClick={() => setShowRepairModal(false)}
                  className="px-4 py-2 text-sm text-stone-600 hover:bg-stone-100 rounded-lg"
                >
                  Cancel
                </button>
                <button type="submit" className="px-4 py-2 text-sm font-medium text-white bg-stone-900 rounded-lg hover:bg-stone-800">
                  Save Repair Record
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
