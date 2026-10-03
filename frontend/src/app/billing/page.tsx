"use client";

import { useEffect, useState } from "react";
import {
  AlertCircle,
  AlertTriangle,
  ArrowDownLeft,
  ArrowUpRight,
  CheckCircle2,
  Clock,
  DollarSign,
  FileText,
  Percent,
  PieChart,
  Plus,
  RefreshCw,
  Repeat,
  ShieldAlert,
  ShieldCheck,
  Store,
  Wallet,
  X,
  Calendar,
  Play,
  Pause,
  Layers,
  Calculator,
  Coins,
} from "lucide-react";
import Link from "next/link";
import { api } from "@/lib/api";

const formatMoney = (val: any) => {
  const num = Number(val);
  return isNaN(num) ? "0.00" : num.toFixed(2);
};

export default function BillingPage() {
  const [activeTab, setActiveTab] = useState<
    | "subscriptions"
    | "payment-terms"
    | "tax-templates"
    | "dunning"
    | "budgets"
    | "credit-notes"
    | "debit-notes"
    | "tax-withholding"
  >("subscriptions");

  const [subscriptions, setSubscriptions] = useState<any[]>([]);
  const [plans, setPlans] = useState<any[]>([]);
  const [dunningNotices, setDunningNotices] = useState<any[]>([]);
  const [dunningTypes, setDunningTypes] = useState<any[]>([]);
  const [budgets, setBudgets] = useState<any[]>([]);
  const [creditNotes, setCreditNotes] = useState<any[]>([]);
  const [debitNotes, setDebitNotes] = useState<any[]>([]);
  const [taxCategories, setTaxCategories] = useState<any[]>([]);
  const [customers, setCustomers] = useState<any[]>([]);
  const [suppliers, setSuppliers] = useState<any[]>([]);
  const [items, setItems] = useState<any[]>([]);

  // Phase 1 Parity States
  const [paymentTermsTemplates, setPaymentTermsTemplates] = useState<any[]>([]);
  const [taxTemplates, setTaxTemplates] = useState<any[]>([]);
  const [salesInvoices, setSalesInvoices] = useState<any[]>([]);

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Modal States
  const [showPlanModal, setShowPlanModal] = useState(false);
  const [showSubModal, setShowSubModal] = useState(false);
  const [showBudgetModal, setShowBudgetModal] = useState(false);
  const [showCreditNoteModal, setShowCreditNoteModal] = useState(false);
  const [showDebitNoteModal, setShowDebitNoteModal] = useState(false);
  const [showPaymentTermsModal, setShowPaymentTermsModal] = useState(false);
  const [showTaxTemplateModal, setShowTaxTemplateModal] = useState(false);
  const [showAdvanceModal, setShowAdvanceModal] = useState(false);

  // Form states
  const [newPlan, setNewPlan] = useState({ plan_name: "", billing_interval: "MONTHLY", cost: 100 });
  const [newSub, setNewSub] = useState({ customer_id: "", plan_id: "" });
  const [newBudget, setNewBudget] = useState({
    budget_name: "",
    fiscal_year: 2026,
    cost_center: "CORP-FINANCE",
    account_code: "5000-COGS-MATERIALS",
    budget_amount: 50000,
    action_on_exceed: "WARN",
  });
  const [newCN, setNewCN] = useState({
    customer_id: "",
    reason: "Damaged on delivery",
    item_id: "",
    quantity: 1,
    unit_price: 100,
  });
  const [newDN, setNewDN] = useState({
    supplier_id: "",
    reason: "Defective raw material batch",
    item_id: "",
    quantity: 1,
    unit_price: 50,
  });

  // Payment Terms Form & Schedule Generator
  const [newPTT, setNewPTT] = useState({
    template_name: "Standard 30-50-20 Terms",
    allocate_payment_based_on_payment_terms: true,
    terms: [
      { description: "Advance on Order Confirmation", invoice_portion: 30, due_date_based_on: "Day(s) after invoice date", credit_days: 0 },
      { description: "Payment on Dispatch", invoice_portion: 50, due_date_based_on: "Day(s) after invoice date", credit_days: 15 },
      { description: "Retention / Net 30", invoice_portion: 20, due_date_based_on: "Day(s) after invoice date", credit_days: 30 },
    ],
  });
  const [selectedInvoiceForSchedule, setSelectedInvoiceForSchedule] = useState("");
  const [selectedTemplateForSchedule, setSelectedTemplateForSchedule] = useState("");
  const [invoiceScheduleResult, setInvoiceScheduleResult] = useState<any[] | null>(null);
  const [isApplyingTerms, setIsApplyingTerms] = useState(false);

  // Taxes & Charges Template Form & Interactive Calculator
  const [newTaxTmpl, setNewTaxTmpl] = useState({
    title: "Standard Sales VAT + Freight + Surcharge",
    tax_category: "Standard",
    taxes: [
      { charge_type: "On Net Total", account_head: "2200-OUTPUT-VAT", description: "Standard Sales VAT", rate: 10 },
      { charge_type: "Actual", account_head: "5100-FREIGHT", description: "Fixed Freight & Handling", rate: 50 },
      { charge_type: "On Previous Row Amount", row_id: 1, account_head: "2210-CESS", description: "VAT Surcharge / Cess", rate: 5 },
    ],
  });
  const [interactiveTaxNetTotal, setInteractiveTaxNetTotal] = useState(1000);
  const [interactiveTaxResult, setInteractiveTaxResult] = useState<any>(null);

  // Advance Payment Allocation Form
  const [advanceInvoiceId, setAdvanceInvoiceId] = useState("");
  const [advanceCustomerId, setAdvanceCustomerId] = useState("");
  const [advanceAmount, setAdvanceAmount] = useState(1000);
  const [advanceNote, setAdvanceNote] = useState("");
  const [isAllocatingAdvance, setIsAllocatingAdvance] = useState(false);

  // Budget Compliance Evaluation Tool state
  const [evalCostCenter, setEvalCostCenter] = useState("CORP-FINANCE");
  const [evalAccount, setEvalAccount] = useState("5000-COGS-MATERIALS");
  const [evalAmount, setEvalAmount] = useState(15000);
  const [evalResult, setEvalResult] = useState<any>(null);
  const [isEvaluatingBudget, setIsEvaluatingBudget] = useState(false);

  const loadData = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [
        subsData,
        plansData,
        dunningData,
        typesData,
        budgetsData,
        cnData,
        dnData,
        taxData,
        custsData,
        suppsData,
        itemsData,
        pttData,
        taxTmplData,
        invoicesData,
      ] = await Promise.all([
        api.getSubscriptions().catch(() => []),
        api.getSubscriptionPlans().catch(() => []),
        api.getDunningNotices().catch(() => []),
        api.getDunningTypes().catch(() => []),
        api.getBudgets().catch(() => []),
        api.getCreditNotes().catch(() => []),
        api.getDebitNotes().catch(() => []),
        api.getTaxWithholdingCategories().catch(() => []),
        api.getCustomers().catch(() => []),
        api.getSuppliers().catch(() => []),
        api.getItems().catch(() => []),
        api.getPaymentTermsTemplates().catch(() => []),
        api.getTaxTemplates().catch(() => []),
        api.getSalesInvoices().catch(() => []),
      ]);

      setSubscriptions(subsData || []);
      setPlans(plansData || []);
      setDunningNotices(dunningData || []);
      setDunningTypes(typesData || []);
      setBudgets(budgetsData || []);
      setCreditNotes(cnData || []);
      setDebitNotes(dnData || []);
      setTaxCategories(taxData || []);
      setCustomers(custsData || []);
      setSuppliers(suppsData || []);
      setItems(itemsData || []);
      setPaymentTermsTemplates(pttData || []);
      setTaxTemplates(taxTmplData || []);
      setSalesInvoices(invoicesData || []);

      if (pttData && pttData.length > 0 && !selectedTemplateForSchedule) {
        setSelectedTemplateForSchedule(pttData[0].template_id);
      }
      if (invoicesData && invoicesData.length > 0 && !selectedInvoiceForSchedule) {
        setSelectedInvoiceForSchedule(invoicesData[0].invoice_id);
        setAdvanceInvoiceId(invoicesData[0].invoice_id);
        if (invoicesData[0].customer_id) {
          setAdvanceCustomerId(invoicesData[0].customer_id);
        }
      }

      if (custsData && custsData.length > 0 && !newSub.customer_id) {
        setNewSub((s) => ({ ...s, customer_id: custsData[0].customer_id }));
        setNewCN((c) => ({ ...c, customer_id: custsData[0].customer_id }));
      }
      if (plansData && plansData.length > 0 && !newSub.plan_id) {
        setNewSub((s) => ({ ...s, plan_id: plansData[0].plan_id }));
      }
      if (suppsData && suppsData.length > 0 && !newDN.supplier_id) {
        setNewDN((d) => ({ ...d, supplier_id: suppsData[0].supplier_id }));
      }
      if (itemsData && itemsData.length > 0) {
        setNewCN((c) => ({
          ...c,
          item_id: itemsData[0].item_id,
          unit_price: Number(itemsData[0].standard_rate || 100),
        }));
        setNewDN((d) => ({
          ...d,
          item_id: itemsData[0].item_id,
          unit_price: Number(itemsData[0].standard_rate || 50),
        }));
      }
    } catch (err: any) {
      setError(err?.message || "Failed to load billing and accounts data.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  // Handlers
  const handleCreatePlan = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newPlan.plan_name) return;
    try {
      await api.createSubscriptionPlan({
        plan_name: newPlan.plan_name,
        billing_interval: newPlan.billing_interval,
        cost: Number(newPlan.cost),
        currency: "USD",
      });
      setShowPlanModal(false);
      setNewPlan({ plan_name: "", billing_interval: "MONTHLY", cost: 100 });
      setSuccessMsg("Subscription plan created successfully.");
      await loadData();
    } catch (err: any) {
      setError(err?.message || "Failed to create plan");
    }
  };

  const handleCreateSub = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newSub.customer_id || !newSub.plan_id) return;
    try {
      await api.createSubscription({
        customer_id: newSub.customer_id,
        plan_id: newSub.plan_id,
        start_date: new Date().toISOString().split("T")[0],
      });
      setShowSubModal(false);
      setSuccessMsg("Customer enrolled in subscription successfully.");
      await loadData();
    } catch (err: any) {
      setError(err?.message || "Failed to enroll subscription");
    }
  };

  const handleProcessBilling = async () => {
    try {
      setError(null);
      const res = await api.processSubscriptionBillingRun(new Date().toISOString().split("T")[0]);
      setSuccessMsg(`Billing run completed: ${res.invoices_generated} recurring invoice(s) generated.`);
      await loadData();
    } catch (err: any) {
      setError(err?.message || "Billing run failed");
    }
  };

  const handleEvaluateDunning = async () => {
    try {
      setError(null);
      const res = await api.evaluateDunningOverdue();
      setSuccessMsg(`Dunning evaluation completed: ${res.notices_issued} notice(s) generated.`);
      await loadData();
    } catch (err: any) {
      setError(err?.message || "Dunning evaluation failed");
    }
  };

  const handleCreateBudget = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newBudget.budget_name) return;
    try {
      await api.createBudget({
        budget_name: newBudget.budget_name,
        fiscal_year: Number(newBudget.fiscal_year),
        cost_center: newBudget.cost_center,
        account_code: newBudget.account_code,
        budget_amount: Number(newBudget.budget_amount),
        action_on_exceed: newBudget.action_on_exceed,
      });
      setShowBudgetModal(false);
      setSuccessMsg("Budget limit established successfully.");
      await loadData();
    } catch (err: any) {
      setError(err?.message || "Failed to create budget");
    }
  };

  const handleEvaluateBudgetTest = async () => {
    setIsEvaluatingBudget(true);
    try {
      const res = await api.evaluateBudgetCompliance({
        cost_center: evalCostCenter,
        account_code: evalAccount,
        proposed_expenditure: Number(evalAmount),
        fiscal_year: 2026,
      });
      setEvalResult(res);
    } catch (err: any) {
      setEvalResult({
        compliant: false,
        action: "STOP",
        message: err?.message || "Budget validation failed with STOP threshold.",
      });
    } finally {
      setIsEvaluatingBudget(false);
    }
  };

  const handleCreateCreditNote = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newCN.customer_id) return;
    try {
      await api.createCreditNote({
        customer_id: newCN.customer_id,
        reason: newCN.reason,
        items: [
          {
            item_id: newCN.item_id,
            quantity: Number(newCN.quantity),
            unit_price: Number(newCN.unit_price),
            tax_rate: 5.0,
            return_to_inventory: true,
          },
        ],
      });
      setShowCreditNoteModal(false);
      setSuccessMsg("Credit Note issued with GL reversal and inventory return.");
      await loadData();
    } catch (err: any) {
      setError(err?.message || "Failed to issue credit note");
    }
  };

  const handleCreateDebitNote = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newDN.supplier_id) return;
    try {
      await api.createDebitNote({
        supplier_id: newDN.supplier_id,
        reason: newDN.reason,
        items: [
          {
            item_id: newDN.item_id,
            quantity: Number(newDN.quantity),
            unit_price: Number(newDN.unit_price),
            tax_rate: 5.0,
            return_from_inventory: true,
          },
        ],
      });
      setShowDebitNoteModal(false);
      setSuccessMsg("Debit Note issued with AP reduction and warehouse deduction.");
      await loadData();
    } catch (err: any) {
      setError(err?.message || "Failed to issue debit note");
    }
  };

  // Payment Terms & Schedules Handlers
  const handleCreatePaymentTerms = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newPTT.template_name) return;
    try {
      await api.createPaymentTermsTemplate(newPTT);
      setShowPaymentTermsModal(false);
      setSuccessMsg(`Payment terms template '${newPTT.template_name}' created.`);
      await loadData();
    } catch (err: any) {
      setError(err?.message || "Failed to create payment terms template");
    }
  };

  const handleApplyPaymentTerms = async () => {
    if (!selectedInvoiceForSchedule || !selectedTemplateForSchedule) {
      setError("Please select both a Sales Invoice and a Payment Terms Template.");
      return;
    }
    setIsApplyingTerms(true);
    try {
      setError(null);
      const res = await api.applyPaymentTermsToInvoice(selectedInvoiceForSchedule, selectedTemplateForSchedule);
      setInvoiceScheduleResult(res.schedules || []);
      setSuccessMsg(res.message || "Payment terms applied and milestone schedule generated.");
    } catch (err: any) {
      setError(err?.message || "Failed to apply payment terms");
    } finally {
      setIsApplyingTerms(false);
    }
  };

  // Advance Payment Allocation Handler
  const handleReconcileAdvance = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!advanceInvoiceId || !advanceCustomerId) {
      setError("Select both invoice and customer to reconcile advance.");
      return;
    }
    setIsAllocatingAdvance(true);
    try {
      setError(null);
      const res = await api.reconcileAdvancePayment(advanceInvoiceId, {
        customer_id: advanceCustomerId,
        allocated_amount: Number(advanceAmount),
        reference_note: advanceNote || undefined,
      });
      setShowAdvanceModal(false);
      setSuccessMsg(res.message || "Customer advance allocated successfully.");
      await loadData();
    } catch (err: any) {
      setError(err?.message || "Failed to reconcile advance payment");
    } finally {
      setIsAllocatingAdvance(false);
    }
  };

  // Tax Template & Cascading Calculator Handlers
  const handleCreateTaxTemplate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTaxTmpl.title) return;
    try {
      await api.createTaxTemplate(newTaxTmpl);
      setShowTaxTemplateModal(false);
      setSuccessMsg(`Tax & Charges Template '${newTaxTmpl.title}' created.`);
      await loadData();
    } catch (err: any) {
      setError(err?.message || "Failed to create tax template");
    }
  };

  const handleCalculateCascadingTaxes = async () => {
    try {
      setError(null);
      const res = await api.calculateCascadingTaxes({
        net_total: Number(interactiveTaxNetTotal),
        taxes: newTaxTmpl.taxes,
      });
      setInteractiveTaxResult(res);
      setSuccessMsg("Cascading taxes evaluated successfully.");
    } catch (err: any) {
      setError(err?.message || "Failed to calculate cascading taxes");
    }
  };

  // Subscription Lifecycle Handlers
  const handlePauseSubscription = async (subId: string) => {
    try {
      setError(null);
      await api.pauseSubscription(subId);
      setSuccessMsg("Subscription paused successfully.");
      await loadData();
    } catch (err: any) {
      setError(err?.message || "Failed to pause subscription");
    }
  };

  const handleResumeSubscription = async (subId: string) => {
    try {
      setError(null);
      await api.resumeSubscription(subId);
      setSuccessMsg("Subscription resumed successfully.");
      await loadData();
    } catch (err: any) {
      setError(err?.message || "Failed to resume subscription");
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between border-b border-cream-300 pb-5">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-cream-900 flex items-center gap-2">
            <span>Billing &bull; Accounts &amp; Revenue Management</span>
            <span className="inline-flex items-center gap-1 rounded bg-cream-200 border border-cream-300 px-2 py-0.5 text-[11px] font-mono font-medium text-cream-800">
              ERPNext Parity
            </span>
          </h1>
          <p className="text-xs text-cream-700 mt-1">
            Recurring revenue contracts, dunning overdue escalation, budget controls, and credit/debit return adjustments.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Link
            href="/pos"
            className="flex items-center gap-1.5 rounded-md border border-cream-400 bg-cream-900 px-3 py-1.5 text-xs font-medium text-cream-50 hover:bg-cream-800 transition-colors"
          >
            <Store className="h-3.5 w-3.5" />
            <span>Launch POS Register</span>
          </Link>
          <button
            onClick={loadData}
            disabled={isLoading}
            className="flex items-center gap-1.5 rounded-md border border-cream-300 bg-cream-100 px-3 py-1.5 text-xs font-medium text-cream-800 hover:bg-cream-200 transition-colors"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? "animate-spin" : ""}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Notifications */}
      {error && (
        <div className="rounded-lg border border-terracotta-300 bg-terracotta-50 p-3 text-xs text-terracotta-900 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertCircle className="h-4 w-4 text-terracotta-700 flex-shrink-0" />
            <span>{error}</span>
          </div>
          <button onClick={() => setError(null)} className="text-terracotta-700 hover:text-terracotta-900">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}
      {successMsg && (
        <div className="rounded-lg border border-sage-300 bg-sage-50 p-3 text-xs text-sage-900 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-sage-700 flex-shrink-0" />
            <span>{successMsg}</span>
          </div>
          <button onClick={() => setSuccessMsg(null)} className="text-sage-700 hover:text-sage-900">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Metric Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="rounded-lg border border-cream-300 bg-cream-50 p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs text-cream-600">Active Subscriptions</span>
            <Repeat className="h-4 w-4 text-cream-600" />
          </div>
          <p className="mt-2 text-2xl font-bold tracking-tight text-cream-900">
            {subscriptions.length}
          </p>
          <p className="text-[11px] text-cream-600 mt-0.5">{plans.length} recurring plan tiers</p>
        </div>

        <div className="rounded-lg border border-cream-300 bg-cream-50 p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs text-cream-600">Dunning Overdue Notices</span>
            <ShieldAlert className="h-4 w-4 text-terracotta-600" />
          </div>
          <p className="mt-2 text-2xl font-bold tracking-tight text-cream-900">
            {dunningNotices.length}
          </p>
          <p className="text-[11px] text-cream-600 mt-0.5">Automated late charge sweeps</p>
        </div>

        <div className="rounded-lg border border-cream-300 bg-cream-50 p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs text-cream-600">Budgets Monitored</span>
            <PieChart className="h-4 w-4 text-cream-600" />
          </div>
          <p className="mt-2 text-2xl font-bold tracking-tight text-cream-900">
            {budgets.length}
          </p>
          <p className="text-[11px] text-cream-600 mt-0.5">Expenditure controls active</p>
        </div>

        <div className="rounded-lg border border-cream-300 bg-cream-50 p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs text-cream-600">Return Adjustments</span>
            <ArrowDownLeft className="h-4 w-4 text-sage-600" />
          </div>
          <p className="mt-2 text-2xl font-bold tracking-tight text-cream-900">
            {creditNotes.length + debitNotes.length}
          </p>
          <p className="text-[11px] text-cream-600 mt-0.5">
            {creditNotes.length} Credit / {debitNotes.length} Debit
          </p>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="flex border-b border-cream-300 gap-6 text-xs text-cream-600 overflow-x-auto">
        {[
          { key: "subscriptions", label: `Subscriptions (${subscriptions.length})`, icon: Repeat },
          { key: "payment-terms", label: `Payment Terms (${paymentTermsTemplates.length})`, icon: Calendar },
          { key: "tax-templates", label: `Tax & Charges (${taxTemplates.length})`, icon: Layers },
          { key: "dunning", label: `Dunning & Overdue (${dunningNotices.length})`, icon: ShieldAlert },
          { key: "budgets", label: `Budgets & Control (${budgets.length})`, icon: PieChart },
          { key: "credit-notes", label: `Credit Notes (${creditNotes.length})`, icon: ArrowDownLeft },
          { key: "debit-notes", label: `Debit Notes (${debitNotes.length})`, icon: ArrowUpRight },
          { key: "tax-withholding", label: `TDS / Withholding (${taxCategories.length})`, icon: Percent },
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.key;
          return (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key as any)}
              className={`pb-3 flex items-center gap-2 border-b-2 transition-colors whitespace-nowrap ${
                isActive
                  ? "border-cream-900 text-cream-900 font-semibold"
                  : "border-transparent hover:text-cream-900"
              }`}
            >
              <Icon className="h-4 w-4" />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* TAB 1: Subscriptions */}
      {activeTab === "subscriptions" && (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-cream-900">Active Customer Subscriptions</h2>
              <p className="text-xs text-cream-600">
                Recurring automated invoicing engine honoring monthly, quarterly, and annual intervals.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <button
                onClick={() => setShowPlanModal(true)}
                className="flex items-center gap-1.5 rounded-md border border-cream-300 bg-cream-100 px-3 py-1.5 text-xs font-medium text-cream-900 hover:bg-cream-200 transition-colors"
              >
                <Plus className="h-3.5 w-3.5" />
                <span>New Plan</span>
              </button>
              <button
                onClick={() => setShowSubModal(true)}
                className="flex items-center gap-1.5 rounded-md border border-cream-300 bg-cream-100 px-3 py-1.5 text-xs font-medium text-cream-900 hover:bg-cream-200 transition-colors"
              >
                <Plus className="h-3.5 w-3.5" />
                <span>Enroll Customer</span>
              </button>
              <button
                onClick={handleProcessBilling}
                className="flex items-center gap-1.5 rounded-md border border-sage-400 bg-sage-50 px-3 py-1.5 text-xs font-medium text-sage-900 hover:bg-sage-100 transition-colors shadow-2xs"
              >
                <Repeat className="h-3.5 w-3.5 text-sage-700" />
                <span>Run Due Renewals</span>
              </button>
            </div>
          </div>

          <div className="rounded-lg border border-cream-300 bg-cream-50 overflow-hidden shadow-2xs">
            <table className="w-full text-left text-xs">
              <thead className="bg-cream-100 text-cream-700 font-medium border-b border-cream-300">
                <tr>
                  <th className="py-2.5 px-4 font-mono text-[11px] uppercase tracking-wider text-cream-600">Customer</th>
                  <th className="py-2.5 px-4 font-mono text-[11px] uppercase tracking-wider text-cream-600">Plan / Bundles</th>
                  <th className="py-2.5 px-4 font-mono text-[11px] uppercase tracking-wider text-cream-600">Cost / Cadence</th>
                  <th className="py-2.5 px-4 font-mono text-[11px] uppercase tracking-wider text-cream-600">Next Billing Date</th>
                  <th className="py-2.5 px-4 font-mono text-[11px] uppercase tracking-wider text-cream-600">Lifecycle Status</th>
                  <th className="py-2.5 px-4 font-mono text-[11px] uppercase tracking-wider text-cream-600 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-cream-200">
                {subscriptions.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-8 text-center text-xs text-cream-600">
                      No active customer subscriptions found. Enroll a customer or create a plan to begin.
                    </td>
                  </tr>
                ) : (
                  subscriptions.map((s) => {
                    const isPaused = s.status === "PAUSED";
                    const isTrial = s.status === "TRIALING";
                    const isGrace = s.status === "GRACE_PERIOD";

                    return (
                      <tr key={s.subscription_id} className="hover:bg-cream-100/60 transition-colors">
                        <td className="py-3 px-4 font-semibold text-cream-900">
                          {s.customer_name || s.customer_id?.slice(0, 8)}
                        </td>
                        <td className="py-3 px-4 text-cream-800">
                          <div className="font-medium">{s.plan_name}</div>
                          {s.items && s.items.length > 0 && (
                            <div className="text-[10px] text-cream-500 font-mono mt-0.5">
                              {s.items.length} Bundled Plan Item(s)
                            </div>
                          )}
                        </td>
                        <td className="py-3 px-4 font-mono text-cream-900 font-medium">
                          ${formatMoney(s.cost)} / {s.billing_interval?.toLowerCase()}
                        </td>
                        <td className="py-3 px-4 font-mono text-cream-700">{s.next_billing_date}</td>
                        <td className="py-3 px-4">
                          {isTrial ? (
                            <span className="inline-flex items-center gap-1 rounded bg-amber-100 border border-amber-400 px-2 py-0.5 text-[10px] font-semibold text-amber-900">
                              Free Trial
                            </span>
                          ) : isGrace ? (
                            <span className="inline-flex items-center gap-1 rounded bg-terracotta-100 border border-terracotta-400 px-2 py-0.5 text-[10px] font-semibold text-terracotta-900">
                              Grace Period
                            </span>
                          ) : isPaused ? (
                            <span className="inline-flex items-center gap-1 rounded bg-cream-200 border border-cream-400 px-2 py-0.5 text-[10px] font-semibold text-cream-800">
                              Paused
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 rounded bg-sage-100 border border-sage-500/30 px-2 py-0.5 text-[10px] font-semibold text-sage-800">
                              {s.status}
                            </span>
                          )}
                        </td>
                        <td className="py-3 px-4 text-right">
                          {isPaused ? (
                            <button
                              onClick={() => handleResumeSubscription(s.subscription_id)}
                              className="rounded border border-sage-400 bg-sage-50 px-2.5 py-1 text-[11px] font-semibold text-sage-900 hover:bg-sage-100 transition-colors inline-flex items-center gap-1"
                            >
                              <Play className="h-3 w-3 text-sage-700" />
                              <span>Resume</span>
                            </button>
                          ) : (
                            <button
                              onClick={() => handlePauseSubscription(s.subscription_id)}
                              className="rounded border border-cream-300 bg-white px-2.5 py-1 text-[11px] font-medium text-cream-800 hover:bg-cream-100 transition-colors inline-flex items-center gap-1"
                            >
                              <Pause className="h-3 w-3 text-cream-600" />
                              <span>Pause</span>
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

      {/* TAB: Payment Terms & Schedules */}
      {activeTab === "payment-terms" && (
        <div className="space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-cream-900">Payment Terms Templates &amp; Milestone Schedules</h2>
              <p className="text-xs text-cream-600">
                ERPNext-standard milestone installment schedules (e.g. 30% Advance, 50% Dispatch, 20% Net 30) and advance allocation.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setShowPaymentTermsModal(true)}
                className="flex items-center gap-1.5 rounded-md border border-cream-300 bg-cream-100 px-3 py-1.5 text-xs font-medium text-cream-900 hover:bg-cream-200 transition-colors"
              >
                <Plus className="h-3.5 w-3.5" />
                <span>New Terms Template</span>
              </button>
              <button
                onClick={() => setShowAdvanceModal(true)}
                className="flex items-center gap-1.5 rounded-md border border-sage-400 bg-sage-50 px-3 py-1.5 text-xs font-medium text-sage-900 hover:bg-sage-100 transition-colors shadow-2xs"
              >
                <Coins className="h-3.5 w-3.5 text-sage-700" />
                <span>Reconcile Advance Deposit</span>
              </button>
            </div>
          </div>

          {/* Active Payment Terms Templates List */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {paymentTermsTemplates.length === 0 ? (
              <div className="col-span-2 py-8 text-center text-xs text-cream-600 border border-cream-300 rounded-lg bg-cream-50">
                No payment terms templates found. Create one to enable installment milestones on invoices.
              </div>
            ) : (
              paymentTermsTemplates.map((tmpl) => (
                <div key={tmpl.template_id} className="rounded-lg border border-cream-300 bg-cream-50 p-4 space-y-3 shadow-2xs">
                  <div className="flex items-center justify-between border-b border-cream-200 pb-2">
                    <span className="font-semibold text-xs text-cream-900">{tmpl.template_name}</span>
                    <span className="rounded bg-cream-200 text-cream-800 px-2 py-0.5 text-[10px] font-mono font-medium">
                      {tmpl.terms?.length || 0} Milestones
                    </span>
                  </div>
                  <div className="space-y-1.5 text-xs">
                    {tmpl.terms?.map((t: any, idx: number) => (
                      <div key={idx} className="flex justify-between items-center text-cream-700 font-mono text-[11px] bg-cream-100/70 p-2 rounded">
                        <span className="font-medium text-cream-900">{t.description}</span>
                        <span>{t.invoice_portion}% &bull; {t.credit_days} days credit</span>
                      </div>
                    ))}
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Generator Tool: Apply Terms to Sales Invoice */}
          <div className="rounded-xl border border-cream-300 bg-cream-100/60 p-5 space-y-4 shadow-2xs">
            <div className="border-b border-cream-300 pb-2">
              <h3 className="text-xs font-bold text-cream-900 uppercase tracking-wider">
                Installment Payment Schedule Generator
              </h3>
              <p className="text-[11px] text-cream-600 mt-0.5">
                Apply a terms template to an issued sales invoice to compute exact milestone maturity dates and amounts.
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs items-end">
              <div>
                <label className="text-cream-800 font-medium block mb-1">Target Sales Invoice</label>
                <select
                  value={selectedInvoiceForSchedule}
                  onChange={(e) => setSelectedInvoiceForSchedule(e.target.value)}
                  className="w-full rounded border border-cream-300 bg-white px-3 py-2 text-xs text-cream-900"
                >
                  <option value="">Select Invoice...</option>
                  {salesInvoices.map((inv) => (
                    <option key={inv.invoice_id} value={inv.invoice_id}>
                      {inv.invoice_number} - {inv.customer_name} (${formatMoney(inv.total_amount)})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="text-cream-800 font-medium block mb-1">Terms Template</label>
                <select
                  value={selectedTemplateForSchedule}
                  onChange={(e) => setSelectedTemplateForSchedule(e.target.value)}
                  className="w-full rounded border border-cream-300 bg-white px-3 py-2 text-xs text-cream-900"
                >
                  <option value="">Select Template...</option>
                  {paymentTermsTemplates.map((t) => (
                    <option key={t.template_id} value={t.template_id}>
                      {t.template_name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <button
                  type="button"
                  onClick={handleApplyPaymentTerms}
                  disabled={isApplyingTerms}
                  className="w-full rounded-md border border-cream-400 bg-cream-900 py-2 text-xs font-semibold text-cream-50 hover:bg-cream-800 transition-colors flex items-center justify-center gap-1.5 shadow-2xs cursor-pointer"
                >
                  <Calendar className="h-3.5 w-3.5" />
                  <span>{isApplyingTerms ? "Generating..." : "Generate Installment Schedule"}</span>
                </button>
              </div>
            </div>

            {invoiceScheduleResult && invoiceScheduleResult.length > 0 && (
              <div className="rounded-lg border border-cream-300 bg-white p-4 space-y-2">
                <div className="font-semibold text-xs text-cream-900 pb-2 border-b border-cream-200">
                  Generated Invoice Milestones ({invoiceScheduleResult.length} Installments)
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="text-[10px] uppercase font-mono text-cream-600 border-b border-cream-200">
                        <th className="pb-1">Milestone Description</th>
                        <th className="pb-1">Due Date</th>
                        <th className="pb-1 text-right">Portion %</th>
                        <th className="pb-1 text-right">Amount Due</th>
                        <th className="pb-1 text-center">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-cream-100">
                      {invoiceScheduleResult.map((m: any, idx: number) => (
                        <tr key={idx}>
                          <td className="py-2 font-medium text-cream-900">{m.payment_term}</td>
                          <td className="py-2 font-mono text-cream-700">{m.due_date}</td>
                          <td className="py-2 text-right font-mono text-cream-800">{m.portion_pct}%</td>
                          <td className="py-2 text-right font-mono font-bold text-cream-950">${formatMoney(m.portion_amount)}</td>
                          <td className="py-2 text-center">
                            <span className="rounded bg-cream-200 px-2 py-0.5 text-[10px] font-semibold text-cream-800">
                              {m.status}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB: Multi-Tier Tax & Charges Templates */}
      {activeTab === "tax-templates" && (
        <div className="space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-cream-900">Multi-Tier Sales Taxes &amp; Charges Templates</h2>
              <p className="text-xs text-cream-600">
                1:1 ERPNext compound cascading tax calculation engine supporting Actual, On Net Total, and On Previous Row.
              </p>
            </div>
            <button
              onClick={() => setShowTaxTemplateModal(true)}
              className="flex items-center gap-1.5 rounded-md border border-cream-300 bg-cream-100 px-3 py-1.5 text-xs font-medium text-cream-900 hover:bg-cream-200 transition-colors"
            >
              <Plus className="h-3.5 w-3.5" />
              <span>New Tax Template</span>
            </button>
          </div>

          {/* Configured Tax Templates */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {taxTemplates.length === 0 ? (
              <div className="col-span-2 py-8 text-center text-xs text-cream-600 border border-cream-300 rounded-lg bg-cream-50">
                No custom tax templates found. Create a template to define compound tax charges.
              </div>
            ) : (
              taxTemplates.map((tmpl) => (
                <div key={tmpl.template_id} className="rounded-lg border border-cream-300 bg-cream-50 p-4 space-y-3 shadow-2xs">
                  <div className="flex items-center justify-between border-b border-cream-200 pb-2">
                    <span className="font-semibold text-xs text-cream-900">{tmpl.title}</span>
                    <span className="rounded bg-cream-200 text-cream-800 px-2 py-0.5 text-[10px] font-mono font-medium">
                      {tmpl.taxes?.length || 0} Charges
                    </span>
                  </div>
                  <div className="space-y-1.5 text-xs">
                    {tmpl.taxes?.map((tx: any, idx: number) => (
                      <div key={idx} className="flex justify-between items-center text-cream-700 font-mono text-[11px] bg-cream-100/70 p-2 rounded">
                        <div>
                          <span className="font-semibold text-cream-900">{tx.description}</span>
                          <span className="ml-1 text-[10px] text-cream-500">[{tx.charge_type}]</span>
                        </div>
                        <span className="font-bold text-cream-950">
                          {tx.charge_type === "Actual" ? `$${formatMoney(tx.rate)}` : `${tx.rate}%`}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Interactive Live Cascading Tax Engine */}
          <div className="rounded-xl border border-cream-300 bg-cream-100/60 p-5 space-y-4 shadow-2xs">
            <div className="border-b border-cream-300 pb-2">
              <h3 className="text-xs font-bold text-cream-900 uppercase tracking-wider flex items-center gap-1.5">
                <Calculator className="h-4 w-4 text-cream-700" />
                <span>Interactive Live Cascading Tax Engine Simulator</span>
              </h3>
              <p className="text-[11px] text-cream-600 mt-0.5">
                Test compound charge rules: On Net Total (Row 1), Fixed Actual Freight (Row 2), and Surcharge on Previous Row (Row 3).
              </p>
            </div>

            <div className="flex flex-col sm:flex-row items-end gap-3">
              <div className="flex-1">
                <label className="text-xs font-medium text-cream-800 block mb-1">Net Invoice Total ($)</label>
                <input
                  type="number"
                  value={interactiveTaxNetTotal}
                  onChange={(e) => setInteractiveTaxNetTotal(Number(e.target.value))}
                  className="w-full rounded border border-cream-300 bg-white px-3 py-2 text-xs font-mono text-cream-900"
                />
              </div>
              <button
                type="button"
                onClick={handleCalculateCascadingTaxes}
                className="rounded-md border border-cream-400 bg-cream-900 px-4 py-2 text-xs font-semibold text-cream-50 hover:bg-cream-800 transition-colors shadow-2xs cursor-pointer"
              >
                Compute Cascading Taxes &rarr;
              </button>
            </div>

            {interactiveTaxResult && (
              <div className="rounded-lg border border-cream-300 bg-white p-4 space-y-3">
                <div className="font-semibold text-xs text-cream-900 border-b border-cream-200 pb-2">
                  Engine Evaluation Breakdown
                </div>
                <div className="space-y-1.5 text-xs">
                  {interactiveTaxResult.rows?.map((r: any) => (
                    <div key={r.row_id} className="flex justify-between items-center bg-cream-50 p-2 rounded border border-cream-200 font-mono">
                      <div>
                        <span className="font-bold text-cream-900">Row {r.row_id}: {r.description}</span>
                        <span className="ml-1 text-[11px] text-cream-600">({r.charge_type} @ {r.rate}{r.charge_type === 'Actual' ? '$' : '%'})</span>
                      </div>
                      <span className="font-bold text-cream-950">+${formatMoney(r.tax_amount)}</span>
                    </div>
                  ))}
                </div>
                <div className="border-t border-cream-300 pt-2 flex justify-between font-bold text-xs">
                  <span>Grand Total (Net + Taxes &amp; Charges):</span>
                  <span className="font-mono text-sm text-cream-950">${formatMoney(interactiveTaxResult.grand_total)}</span>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 2: Dunning */}
      {activeTab === "dunning" && (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-cream-900">Receivables Dunning &amp; Late Fee Automation</h2>
              <p className="text-xs text-cream-600">
                Tiered overdue debt collection with compounding statutory interest and automated escalation letters.
              </p>
            </div>
            <button
              onClick={handleEvaluateDunning}
              className="flex items-center gap-1.5 rounded-md border border-amber-400 bg-amber-50 px-3 py-1.5 text-xs font-semibold text-amber-950 hover:bg-amber-100 transition-colors shadow-2xs"
            >
              <ShieldAlert className="h-3.5 w-3.5 text-amber-700" />
              <span>Evaluate Overdue Invoices Now</span>
            </button>
          </div>

          {/* Dunning Levels Overview */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {dunningTypes.map((t) => (
              <div key={t.dunning_type_id} className="rounded-lg border border-cream-300 bg-cream-100/70 p-3.5 space-y-1">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-xs text-cream-900">{t.dunning_type_name}</span>
                  <span className="text-[10px] font-mono rounded bg-cream-200 px-1.5 py-0.5 text-cream-800">
                    Tier {t.dunning_level ?? 1}
                  </span>
                </div>
                <div className="text-[11px] text-cream-600">
                  Starts at <strong className="text-cream-900">{t.overdue_days_start ?? t.overdue_days} days overdue</strong>
                </div>
                <div className="text-[11px] text-cream-700 pt-1 border-t border-cream-200 flex justify-between font-mono">
                  <span>Fee: ${formatMoney(t.dunning_fee ?? t.fee_amount)}</span>
                  <span>Interest: {t.interest_rate ?? t.interest_rate_pct}%</span>
                </div>
              </div>
            ))}
          </div>

          {/* Notices Table */}
          <div className="rounded-lg border border-cream-300 bg-cream-50 overflow-hidden shadow-2xs">
            <table className="w-full text-left text-xs">
              <thead className="bg-cream-100 text-cream-700 font-medium border-b border-cream-300">
                <tr>
                  <th className="py-2.5 px-4 font-mono text-[11px] uppercase tracking-wider text-cream-600">Notice #</th>
                  <th className="py-2.5 px-4 font-mono text-[11px] uppercase tracking-wider text-cream-600">Customer</th>
                  <th className="py-2.5 px-4 font-mono text-[11px] uppercase tracking-wider text-cream-600">Overdue Days</th>
                  <th className="py-2.5 px-4 font-mono text-[11px] uppercase tracking-wider text-cream-600">Principal</th>
                  <th className="py-2.5 px-4 font-mono text-[11px] uppercase tracking-wider text-cream-600">Late Fee</th>
                  <th className="py-2.5 px-4 font-mono text-[11px] uppercase tracking-wider text-cream-600">Interest</th>
                  <th className="py-2.5 px-4 font-mono text-[11px] uppercase tracking-wider text-cream-600">Total Due</th>
                  <th className="py-2.5 px-4 font-mono text-[11px] uppercase tracking-wider text-cream-600">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-cream-200">
                {dunningNotices.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="py-8 text-center text-xs text-cream-600">
                      No overdue dunning notices currently issued. All accounts are compliant.
                    </td>
                  </tr>
                ) : (
                  dunningNotices.map((n) => (
                    <tr key={n.dunning_notice_id} className="hover:bg-cream-100/60 transition-colors">
                      <td className="py-3 px-4 font-mono font-semibold text-cream-900">{n.notice_number}</td>
                      <td className="py-3 px-4 text-cream-800">{n.customer_id?.slice(0, 8)}</td>
                      <td className="py-3 px-4 font-mono text-terracotta-700 font-semibold">{n.overdue_days} days</td>
                      <td className="py-3 px-4 font-mono">${formatMoney(n.outstanding_amount)}</td>
                      <td className="py-3 px-4 font-mono text-amber-800">+${formatMoney(n.fee_amount)}</td>
                      <td className="py-3 px-4 font-mono text-amber-800">+${formatMoney(n.interest_amount)}</td>
                      <td className="py-3 px-4 font-mono font-bold text-cream-900">${formatMoney(n.total_dunning_amount)}</td>
                      <td className="py-3 px-4">
                        <span className="inline-flex items-center gap-1 rounded bg-terracotta-100 border border-terracotta-500/30 px-2 py-0.5 text-[10px] font-semibold text-terracotta-800">
                          {n.status}
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 3: Budgets */}
      {activeTab === "budgets" && (
        <div className="space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-cream-900">Budgetary Control &amp; Expenditure Policies</h2>
              <p className="text-xs text-cream-600">
                Pre-flight authorization enforcing WARN and hard STOP ceilings before committing expenses.
              </p>
            </div>
            <button
              onClick={() => setShowBudgetModal(true)}
              className="flex items-center gap-1.5 rounded-md border border-cream-400 bg-cream-900 px-3 py-1.5 text-xs font-medium text-cream-50 hover:bg-cream-800 transition-colors shadow-2xs"
            >
              <Plus className="h-3.5 w-3.5" />
              <span>New Budget Limit</span>
            </button>
          </div>

          <div className="rounded-lg border border-cream-300 bg-cream-50 overflow-hidden shadow-2xs">
            <table className="w-full text-left text-xs">
              <thead className="bg-cream-100 text-cream-700 font-medium border-b border-cream-300">
                <tr>
                  <th className="py-2.5 px-4 font-mono text-[11px] uppercase tracking-wider text-cream-600">Budget Name</th>
                  <th className="py-2.5 px-4 font-mono text-[11px] uppercase tracking-wider text-cream-600">Cost Center</th>
                  <th className="py-2.5 px-4 font-mono text-[11px] uppercase tracking-wider text-cream-600">Account Code</th>
                  <th className="py-2.5 px-4 font-mono text-[11px] uppercase tracking-wider text-cream-600">Year</th>
                  <th className="py-2.5 px-4 font-mono text-[11px] uppercase tracking-wider text-cream-600">Allocated Limit</th>
                  <th className="py-2.5 px-4 font-mono text-[11px] uppercase tracking-wider text-cream-600">Action on Exceed</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-cream-200">
                {budgets.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-8 text-center text-xs text-cream-600">
                      No departmental budgets defined yet. Create a budget to enforce controls.
                    </td>
                  </tr>
                ) : (
                  budgets.map((b) => (
                    <tr key={b.budget_id} className="hover:bg-cream-100/60 transition-colors">
                      <td className="py-3 px-4 font-semibold text-cream-900">{b.budget_name}</td>
                      <td className="py-3 px-4 font-mono text-cream-700">{b.cost_center}</td>
                      <td className="py-3 px-4 font-mono text-cream-700">{b.account_code}</td>
                      <td className="py-3 px-4 font-mono text-cream-700">{b.fiscal_year}</td>
                      <td className="py-3 px-4 font-mono font-bold text-cream-900">
                        ${formatMoney(b.budget_amount)}
                      </td>
                      <td className="py-3 px-4">
                        <span
                          className={`inline-flex items-center gap-1 rounded px-2 py-0.5 text-[10px] font-semibold ${
                            b.action_on_exceed === "STOP"
                              ? "bg-terracotta-100 border border-terracotta-500/30 text-terracotta-800"
                              : "bg-amber-100 border border-amber-500/40 text-amber-900"
                          }`}
                        >
                          {b.action_on_exceed}
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* Interactive Pre-Flight Budget Checker */}
          <div className="rounded-xl border border-cream-300 bg-cream-100/80 p-5 space-y-4 shadow-2xs">
            <div className="flex items-center gap-2 border-b border-cream-200 pb-3">
              <ShieldCheck className="h-4 w-4 text-cream-800" />
              <h3 className="text-xs font-bold text-cream-900 uppercase tracking-wide">
                Interactive Pre-Flight Budget Compliance Simulation
              </h3>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
              <div>
                <label className="text-cream-700 font-medium block mb-1">Cost Center</label>
                <input
                  type="text"
                  value={evalCostCenter}
                  onChange={(e) => setEvalCostCenter(e.target.value)}
                  className="w-full rounded-md border border-cream-300 bg-white px-3 py-1.5 font-mono text-xs text-cream-900"
                />
              </div>
              <div>
                <label className="text-cream-700 font-medium block mb-1">Account Code</label>
                <input
                  type="text"
                  value={evalAccount}
                  onChange={(e) => setEvalAccount(e.target.value)}
                  className="w-full rounded-md border border-cream-300 bg-white px-3 py-1.5 font-mono text-xs text-cream-900"
                />
              </div>
              <div>
                <label className="text-cream-700 font-medium block mb-1">Proposed Spending ($)</label>
                <div className="flex gap-2">
                  <input
                    type="number"
                    value={evalAmount}
                    onChange={(e) => setEvalAmount(Number(e.target.value))}
                    className="w-full rounded-md border border-cream-300 bg-white px-3 py-1.5 font-mono text-xs text-cream-900"
                  />
                  <button
                    onClick={handleEvaluateBudgetTest}
                    disabled={isEvaluatingBudget}
                    className="rounded-md border border-cream-400 bg-cream-900 px-3 py-1.5 text-xs font-semibold text-cream-50 hover:bg-cream-800 transition-colors whitespace-nowrap"
                  >
                    {isEvaluatingBudget ? "Checking..." : "Verify Policy"}
                  </button>
                </div>
              </div>
            </div>

            {evalResult && (
              <div
                className={`p-3 rounded-lg border text-xs flex items-center justify-between ${
                  evalResult.action === "STOP"
                    ? "bg-terracotta-50 border-terracotta-300 text-terracotta-900"
                    : evalResult.action === "WARN"
                    ? "bg-amber-50 border-amber-300 text-amber-950"
                    : "bg-sage-50 border-sage-300 text-sage-900"
                }`}
              >
                <div className="flex items-center gap-2">
                  {evalResult.action === "STOP" ? (
                    <AlertCircle className="h-4 w-4 text-terracotta-700" />
                  ) : evalResult.action === "WARN" ? (
                    <AlertTriangle className="h-4 w-4 text-amber-700" />
                  ) : (
                    <CheckCircle2 className="h-4 w-4 text-sage-700" />
                  )}
                  <span>{evalResult.message || `Policy Decision: ${evalResult.action}`}</span>
                </div>
                <span className="font-mono font-bold text-[11px]">
                  {evalResult.action === "STOP"
                    ? "BLOCK TRANSACTION"
                    : evalResult.action === "WARN"
                    ? "NOTIFY CONTROLLER"
                    : "PASSED"}
                </span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 4: Credit Notes */}
      {activeTab === "credit-notes" && (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-cream-900">Sales Return &bull; Credit Notes (AR Reversals)</h2>
              <p className="text-xs text-cream-600">
                Customer returns linked to sales invoices with warehouse restocking and reverse GL journal entries.
              </p>
            </div>
            <button
              onClick={() => setShowCreditNoteModal(true)}
              className="flex items-center gap-1.5 rounded-md border border-cream-400 bg-cream-900 px-3 py-1.5 text-xs font-medium text-cream-50 hover:bg-cream-800 transition-colors shadow-2xs"
            >
              <Plus className="h-3.5 w-3.5" />
              <span>Issue Credit Note</span>
            </button>
          </div>

          <div className="rounded-lg border border-cream-300 bg-cream-50 overflow-hidden shadow-2xs">
            <table className="w-full text-left text-xs">
              <thead className="bg-cream-100 text-cream-700 font-medium border-b border-cream-300">
                <tr>
                  <th className="py-2.5 px-4 font-mono text-[11px] uppercase tracking-wider text-cream-600">Credit Note #</th>
                  <th className="py-2.5 px-4 font-mono text-[11px] uppercase tracking-wider text-cream-600">Customer</th>
                  <th className="py-2.5 px-4 font-mono text-[11px] uppercase tracking-wider text-cream-600">Reason</th>
                  <th className="py-2.5 px-4 font-mono text-[11px] uppercase tracking-wider text-cream-600">Subtotal</th>
                  <th className="py-2.5 px-4 font-mono text-[11px] uppercase tracking-wider text-cream-600">Tax</th>
                  <th className="py-2.5 px-4 font-mono text-[11px] uppercase tracking-wider text-cream-600">Total Credited</th>
                  <th className="py-2.5 px-4 font-mono text-[11px] uppercase tracking-wider text-cream-600">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-cream-200">
                {creditNotes.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="py-8 text-center text-xs text-cream-600">
                      No sales return credit notes logged.
                    </td>
                  </tr>
                ) : (
                  creditNotes.map((c) => (
                    <tr key={c.credit_note_id} className="hover:bg-cream-100/60 transition-colors">
                      <td className="py-3 px-4 font-mono font-semibold text-cream-900">{c.credit_note_number}</td>
                      <td className="py-3 px-4 text-cream-800">{c.customer_id?.slice(0, 8)}</td>
                      <td className="py-3 px-4 text-cream-700 truncate max-w-xs">{c.reason}</td>
                      <td className="py-3 px-4 font-mono">${formatMoney(c.subtotal)}</td>
                      <td className="py-3 px-4 font-mono text-sage-700">${formatMoney(c.tax_amount)}</td>
                      <td className="py-3 px-4 font-mono font-bold text-cream-900">${formatMoney(c.total_amount)}</td>
                      <td className="py-3 px-4">
                        <span className="inline-flex items-center gap-1 rounded bg-cream-200 border border-cream-300 px-2 py-0.5 text-[10px] font-semibold text-cream-800">
                          {c.status}
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 5: Debit Notes */}
      {activeTab === "debit-notes" && (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-cream-900">Purchase Return &bull; Debit Notes (AP Reversals)</h2>
              <p className="text-xs text-cream-600">
                Supplier chargebacks and raw material returns reducing outstanding accounts payable balances.
              </p>
            </div>
            <button
              onClick={() => setShowDebitNoteModal(true)}
              className="flex items-center gap-1.5 rounded-md border border-cream-400 bg-cream-900 px-3 py-1.5 text-xs font-medium text-cream-50 hover:bg-cream-800 transition-colors shadow-2xs"
            >
              <Plus className="h-3.5 w-3.5" />
              <span>Issue Debit Note</span>
            </button>
          </div>

          <div className="rounded-lg border border-cream-300 bg-cream-50 overflow-hidden shadow-2xs">
            <table className="w-full text-left text-xs">
              <thead className="bg-cream-100 text-cream-700 font-medium border-b border-cream-300">
                <tr>
                  <th className="py-2.5 px-4 font-mono text-[11px] uppercase tracking-wider text-cream-600">Debit Note #</th>
                  <th className="py-2.5 px-4 font-mono text-[11px] uppercase tracking-wider text-cream-600">Supplier</th>
                  <th className="py-2.5 px-4 font-mono text-[11px] uppercase tracking-wider text-cream-600">Reason</th>
                  <th className="py-2.5 px-4 font-mono text-[11px] uppercase tracking-wider text-cream-600">Subtotal</th>
                  <th className="py-2.5 px-4 font-mono text-[11px] uppercase tracking-wider text-cream-600">Tax</th>
                  <th className="py-2.5 px-4 font-mono text-[11px] uppercase tracking-wider text-cream-600">Total Debited</th>
                  <th className="py-2.5 px-4 font-mono text-[11px] uppercase tracking-wider text-cream-600">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-cream-200">
                {debitNotes.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="py-8 text-center text-xs text-cream-600">
                      No purchase return debit notes logged.
                    </td>
                  </tr>
                ) : (
                  debitNotes.map((d) => (
                    <tr key={d.debit_note_id} className="hover:bg-cream-100/60 transition-colors">
                      <td className="py-3 px-4 font-mono font-semibold text-cream-900">{d.debit_note_number}</td>
                      <td className="py-3 px-4 text-cream-800">{d.supplier_id?.slice(0, 8)}</td>
                      <td className="py-3 px-4 text-cream-700 truncate max-w-xs">{d.reason}</td>
                      <td className="py-3 px-4 font-mono">${formatMoney(d.subtotal)}</td>
                      <td className="py-3 px-4 font-mono text-cream-700">${formatMoney(d.tax_amount)}</td>
                      <td className="py-3 px-4 font-mono font-bold text-cream-900">${formatMoney(d.total_amount)}</td>
                      <td className="py-3 px-4">
                        <span className="inline-flex items-center gap-1 rounded bg-cream-200 border border-cream-300 px-2 py-0.5 text-[10px] font-semibold text-cream-800">
                          {d.status}
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 6: TDS / Withholding */}
      {activeTab === "tax-withholding" && (
        <div className="space-y-4">
          <div>
            <h2 className="text-sm font-semibold text-cream-900">Tax Deducted at Source (TDS) &amp; Withholding Categories</h2>
            <p className="text-xs text-cream-600">
              Statutory fiscal thresholds for contractor, rental, and professional service withholding.
            </p>
          </div>

          <div className="rounded-lg border border-cream-300 bg-cream-50 overflow-hidden shadow-2xs">
            <table className="w-full text-left text-xs">
              <thead className="bg-cream-100 text-cream-700 font-medium border-b border-cream-300">
                <tr>
                  <th className="py-2.5 px-4 font-mono text-[11px] uppercase tracking-wider text-cream-600">Category Name</th>
                  <th className="py-2.5 px-4 font-mono text-[11px] uppercase tracking-wider text-cream-600">Single Threshold</th>
                  <th className="py-2.5 px-4 font-mono text-[11px] uppercase tracking-wider text-cream-600">Cumulative Threshold</th>
                  <th className="py-2.5 px-4 font-mono text-[11px] uppercase tracking-wider text-cream-600">Standard Rate</th>
                  <th className="py-2.5 px-4 font-mono text-[11px] uppercase tracking-wider text-cream-600">GL Account</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-cream-200">
                {taxCategories.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="py-8 text-center text-xs text-cream-600">
                      No tax withholding categories defined yet.
                    </td>
                  </tr>
                ) : (
                  taxCategories.map((t) => (
                    <tr key={t.category_id} className="hover:bg-cream-100/60 transition-colors">
                      <td className="py-3 px-4 font-semibold text-cream-900">{t.category_name}</td>
                      <td className="py-3 px-4 font-mono">${formatMoney(t.single_transaction_threshold ?? t.single_threshold)}</td>
                      <td className="py-3 px-4 font-mono">${formatMoney(t.cumulative_threshold)}</td>
                      <td className="py-3 px-4 font-mono font-bold text-amber-800">{t.standard_rate ?? t.rate_pct}%</td>
                      <td className="py-3 px-4 font-mono text-cream-700">{t.account_code || "2200-TDS-PAYABLE"}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* MODAL 1: New Plan */}
      {showPlanModal && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-cream-50 border border-cream-300 rounded-xl shadow-xl w-full max-w-md p-6 space-y-4">
            <div className="flex justify-between items-center border-b border-cream-300 pb-3">
              <h3 className="text-sm font-bold text-cream-900">Create Subscription Plan</h3>
              <button onClick={() => setShowPlanModal(false)} className="text-cream-600 hover:text-cream-900">
                <X className="h-4 w-4" />
              </button>
            </div>
            <form onSubmit={handleCreatePlan} className="space-y-3 text-xs">
              <div>
                <label className="text-cream-800 font-medium block mb-1">Plan Name</label>
                <input
                  type="text"
                  placeholder="e.g. Enterprise SLA Monthly"
                  value={newPlan.plan_name}
                  onChange={(e) => setNewPlan({ ...newPlan, plan_name: e.target.value })}
                  className="w-full rounded-md border border-cream-300 bg-white px-3 py-2 text-xs text-cream-900"
                  required
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-cream-800 font-medium block mb-1">Billing Interval</label>
                  <select
                    value={newPlan.billing_interval}
                    onChange={(e) => setNewPlan({ ...newPlan, billing_interval: e.target.value })}
                    className="w-full rounded-md border border-cream-300 bg-white px-3 py-2 text-xs text-cream-900"
                  >
                    <option value="MONTHLY">Monthly</option>
                    <option value="QUARTERLY">Quarterly</option>
                    <option value="ANNUAL">Annual</option>
                  </select>
                </div>
                <div>
                  <label className="text-cream-800 font-medium block mb-1">Recurring Cost ($)</label>
                  <input
                    type="number"
                    value={newPlan.cost}
                    onChange={(e) => setNewPlan({ ...newPlan, cost: Number(e.target.value) })}
                    className="w-full rounded-md border border-cream-300 bg-white px-3 py-2 text-xs font-mono text-cream-900"
                    required
                  />
                </div>
              </div>
              <div className="flex justify-end gap-2 border-t border-cream-300 pt-4">
                <button
                  type="button"
                  onClick={() => setShowPlanModal(false)}
                  className="rounded-md border border-cream-300 bg-cream-100 px-3 py-1.5 text-xs font-medium text-cream-800 hover:bg-cream-200"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="rounded-md border border-cream-400 bg-cream-900 px-4 py-1.5 text-xs font-medium text-cream-50 hover:bg-cream-800"
                >
                  Save Plan
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 2: Enroll Customer */}
      {showSubModal && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-cream-50 border border-cream-300 rounded-xl shadow-xl w-full max-w-md p-6 space-y-4">
            <div className="flex justify-between items-center border-b border-cream-300 pb-3">
              <h3 className="text-sm font-bold text-cream-900">Enroll Customer in Subscription</h3>
              <button onClick={() => setShowSubModal(false)} className="text-cream-600 hover:text-cream-900">
                <X className="h-4 w-4" />
              </button>
            </div>
            <form onSubmit={handleCreateSub} className="space-y-3 text-xs">
              <div>
                <label className="text-cream-800 font-medium block mb-1">Select Customer</label>
                <select
                  value={newSub.customer_id}
                  onChange={(e) => setNewSub({ ...newSub, customer_id: e.target.value })}
                  className="w-full rounded-md border border-cream-300 bg-white px-3 py-2 text-xs text-cream-900"
                  required
                >
                  {customers.map((c) => (
                    <option key={c.customer_id} value={c.customer_id}>
                      {c.customer_name} ({c.customer_code})
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-cream-800 font-medium block mb-1">Subscription Plan</label>
                <select
                  value={newSub.plan_id}
                  onChange={(e) => setNewSub({ ...newSub, plan_id: e.target.value })}
                  className="w-full rounded-md border border-cream-300 bg-white px-3 py-2 text-xs text-cream-900"
                  required
                >
                  {plans.map((p) => (
                    <option key={p.plan_id} value={p.plan_id}>
                      {p.plan_name} (${formatMoney(p.cost)} / {p.billing_interval?.toLowerCase()})
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex justify-end gap-2 border-t border-cream-300 pt-4">
                <button
                  type="button"
                  onClick={() => setShowSubModal(false)}
                  className="rounded-md border border-cream-300 bg-cream-100 px-3 py-1.5 text-xs font-medium text-cream-800 hover:bg-cream-200"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="rounded-md border border-cream-400 bg-cream-900 px-4 py-1.5 text-xs font-medium text-cream-50 hover:bg-cream-800"
                >
                  Enroll Now
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 3: New Budget */}
      {showBudgetModal && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-cream-50 border border-cream-300 rounded-xl shadow-xl w-full max-w-md p-6 space-y-4">
            <div className="flex justify-between items-center border-b border-cream-300 pb-3">
              <h3 className="text-sm font-bold text-cream-900">Define Departmental Budget Limit</h3>
              <button onClick={() => setShowBudgetModal(false)} className="text-cream-600 hover:text-cream-900">
                <X className="h-4 w-4" />
              </button>
            </div>
            <form onSubmit={handleCreateBudget} className="space-y-3 text-xs">
              <div>
                <label className="text-cream-800 font-medium block mb-1">Budget Label</label>
                <input
                  type="text"
                  placeholder="e.g. FY2026 Production Tooling Budget"
                  value={newBudget.budget_name}
                  onChange={(e) => setNewBudget({ ...newBudget, budget_name: e.target.value })}
                  className="w-full rounded-md border border-cream-300 bg-white px-3 py-2 text-xs text-cream-900"
                  required
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-cream-800 font-medium block mb-1">Cost Center</label>
                  <input
                    type="text"
                    value={newBudget.cost_center}
                    onChange={(e) => setNewBudget({ ...newBudget, cost_center: e.target.value })}
                    className="w-full rounded-md border border-cream-300 bg-white px-3 py-2 text-xs font-mono text-cream-900"
                    required
                  />
                </div>
                <div>
                  <label className="text-cream-800 font-medium block mb-1">GL Account Code</label>
                  <input
                    type="text"
                    value={newBudget.account_code}
                    onChange={(e) => setNewBudget({ ...newBudget, account_code: e.target.value })}
                    className="w-full rounded-md border border-cream-300 bg-white px-3 py-2 text-xs font-mono text-cream-900"
                    required
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-cream-800 font-medium block mb-1">Total Limit ($)</label>
                  <input
                    type="number"
                    value={newBudget.budget_amount}
                    onChange={(e) => setNewBudget({ ...newBudget, budget_amount: Number(e.target.value) })}
                    className="w-full rounded-md border border-cream-300 bg-white px-3 py-2 text-xs font-mono text-cream-900"
                    required
                  />
                </div>
                <div>
                  <label className="text-cream-800 font-medium block mb-1">On Exceed Policy</label>
                  <select
                    value={newBudget.action_on_exceed}
                    onChange={(e) => setNewBudget({ ...newBudget, action_on_exceed: e.target.value })}
                    className="w-full rounded-md border border-cream-300 bg-white px-3 py-2 text-xs text-cream-900"
                  >
                    <option value="WARN">WARN (Log Notification)</option>
                    <option value="STOP">STOP (Hard Rejection)</option>
                  </select>
                </div>
              </div>
              <div className="flex justify-end gap-2 border-t border-cream-300 pt-4">
                <button
                  type="button"
                  onClick={() => setShowBudgetModal(false)}
                  className="rounded-md border border-cream-300 bg-cream-100 px-3 py-1.5 text-xs font-medium text-cream-800 hover:bg-cream-200"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="rounded-md border border-cream-400 bg-cream-900 px-4 py-1.5 text-xs font-medium text-cream-50 hover:bg-cream-800"
                >
                  Save Budget
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 4: Issue Credit Note */}
      {showCreditNoteModal && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-cream-50 border border-cream-300 rounded-xl shadow-xl w-full max-w-md p-6 space-y-4">
            <div className="flex justify-between items-center border-b border-cream-300 pb-3">
              <h3 className="text-sm font-bold text-cream-900">Issue Sales Credit Note (Return)</h3>
              <button onClick={() => setShowCreditNoteModal(false)} className="text-cream-600 hover:text-cream-900">
                <X className="h-4 w-4" />
              </button>
            </div>
            <form onSubmit={handleCreateCreditNote} className="space-y-3 text-xs">
              <div>
                <label className="text-cream-800 font-medium block mb-1">Customer</label>
                <select
                  value={newCN.customer_id}
                  onChange={(e) => setNewCN({ ...newCN, customer_id: e.target.value })}
                  className="w-full rounded-md border border-cream-300 bg-white px-3 py-2 text-xs text-cream-900"
                  required
                >
                  {customers.map((c) => (
                    <option key={c.customer_id} value={c.customer_id}>
                      {c.customer_name} ({c.customer_code})
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-cream-800 font-medium block mb-1">Return Reason</label>
                <input
                  type="text"
                  value={newCN.reason}
                  onChange={(e) => setNewCN({ ...newCN, reason: e.target.value })}
                  className="w-full rounded-md border border-cream-300 bg-white px-3 py-2 text-xs text-cream-900"
                  required
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-cream-800 font-medium block mb-1">Item</label>
                  <select
                    value={newCN.item_id}
                    onChange={(e) => setNewCN({ ...newCN, item_id: e.target.value })}
                    className="w-full rounded-md border border-cream-300 bg-white px-3 py-2 text-xs text-cream-900"
                  >
                    {items.map((i) => (
                      <option key={i.item_id} value={i.item_id}>
                        {i.item_code}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="text-cream-800 font-medium block mb-1">Return Qty</label>
                  <input
                    type="number"
                    value={newCN.quantity}
                    onChange={(e) => setNewCN({ ...newCN, quantity: Number(e.target.value) })}
                    className="w-full rounded-md border border-cream-300 bg-white px-3 py-2 text-xs font-mono text-cream-900"
                  />
                </div>
              </div>
              <div className="flex justify-end gap-2 border-t border-cream-300 pt-4">
                <button
                  type="button"
                  onClick={() => setShowCreditNoteModal(false)}
                  className="rounded-md border border-cream-300 bg-cream-100 px-3 py-1.5 text-xs font-medium text-cream-800 hover:bg-cream-200"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="rounded-md border border-cream-400 bg-cream-900 px-4 py-1.5 text-xs font-medium text-cream-50 hover:bg-cream-800"
                >
                  Issue Credit Note
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 5: Issue Debit Note */}
      {showDebitNoteModal && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-cream-50 border border-cream-300 rounded-xl shadow-xl w-full max-w-md p-6 space-y-4">
            <div className="flex justify-between items-center border-b border-cream-300 pb-3">
              <h3 className="text-sm font-bold text-cream-900">Issue Purchase Debit Note (Vendor Return)</h3>
              <button onClick={() => setShowDebitNoteModal(false)} className="text-cream-600 hover:text-cream-900">
                <X className="h-4 w-4" />
              </button>
            </div>
            <form onSubmit={handleCreateDebitNote} className="space-y-3 text-xs">
              <div>
                <label className="text-cream-800 font-medium block mb-1">Supplier</label>
                <select
                  value={newDN.supplier_id}
                  onChange={(e) => setNewDN({ ...newDN, supplier_id: e.target.value })}
                  className="w-full rounded-md border border-cream-300 bg-white px-3 py-2 text-xs text-cream-900"
                  required
                >
                  {suppliers.map((s) => (
                    <option key={s.supplier_id} value={s.supplier_id}>
                      {s.supplier_name} ({s.supplier_code})
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-cream-800 font-medium block mb-1">Dispute / Return Reason</label>
                <input
                  type="text"
                  value={newDN.reason}
                  onChange={(e) => setNewDN({ ...newDN, reason: e.target.value })}
                  className="w-full rounded-md border border-cream-300 bg-white px-3 py-2 text-xs text-cream-900"
                  required
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-cream-800 font-medium block mb-1">Item</label>
                  <select
                    value={newDN.item_id}
                    onChange={(e) => setNewDN({ ...newDN, item_id: e.target.value })}
                    className="w-full rounded-md border border-cream-300 bg-white px-3 py-2 text-xs text-cream-900"
                  >
                    {items.map((i) => (
                      <option key={i.item_id} value={i.item_id}>
                        {i.item_code}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="text-cream-800 font-medium block mb-1">Return Qty</label>
                  <input
                    type="number"
                    value={newDN.quantity}
                    onChange={(e) => setNewDN({ ...newDN, quantity: Number(e.target.value) })}
                    className="w-full rounded-md border border-cream-300 bg-white px-3 py-2 text-xs font-mono text-cream-900"
                  />
                </div>
              </div>
              <div className="flex justify-end gap-2 border-t border-cream-300 pt-4">
                <button
                  type="button"
                  onClick={() => setShowDebitNoteModal(false)}
                  className="rounded-md border border-cream-300 bg-cream-100 px-3 py-1.5 text-xs font-medium text-cream-800 hover:bg-cream-200"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="rounded-md border border-cream-400 bg-cream-900 px-4 py-1.5 text-xs font-medium text-cream-50 hover:bg-cream-800"
                >
                  Issue Debit Note
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 6: New Payment Terms Template */}
      {showPaymentTermsModal && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-cream-50 border border-cream-300 rounded-xl shadow-xl w-full max-w-lg p-6 space-y-4">
            <div className="flex justify-between items-center border-b border-cream-300 pb-3">
              <h3 className="text-sm font-bold text-cream-900">Create Payment Terms Template</h3>
              <button onClick={() => setShowPaymentTermsModal(false)} className="text-cream-600 hover:text-cream-900">
                <X className="h-4 w-4" />
              </button>
            </div>
            <form onSubmit={handleCreatePaymentTerms} className="space-y-4 text-xs">
              <div>
                <label className="text-cream-800 font-medium block mb-1">Template Name *</label>
                <input
                  type="text"
                  required
                  value={newPTT.template_name}
                  onChange={(e) => setNewPTT({ ...newPTT, template_name: e.target.value })}
                  placeholder="e.g. 30-50-20 Construction Milestones"
                  className="w-full rounded-md border border-cream-300 bg-white px-3 py-2 text-xs text-cream-900 focus:outline-none focus:ring-1 focus:ring-cream-900"
                />
              </div>

              <div>
                <div className="flex justify-between items-center mb-1">
                  <label className="text-cream-800 font-medium">Terms Milestones (Total Must Equal 100%)</label>
                  <span className="font-mono text-[11px] font-bold text-cream-900">
                    Total: {newPTT.terms.reduce((acc, t) => acc + Number(t.invoice_portion || 0), 0)}%
                  </span>
                </div>
                <div className="space-y-2 max-h-[220px] overflow-y-auto">
                  {newPTT.terms.map((term, idx) => (
                    <div key={idx} className="p-2.5 rounded border border-cream-200 bg-cream-100 flex items-center gap-2">
                      <input
                        type="text"
                        placeholder="Description"
                        value={term.description}
                        onChange={(e) => {
                          const updated = [...newPTT.terms];
                          updated[idx].description = e.target.value;
                          setNewPTT({ ...newPTT, terms: updated });
                        }}
                        className="flex-1 rounded border border-cream-300 bg-white px-2 py-1 text-xs"
                      />
                      <div className="flex items-center gap-1 w-24">
                        <input
                          type="number"
                          placeholder="%"
                          value={term.invoice_portion}
                          onChange={(e) => {
                            const updated = [...newPTT.terms];
                            updated[idx].invoice_portion = Number(e.target.value);
                            setNewPTT({ ...newPTT, terms: updated });
                          }}
                          className="w-full rounded border border-cream-300 bg-white px-2 py-1 text-xs font-mono"
                        />
                        <span className="font-mono text-cream-600">%</span>
                      </div>
                      <div className="flex items-center gap-1 w-24">
                        <input
                          type="number"
                          placeholder="Days"
                          value={term.credit_days}
                          onChange={(e) => {
                            const updated = [...newPTT.terms];
                            updated[idx].credit_days = Number(e.target.value);
                            setNewPTT({ ...newPTT, terms: updated });
                          }}
                          className="w-full rounded border border-cream-300 bg-white px-2 py-1 text-xs font-mono"
                        />
                        <span className="text-[10px] text-cream-600">days</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="flex justify-end gap-2 border-t border-cream-300 pt-4">
                <button
                  type="button"
                  onClick={() => setShowPaymentTermsModal(false)}
                  className="rounded-md border border-cream-300 bg-cream-100 px-3 py-1.5 text-xs font-medium text-cream-800 hover:bg-cream-200"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="rounded-md border border-cream-400 bg-cream-900 px-4 py-1.5 text-xs font-medium text-cream-50 hover:bg-cream-800"
                >
                  Save Terms Template
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 7: New Tax Template */}
      {showTaxTemplateModal && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-cream-50 border border-cream-300 rounded-xl shadow-xl w-full max-w-lg p-6 space-y-4">
            <div className="flex justify-between items-center border-b border-cream-300 pb-3">
              <h3 className="text-sm font-bold text-cream-900">Create Sales Taxes &amp; Charges Template</h3>
              <button onClick={() => setShowTaxTemplateModal(false)} className="text-cream-600 hover:text-cream-900">
                <X className="h-4 w-4" />
              </button>
            </div>
            <form onSubmit={handleCreateTaxTemplate} className="space-y-4 text-xs">
              <div>
                <label className="text-cream-800 font-medium block mb-1">Template Title *</label>
                <input
                  type="text"
                  required
                  value={newTaxTmpl.title}
                  onChange={(e) => setNewTaxTmpl({ ...newTaxTmpl, title: e.target.value })}
                  placeholder="e.g. Standard VAT + Freight + Surcharge"
                  className="w-full rounded-md border border-cream-300 bg-white px-3 py-2 text-xs text-cream-900 focus:outline-none focus:ring-1 focus:ring-cream-900"
                />
              </div>

              <div>
                <label className="text-cream-800 font-medium block mb-1">Configured Tax Heads</label>
                <div className="space-y-2 max-h-[220px] overflow-y-auto">
                  {newTaxTmpl.taxes.map((tx, idx) => (
                    <div key={idx} className="p-2.5 rounded border border-cream-200 bg-cream-100 space-y-1.5">
                      <div className="flex items-center gap-2">
                        <input
                          type="text"
                          placeholder="Description"
                          value={tx.description}
                          onChange={(e) => {
                            const updated = [...newTaxTmpl.taxes];
                            updated[idx].description = e.target.value;
                            setNewTaxTmpl({ ...newTaxTmpl, taxes: updated });
                          }}
                          className="flex-1 rounded border border-cream-300 bg-white px-2 py-1 text-xs"
                        />
                        <select
                          value={tx.charge_type}
                          onChange={(e) => {
                            const updated = [...newTaxTmpl.taxes];
                            updated[idx].charge_type = e.target.value;
                            setNewTaxTmpl({ ...newTaxTmpl, taxes: updated });
                          }}
                          className="rounded border border-cream-300 bg-white px-2 py-1 text-xs"
                        >
                          <option value="On Net Total">On Net Total</option>
                          <option value="Actual">Actual Amount</option>
                          <option value="On Previous Row Amount">On Prev Row</option>
                        </select>
                        <input
                          type="number"
                          placeholder="Rate"
                          value={tx.rate}
                          onChange={(e) => {
                            const updated = [...newTaxTmpl.taxes];
                            updated[idx].rate = Number(e.target.value);
                            setNewTaxTmpl({ ...newTaxTmpl, taxes: updated });
                          }}
                          className="w-20 rounded border border-cream-300 bg-white px-2 py-1 text-xs font-mono"
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="flex justify-end gap-2 border-t border-cream-300 pt-4">
                <button
                  type="button"
                  onClick={() => setShowTaxTemplateModal(false)}
                  className="rounded-md border border-cream-300 bg-cream-100 px-3 py-1.5 text-xs font-medium text-cream-800 hover:bg-cream-200"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="rounded-md border border-cream-400 bg-cream-900 px-4 py-1.5 text-xs font-medium text-cream-50 hover:bg-cream-800"
                >
                  Save Tax Template
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 8: Reconcile Customer Advance */}
      {showAdvanceModal && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-cream-50 border border-cream-300 rounded-xl shadow-xl w-full max-w-md p-6 space-y-4">
            <div className="flex justify-between items-center border-b border-cream-300 pb-3">
              <h3 className="text-sm font-bold text-cream-900">Reconcile Customer Advance Payment</h3>
              <button onClick={() => setShowAdvanceModal(false)} className="text-cream-600 hover:text-cream-900">
                <X className="h-4 w-4" />
              </button>
            </div>
            <form onSubmit={handleReconcileAdvance} className="space-y-3 text-xs">
              <div>
                <label className="text-cream-800 font-medium block mb-1">Target Sales Invoice</label>
                <select
                  value={advanceInvoiceId}
                  onChange={(e) => {
                    setAdvanceInvoiceId(e.target.value);
                    const inv = salesInvoices.find((i) => i.invoice_id === e.target.value);
                    if (inv?.customer_id) {
                      setAdvanceCustomerId(inv.customer_id);
                    }
                  }}
                  className="w-full rounded-md border border-cream-300 bg-white px-3 py-2 text-xs text-cream-900"
                  required
                >
                  <option value="">Select Invoice...</option>
                  {salesInvoices.map((inv) => (
                    <option key={inv.invoice_id} value={inv.invoice_id}>
                      {inv.invoice_number} ({inv.customer_name}) - Outstanding: ${formatMoney(inv.outstanding_amount || inv.total_amount)}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="text-cream-800 font-medium block mb-1">Customer</label>
                <select
                  value={advanceCustomerId}
                  onChange={(e) => setAdvanceCustomerId(e.target.value)}
                  className="w-full rounded-md border border-cream-300 bg-white px-3 py-2 text-xs text-cream-900"
                  required
                >
                  <option value="">Select Customer...</option>
                  {customers.map((c) => (
                    <option key={c.customer_id} value={c.customer_id}>
                      {c.customer_name} ({c.customer_code})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="text-cream-800 font-medium block mb-1">Advance Allocation Amount ($)</label>
                <input
                  type="number"
                  required
                  value={advanceAmount}
                  onChange={(e) => setAdvanceAmount(Number(e.target.value))}
                  className="w-full rounded-md border border-cream-300 bg-white px-3 py-2 text-xs font-mono text-cream-900"
                />
              </div>

              <div>
                <label className="text-cream-800 font-medium block mb-1">Reference Note (Optional)</label>
                <input
                  type="text"
                  placeholder="e.g. Deposit Slip #DEP-904"
                  value={advanceNote}
                  onChange={(e) => setAdvanceNote(e.target.value)}
                  className="w-full rounded-md border border-cream-300 bg-white px-3 py-2 text-xs text-cream-900"
                />
              </div>

              <div className="flex justify-end gap-2 border-t border-cream-300 pt-4">
                <button
                  type="button"
                  onClick={() => setShowAdvanceModal(false)}
                  className="rounded-md border border-cream-300 bg-cream-100 px-3 py-1.5 text-xs font-medium text-cream-800 hover:bg-cream-200"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isAllocatingAdvance}
                  className="rounded-md border border-sage-500 bg-sage-50 px-4 py-1.5 text-xs font-semibold text-sage-900 hover:bg-sage-100"
                >
                  {isAllocatingAdvance ? "Reconciling..." : "Reconcile Advance"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
