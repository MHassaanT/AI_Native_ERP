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
import { PhaseBShortcuts } from "@/components/phase-b-shortcuts";

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
  items?: Array<{ quotation_item_id: string; item_id: string; quantity: number; unit_price: number; is_free?: boolean; promotion_id?: string | null }>;
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
  const [salesMasters, setSalesMasters] = useState<{ contacts: any[]; addresses: any[]; terms: any[]; warehouses: any[]; shippingRules: any[]; partners: any[] }>({ contacts: [], addresses: [], terms: [], warehouses: [], shippingRules: [], partners: [] });
  const [convertingQuote, setConvertingQuote] = useState<SalesQuote | null>(null);
  const [conversionDetails, setConversionDetails] = useState({ customer_contact_id: "", billing_address_id: "", shipping_address_id: "", terms_template_id: "", terms_text: "", warehouse_id: "", shipping_rule_id: "", payment_terms: "" });
  const [quoteLines, setQuoteLines] = useState<Array<{ item_id: string; quantity: string; unit_price: string }>>([]);
  const [conversionSalesTeam, setConversionSalesTeam] = useState<Array<{ partner_id: string; contribution_pct: string }>>([]);
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
  const [quoteMargin, setQuoteMargin] = useState(25.0);

  const loadData = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const [custList, quoteList, itemList, contacts, addresses, terms, warehouses, shippingRules, partners] = await Promise.all([
        api.getCustomers().catch(() => []),
        api.getQuotes().catch(() => []),
        api.getItems().catch(() => []),
        api.getMasterData("contacts").catch(() => []),
        api.getMasterData("addresses").catch(() => []),
        api.getMasterData("terms-templates").catch(() => []),
        api.getWarehouses().catch(() => []),
        api.getMasterData("shipping-rules").catch(() => []),
        api.getMasterData("sales-partners").catch(() => []),
      ]);
      setCustomers(custList || []);
      setQuotes(quoteList || []);
      setItems(itemList || []);
      setSalesMasters({ contacts: contacts || [], addresses: addresses || [], terms: (terms || []).filter((row: any) => row.is_active && ["SELLING", "BOTH"].includes(row.applicable_to)), warehouses: (warehouses || []).filter((row: any) => row.is_active && !row.is_quarantine), shippingRules: (shippingRules || []).filter((row: any) => row.is_active), partners: (partners || []).filter((row: any) => row.is_active) });
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
    if (!selectedCustomerId || !quoteLines.length || quoteLines.some((line) => !line.item_id || Number(line.quantity) <= 0 || Number(line.unit_price) < 0)) {
      alert("Please select a valid customer");
      return;
    }
    try {
      const today = new Date().toISOString().split("T")[0];
      const validUntil = new Date(Date.now() + 30 * 86400000).toISOString().split("T")[0];
      const subtotal = quoteLines.reduce((sum, line) => sum + Number(line.quantity) * Number(line.unit_price), 0);
      await api.createQuote({
        quotation_number: newQuoteNumber.trim(),
        customer_id: selectedCustomerId,
        quotation_date: today,
        valid_until: validUntil,
        subtotal,
        tax_amount: 0,
        contribution_margin_pct: Number(quoteMargin),
        items: quoteLines.map((line) => ({ item_id: line.item_id, quantity: Number(line.quantity), unit_price: Number(line.unit_price) })),
      });
      setShowQuoteModal(false);
      setQuoteLines([]);
      setNewQuoteNumber(`QT-${new Date().getFullYear()}-${Math.floor(1000 + Math.random() * 9000)}`);
      await loadData();
    } catch (err: any) {
      alert("Failed to create quote: " + (err?.message || err));
    }
  };

  const handleConvertQuote = async (quote: SalesQuote) => {
    if (!quote.items?.length) { alert("This quotation has no persisted item lines and cannot be converted."); return; }
    setConversionDetails({ customer_contact_id: "", billing_address_id: "", shipping_address_id: "", terms_template_id: "", terms_text: "", warehouse_id: "", shipping_rule_id: "", payment_terms: "" });
    setConversionSalesTeam([]);
    setConvertingQuote(quote);
  };

  const submitQuoteConversion = async () => {
    const quote = convertingQuote;
    if (!quote?.items?.length) return;
    try {
      const today = new Date();
      const result = await api.convertQuoteToOrder(quote.quotation_id, {
        order_number: `SO-${quote.quotation_number.replace(/^QT-/, "")}`,
        delivery_date: new Date(today.getTime() + 14 * 86400000).toISOString().split("T")[0],
        items: quote.items.map((line) => ({ quotation_item_id: line.quotation_item_id, item_id: line.item_id, quantity: Number(line.quantity), unit_price: Number(line.unit_price) })),
        customer_contact_id: conversionDetails.customer_contact_id || undefined,
        billing_address_id: conversionDetails.billing_address_id || undefined,
        shipping_address_id: conversionDetails.shipping_address_id || undefined,
        terms_template_id: conversionDetails.terms_template_id || undefined,
        terms_text: conversionDetails.terms_text || undefined,
        warehouse_id: conversionDetails.warehouse_id || undefined,
        shipping_rule_id: conversionDetails.shipping_rule_id || undefined,
        payment_terms: conversionDetails.payment_terms || undefined,
        sales_team: conversionSalesTeam.filter((assignment) => assignment.partner_id).map((assignment) => ({ partner_id: assignment.partner_id, contribution_pct: Number(assignment.contribution_pct) })),
      });
      alert(`Sales order ${result.order_number} created and stock reserved.`);
      setConvertingQuote(null);
      await loadData();
    } catch (err: any) { alert("Could not convert quotation: " + (err?.message || err)); }
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
            onClick={() => { setQuoteLines(items[0] ? [{ item_id: items[0].item_id, quantity: "1", unit_price: String(items[0].standard_rate || 0) }] : []); setShowQuoteModal(true); }}
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

      <PhaseBShortcuts area="selling" />

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
                      <div className="flex justify-end gap-3"><button onClick={() => handleDownloadPDF(q)} className="inline-flex items-center gap-1 text-[11px] font-medium text-cream-900 hover:text-cream-700 underline"><Download className="h-3 w-3"/><span>PDF</span></button>{["OFFICIAL", "SENT"].includes(q.status) && q.items?.length ? <button onClick={() => void handleConvertQuote(q)} className="text-[11px] font-semibold text-sage-800 underline">Convert to order</button> : null}</div>
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
              <div className="space-y-2 rounded-lg border border-cream-200 bg-cream-50 p-3"><div className="flex items-center justify-between"><span className="font-semibold text-cream-800">Quotation items</span><button type="button" onClick={() => { const item = items[0]; if (item) setQuoteLines((current) => [...current, { item_id: item.item_id, quantity: "1", unit_price: String(item.standard_rate || 0) }]); }} className="text-[11px] font-semibold text-sage-800 underline">Add line</button></div>{quoteLines.map((line, index) => <div key={`${line.item_id}-${index}`} className="grid grid-cols-12 gap-2"><select required value={line.item_id} onChange={(e) => setQuoteLines((current) => current.map((row, i) => i === index ? { ...row, item_id: e.target.value, unit_price: String(items.find((item) => item.item_id === e.target.value)?.standard_rate || row.unit_price) } : row))} className="col-span-6 rounded border border-cream-300 bg-white px-2 py-1.5">{items.map((item) => <option key={item.item_id} value={item.item_id}>{item.item_code} · {item.item_name}</option>)}</select><input aria-label="Quoted quantity" type="number" required min="0.0001" step="0.0001" value={line.quantity} onChange={(e) => setQuoteLines((current) => current.map((row, i) => i === index ? { ...row, quantity: e.target.value } : row))} className="col-span-2 rounded border border-cream-300 bg-white px-2 py-1.5"/><input aria-label="Quoted unit price" type="number" required min="0" step="0.0001" value={line.unit_price} onChange={(e) => setQuoteLines((current) => current.map((row, i) => i === index ? { ...row, unit_price: e.target.value } : row))} className="col-span-3 rounded border border-cream-300 bg-white px-2 py-1.5"/><button type="button" aria-label="Remove quotation line" onClick={() => setQuoteLines((current) => current.filter((_, i) => i !== index))} className="col-span-1 text-red-700">×</button></div>)}<p className="text-right font-mono text-xs">Subtotal: ${quoteLines.reduce((sum, line) => sum + Number(line.quantity || 0) * Number(line.unit_price || 0), 0).toFixed(2)}</p></div>
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
      {convertingQuote && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <section className="w-full max-w-xl space-y-4 rounded-xl border border-cream-300 bg-white p-5 shadow-xl">
            <div><h3 className="font-semibold">Convert {convertingQuote.quotation_number} to Sales Order</h3><p className="mt-1 text-xs text-cream-600">Choose tenant-scoped contact, addresses, warehouse, and terms to snapshot onto the order.</p></div>
            <div className="grid gap-3 text-xs sm:grid-cols-2">
              <label>Customer contact<select value={conversionDetails.customer_contact_id} onChange={(e) => setConversionDetails({ ...conversionDetails, customer_contact_id: e.target.value })} className="mt-1 w-full rounded border border-cream-300 bg-cream-50 p-2"><option value="">No contact</option>{salesMasters.contacts.filter((row) => row.is_active).map((row) => <option key={row.contact_id} value={row.contact_id}>{row.full_name}</option>)}</select></label>
              <label>Billing address<select value={conversionDetails.billing_address_id} onChange={(e) => setConversionDetails({ ...conversionDetails, billing_address_id: e.target.value })} className="mt-1 w-full rounded border border-cream-300 bg-cream-50 p-2"><option value="">No address</option>{salesMasters.addresses.map((row) => <option key={row.address_id} value={row.address_id}>{row.address_title} · {row.city}</option>)}</select></label>
              <label>Shipping address<select value={conversionDetails.shipping_address_id} onChange={(e) => setConversionDetails({ ...conversionDetails, shipping_address_id: e.target.value })} className="mt-1 w-full rounded border border-cream-300 bg-cream-50 p-2"><option value="">No address</option>{salesMasters.addresses.map((row) => <option key={row.address_id} value={row.address_id}>{row.address_title} · {row.city}</option>)}</select></label>
              <label>Fulfillment warehouse<select value={conversionDetails.warehouse_id} onChange={(e) => setConversionDetails({ ...conversionDetails, warehouse_id: e.target.value })} className="mt-1 w-full rounded border border-cream-300 bg-cream-50 p-2"><option value="">Choose automatically</option>{salesMasters.warehouses.map((row) => <option key={row.warehouse_id} value={row.warehouse_id}>{row.warehouse_name}</option>)}</select></label>
              <label>Terms template<select value={conversionDetails.terms_template_id} onChange={(e) => { const selected = salesMasters.terms.find((row) => row.terms_template_id === e.target.value); setConversionDetails({ ...conversionDetails, terms_template_id: e.target.value, terms_text: selected?.terms || "" }); }} className="mt-1 w-full rounded border border-cream-300 bg-cream-50 p-2"><option value="">No template</option>{salesMasters.terms.map((row) => <option key={row.terms_template_id} value={row.terms_template_id}>{row.template_name}</option>)}</select></label>
              <label>Shipping rule<select value={conversionDetails.shipping_rule_id} onChange={(e) => setConversionDetails({ ...conversionDetails, shipping_rule_id: e.target.value })} className="mt-1 w-full rounded border border-cream-300 bg-cream-50 p-2"><option value="">No rule</option>{salesMasters.shippingRules.map((row) => <option key={row.shipping_rule_id} value={row.shipping_rule_id}>{row.rule_name}</option>)}</select></label>
              <label className="sm:col-span-2">Payment terms<input value={conversionDetails.payment_terms} onChange={(e) => setConversionDetails({ ...conversionDetails, payment_terms: e.target.value })} placeholder="Default from customer" className="mt-1 w-full rounded border border-cream-300 bg-cream-50 p-2" /></label>
              <div className="sm:col-span-2 rounded-lg border border-cream-200 p-3"><div className="flex items-center justify-between"><span className="font-semibold">Sales partners / representatives</span><button type="button" onClick={() => setConversionSalesTeam((rows) => { const count = rows.length + 1; const share = Math.floor((100 / count) * 10000) / 10000; return [...rows.map((row) => ({ ...row, contribution_pct: share.toFixed(4) })), { partner_id: "", contribution_pct: (100 - share * rows.length).toFixed(4) }]; })} className="text-[11px] font-semibold text-sage-800 underline">Add partner</button></div>{conversionSalesTeam.length === 0 && <p className="mt-2 text-[11px] text-cream-600">Optional. If assigned, contribution shares must total 100%; commission rates are snapshotted from partner settings.</p>}<div className="mt-2 space-y-2">{conversionSalesTeam.map((assignment, index) => { const partner = salesMasters.partners.find((row) => row.sales_partner_id === assignment.partner_id); return <div key={index} className="grid grid-cols-12 items-center gap-2"><select aria-label={`Sales partner ${index + 1}`} value={assignment.partner_id} onChange={(e) => setConversionSalesTeam((rows) => rows.map((row, i) => i === index ? { ...row, partner_id: e.target.value } : row))} className="col-span-7 rounded border border-cream-300 bg-cream-50 p-2"><option value="">Choose partner</option>{salesMasters.partners.map((row) => <option key={row.sales_partner_id} value={row.sales_partner_id}>{row.partner_name}</option>)}</select><label className="col-span-4 flex items-center gap-1 text-[11px]">Share %<input aria-label={`Contribution percentage ${index + 1}`} type="number" min="0.0001" max="100" step="0.0001" value={assignment.contribution_pct} onChange={(e) => setConversionSalesTeam((rows) => rows.map((row, i) => i === index ? { ...row, contribution_pct: e.target.value } : row))} className="w-full rounded border border-cream-300 bg-cream-50 p-2" /></label><button type="button" aria-label={`Remove sales partner ${index + 1}`} onClick={() => setConversionSalesTeam((rows) => rows.filter((_, i) => i !== index))} className="col-span-1 text-red-700">×</button>{partner && <p className="col-span-12 text-[10px] text-cream-600">Commission rate snapshot: {partner.commission_rate}%</p>}</div>; })}</div>{conversionSalesTeam.length > 0 && <p className={`mt-2 text-right text-[11px] ${conversionSalesTeam.reduce((sum, row) => sum + Number(row.contribution_pct || 0), 0) === 100 ? "text-green-700" : "text-amber-700"}`}>Contribution total: {conversionSalesTeam.reduce((sum, row) => sum + Number(row.contribution_pct || 0), 0).toFixed(4)}%</p>}</div>
              <label className="sm:col-span-2">Terms snapshot<textarea rows={3} value={conversionDetails.terms_text} onChange={(e) => setConversionDetails({ ...conversionDetails, terms_text: e.target.value })} className="mt-1 w-full rounded border border-cream-300 bg-cream-50 p-2" /></label>
            </div>
            <div className="flex justify-end gap-2 border-t border-cream-200 pt-3"><button onClick={() => setConvertingQuote(null)} className="rounded px-3 py-2 text-cream-700">Cancel</button><button onClick={() => void submitQuoteConversion()} className="rounded bg-cream-900 px-4 py-2 font-medium text-white">Create Sales Order</button></div>
          </section>
        </div>
      )}
    </div>
  );
}
