"use client";

import { useEffect, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  DollarSign,
  Download,
  FileText,
  Plus,
  RefreshCw,
  TrendingUp,
  Users,
  ShieldCheck,
  Building,
} from "lucide-react";
import { api } from "@/lib/api";

interface Customer {
  customer_id: string;
  customer_code: string;
  customer_name: string;
  email?: string;
  credit_limit: number;
  lifetime_value: number;
  is_active: boolean;
}

interface SalesQuote {
  quotation_id: string;
  quotation_number: string;
  customer_id: string;
  quotation_date: string;
  valid_until: string;
  subtotal: number;
  tax_amount: number;
  total_amount: number;
  contribution_margin_pct: number;
  status: string;
}

interface CatalogItem {
  item_id: string;
  item_code: string;
  item_name: string;
  standard_rate: number;
}

export default function CommercialPage() {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [quotes, setQuotes] = useState<SalesQuote[]>([]);
  const [items, setItems] = useState<CatalogItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Dynamic Pricing State
  const [sku, setSku] = useState("AERO-TITANIUM-RIB");
  const [bomCost, setBomCost] = useState(48.5);
  const [depreciation, setDepreciation] = useState(4.5);
  const [labor, setLabor] = useState(6.0);
  const [freight, setFreight] = useState(1.25);
  const [markupMultiplier, setMarkupMultiplier] = useState(1.35);

  // Dynamic Pricing Computed State
  const [pricingEval, setPricingEval] = useState<any>(null);
  const [isCalculating, setIsCalculating] = useState(false);

  // Invalidation State
  const [invQuoteNumber, setInvQuoteNumber] = useState("QT-ACTIVE-001");
  const [invCustomer, setInvCustomer] = useState("Tesla Energy Inc.");
  const [invSku, setInvSku] = useState("AERO-TITANIUM-RIB");
  const [invCurrentPrice, setInvCurrentPrice] = useState(85.0);
  const [invNewBomCost, setInvNewBomCost] = useState(62.0);
  const [invalidationResult, setInvalidationResult] = useState<any>(null);
  const [isEvaluatingInv, setIsEvaluatingInv] = useState(false);

  // PDF Download State
  const [isDownloading, setIsDownloading] = useState(false);

  // Modals
  const [showCustomerModal, setShowCustomerModal] = useState(false);
  const [newCustCode, setNewCustCode] = useState("");
  const [newCustName, setNewCustName] = useState("");
  const [newCustEmail, setNewCustEmail] = useState("");
  const [newCustCredit, setNewCustCredit] = useState(50000);

  const [showQuoteModal, setShowQuoteModal] = useState(false);
  const [newQuoteNumber, setNewQuoteNumber] = useState(`QT-${new Date().getFullYear()}-${Math.floor(1000 + Math.random() * 9000)}`);
  const [selectedCustomerId, setSelectedCustomerId] = useState("");
  const [quoteSubtotal, setQuoteSubtotal] = useState(12500);
  const [quoteMargin, setQuoteMargin] = useState(25.0);

  const loadData = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const [custList, quoteList, itemList] = await Promise.all([
        api.getCustomers().catch(() => []),
        api.getQuotes().catch(() => []),
        api.getItems().catch(() => []),
      ]);
      setCustomers(custList || []);
      setQuotes(quoteList || []);
      setItems(itemList || []);
      if (custList && custList.length > 0) {
        setSelectedCustomerId(custList[0].customer_id);
        setInvCustomer(custList[0].customer_name);
      }
      if (itemList && itemList.length > 0) {
        setSku(itemList[0].item_code);
        setInvSku(itemList[0].item_code);
        setBomCost(Number(itemList[0].standard_rate) || 48.5);
      }
    } catch (err: any) {
      setError(err?.message || "Failed to load commercial records");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  // Recalculate Pricing via API
  const calculatePricing = async () => {
    try {
      setIsCalculating(true);
      const res = await api.calculateDynamicPricing({
        sku,
        bom_material_cost: bomCost,
        machine_depreciation: depreciation,
        direct_labor: labor,
        freight,
        target_markup_multiplier: markupMultiplier,
      });
      setPricingEval(res);
    } catch (err: any) {
      console.error("Pricing calculation error:", err);
    } finally {
      setIsCalculating(false);
    }
  };

  useEffect(() => {
    calculatePricing();
  }, [sku, bomCost, depreciation, labor, freight, markupMultiplier]);

  // Evaluate Quote Invalidation via API
  const evaluateInvalidation = async () => {
    try {
      setIsEvaluatingInv(true);
      const res = await api.evaluateQuoteInvalidation({
        quote_number: invQuoteNumber,
        customer_name: invCustomer,
        sku: invSku,
        current_quoted_price: invCurrentPrice,
        new_bom_material_cost: invNewBomCost,
      });
      setInvalidationResult(res);
    } catch (err: any) {
      console.error("Invalidation evaluation error:", err);
    } finally {
      setIsEvaluatingInv(false);
    }
  };

  useEffect(() => {
    evaluateInvalidation();
  }, [invQuoteNumber, invCustomer, invSku, invCurrentPrice, invNewBomCost]);

  // Client-side fallback computation if API is in-flight
  const totalLandedCost = pricingEval ? Number(pricingEval.total_landed_cost) : bomCost + depreciation + labor + freight;
  const floorPrice = pricingEval ? Number(pricingEval.minimum_floor_price ?? pricingEval.statutory_floor_price ?? (totalLandedCost / (1.0 - 0.22))) : totalLandedCost / (1.0 - 0.22);
  const effectivePrice = pricingEval ? Number(pricingEval.proposed_unit_price) : Math.max(totalLandedCost * markupMultiplier, floorPrice);
  const actualMarginPercent = pricingEval ? Number(pricingEval.computed_margin_percentage) : ((effectivePrice - totalLandedCost) / effectivePrice) * 100.0;
  const isFloorActive = pricingEval ? Boolean(pricingEval.requires_price_escalation ?? pricingEval.is_margin_floor_enforced) : (totalLandedCost * markupMultiplier) < floorPrice;

  // Handle Customer Creation
  const handleCreateCustomer = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newCustCode || !newCustName) return;
    try {
      await api.createCustomer({
        customer_code: newCustCode.trim().toUpperCase(),
        customer_name: newCustName.trim(),
        email: newCustEmail.trim() || undefined,
        credit_limit: Number(newCustCredit),
      });
      setShowCustomerModal(false);
      setNewCustCode("");
      setNewCustName("");
      setNewCustEmail("");
      await loadData();
    } catch (err: any) {
      alert("Failed to create customer: " + (err?.message || err));
    }
  };

  // Handle Sales Quote Creation
  const handleCreateQuote = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCustomerId) {
      alert("Please select a valid customer");
      return;
    }
    try {
      const today = new Date().toISOString().split("T")[0];
      const validUntil = new Date(Date.now() + 30 * 86400000).toISOString().split("T")[0];
      await api.createQuote({
        quotation_number: newQuoteNumber.trim(),
        customer_id: selectedCustomerId,
        quotation_date: today,
        valid_until: validUntil,
        subtotal: Number(quoteSubtotal),
        tax_amount: 0,
        contribution_margin_pct: Number(quoteMargin),
      });
      setShowQuoteModal(false);
      setNewQuoteNumber(`QT-${new Date().getFullYear()}-${Math.floor(1000 + Math.random() * 9000)}`);
      await loadData();
    } catch (err: any) {
      alert("Failed to create quote: " + (err?.message || err));
    }
  };

  // Download PDF Quote
  const handleDownloadPDF = async (quote?: SalesQuote) => {
    try {
      setIsDownloading(true);
      const cust = customers.find((c) => c.customer_id === quote?.customer_id) || customers[0];
      const today = new Date().toISOString().split("T")[0];
      const validUntil = quote?.valid_until || new Date(Date.now() + 30 * 86400000).toISOString().split("T")[0];
      const promisedDelivery = new Date(Date.now() + 14 * 86400000).toISOString().split("T")[0];

      const unitPrice = quote ? Number((Number(quote.total_amount) / 100).toFixed(2)) : Number(effectivePrice.toFixed(2));
      const qty = quote ? 100 : 250;
      const sub = Number((qty * unitPrice).toFixed(2));

      await api.downloadQuotePDF({
        quote_number: quote?.quotation_number || "QT-OFFICIAL-DEFENDED",
        customer_name: cust?.customer_name || "Enterprise Client Inc.",
        customer_email: cust?.email || "procurement@client.com",
        valid_until_date: validUntil,
        promised_delivery_date: promisedDelivery,
        currency: "USD",
        items: [
          {
            item_code: sku,
            description: `Precision Manufactured Component (${sku})`,
            quantity: qty,
            unit_price: unitPrice,
            line_total: sub,
          },
        ],
        subtotal: sub,
        tax_amount: 0.0,
        total_amount: sub,
        margin_percentage: quote ? Number(quote.contribution_margin_pct) : Number(actualMarginPercent.toFixed(2)),
      });
    } catch (err: any) {
      alert("Failed to download PDF: " + (err?.message || err));
    } finally {
      setIsDownloading(false);
    }
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between border-b border-cream-300 pb-5">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-cream-900 flex items-center gap-2">
            <span>Commercial &bull; Margin-Defended Dynamic Pricing &amp; Quotation</span>
            <span className="inline-flex items-center gap-1 rounded bg-cream-200 border border-cream-300 px-2 py-0.5 text-[11px] font-mono font-medium text-cream-800">
              Live DB
            </span>
          </h1>
          <p className="text-xs text-cream-700 mt-1">
            Real-time BOM landed cost rollups defending corporate 22.0% contribution margin floor with autonomous quote invalidation.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => setShowCustomerModal(true)}
            className="flex items-center gap-1.5 rounded-md border border-cream-400 bg-cream-100 px-3 py-1.5 text-xs font-medium text-cream-900 hover:bg-cream-200"
          >
            <Plus className="h-3.5 w-3.5" />
            <span>Add Customer</span>
          </button>
          <button
            onClick={() => setShowQuoteModal(true)}
            className="flex items-center gap-1.5 rounded-md border border-cream-400 bg-cream-100 px-3 py-1.5 text-xs font-medium text-cream-900 hover:bg-cream-200"
          >
            <Plus className="h-3.5 w-3.5" />
            <span>Create Quote</span>
          </button>
          <button
            onClick={() => handleDownloadPDF()}
            disabled={isDownloading}
            className="flex items-center gap-1.5 rounded-md border border-cream-400 bg-cream-900 px-3 py-1.5 text-xs font-medium text-cream-50 hover:bg-cream-800 disabled:opacity-50"
          >
            <Download className="h-3.5 w-3.5" />
            <span>{isDownloading ? "Generating PDF..." : "Download Active Quote PDF"}</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-rose-300 bg-rose-50 p-3 text-xs text-rose-800 flex items-center justify-between">
          <span>{error}</span>
          <button onClick={loadData} className="underline font-semibold">Retry</button>
        </div>
      )}

      {/* Metric Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="rounded-lg border border-cream-300 bg-cream-50 p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs text-cream-600">Commercial Clients</span>
            <Users className="h-4 w-4 text-cream-600" />
          </div>
          <p className="mt-2 text-2xl font-bold tracking-tight text-cream-900">
            {customers.length}
          </p>
          <p className="text-[11px] text-cream-600 mt-0.5">Active accounts in DB</p>
        </div>

        <div className="rounded-lg border border-cream-300 bg-cream-50 p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs text-cream-600">Official Quotations</span>
            <FileText className="h-4 w-4 text-cream-600" />
          </div>
          <p className="mt-2 text-2xl font-bold tracking-tight text-cream-900">
            {quotes.length}
          </p>
          <p className="text-[11px] text-cream-600 mt-0.5">Defended quotes issued</p>
        </div>

        <div className="rounded-lg border border-cream-300 bg-cream-50 p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs text-cream-600">Statutory Margin Floor</span>
            <ShieldCheck className="h-4 w-4 text-sage-600" />
          </div>
          <p className="mt-2 text-2xl font-bold tracking-tight text-sage-700">
            22.0%
          </p>
          <p className="text-[11px] text-cream-600 mt-0.5">Corporate hard invariant</p>
        </div>

        <div className="rounded-lg border border-cream-300 bg-cream-50 p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs text-cream-600">Floor Defense Status</span>
            <TrendingUp className="h-4 w-4 text-cream-600" />
          </div>
          <p className="mt-2 text-sm font-semibold tracking-tight text-cream-900">
            {isFloorActive ? (
              <span className="text-amber-700">FLOOR ENFORCED</span>
            ) : (
              <span className="text-sage-700">MARKUP COMPLIANT</span>
            )}
          </p>
          <p className="text-[11px] text-cream-600 mt-0.5">
            Achieved: {Number(actualMarginPercent).toFixed(1)}% margin
          </p>
        </div>
      </div>

      {/* Grid: Dynamic Pricing Engine + Quote Invalidator */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Module 1: Margin-Defended Dynamic Pricing Engine */}
        <div className="rounded-lg border border-cream-300 bg-cream-50 p-5 space-y-5">
          <div className="flex items-center justify-between border-b border-cream-200 pb-3">
            <div className="flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-cream-800" />
              <h2 className="text-sm font-semibold text-cream-900">
                Dynamic Landed Cost &amp; 22% Margin Defense
              </h2>
            </div>
            <span className="text-[11px] font-mono text-cream-600">
              PRD &sect;Pricing Strategy
            </span>
          </div>

          {/* Pricing Controls */}
          <div className="grid grid-cols-2 gap-3 text-xs">
            <div>
              <span className="text-cream-600 text-[11px] block">Target SKU</span>
              {items.length > 0 ? (
                <select
                  value={sku}
                  onChange={(e) => {
                    setSku(e.target.value);
                    const selected = items.find((i) => i.item_code === e.target.value);
                    if (selected) setBomCost(Number(selected.standard_rate) || 48.5);
                  }}
                  className="w-full mt-1 rounded border border-cream-300 bg-cream-100 px-2.5 py-1.5 font-mono text-cream-900"
                >
                  {items.map((i) => (
                    <option key={i.item_id} value={i.item_code}>
                      {i.item_code} - {i.item_name}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  type="text"
                  value={sku}
                  onChange={(e) => setSku(e.target.value)}
                  className="w-full mt-1 rounded border border-cream-300 bg-cream-100 px-2.5 py-1 font-mono text-cream-900"
                />
              )}
            </div>
            <div>
              <span className="text-cream-600 text-[11px] block">Raw Material BOM Cost ($)</span>
              <input
                type="number"
                step="0.5"
                value={bomCost}
                onChange={(e) => setBomCost(parseFloat(e.target.value) || 0)}
                className="w-full mt-1 rounded border border-cream-300 bg-cream-100 px-2.5 py-1 font-mono text-cream-900"
              />
            </div>
            <div>
              <span className="text-cream-600 text-[11px] block">Machine Depreciation ($)</span>
              <input
                type="number"
                step="0.25"
                value={depreciation}
                onChange={(e) => setDepreciation(parseFloat(e.target.value) || 0)}
                className="w-full mt-1 rounded border border-cream-300 bg-cream-100 px-2.5 py-1 font-mono text-cream-900"
              />
            </div>
            <div>
              <span className="text-cream-600 text-[11px] block">Direct Labor ($)</span>
              <input
                type="number"
                step="0.25"
                value={labor}
                onChange={(e) => setLabor(parseFloat(e.target.value) || 0)}
                className="w-full mt-1 rounded border border-cream-300 bg-cream-100 px-2.5 py-1 font-mono text-cream-900"
              />
            </div>
            <div>
              <span className="text-cream-600 text-[11px] block">Dynamic Freight ($)</span>
              <input
                type="number"
                step="0.25"
                value={freight}
                onChange={(e) => setFreight(parseFloat(e.target.value) || 0)}
                className="w-full mt-1 rounded border border-cream-300 bg-cream-100 px-2.5 py-1 font-mono text-cream-900"
              />
            </div>
            <div>
              <span className="text-cream-600 text-[11px] block">Target Markup Multiplier</span>
              <input
                type="number"
                step="0.05"
                value={markupMultiplier}
                onChange={(e) => setMarkupMultiplier(parseFloat(e.target.value) || 1.0)}
                className="w-full mt-1 rounded border border-cream-300 bg-cream-100 px-2.5 py-1 font-mono text-cream-900"
              />
            </div>
          </div>

          {/* Margin Defense Dial Card */}
          <div className="rounded-lg border border-cream-300 bg-cream-100 p-4 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-cream-900">Pricing Evaluation Breakdown</span>
              <span
                className={`inline-flex items-center gap-1 rounded px-2 py-0.5 text-[10px] font-medium ${
                  isFloorActive
                    ? "bg-amber-100 text-amber-800 border border-amber-300"
                    : "bg-sage-100 text-sage-800 border border-sage-300"
                }`}
              >
                {isFloorActive ? "Margin Floor Defense Active" : "Margin Floor Compliant"}
              </span>
            </div>

            <div className="grid grid-cols-3 gap-2 text-center text-xs">
              <div className="rounded bg-white p-2 border border-cream-200">
                <span className="text-[10px] text-cream-600 block uppercase">Total Landed</span>
                <span className="font-mono text-sm font-semibold text-cream-900">
                  ${Number(totalLandedCost).toFixed(2)}
                </span>
              </div>
              <div className="rounded bg-white p-2 border border-cream-200">
                <span className="text-[10px] text-cream-600 block uppercase">Floor Price (22%)</span>
                <span className="font-mono text-sm font-semibold text-cream-900">
                  ${Number(floorPrice).toFixed(2)}
                </span>
              </div>
              <div className="rounded bg-white p-2 border border-cream-200">
                <span className="text-[10px] text-cream-600 block uppercase">Proposed Unit Price</span>
                <span className="font-mono text-sm font-bold text-sage-700">
                  ${Number(effectivePrice).toFixed(2)}
                </span>
              </div>
            </div>

            <div className="flex items-center justify-between text-xs pt-1 border-t border-cream-200 text-cream-700">
              <span>Achieved Contribution Margin:</span>
              <span className="font-mono font-bold text-sage-700">
                {Number(actualMarginPercent).toFixed(1)}% (&ge; 22.0% floor)
              </span>
            </div>
          </div>
        </div>

        {/* Module 2: Upstream BOM Spike & Active Quote Invalidator */}
        <div className="rounded-lg border border-cream-300 bg-cream-50 p-5 space-y-5">
          <div className="flex items-center justify-between border-b border-cream-200 pb-3">
            <div className="flex items-center gap-2">
              <RefreshCw className="h-4 w-4 text-cream-800" />
              <h2 className="text-sm font-semibold text-cream-900">
                Upstream BOM Inflation &amp; Quote Invalidator
              </h2>
            </div>
            <span className="text-[11px] font-mono text-cream-600">
              PRD &sect;Margin Defense
            </span>
          </div>

          <div className="grid grid-cols-2 gap-3 text-xs">
            <div>
              <span className="text-cream-600 text-[11px] block">Quote Reference</span>
              <input
                type="text"
                value={invQuoteNumber}
                onChange={(e) => setInvQuoteNumber(e.target.value)}
                className="w-full mt-1 rounded border border-cream-300 bg-cream-100 px-2.5 py-1 font-mono text-cream-900"
              />
            </div>
            <div>
              <span className="text-cream-600 text-[11px] block">Customer Name</span>
              <input
                type="text"
                value={invCustomer}
                onChange={(e) => setInvCustomer(e.target.value)}
                className="w-full mt-1 rounded border border-cream-300 bg-cream-100 px-2.5 py-1 text-cream-900"
              />
            </div>
            <div>
              <span className="text-cream-600 text-[11px] block">Target SKU</span>
              <input
                type="text"
                value={invSku}
                onChange={(e) => setInvSku(e.target.value)}
                className="w-full mt-1 rounded border border-cream-300 bg-cream-100 px-2.5 py-1 font-mono text-cream-900"
              />
            </div>
            <div>
              <span className="text-cream-600 text-[11px] block">Quoted Price ($)</span>
              <input
                type="number"
                step="1"
                value={invCurrentPrice}
                onChange={(e) => setInvCurrentPrice(parseFloat(e.target.value) || 0)}
                className="w-full mt-1 rounded border border-cream-300 bg-cream-100 px-2.5 py-1 font-mono text-cream-900"
              />
            </div>
            <div className="col-span-2">
              <span className="text-cream-600 text-[11px] block">New Spiked BOM Cost ($)</span>
              <input
                type="number"
                step="1"
                value={invNewBomCost}
                onChange={(e) => setInvNewBomCost(parseFloat(e.target.value) || 0)}
                className="w-full mt-1 rounded border border-cream-300 bg-cream-100 px-2.5 py-1 font-mono text-cream-900"
              />
            </div>
          </div>

          {/* Invalidation Alert Card */}
          {invalidationResult && (
            <div
              className={`rounded-lg border p-4 text-xs space-y-3 ${
                invalidationResult.is_invalidated
                  ? "border-rose-500/30 bg-rose-50/70 text-rose-900"
                  : "border-sage-500/30 bg-sage-50 text-sage-900"
              }`}
            >
              <div className="flex items-center justify-between font-semibold">
                <div className="flex items-center gap-2">
                  {invalidationResult.is_invalidated ? (
                    <AlertCircle className="h-4 w-4 text-rose-600" />
                  ) : (
                    <CheckCircle2 className="h-4 w-4 text-sage-600" />
                  )}
                  <span>
                    {invalidationResult.is_invalidated
                      ? `Quote ${invalidationResult.quote_number} Invalidated: Margin Eroded`
                      : `Quote ${invalidationResult.quote_number} Still Margin Compliant`}
                  </span>
                </div>
                <span className="font-mono text-[10px] px-2 py-0.5 rounded bg-cream-100 border border-cream-300 text-cream-800">
                  {invalidationResult.is_invalidated ? "INVALIDATED" : "VALID"}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-2 text-[11px] font-mono">
                <div>
                  Eroded Margin:{" "}
                  <span className={invalidationResult.is_invalidated ? "text-rose-700 font-bold" : "text-sage-700 font-bold"}>
                    {Number(invalidationResult.new_margin_with_old_price ?? invalidationResult.eroded_margin_percentage ?? 0).toFixed(1)}% {invalidationResult.is_invalidated ? "(< 22.0%)" : "(>= 22.0%)"}
                  </span>
                </div>
                <div>
                  Revised Defended Rate:{" "}
                  <span className="text-cream-900 font-bold">
                    ${Number(invalidationResult.new_adjusted_price ?? invalidationResult.revised_minimum_quote_price ?? 0).toFixed(2)}
                  </span>
                </div>
              </div>

              {invalidationResult.is_invalidated && (invalidationResult.customer_adjustment_notice || invalidationResult.autonomous_notice_draft) && (
                <div className="bg-white/80 p-3 rounded border border-rose-200 text-[11px] text-cream-800 space-y-1 font-mono">
                  <div className="font-semibold text-rose-800">Autonomous Commercial Notice Draft:</div>
                  <p className="text-[10px] text-cream-700 leading-relaxed">
                    &ldquo;{invalidationResult.customer_adjustment_notice || invalidationResult.autonomous_notice_draft}&rdquo;
                  </p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Live Sales Quotes Table */}
      <div className="rounded-lg border border-cream-300 bg-cream-50 p-5 space-y-4">
        <div className="flex items-center justify-between border-b border-cream-200 pb-3">
          <div className="flex items-center gap-2">
            <FileText className="h-4 w-4 text-cream-800" />
            <h2 className="text-sm font-semibold text-cream-900">
              Official Commercial Sales Quotations
            </h2>
          </div>
          <span className="font-mono text-xs text-cream-600">
            {quotes.length} quotations on record
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-cream-300 bg-cream-100 font-medium text-cream-800">
                <th className="py-2.5 px-3">Quote #</th>
                <th className="py-2.5 px-3">Date</th>
                <th className="py-2.5 px-3">Valid Until</th>
                <th className="py-2.5 px-3 text-right">Subtotal</th>
                <th className="py-2.5 px-3 text-right">Margin %</th>
                <th className="py-2.5 px-3 text-center">Status</th>
                <th className="py-2.5 px-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-cream-200 text-cream-900">
              {quotes.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-cream-500 italic">
                    No sales quotations created yet. Click &quot;Create Quote&quot; or download the dynamic quote above.
                  </td>
                </tr>
              ) : (
                quotes.map((q) => (
                  <tr key={q.quotation_id} className="hover:bg-cream-100/60">
                    <td className="py-2.5 px-3 font-mono font-medium">{q.quotation_number}</td>
                    <td className="py-2.5 px-3 font-mono">{q.quotation_date}</td>
                    <td className="py-2.5 px-3 font-mono">{q.valid_until}</td>
                    <td className="py-2.5 px-3 font-mono text-right font-medium">
                      ${Number(q.subtotal).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </td>
                    <td className="py-2.5 px-3 font-mono text-right">
                      <span className={Number(q.contribution_margin_pct) >= 22 ? "text-sage-700 font-bold" : "text-rose-700 font-bold"}>
                        {Number(q.contribution_margin_pct).toFixed(1)}%
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-center">
                      <span className="inline-flex rounded px-2 py-0.5 text-[10px] font-medium bg-sage-100 text-sage-800 border border-sage-300">
                        {q.status}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-right">
                      <button
                        onClick={() => handleDownloadPDF(q)}
                        className="inline-flex items-center gap-1 text-[11px] font-medium text-cream-900 hover:text-cream-700 underline"
                      >
                        <Download className="h-3 w-3" />
                        <span>PDF</span>
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Customer Directory Table */}
      <div className="rounded-lg border border-cream-300 bg-cream-50 p-5 space-y-4">
        <div className="flex items-center justify-between border-b border-cream-200 pb-3">
          <div className="flex items-center gap-2">
            <Building className="h-4 w-4 text-cream-800" />
            <h2 className="text-sm font-semibold text-cream-900">
              Commercial Customer Accounts
            </h2>
          </div>
          <span className="font-mono text-xs text-cream-600">
            {customers.length} client accounts
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-cream-300 bg-cream-100 font-medium text-cream-800">
                <th className="py-2.5 px-3">Customer Code</th>
                <th className="py-2.5 px-3">Company Name</th>
                <th className="py-2.5 px-3">Contact Email</th>
                <th className="py-2.5 px-3 text-right">Credit Limit</th>
                <th className="py-2.5 px-3 text-right">Lifetime Value</th>
                <th className="py-2.5 px-3 text-center">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-cream-200 text-cream-900">
              {customers.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-cream-500 italic">
                    No customers registered yet. Click &quot;Add Customer&quot; to onboard an account.
                  </td>
                </tr>
              ) : (
                customers.map((c) => (
                  <tr key={c.customer_id} className="hover:bg-cream-100/60">
                    <td className="py-2.5 px-3 font-mono font-medium">{c.customer_code}</td>
                    <td className="py-2.5 px-3 font-medium">{c.customer_name}</td>
                    <td className="py-2.5 px-3 text-cream-700">{c.email || "—"}</td>
                    <td className="py-2.5 px-3 font-mono text-right">
                      ${Number(c.credit_limit).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </td>
                    <td className="py-2.5 px-3 font-mono text-right">
                      ${Number(c.lifetime_value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </td>
                    <td className="py-2.5 px-3 text-center">
                      <span className={`inline-flex rounded px-2 py-0.5 text-[10px] font-medium ${c.is_active ? "bg-sage-100 text-sage-800 border border-sage-300" : "bg-cream-200 text-cream-700"}`}>
                        {c.is_active ? "ACTIVE" : "INACTIVE"}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Add Customer Modal */}
      {showCustomerModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-md rounded-lg border border-cream-300 bg-cream-50 p-6 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b border-cream-300 pb-3">
              <h2 className="text-sm font-semibold text-cream-900">Onboard Commercial Customer</h2>
              <button onClick={() => setShowCustomerModal(false)} className="text-cream-600 hover:text-cream-900 text-lg">&times;</button>
            </div>
            <form onSubmit={handleCreateCustomer} className="space-y-3 text-xs">
              <div>
                <label className="block text-cream-700 font-medium mb-1">Customer Code</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. CUST-BOEING-01"
                  value={newCustCode}
                  onChange={(e) => setNewCustCode(e.target.value)}
                  className="w-full rounded border border-cream-300 bg-cream-100 px-3 py-1.5 font-mono text-cream-900"
                />
              </div>
              <div>
                <label className="block text-cream-700 font-medium mb-1">Company Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Boeing Defense & Space"
                  value={newCustName}
                  onChange={(e) => setNewCustName(e.target.value)}
                  className="w-full rounded border border-cream-300 bg-cream-100 px-3 py-1.5 text-cream-900"
                />
              </div>
              <div>
                <label className="block text-cream-700 font-medium mb-1">Procurement Email</label>
                <input
                  type="email"
                  placeholder="e.g. procurement@boeing.com"
                  value={newCustEmail}
                  onChange={(e) => setNewCustEmail(e.target.value)}
                  className="w-full rounded border border-cream-300 bg-cream-100 px-3 py-1.5 text-cream-900"
                />
              </div>
              <div>
                <label className="block text-cream-700 font-medium mb-1">Credit Limit ($)</label>
                <input
                  type="number"
                  required
                  step="1000"
                  value={newCustCredit}
                  onChange={(e) => setNewCustCredit(Number(e.target.value))}
                  className="w-full rounded border border-cream-300 bg-cream-100 px-3 py-1.5 font-mono text-cream-900"
                />
              </div>
              <div className="flex justify-end gap-2 pt-3 border-t border-cream-300">
                <button
                  type="button"
                  onClick={() => setShowCustomerModal(false)}
                  className="rounded px-3 py-1.5 text-cream-700 hover:bg-cream-200"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="rounded bg-cream-900 px-4 py-1.5 text-cream-50 hover:bg-cream-800 font-medium"
                >
                  Save Customer
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Create Quote Modal */}
      {showQuoteModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-md rounded-lg border border-cream-300 bg-cream-50 p-6 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b border-cream-300 pb-3">
              <h2 className="text-sm font-semibold text-cream-900">Record Defended Sales Quote</h2>
              <button onClick={() => setShowQuoteModal(false)} className="text-cream-600 hover:text-cream-900 text-lg">&times;</button>
            </div>
            <form onSubmit={handleCreateQuote} className="space-y-3 text-xs">
              <div>
                <label className="block text-cream-700 font-medium mb-1">Quote Reference #</label>
                <input
                  type="text"
                  required
                  value={newQuoteNumber}
                  onChange={(e) => setNewQuoteNumber(e.target.value)}
                  className="w-full rounded border border-cream-300 bg-cream-100 px-3 py-1.5 font-mono text-cream-900"
                />
              </div>
              <div>
                <label className="block text-cream-700 font-medium mb-1">Select Customer</label>
                <select
                  required
                  value={selectedCustomerId}
                  onChange={(e) => setSelectedCustomerId(e.target.value)}
                  className="w-full rounded border border-cream-300 bg-cream-100 px-3 py-1.5 text-cream-900"
                >
                  {customers.map((c) => (
                    <option key={c.customer_id} value={c.customer_id}>
                      {c.customer_name} ({c.customer_code})
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-cream-700 font-medium mb-1">Subtotal ($)</label>
                <input
                  type="number"
                  required
                  step="100"
                  value={quoteSubtotal}
                  onChange={(e) => setQuoteSubtotal(Number(e.target.value))}
                  className="w-full rounded border border-cream-300 bg-cream-100 px-3 py-1.5 font-mono text-cream-900"
                />
              </div>
              <div>
                <label className="block text-cream-700 font-medium mb-1">Guaranteed Margin % (&ge; 22.0%)</label>
                <input
                  type="number"
                  required
                  step="0.5"
                  min="22.0"
                  value={quoteMargin}
                  onChange={(e) => setQuoteMargin(Number(e.target.value))}
                  className="w-full rounded border border-cream-300 bg-cream-100 px-3 py-1.5 font-mono text-cream-900"
                />
                <p className="text-[10px] text-cream-600 mt-0.5">Corporate margin guardrail automatically enforced.</p>
              </div>
              <div className="flex justify-end gap-2 pt-3 border-t border-cream-300">
                <button
                  type="button"
                  onClick={() => setShowQuoteModal(false)}
                  className="rounded px-3 py-1.5 text-cream-700 hover:bg-cream-200"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="rounded bg-cream-900 px-4 py-1.5 text-cream-50 hover:bg-cream-800 font-medium"
                >
                  Save &amp; Issue Quote
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
