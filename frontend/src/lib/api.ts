import { getToken, getUser, clearAuth } from "./auth";

const API_BASE = "/api/v1";
const DEFAULT_TENANT = "00000000-0000-0000-0000-000000000001";

export async function fetchWithTenant(endpoint: string, options: RequestInit = {}) {
  const headers = new Headers(options.headers || {});
  
  const token = getToken();
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const user = getUser();
  if (!headers.has("X-Tenant-ID")) {
    headers.set("X-Tenant-ID", user?.tenant_id || DEFAULT_TENANT);
  }

  if (!headers.has("Content-Type") && options.body && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  const res = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });

  if (res.status === 401) {
    clearAuth();
    if (typeof window !== "undefined") {
      const isAuthPage =
        window.location.pathname === "/login" || window.location.pathname === "/signup";
      if (!isAuthPage) {
        window.location.href = "/login";
      }
    }
    const err = await res.json().catch(() => ({ detail: "Session expired. Please sign in again." }));
    throw new Error(err.detail || "Session expired. Please sign in again.");
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    let errorMsg = "Request failed";
    if (typeof err.detail === "string") {
      errorMsg = err.detail;
    } else if (Array.isArray(err.detail)) {
      errorMsg = err.detail
        .map((d: any) => `${d.loc ? d.loc.slice(1).join(".") + ": " : ""}${d.msg || JSON.stringify(d)}`)
        .join("; ");
    } else if (err.detail && typeof err.detail === "object") {
      errorMsg = JSON.stringify(err.detail);
    } else if (err.message) {
      errorMsg = err.message;
    }
    throw new Error(errorMsg);
  }
  return res.json();
}

export const api = {
  // --- Multi-Tenant Auth ---
  register: (data: {
    company_name: string;
    tenant_slug: string;
    email: string;
    password: string;
    full_name: string;
  }) => fetchWithTenant("/auth/register", { method: "POST", body: JSON.stringify(data) }),

  login: (data: { email: string; password: string; tenant_slug?: string }) =>
    fetchWithTenant("/auth/login", { method: "POST", body: JSON.stringify(data) }),

  getMe: () => fetchWithTenant("/auth/me"),

  // --- Setup Wizard ---
  getSetupStatus: () => fetchWithTenant("/setup/status"),
  getSetupCountries: () => fetchWithTenant("/setup/countries"),
  getSetupIndustries: () => fetchWithTenant("/setup/industries"),
  getSetupCharts: (country: string) =>
    fetchWithTenant(`/setup/charts?country=${encodeURIComponent(country)}`),
  completeSetup: (data: any) =>
    fetchWithTenant("/setup/complete", { method: "POST", body: JSON.stringify(data) }),

  // --- In-App Module Onboarding ---
  getOnboardingProgress: () => fetchWithTenant("/onboarding/progress"),
  completeOnboardingStep: (stepId: string) =>
    fetchWithTenant(`/onboarding/steps/${encodeURIComponent(stepId)}/complete`, { method: "POST" }),
  validateOnboardingStep: (stepId: string) =>
    fetchWithTenant(`/onboarding/steps/${encodeURIComponent(stepId)}/validate`, { method: "POST" }),
  skipOnboardingModule: (moduleSlug: string) =>
    fetchWithTenant(`/onboarding/modules/${encodeURIComponent(moduleSlug)}/skip`, { method: "POST" }),

  getHealth: () => fetchWithTenant("/health"),
  getReadiness: () => fetchWithTenant("/ready"),
  getAgentStates: () => fetchWithTenant("/agents/states"),
  dispatchRFQ: (data: { customer_name: string; inquiry_text: string }) =>
    fetchWithTenant("/agents/dispatch-rfq", { method: "POST", body: JSON.stringify(data) }),
  getLatestDag: () => fetchWithTenant("/agents/dags/latest"),
  getDag: (dagId: string) => fetchWithTenant(`/agents/dags/${encodeURIComponent(dagId)}`),
  listDags: () => fetchWithTenant("/agents/dags"),
  recoverDag: (dagId: string, notes: string) =>
    fetchWithTenant(`/agents/dags/${encodeURIComponent(dagId)}/recover`, {
      method: "POST",
      body: JSON.stringify({ notes }),
    }),

  // --- Inbound Email & Gmail OAuth ---
  getGmailStatus: () => fetchWithTenant("/webhooks/gmail/status"),
  getGmailCredentials: () => fetchWithTenant("/webhooks/gmail/credentials"),
  saveGmailCredentials: (data: { client_id: string; client_secret: string }) =>
    fetchWithTenant("/webhooks/gmail/credentials", { method: "POST", body: JSON.stringify(data) }),
  getGmailAuthUrl: (redirectUri?: string) =>
    fetchWithTenant(`/webhooks/gmail/authorize${redirectUri ? `?redirect_uri=${encodeURIComponent(redirectUri)}` : ""}`),
  connectGmailCallback: (data: { code: string; redirect_uri: string }) =>
    fetchWithTenant("/webhooks/gmail/callback", { method: "POST", body: JSON.stringify(data) }),
  disconnectGmail: () => fetchWithTenant("/webhooks/gmail/disconnect", { method: "POST" }),
  syncGmailInbox: () => fetchWithTenant("/webhooks/gmail/sync", { method: "POST" }),
  getEmailInbox: () => fetchWithTenant("/webhooks/email/inbox"),
  reviewInboundEmail: (messageId: string, data: { decision: "ACCEPT_FOR_MANUAL_PROCESSING" | "REJECT"; notes: string }) =>
    fetchWithTenant(`/webhooks/email/inbox/${encodeURIComponent(messageId)}/review`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  createSalesOrderFromEmail: (messageId: string, data: { customer_id: string; order_number: string; delivery_date: string; items: Array<{ item_id: string; quantity: string; unit_price: string }> }) =>
    fetchWithTenant(`/webhooks/email/inbox/${encodeURIComponent(messageId)}/sales-order`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  confirmSalesOrder: (orderId: string, warehouseId?: string) =>
    fetchWithTenant(`/commercial/orders/${encodeURIComponent(orderId)}/confirm`, {
      method: "POST",
      body: JSON.stringify({ warehouse_id: warehouseId || null }),
    }),
  getEmailSent: () => fetchWithTenant("/webhooks/email/sent"),
  simulateInboundEmail: (data: { sender: string; recipient?: string; subject: string; body_text: string; attachments?: string[] }) =>
    fetchWithTenant("/webhooks/email/inbound", { method: "POST", body: JSON.stringify(data) }),

  // --- Accounts Payable & 3-Way Match ---
  getSuppliers: () => fetchWithTenant("/ap/suppliers"),
  createSupplier: (data: any) =>
    fetchWithTenant("/ap/suppliers", { method: "POST", body: JSON.stringify(data) }),
  getPurchaseOrders: () => fetchWithTenant("/ap/purchase-orders"),
  createPurchaseOrder: (data: any) =>
    fetchWithTenant("/ap/purchase-orders", { method: "POST", body: JSON.stringify(data) }),
  getGoodsReceipts: () => fetchWithTenant("/ap/goods-receipts"),
  createGoodsReceipt: (data: any) =>
    fetchWithTenant("/ap/goods-receipts", { method: "POST", body: JSON.stringify(data) }),
  getInvoices: () => fetchWithTenant("/ap/invoices"),
  createInvoice: (data: any) =>
    fetchWithTenant("/ap/invoices", { method: "POST", body: JSON.stringify(data) }),
  matchInvoice: (invoiceId: string, humanApproved: boolean = false) =>
    fetchWithTenant(`/ap/match/${invoiceId}${humanApproved ? "?human_approved=true" : ""}`, { method: "POST" }),

  // --- Bank Reconciliation ---
  getReceivables: () => fetchWithTenant("/reconciliation/orders"),
  createReceivable: (data: { order_number: string; customer_name: string; total_amount: number }) =>
    fetchWithTenant("/reconciliation/orders", { method: "POST", body: JSON.stringify(data) }),
  ingestBankFeed: (data: { amount: number; counterparty_name: string; remittance_information: string }) =>
    fetchWithTenant("/reconciliation/feed", { method: "POST", body: JSON.stringify(data) }),

  // --- Inventory & Stock ---
  getItems: () => fetchWithTenant("/inventory/items"),
  createItem: (data: any) =>
    fetchWithTenant("/inventory/items", { method: "POST", body: JSON.stringify(data) }),
  adjustStock: (data: { item_id: string; delta_qty: number; reason?: string }) =>
    fetchWithTenant("/inventory/stock-adjustment", { method: "POST", body: JSON.stringify(data) }),
  calculateROP: (data: {
    item_code: string;
    daily_demand_mean: number;
    daily_demand_std: number;
    lead_time_mean_days: number;
    lead_time_std_days: number;
  }) => fetchWithTenant("/inventory/calculate-rop", { method: "POST", body: JSON.stringify(data) }),
  triggerReplenishment: (itemId: string) =>
    fetchWithTenant(`/inventory/replenish/${itemId}`, { method: "POST" }),

  // --- Production & Shop Floor MES ---
  getWorkstations: () => fetchWithTenant("/production/workstations"),
  createWorkstation: (data: any) =>
    fetchWithTenant("/production/workstations", { method: "POST", body: JSON.stringify(data) }),
  getWorkstationOEE: (workstationId: string, plannedMinutes?: number) =>
    fetchWithTenant(`/production/workstations/${workstationId}/oee${plannedMinutes ? `?planned_minutes=${plannedMinutes}` : ""}`),
  
  getOperations: () => fetchWithTenant("/production/operations"),
  createOperation: (data: any) =>
    fetchWithTenant("/production/operations", { method: "POST", body: JSON.stringify(data) }),

  getRoutings: () => fetchWithTenant("/production/routings"),
  createRouting: (data: any) =>
    fetchWithTenant("/production/routings", { method: "POST", body: JSON.stringify(data) }),
  getRouting: (id: string) => fetchWithTenant(`/production/routings/${id}`),

  getBoms: (itemId?: string) =>
    fetchWithTenant(`/production/boms${itemId ? `?item_id=${itemId}` : ""}`),
  createBom: (data: any) =>
    fetchWithTenant("/production/boms", { method: "POST", body: JSON.stringify(data) }),
  getBom: (id: string) => fetchWithTenant(`/production/boms/${id}`),
  getBomTree: (id: string) => fetchWithTenant(`/production/boms/${id}/tree`),

  getProductionPlans: (status?: string) =>
    fetchWithTenant(`/production/plans${status ? `?status=${status}` : ""}`),
  createProductionPlan: (data: any) =>
    fetchWithTenant("/production/plans", { method: "POST", body: JSON.stringify(data) }),
  getProductionPlan: (id: string) => fetchWithTenant(`/production/plans/${id}`),
  getPlanShortages: (planId: string) => fetchWithTenant(`/production/plans/${planId}/shortages`),
  createWorkOrdersFromPlan: (planId: string) =>
    fetchWithTenant(`/production/plans/${planId}/create-work-orders`, { method: "POST" }),

  getWorkOrders: (status?: string) =>
    fetchWithTenant(`/production/work-orders${status ? `?status=${status}` : ""}`),
  createWorkOrder: (data: any) =>
    fetchWithTenant("/production/work-orders", { method: "POST", body: JSON.stringify(data) }),
  getWorkOrder: (id: string) => fetchWithTenant(`/production/work-orders/${id}`),
  stageWorkOrderMaterials: (workOrderId: string) =>
    fetchWithTenant(`/production/work-orders/${workOrderId}/stage-materials`, { method: "POST" }),
  completeWorkOrder: (workOrderId: string, data?: any) =>
    fetchWithTenant(`/production/work-orders/${workOrderId}/complete`, {
      method: "POST",
      body: JSON.stringify(data || {}),
    }),

  getJobCards: (params?: { work_order_id?: string; workstation_id?: string; employee_id?: string; status?: string }) => {
    const query = new URLSearchParams();
    if (params?.work_order_id) query.append("work_order_id", params.work_order_id);
    if (params?.workstation_id) query.append("workstation_id", params.workstation_id);
    if (params?.employee_id) query.append("employee_id", params.employee_id);
    if (params?.status) query.append("status", params.status);
    const qs = query.toString();
    return fetchWithTenant(`/production/job-cards${qs ? `?${qs}` : ""}`);
  },
  getJobCard: (id: string) => fetchWithTenant(`/production/job-cards/${id}`),
  startJobCard: (id: string, data?: any) =>
    fetchWithTenant(`/production/job-cards/${id}/start`, { method: "POST", body: JSON.stringify(data || {}) }),
  pauseJobCard: (id: string, data?: any) =>
    fetchWithTenant(`/production/job-cards/${id}/pause`, { method: "POST", body: JSON.stringify(data || {}) }),
  completeJobCard: (id: string, data?: any) =>
    fetchWithTenant(`/production/job-cards/${id}/complete`, { method: "POST", body: JSON.stringify(data || {}) }),

  getDowntimes: (workstationId?: string, status?: string) => {
    const query = new URLSearchParams();
    if (workstationId) query.append("workstation_id", workstationId);
    if (status) query.append("status", status);
    const qs = query.toString();
    return fetchWithTenant(`/production/downtimes${qs ? `?${qs}` : ""}`);
  },
  recordDowntime: (data: any) =>
    fetchWithTenant("/production/downtimes", { method: "POST", body: JSON.stringify(data) }),
  resolveDowntime: (downtimeId: string) =>
    fetchWithTenant(`/production/downtimes/${downtimeId}/resolve`, { method: "POST" }),

  solveSchedule: (data?: any) =>
    fetchWithTenant("/production/solve-schedule", { method: "POST", body: JSON.stringify(data || {}) }),
  simulateFaultReroute: (faultedMachine: string) =>
    fetchWithTenant("/production/fault-reroute", {
      method: "POST",
      body: JSON.stringify({ faulted_workstation_code: faultedMachine }),
    }),

  // --- IoT Telemetry & Predictive Maintenance ---
  getTickets: () => fetchWithTenant("/iot/tickets"),
  createTicket: (data: any) =>
    fetchWithTenant("/iot/tickets", { method: "POST", body: JSON.stringify(data) }),
  updateTicketStatus: (ticketId: string, status: string) =>
    fetchWithTenant(`/iot/tickets/${ticketId}`, { method: "PATCH", body: JSON.stringify({ status }) }),
  simulateTelemetry: (data: {
    workstation_code: string;
    inject_anomaly?: boolean;
    inject_catastrophic?: boolean;
  }) => fetchWithTenant("/iot/simulate", { method: "POST", body: JSON.stringify(data) }),
  ingestTelemetry: (frame: any) =>
    fetchWithTenant("/iot/telemetry", { method: "POST", body: JSON.stringify(frame) }),

  // --- General Ledger ---
  getGLEntries: () => fetchWithTenant("/ledger/entries"),
  getAccounts: () => fetchWithTenant("/ledger/accounts"),
  stageTransaction: (data: any) =>
    fetchWithTenant("/ledger/stage", { method: "POST", body: JSON.stringify(data) }),

  // --- Workforce (HR) Agent ---
  getEmployees: () => fetchWithTenant("/workforce/employees"),
  createEmployee: (data: any) =>
    fetchWithTenant("/workforce/employees", { method: "POST", body: JSON.stringify(data) }),
  getCertifications: () => fetchWithTenant("/workforce/certifications"),
  addCertification: (data: any) =>
    fetchWithTenant("/workforce/certifications", { method: "POST", body: JSON.stringify(data) }),
  getExpenses: () => fetchWithTenant("/workforce/expenses"),
  auditExpense: (data: any) =>
    fetchWithTenant("/workforce/expense/audit", { method: "POST", body: JSON.stringify(data) }),
  evaluateShiftTrade: (data: any) =>
    fetchWithTenant("/workforce/shift-trade/evaluate", { method: "POST", body: JSON.stringify(data) }),
  getShifts: () => fetchWithTenant("/workforce/shifts"),
  createShift: (data: any) =>
    fetchWithTenant("/workforce/shifts", { method: "POST", body: JSON.stringify(data) }),

  // --- Commercial & Dynamic Pricing ---
  getCustomers: () => fetchWithTenant("/commercial/customers"),
  createCustomer: (data: any) =>
    fetchWithTenant("/commercial/customers", { method: "POST", body: JSON.stringify(data) }),
  getQuotes: () => fetchWithTenant("/commercial/quotes"),
  createQuote: (data: any) =>
    fetchWithTenant("/commercial/quotes", { method: "POST", body: JSON.stringify(data) }),
  calculateDynamicPricing: (data: any) =>
    fetchWithTenant("/commercial/pricing/calculate", { method: "POST", body: JSON.stringify(data) }),
  calculateBOMRollup: (data: any) =>
    fetchWithTenant("/commercial/bom/rollup", { method: "POST", body: JSON.stringify(data) }),
  evaluateQuoteInvalidation: (data: any) =>
    fetchWithTenant("/commercial/quote/evaluate-invalidation", { method: "POST", body: JSON.stringify(data) }),
  downloadQuotePDF: async (quote: any) => {
    const token = getToken();
    const user = getUser();
    const res = await fetch(`${API_BASE}/commercial/quote/pdf`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        "X-Tenant-ID": user?.tenant_id || DEFAULT_TENANT,
      },
      body: JSON.stringify(quote),
    });
    if (!res.ok) throw new Error("Failed to download quote PDF");
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${quote.quote_number || "quote"}.pdf`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  },

  // --- SOC 2 Cryptographic Audit & Agent Mesh ---
  getSOC2Report: () => fetchWithTenant("/audit/soc2/report"),
  runTamperTest: (data?: {
    tamper_block_index?: number;
    tampered_payload_key?: string;
    tampered_payload_value?: string;
  }) => fetchWithTenant("/audit/soc2/tamper-test", { method: "POST", body: JSON.stringify(data || {}) }),
  executeMeshRFQ: (data: {
    customer_name: string;
    target_sku: string;
    quantity: number;
    delivery_deadline_days?: number;
  }) => fetchWithTenant("/audit/mesh/execute-rfq", { method: "POST", body: JSON.stringify(data) }),

  // --- Edge Quality Control & PLC Scrap Diversion ---
  getQualityTelemetry: () => fetchWithTenant("/quality/telemetry"),
  submitOpticalInspection: (data: {
    item_code: string;
    lot_number: string;
    workstation_code?: string;
    defect_type: string;
    confidence_score: number;
  }) => fetchWithTenant("/quality/inspect", { method: "POST", body: JSON.stringify(data) }),
  getQuarantinedLots: () => fetchWithTenant("/quality/lots"),
  releaseQuarantinedLot: (data: { lot_number: string; release_notes?: string }) =>
    fetchWithTenant("/quality/release-lot", { method: "POST", body: JSON.stringify(data) }),

  // --- Phase 1: Accounts, POS & Invoicing ---
  getPOSProfiles: () => fetchWithTenant("/billing/pos/profiles"),
  createPOSProfile: (data: any) =>
    fetchWithTenant("/billing/pos/profiles", { method: "POST", body: JSON.stringify(data) }),
  openPOSShift: (data: any) =>
    fetchWithTenant("/billing/pos/shifts/open", { method: "POST", body: JSON.stringify(data) }),
  getCurrentPOSShift: (userId: string) =>
    fetchWithTenant(`/billing/pos/shifts/current?user_id=${userId}`),
  closePOSShift: (data: any) =>
    fetchWithTenant("/billing/pos/shifts/close", { method: "POST", body: JSON.stringify(data) }),
  createPOSInvoice: (data: any) =>
    fetchWithTenant("/billing/pos/invoices", { method: "POST", body: JSON.stringify(data) }),
  getPOSInvoices: (openingId?: string) =>
    fetchWithTenant(`/billing/pos/invoices${openingId ? `?opening_id=${openingId}` : ""}`),

  getSubscriptionPlans: () => fetchWithTenant("/billing/subscriptions/plans"),
  createSubscriptionPlan: (data: any) =>
    fetchWithTenant("/billing/subscriptions/plans", { method: "POST", body: JSON.stringify(data) }),
  getSubscriptions: () => fetchWithTenant("/billing/subscriptions"),
  subscribeCustomer: (data: any) =>
    fetchWithTenant("/billing/subscriptions", { method: "POST", body: JSON.stringify(data) }),
  createSubscription: (data: any) =>
    fetchWithTenant("/billing/subscriptions", { method: "POST", body: JSON.stringify(data) }),
  processSubscriptionBilling: (asOfDate?: string) =>
    fetchWithTenant(`/billing/subscriptions/process-billing${asOfDate ? `?as_of_date=${asOfDate}` : ""}`, {
      method: "POST",
    }),
  processSubscriptionBillingRun: (asOfDate?: string) =>
    fetchWithTenant(`/billing/subscriptions/process-billing${asOfDate ? `?as_of_date=${asOfDate}` : ""}`, {
      method: "POST",
    }),

  getDunningTypes: () => fetchWithTenant("/billing/dunning/types"),
  createDunningType: (data: any) =>
    fetchWithTenant("/billing/dunning/types", { method: "POST", body: JSON.stringify(data) }),
  getDunningNotices: () => fetchWithTenant("/billing/dunning/notices"),
  evaluateOverdueDunning: (asOfDate?: string) =>
    fetchWithTenant(`/billing/dunning/evaluate-overdue${asOfDate ? `?as_of_date=${asOfDate}` : ""}`, {
      method: "POST",
    }),
  evaluateDunningOverdue: (asOfDate?: string) =>
    fetchWithTenant(`/billing/dunning/evaluate-overdue${asOfDate ? `?as_of_date=${asOfDate}` : ""}`, {
      method: "POST",
    }),

  getBudgets: () => fetchWithTenant("/billing/budgets"),
  createBudget: (data: any) =>
    fetchWithTenant("/billing/budgets", { method: "POST", body: JSON.stringify(data) }),
  checkBudgetCompliance: (data: any) =>
    fetchWithTenant("/billing/budgets/check", { method: "POST", body: JSON.stringify(data) }),
  evaluateBudgetCompliance: (data: any) =>
    fetchWithTenant("/billing/budgets/check", { method: "POST", body: JSON.stringify(data) }),

  getCreditNotes: () => fetchWithTenant("/billing/credit-notes"),
  createCreditNote: (data: any) =>
    fetchWithTenant("/billing/credit-notes", { method: "POST", body: JSON.stringify(data) }),
  getDebitNotes: () => fetchWithTenant("/billing/debit-notes"),
  createDebitNote: (data: any) =>
    fetchWithTenant("/billing/debit-notes", { method: "POST", body: JSON.stringify(data) }),

  getTaxWithholdingCategories: () => fetchWithTenant("/billing/tax-withholding/categories"),
  createTaxWithholdingCategory: (data: any) =>
    fetchWithTenant("/billing/tax-withholding/categories", { method: "POST", body: JSON.stringify(data) }),

  // --- POS Parity Extensions (Split payments, Park/Hold Cart, Returns, Consolidation) ---
  parkPOSCart: (data: { profile_id: string; user_id: string; cart_data: any; customer_id?: string; hold_note?: string }) =>
    fetchWithTenant("/billing/pos/park-cart", { method: "POST", body: JSON.stringify(data) }),
  getParkedPOSCarts: (profileId?: string) =>
    fetchWithTenant(`/billing/pos/parked-carts${profileId ? `?profile_id=${profileId}` : ""}`),
  restoreParkedPOSCart: (parkedId: string) =>
    fetchWithTenant(`/billing/pos/parked-carts/${parkedId}/restore`, { method: "POST" }),
  deleteParkedPOSCart: (parkedId: string) =>
    fetchWithTenant(`/billing/pos/parked-carts/${parkedId}`, { method: "DELETE" }),
  consolidateShiftInvoices: (closingId: string) =>
    fetchWithTenant(`/billing/pos/shifts/${closingId}/consolidate`, { method: "POST" }),
  getPOSInvoice: (invoiceId: string) =>
    fetchWithTenant(`/billing/pos/invoices/${invoiceId}`),
  lookupPOSInvoice: (invoiceRef: string) =>
    fetchWithTenant(`/billing/pos/invoices/lookup/${encodeURIComponent(invoiceRef)}`),

  // --- Subscriptions Lifecycle & Proration ---
  pauseSubscription: (subId: string, data?: { resume_at?: string }) =>
    fetchWithTenant(`/billing/subscriptions/${subId}/pause`, { method: "POST", body: JSON.stringify(data || {}) }),
  resumeSubscription: (subId: string) =>
    fetchWithTenant(`/billing/subscriptions/${subId}/resume`, { method: "POST" }),
  previewProration: (data: { current_amount: number; new_amount: number; start_date: string; end_date: string; change_date: string }) =>
    fetchWithTenant("/billing/subscriptions/prorate-preview", { method: "POST", body: JSON.stringify(data) }),

  // --- Payment Terms Templates & Schedules ---
  getPaymentTermsTemplates: () => fetchWithTenant("/billing/payment-terms/templates"),
  createPaymentTermsTemplate: (data: any) =>
    fetchWithTenant("/billing/payment-terms/templates", { method: "POST", body: JSON.stringify(data) }),
  applyPaymentTermsToInvoice: (invoiceId: string, templateId: string) =>
    fetchWithTenant(`/billing/invoices/${invoiceId}/apply-payment-terms`, { method: "POST", body: JSON.stringify({ template_id: templateId }) }),
  getInvoicePaymentSchedule: (invoiceId: string) =>
    fetchWithTenant(`/billing/invoices/${invoiceId}/payment-schedule`),
  getSalesInvoices: () => fetchWithTenant("/billing/invoices"),

  // --- Multi-Tier Cascading Taxes & Charges ---
  getTaxTemplates: () => fetchWithTenant("/billing/tax-templates"),
  createTaxTemplate: (data: any) =>
    fetchWithTenant("/billing/tax-templates", { method: "POST", body: JSON.stringify(data) }),
  calculateCascadingTaxes: (data: { net_total: number; taxes: any[] }) =>
    fetchWithTenant("/billing/tax-templates/calculate", { method: "POST", body: JSON.stringify(data) }),

  // --- Customer Advance Payment Reconciliation ---
  reconcileAdvancePayment: (invoiceId: string, data: { customer_id: string; allocated_amount: number; reference_note?: string }) =>
    fetchWithTenant(`/billing/invoices/${invoiceId}/reconcile-advance`, { method: "POST", body: JSON.stringify(data) }),
  getInvoiceAdvanceAllocations: (invoiceId: string) =>
    fetchWithTenant(`/billing/invoices/${invoiceId}/advance-allocations`),

  // --- Phase 2: Buying, Strategic Sourcing, Landed Costs & Subcontracting ---
  getWarehouses: () => fetchWithTenant("/procurement/warehouses"),
  // Material Requests (Requisitions)
  getMaterialRequests: (params?: { status?: string; type?: string }) => {
    const q = new URLSearchParams();
    if (params?.status) q.append("status", params.status);
    if (params?.type) q.append("material_request_type", params.type);
    const qs = q.toString();
    return fetchWithTenant(`/procurement/material-requests${qs ? `?${qs}` : ""}`);
  },
  createMaterialRequest: (data: any) =>
    fetchWithTenant("/procurement/material-requests", { method: "POST", body: JSON.stringify(data) }),
  getMaterialRequest: (mrId: string) =>
    fetchWithTenant(`/procurement/material-requests/${mrId}`),
  submitMaterialRequest: (mrId: string) =>
    fetchWithTenant(`/procurement/material-requests/${mrId}/submit`, { method: "POST" }),
  cancelMaterialRequest: (mrId: string) =>
    fetchWithTenant(`/procurement/material-requests/${mrId}/cancel`, { method: "POST" }),
  convertMRToPO: (mrId: string, data: { po_number: string; supplier_id: string; items?: any[] }) =>
    fetchWithTenant(`/procurement/material-requests/${mrId}/create-po`, { method: "POST", body: JSON.stringify(data) }),
  checkReplenishment: () =>
    fetchWithTenant("/procurement/replenishment/check", { method: "POST" }),

  // RFQs & Supplier Quotations
  getRFQs: (status?: string) =>
    fetchWithTenant(`/procurement/rfqs${status ? `?status=${status}` : ""}`),
  createRFQ: (data: any) =>
    fetchWithTenant("/procurement/rfqs", { method: "POST", body: JSON.stringify(data) }),
  getRFQ: (rfqId: string) =>
    fetchWithTenant(`/procurement/rfqs/${rfqId}`),
  sendRFQ: (rfqId: string) =>
    fetchWithTenant(`/procurement/rfqs/${rfqId}/send`, { method: "POST" }),
  getQuoteComparisonMatrix: (rfqId: string) =>
    fetchWithTenant(`/procurement/rfqs/${rfqId}/comparison-matrix`),
  getSupplierQuotations: (params?: { rfq_id?: string; supplier_id?: string; status?: string }) => {
    const q = new URLSearchParams();
    if (params?.rfq_id) q.append("rfq_id", params.rfq_id);
    if (params?.supplier_id) q.append("supplier_id", params.supplier_id);
    if (params?.status) q.append("status", params.status);
    const qs = q.toString();
    return fetchWithTenant(`/procurement/supplier-quotations${qs ? `?${qs}` : ""}`);
  },
  createSupplierQuotation: (data: any) =>
    fetchWithTenant("/procurement/supplier-quotations", { method: "POST", body: JSON.stringify(data) }),
  getSupplierQuotation: (sqId: string) =>
    fetchWithTenant(`/procurement/supplier-quotations/${sqId}`),
  awardSupplierQuotation: (sqId: string, poNumber: string) =>
    fetchWithTenant(`/procurement/supplier-quotations/${sqId}/award`, { method: "POST", body: JSON.stringify({ po_number: poNumber }) }),

  // Blanket Orders
  getBlanketOrders: (params?: { supplier_id?: string; status?: string }) => {
    const q = new URLSearchParams();
    if (params?.supplier_id) q.append("supplier_id", params.supplier_id);
    if (params?.status) q.append("status", params.status);
    const qs = q.toString();
    return fetchWithTenant(`/procurement/blanket-orders${qs ? `?${qs}` : ""}`);
  },
  createBlanketOrder: (data: any) =>
    fetchWithTenant("/procurement/blanket-orders", { method: "POST", body: JSON.stringify(data) }),
  getBlanketOrder: (boId: string) =>
    fetchWithTenant(`/procurement/blanket-orders/${boId}`),
  drawdownBlanketOrder: (boId: string, data: { po_number: string; items: { item_id: string; quantity: number }[]; order_date?: string }) =>
    fetchWithTenant(`/procurement/blanket-orders/${boId}/create-po`, { method: "POST", body: JSON.stringify(data) }),

  // Landed Cost Vouchers
  getLandedCostVouchers: (status?: string) =>
    fetchWithTenant(`/procurement/landed-cost-vouchers${status ? `?status=${status}` : ""}`),
  createLandedCostVoucher: (data: any) =>
    fetchWithTenant("/procurement/landed-cost-vouchers", { method: "POST", body: JSON.stringify(data) }),
  getLandedCostVoucher: (lcvId: string) =>
    fetchWithTenant(`/procurement/landed-cost-vouchers/${lcvId}`),
  submitLandedCostVoucher: (lcvId: string) =>
    fetchWithTenant(`/procurement/landed-cost-vouchers/${lcvId}/submit`, { method: "POST" }),

  // Supplier Scorecards & Leaderboard
  getSupplierScorecards: (params?: { supplier_id?: string; standing?: string }) => {
    const q = new URLSearchParams();
    if (params?.supplier_id) q.append("supplier_id", params.supplier_id);
    if (params?.standing) q.append("standing", params.standing);
    const qs = q.toString();
    return fetchWithTenant(`/procurement/scorecards${qs ? `?${qs}` : ""}`);
  },
  calculateSupplierScorecard: (data: { supplier_id: string; period_start: string; period_end: string; evaluation_period?: string }) =>
    fetchWithTenant("/procurement/scorecards/calculate", { method: "POST", body: JSON.stringify(data) }),
  getSupplierLeaderboard: () =>
    fetchWithTenant("/procurement/suppliers/leaderboard"),

  // Subcontracting Operations
  getSubcontractingOrders: (params?: { supplier_id?: string; status?: string }) => {
    const q = new URLSearchParams();
    if (params?.supplier_id) q.append("supplier_id", params.supplier_id);
    if (params?.status) q.append("status", params.status);
    const qs = q.toString();
    return fetchWithTenant(`/subcontracting/orders${qs ? `?${qs}` : ""}`);
  },
  createSubcontractingOrder: (data: any) =>
    fetchWithTenant("/subcontracting/orders", { method: "POST", body: JSON.stringify(data) }),
  getSubcontractingOrder: (scoId: string) =>
    fetchWithTenant(`/subcontracting/orders/${scoId}`),
  submitSubcontractingOrder: (scoId: string) =>
    fetchWithTenant(`/subcontracting/orders/${scoId}/submit`, { method: "POST" }),
  transferSubcontractingMaterials: (scoId: string, data: any) =>
    fetchWithTenant(`/subcontracting/orders/${scoId}/transfer`, {
      method: "POST",
      body: JSON.stringify(Array.isArray(data) ? { transfers: data } : (data.transfers ? data : { transfers: [data] })),
    }),
  getSubcontractingReceipts: (scoId?: string) =>
    fetchWithTenant(`/subcontracting/receipts${scoId ? `?sco_id=${scoId}` : ""}`),
  createSubcontractingReceipt: (data: any) =>
    fetchWithTenant("/subcontracting/receipts", { method: "POST", body: JSON.stringify(data) }),
  getSubcontractingReceipt: (scrId: string) =>
    fetchWithTenant(`/subcontracting/receipts/${scrId}`),

  // GRN Quality Inspection
  inspectGRN: (grnId: string, items: { grn_item_id: string; quantity_accepted: number; quantity_rejected: number; rejected_warehouse_id?: string }[]) =>
    fetchWithTenant(`/procurement/grn/${grnId}/inspect`, { method: "POST", body: JSON.stringify({ items }) }),

  // Phase 3: Stock Entries
  getStockEntries: (params?: { stock_entry_type?: string; status?: string }) => {
    const q = new URLSearchParams();
    if (params?.stock_entry_type) q.append("stock_entry_type", params.stock_entry_type);
    if (params?.status) q.append("status", params.status);
    const qs = q.toString();
    return fetchWithTenant(`/stock/entries${qs ? `?${qs}` : ""}`);
  },
  createStockEntry: (data: any) =>
    fetchWithTenant("/stock/entries", { method: "POST", body: JSON.stringify(data) }),
  submitStockEntry: (entryId: string) =>
    fetchWithTenant(`/stock/entries/${entryId}/submit`, { method: "POST" }),
  cancelStockEntry: (entryId: string) =>
    fetchWithTenant(`/stock/entries/${entryId}/cancel`, { method: "POST" }),

  // Stock Reconciliation
  getStockReconciliations: (status?: string) =>
    fetchWithTenant(`/stock/reconciliations${status ? `?status=${status}` : ""}`),
  createStockReconciliation: (data: any) =>
    fetchWithTenant("/stock/reconciliations", { method: "POST", body: JSON.stringify(data) }),
  submitStockReconciliation: (reconId: string) =>
    fetchWithTenant(`/stock/reconciliations/${reconId}/submit`, { method: "POST" }),

  // Batches & Serials
  getBatches: (params?: { item_id?: string; status?: string }) => {
    const q = new URLSearchParams();
    if (params?.item_id) q.append("item_id", params.item_id);
    if (params?.status) q.append("status", params.status);
    const qs = q.toString();
    return fetchWithTenant(`/stock/batches${qs ? `?${qs}` : ""}`);
  },
  createBatch: (data: any) =>
    fetchWithTenant("/stock/batches", { method: "POST", body: JSON.stringify(data) }),
  getSerials: (params?: { item_id?: string; warehouse_id?: string; status?: string }) => {
    const q = new URLSearchParams();
    if (params?.item_id) q.append("item_id", params.item_id);
    if (params?.warehouse_id) q.append("warehouse_id", params.warehouse_id);
    if (params?.status) q.append("status", params.status);
    const qs = q.toString();
    return fetchWithTenant(`/stock/serials${qs ? `?${qs}` : ""}`);
  },
  createSerial: (data: any) =>
    fetchWithTenant("/stock/serials", { method: "POST", body: JSON.stringify(data) }),
  updateSerialStatus: (serialNumber: string, data: any) =>
    fetchWithTenant(`/stock/serials/${encodeURIComponent(serialNumber)}/status`, { method: "POST", body: JSON.stringify(data) }),

  // Pick Lists & Packing Slips
  getPickLists: (status?: string) =>
    fetchWithTenant(`/stock/pick-lists${status ? `?status=${status}` : ""}`),
  createPickList: (data: any) =>
    fetchWithTenant("/stock/pick-lists", { method: "POST", body: JSON.stringify(data) }),
  updatePickedQty: (pickListId: string, pickItemId: string, pickedQty: number) =>
    fetchWithTenant(`/stock/pick-lists/${pickListId}/items/${pickItemId}/picked`, { method: "POST", body: JSON.stringify({ picked_qty: pickedQty }) }),
  completePickList: (pickListId: string) =>
    fetchWithTenant(`/stock/pick-lists/${pickListId}/complete`, { method: "POST" }),
  getPackingSlips: (deliveryNoteId?: string) =>
    fetchWithTenant(`/stock/packing-slips${deliveryNoteId ? `?delivery_note_id=${deliveryNoteId}` : ""}`),
  createPackingSlip: (data: any) =>
    fetchWithTenant("/stock/packing-slips", { method: "POST", body: JSON.stringify(data) }),
  submitPackingSlip: (slipId: string) =>
    fetchWithTenant(`/stock/packing-slips/${slipId}/submit`, { method: "POST" }),

  // Delivery Trips
  getDeliveryTrips: (status?: string) =>
    fetchWithTenant(`/stock/delivery-trips${status ? `?status=${status}` : ""}`),
  createDeliveryTrip: (data: any) =>
    fetchWithTenant("/stock/delivery-trips", { method: "POST", body: JSON.stringify(data) }),
  dispatchDeliveryTrip: (tripId: string) =>
    fetchWithTenant(`/stock/delivery-trips/${tripId}/dispatch`, { method: "POST" }),
  completeDeliveryStop: (tripId: string, stopId: string, signature?: string) =>
    fetchWithTenant(`/stock/delivery-trips/${tripId}/stops/${stopId}/complete`, { method: "POST", body: JSON.stringify({ customer_signature: signature || "SIGNED" }) }),
  completeDeliveryTrip: (tripId: string) =>
    fetchWithTenant(`/stock/delivery-trips/${tripId}/complete`, { method: "POST" }),

  // Stock Reservations
  getStockReservations: (params?: { item_id?: string; warehouse_id?: string; status?: string }) => {
    const q = new URLSearchParams();
    if (params?.item_id) q.append("item_id", params.item_id);
    if (params?.warehouse_id) q.append("warehouse_id", params.warehouse_id);
    if (params?.status) q.append("status", params.status);
    const qs = q.toString();
    return fetchWithTenant(`/stock/reservations${qs ? `?${qs}` : ""}`);
  },
  createStockReservation: (data: any) =>
    fetchWithTenant("/stock/reservations", { method: "POST", body: JSON.stringify(data) }),
  cancelStockReservation: (reservationId: string) =>
    fetchWithTenant(`/stock/reservations/${reservationId}/cancel`, { method: "POST" }),

  // Item Attributes & Variants
  getItemAttributes: () =>
    fetchWithTenant("/stock/attributes"),
  createItemAttribute: (data: any) =>
    fetchWithTenant("/stock/attributes", { method: "POST", body: JSON.stringify(data) }),
  generateItemVariants: (templateItemId: string, data: any) =>
    fetchWithTenant(`/stock/items/${templateItemId}/variants`, { method: "POST", body: JSON.stringify(data) }),
  getItemVariants: (templateItemId: string) =>
    fetchWithTenant(`/stock/items/${templateItemId}/variants`),

  // --- Phase 4: HRMS & Payroll API Methods ---
  // Departments & Designations
  getDepartments: () => fetchWithTenant("/hr/departments"),
  createDepartment: (data: any) => fetchWithTenant("/hr/departments", { method: "POST", body: JSON.stringify(data) }),
  getDesignations: () => fetchWithTenant("/hr/designations"),
  createDesignation: (data: any) => fetchWithTenant("/hr/designations", { method: "POST", body: JSON.stringify(data) }),

  // Full Employee Lifecycle
  createEmployeeFull: (data: any) => fetchWithTenant("/hr/employees", { method: "POST", body: JSON.stringify(data) }),
  getEmployeesHR: (params?: { department_id?: string; status?: string }) => {
    const q = new URLSearchParams();
    if (params?.department_id) q.append("department_id", params.department_id);
    if (params?.status) q.append("status", params.status);
    const qs = q.toString();
    return fetchWithTenant(`/hr/employees${qs ? `?${qs}` : ""}`);
  },
  getEmployeeHR: (employeeId: string) => fetchWithTenant(`/hr/employees/${employeeId}`),

  // Onboarding & Separation
  getOnboardings: (employeeId?: string) =>
    fetchWithTenant(`/hr/onboarding${employeeId ? `?employee_id=${employeeId}` : ""}`),
  startOnboarding: (data: any) => fetchWithTenant("/hr/onboarding", { method: "POST", body: JSON.stringify(data) }),
  completeOnboardingTask: (onboardingId: string, taskId: string) =>
    fetchWithTenant(`/hr/onboarding/${onboardingId}/tasks/${taskId}/complete`, { method: "POST" }),
  getSeparations: (employeeId?: string) =>
    fetchWithTenant(`/hr/separation${employeeId ? `?employee_id=${employeeId}` : ""}`),
  startSeparation: (data: any) => fetchWithTenant("/hr/separation", { method: "POST", body: JSON.stringify(data) }),
  completeSeparationTask: (separationId: string, taskId: string) =>
    fetchWithTenant(`/hr/separation/${separationId}/tasks/${taskId}/complete`, { method: "POST" }),

  // Shifts & Attendance
  getShiftTypes: () => fetchWithTenant("/hr/shifts/types"),
  createShiftType: (data: any) => fetchWithTenant("/hr/shifts/types", { method: "POST", body: JSON.stringify(data) }),
  assignShift: (data: any) => fetchWithTenant("/hr/shifts/assignments", { method: "POST", body: JSON.stringify(data) }),
  markAttendance: (data: any) => fetchWithTenant("/hr/attendance/punch", { method: "POST", body: JSON.stringify(data) }),
  getAttendances: (params?: { employee_id?: string; from_date?: string; to_date?: string }) => {
    const q = new URLSearchParams();
    if (params?.employee_id) q.append("employee_id", params.employee_id);
    if (params?.from_date) q.append("from_date", params.from_date);
    if (params?.to_date) q.append("to_date", params.to_date);
    const qs = q.toString();
    return fetchWithTenant(`/hr/attendance${qs ? `?${qs}` : ""}`);
  },

  // Leaves
  getLeaveTypes: () => fetchWithTenant("/hr/leaves/types"),
  createLeaveType: (data: any) => fetchWithTenant("/hr/leaves/types", { method: "POST", body: JSON.stringify(data) }),
  allocateLeaves: (data: any) => fetchWithTenant("/hr/leaves/allocations", { method: "POST", body: JSON.stringify(data) }),
  getLeaveBalance: (employeeId: string, leaveTypeId: string, fiscalYear?: number) =>
    fetchWithTenant(`/hr/leaves/balance?employee_id=${employeeId}&leave_type_id=${leaveTypeId}${fiscalYear ? `&fiscal_year=${fiscalYear}` : ""}`),
  submitLeaveApplication: (data: any) => fetchWithTenant("/hr/leaves/applications", { method: "POST", body: JSON.stringify(data) }),
  getLeaveApplications: (params?: { employee_id?: string; status?: string }) => {
    const q = new URLSearchParams();
    if (params?.employee_id) q.append("employee_id", params.employee_id);
    if (params?.status) q.append("status", params.status);
    const qs = q.toString();
    return fetchWithTenant(`/hr/leaves/applications${qs ? `?${qs}` : ""}`);
  },
  approveLeaveApplication: (appId: string) => fetchWithTenant(`/hr/leaves/applications/${appId}/approve`, { method: "POST" }),
  rejectLeaveApplication: (appId: string, reason?: string) =>
    fetchWithTenant(`/hr/leaves/applications/${appId}/reject${reason ? `?reason=${encodeURIComponent(reason)}` : ""}`, { method: "POST" }),

  // Advances & Expenses
  getAdvances: (params?: { employee_id?: string; status?: string }) => {
    const q = new URLSearchParams();
    if (params?.employee_id) q.append("employee_id", params.employee_id);
    if (params?.status) q.append("status", params.status);
    const qs = q.toString();
    return fetchWithTenant(`/hr/advances${qs ? `?${qs}` : ""}`);
  },
  createAdvance: (data: any) => fetchWithTenant("/hr/advances", { method: "POST", body: JSON.stringify(data) }),
  disburseAdvance: (advanceId: string) => fetchWithTenant(`/hr/advances/${advanceId}/disburse`, { method: "POST" }),
  reimburseExpense: (claimId: string) => fetchWithTenant(`/hr/expenses/${claimId}/reimburse`, { method: "POST" }),

  // Payroll Components & Structures
  getSalaryComponents: () => fetchWithTenant("/payroll/components"),
  createSalaryComponent: (data: any) => fetchWithTenant("/payroll/components", { method: "POST", body: JSON.stringify(data) }),
  getSalaryStructures: () => fetchWithTenant("/payroll/structures"),
  createSalaryStructure: (data: any) => fetchWithTenant("/payroll/structures", { method: "POST", body: JSON.stringify(data) }),
  assignSalaryStructure: (data: any) => fetchWithTenant("/payroll/assignments", { method: "POST", body: JSON.stringify(data) }),

  // Salary Slips
  generateSalarySlip: (data: any) => fetchWithTenant("/payroll/slips/generate", { method: "POST", body: JSON.stringify(data) }),
  getSalarySlips: (params?: { employee_id?: string; status?: string }) => {
    const q = new URLSearchParams();
    if (params?.employee_id) q.append("employee_id", params.employee_id);
    if (params?.status) q.append("status", params.status);
    const qs = q.toString();
    return fetchWithTenant(`/payroll/slips${qs ? `?${qs}` : ""}`);
  },
  getSalarySlip: (slipId: string) => fetchWithTenant(`/payroll/slips/${slipId}`),
  submitSalarySlip: (slipId: string) => fetchWithTenant(`/payroll/slips/${slipId}/submit`, { method: "POST" }),

  // Batch Payroll
  generateBatchPayroll: (data: any) => fetchWithTenant("/payroll/batches/generate", { method: "POST", body: JSON.stringify(data) }),
  getBatchPayrolls: () => fetchWithTenant("/payroll/batches"),
  submitBatchPayroll: (batchId: string) => fetchWithTenant(`/payroll/batches/${batchId}/submit`, { method: "POST" }),

  // --- Phase 6: CRM & Omnichannel Support Helpdesk ---
  // Leads & AI Qualification
  getLeads: (params?: { status?: string; industry?: string; search?: string }) => {
    const q = new URLSearchParams();
    if (params?.status) q.append("status", params.status);
    if (params?.industry) q.append("industry", params.industry);
    if (params?.search) q.append("search", params.search);
    const qs = q.toString();
    return fetchWithTenant(`/crm/leads${qs ? `?${qs}` : ""}`);
  },
  createLead: (data: any) =>
    fetchWithTenant("/crm/leads", { method: "POST", body: JSON.stringify(data) }),
  getLead: (leadId: string) => fetchWithTenant(`/crm/leads/${leadId}`),
  convertLeadToOpportunity: (leadId: string, data: { title: string; opportunity_amount?: number; sales_stage?: string }) =>
    fetchWithTenant(`/crm/leads/${leadId}/convert-opportunity`, { method: "POST", body: JSON.stringify(data) }),
  convertLeadToCustomer: (leadId: string) =>
    fetchWithTenant(`/crm/leads/${leadId}/convert-customer`, { method: "POST" }),

  // Opportunities & Deal Pipeline
  getOpportunities: (params?: { sales_stage?: string; search?: string }) => {
    const q = new URLSearchParams();
    if (params?.sales_stage) q.append("sales_stage", params.sales_stage);
    if (params?.search) q.append("search", params.search);
    const qs = q.toString();
    return fetchWithTenant(`/crm/opportunities${qs ? `?${qs}` : ""}`);
  },
  createOpportunity: (data: any) =>
    fetchWithTenant("/crm/opportunities", { method: "POST", body: JSON.stringify(data) }),
  getOpportunity: (oppId: string) => fetchWithTenant(`/crm/opportunities/${oppId}`),
  updateOpportunityStage: (oppId: string, data: { new_stage: string; lost_reason?: string }) =>
    fetchWithTenant(`/crm/opportunities/${oppId}/stage`, { method: "POST", body: JSON.stringify(data) }),
  convertOpportunityToQuotation: (oppId: string, data?: { valid_days?: number }) =>
    fetchWithTenant(`/crm/opportunities/${oppId}/convert-quotation`, { method: "POST", body: JSON.stringify(data || {}) }),
  getPipelineSummary: () => fetchWithTenant("/crm/pipeline-summary"),

  // Marketing Campaigns & Drip Sequences
  getCampaigns: (status?: string) =>
    fetchWithTenant(`/crm/campaigns${status ? `?status=${status}` : ""}`),
  createCampaign: (data: any) =>
    fetchWithTenant("/crm/campaigns", { method: "POST", body: JSON.stringify(data) }),
  addDripStep: (campaignId: string, data: any) =>
    fetchWithTenant(`/crm/campaigns/${campaignId}/drip-step`, { method: "POST", body: JSON.stringify(data) }),
  getAppointments: (params?: { status?: string; date_str?: string }) => {
    const q = new URLSearchParams();
    if (params?.status) q.append("status", params.status);
    if (params?.date_str) q.append("date_str", params.date_str);
    const qs = q.toString();
    return fetchWithTenant(`/crm/appointments${qs ? `?${qs}` : ""}`);
  },
  createAppointment: (data: any) =>
    fetchWithTenant("/crm/appointments", { method: "POST", body: JSON.stringify(data) }),
  getContracts: (status?: string) =>
    fetchWithTenant(`/crm/contracts${status ? `?status=${status}` : ""}`),
  createContract: (data: any) =>
    fetchWithTenant("/crm/contracts", { method: "POST", body: JSON.stringify(data) }),

  // Support Helpdesk & SLA Engine
  getSlas: () => fetchWithTenant("/support/slas"),
  createSla: (data: any) =>
    fetchWithTenant("/support/slas", { method: "POST", body: JSON.stringify(data) }),
  getIssues: (params?: { status?: string; priority?: string; search?: string }) => {
    const q = new URLSearchParams();
    if (params?.status) q.append("status", params.status);
    if (params?.priority) q.append("priority", params.priority);
    if (params?.search) q.append("search", params.search);
    const qs = q.toString();
    return fetchWithTenant(`/support/issues${qs ? `?${qs}` : ""}`);
  },
  createIssue: (data: any) =>
    fetchWithTenant("/support/issues", { method: "POST", body: JSON.stringify(data) }),
  getIssue: (issueId: string) => fetchWithTenant(`/support/issues/${issueId}`),
  addIssueCommunication: (issueId: string, data: any) =>
    fetchWithTenant(`/support/issues/${issueId}/communications`, { method: "POST", body: JSON.stringify(data) }),
  resolveIssue: (issueId: string, data: { resolution_details: string; status?: string }) =>
    fetchWithTenant(`/support/issues/${issueId}/resolve`, { method: "POST", body: JSON.stringify(data) }),

  // Serial Warranty Claims & RMA
  verifyWarranty: (serialNumber: string) =>
    fetchWithTenant(`/support/warranty/verify?serial_number=${encodeURIComponent(serialNumber)}`),
  getWarrantyClaims: (status?: string) =>
    fetchWithTenant(`/support/warranty/claims${status ? `?status=${status}` : ""}`),
  createWarrantyClaim: (data: any) =>
    fetchWithTenant("/support/warranty/claims", { method: "POST", body: JSON.stringify(data) }),
  resolveWarrantyClaim: (claimId: string, data: { resolution_type: string; resolution_notes?: string }) =>
    fetchWithTenant(`/support/warranty/claims/${claimId}/resolve`, { method: "POST", body: JSON.stringify(data) }),

  // --- Phase 7: Fixed Assets Lifecycle & Multi-Method Depreciation ---
  getAssetCategories: () => fetchWithTenant("/assets/categories"),
  createAssetCategory: (data: any) =>
    fetchWithTenant("/assets/categories", { method: "POST", body: JSON.stringify(data) }),
  getAssetLocations: () => fetchWithTenant("/assets/locations"),
  createAssetLocation: (data: any) =>
    fetchWithTenant("/assets/locations", { method: "POST", body: JSON.stringify(data) }),
  getAssets: (params?: { status?: string; category_id?: string }) => {
    const q = new URLSearchParams();
    if (params?.status) q.append("status", params.status);
    if (params?.category_id) q.append("category_id", params.category_id);
    const qs = q.toString();
    return fetchWithTenant(`/assets${qs ? `?${qs}` : ""}`);
  },
  getAsset: (assetId: string) => fetchWithTenant(`/assets/${assetId}`),
  createAsset: (data: any) =>
    fetchWithTenant("/assets", { method: "POST", body: JSON.stringify(data) }),
  postAssetDepreciation: (scheduleId: string) =>
    fetchWithTenant(`/assets/schedules/${scheduleId}/post`, { method: "POST" }),
  moveAsset: (assetId: string, data: any) =>
    fetchWithTenant(`/assets/${assetId}/move`, { method: "POST", body: JSON.stringify(data) }),
  repairAsset: (assetId: string, data: any) =>
    fetchWithTenant(`/assets/${assetId}/repair`, { method: "POST", body: JSON.stringify(data) }),
  scrapAsset: (assetId: string, data?: any) =>
    fetchWithTenant(`/assets/${assetId}/scrap`, { method: "POST", body: JSON.stringify(data || {}) }),

  // --- Phase 7: Quality Management & Inspection Suite (ERPNext Parity) ---
  getQualityTemplates: () => fetchWithTenant("/quality/templates"),
  createQualityTemplate: (data: any) =>
    fetchWithTenant("/quality/templates", { method: "POST", body: JSON.stringify(data) }),
  getQualityInspections: (params?: { inspection_type?: string; status?: string }) => {
    const q = new URLSearchParams();
    if (params?.inspection_type) q.append("inspection_type", params.inspection_type);
    if (params?.status) q.append("status", params.status);
    const qs = q.toString();
    return fetchWithTenant(`/quality/inspections${qs ? `?${qs}` : ""}`);
  },
  getQualityInspection: (inspectionId: string) => fetchWithTenant(`/quality/inspections/${inspectionId}`),
  createQualityInspection: (data: any) =>
    fetchWithTenant("/quality/inspections", { method: "POST", body: JSON.stringify(data) }),
  getNonConformances: (status?: string) =>
    fetchWithTenant(`/quality/non-conformances${status ? `?status=${status}` : ""}`),
  getNonConformance: (ncId: string) => fetchWithTenant(`/quality/non-conformances/${ncId}`),
  createNonConformance: (data: any) =>
    fetchWithTenant("/quality/non-conformances", { method: "POST", body: JSON.stringify(data) }),
  getQualityActions: (status?: string) =>
    fetchWithTenant(`/quality/actions${status ? `?status=${status}` : ""}`),
  createQualityAction: (data: any) =>
    fetchWithTenant("/quality/actions", { method: "POST", body: JSON.stringify(data) }),
  resolveQualityAction: (actionId: string, data: { resolution_notes: string; new_status?: string }) =>
    fetchWithTenant(`/quality/actions/${actionId}/resolve`, { method: "POST", body: JSON.stringify(data) }),

  // --- Phase 7: Preventive Maintenance & Service Visits ---
  getMaintenanceSchedules: (status?: string) =>
    fetchWithTenant(`/maintenance/schedules${status ? `?status=${status}` : ""}`),
  getMaintenanceSchedule: (scheduleId: string) => fetchWithTenant(`/maintenance/schedules/${scheduleId}`),
  createMaintenanceSchedule: (data: any) =>
    fetchWithTenant("/maintenance/schedules", { method: "POST", body: JSON.stringify(data) }),
  getMaintenanceVisits: (params?: { asset_id?: string; status?: string }) => {
    const q = new URLSearchParams();
    if (params?.asset_id) q.append("asset_id", params.asset_id);
    if (params?.status) q.append("status", params.status);
    const qs = q.toString();
    return fetchWithTenant(`/maintenance/visits${qs ? `?${qs}` : ""}`);
  },
  createMaintenanceVisit: (data: any) =>
    fetchWithTenant("/maintenance/visits", { method: "POST", body: JSON.stringify(data) }),

  // --- Phase 7: Projects & Timesheet Tracking ---
  getProjects: (status?: string) =>
    fetchWithTenant(`/projects${status ? `?status=${status}` : ""}`),
  getProject: (projectId: string) => fetchWithTenant(`/projects/${projectId}`),
  createProject: (data: any) =>
    fetchWithTenant("/projects", { method: "POST", body: JSON.stringify(data) }),
  createProjectTask: (projectId: string, data: any) =>
    fetchWithTenant(`/projects/${projectId}/tasks`, { method: "POST", body: JSON.stringify(data) }),
  updateProjectTask: (taskId: string, data: any) =>
    fetchWithTenant(`/projects/tasks/${taskId}`, { method: "PATCH", body: JSON.stringify(data) }),
  logProjectTimesheet: (projectId: string, data: any) =>
    fetchWithTenant(`/projects/${projectId}/timesheets`, { method: "POST", body: JSON.stringify(data) }),
  getProjectTimesheets: (params?: { project_id?: string; employee_id?: string }) => {
    const q = new URLSearchParams();
    if (params?.project_id) q.append("project_id", params.project_id);
    if (params?.employee_id) q.append("employee_id", params.employee_id);
    const qs = q.toString();
    return fetchWithTenant(`/projects/timesheets${qs ? `?${qs}` : ""}`);
  },

  // --- Phase 8: Enterprise Reports & Analytics ---
  getTrialBalance: (params?: { from_date?: string; to_date?: string; cost_center?: string }) => {
    const q = new URLSearchParams();
    if (params?.from_date) q.append("from_date", params.from_date);
    if (params?.to_date) q.append("to_date", params.to_date);
    if (params?.cost_center) q.append("cost_center", params.cost_center);
    const qs = q.toString();
    return fetchWithTenant(`/reports/trial-balance${qs ? `?${qs}` : ""}`);
  },
  getBalanceSheet: (asOfDate?: string) =>
    fetchWithTenant(`/reports/balance-sheet${asOfDate ? `?as_of_date=${asOfDate}` : ""}`),
  getProfitAndLoss: (params?: { from_date?: string; to_date?: string }) => {
    const q = new URLSearchParams();
    if (params?.from_date) q.append("from_date", params.from_date);
    if (params?.to_date) q.append("to_date", params.to_date);
    const qs = q.toString();
    return fetchWithTenant(`/reports/profit-and-loss${qs ? `?${qs}` : ""}`);
  },
  getCashFlow: (params?: { from_date?: string; to_date?: string }) => {
    const q = new URLSearchParams();
    if (params?.from_date) q.append("from_date", params.from_date);
    if (params?.to_date) q.append("to_date", params.to_date);
    const qs = q.toString();
    return fetchWithTenant(`/reports/cash-flow${qs ? `?${qs}` : ""}`);
  },
  getArAging: (asOfDate?: string) =>
    fetchWithTenant(`/reports/ar-aging${asOfDate ? `?as_of_date=${asOfDate}` : ""}`),
  getApAging: (asOfDate?: string) =>
    fetchWithTenant(`/reports/ap-aging${asOfDate ? `?as_of_date=${asOfDate}` : ""}`),
  getGeneralLedgerReport: (params: { account_code: string; from_date?: string; to_date?: string }) => {
    const q = new URLSearchParams({ account_code: params.account_code });
    if (params.from_date) q.append("from_date", params.from_date);
    if (params.to_date) q.append("to_date", params.to_date);
    return fetchWithTenant(`/reports/general-ledger?${q.toString()}`);
  },
  getStockBalanceReport: (params?: { warehouse_id?: string; item_id?: string }) => {
    const q = new URLSearchParams();
    if (params?.warehouse_id) q.append("warehouse_id", params.warehouse_id);
    if (params?.item_id) q.append("item_id", params.item_id);
    const qs = q.toString();
    return fetchWithTenant(`/reports/stock-balance${qs ? `?${qs}` : ""}`);
  },
  getStockLedgerReport: (params?: { item_id?: string; warehouse_id?: string; from_date?: string; to_date?: string; limit?: number }) => {
    const q = new URLSearchParams();
    if (params?.item_id) q.append("item_id", params.item_id);
    if (params?.warehouse_id) q.append("warehouse_id", params.warehouse_id);
    if (params?.from_date) q.append("from_date", params.from_date);
    if (params?.to_date) q.append("to_date", params.to_date);
    if (params?.limit) q.append("limit", params.limit.toString());
    const qs = q.toString();
    return fetchWithTenant(`/reports/stock-ledger${qs ? `?${qs}` : ""}`);
  },
  getItemSalesRegister: () => fetchWithTenant("/reports/item-sales-register"),
  getItemPurchaseRegister: () => fetchWithTenant("/reports/item-purchase-register"),
  getProductionAnalytics: () => fetchWithTenant("/reports/production-analytics"),

  // --- Phase 8: Multi-Company Consolidation ---
  getCompanies: () => fetchWithTenant("/companies"),
  createCompany: (data: any) =>
    fetchWithTenant("/companies", { method: "POST", body: JSON.stringify(data) }),
  getInterCompanyTransactions: (isEliminated?: boolean) =>
    fetchWithTenant(`/companies/transactions${isEliminated !== undefined ? `?is_eliminated=${isEliminated}` : ""}`),
  recordInterCompanyTransaction: (data: any) =>
    fetchWithTenant("/companies/transactions", { method: "POST", body: JSON.stringify(data) }),
  getConsolidatedTrialBalance: (params?: { from_date?: string; to_date?: string }) => {
    const q = new URLSearchParams();
    if (params?.from_date) q.append("from_date", params.from_date);
    if (params?.to_date) q.append("to_date", params.to_date);
    const qs = q.toString();
    return fetchWithTenant(`/companies/consolidated-trial-balance${qs ? `?${qs}` : ""}`);
  },

  // --- Phase 8: Currency Exchange & FX Revaluation ---
  getExchangeRates: () => fetchWithTenant("/currency/rates"),
  setExchangeRate: (data: any) =>
    fetchWithTenant("/currency/rates", { method: "POST", body: JSON.stringify(data) }),
  getLatestExchangeRate: (fromCurr: string, toCurr: string, asOfDate?: string) =>
    fetchWithTenant(`/currency/rates/latest?from_currency=${fromCurr}&to_currency=${toCurr}${asOfDate ? `&as_of_date=${asOfDate}` : ""}`),
  getExchangeRevaluations: () => fetchWithTenant("/currency/revaluation"),
  executeExchangeRevaluation: (data: any) =>
    fetchWithTenant("/currency/revaluation", { method: "POST", body: JSON.stringify(data) }),
  // --- Autonomous Workforce Platform & HITL Approvals ---
  listAutonomousAgents: () => fetchWithTenant("/agents"),
  runAutonomousAgent: (slug: string, triggerType: string = "MANUAL") =>
    fetchWithTenant(`/agents/${encodeURIComponent(slug)}/run`, {
      method: "POST",
      body: JSON.stringify({ trigger_type: triggerType }),
    }),
  runAllAutonomousAgents: () =>
    fetchWithTenant("/agents/run-all", { method: "POST" }),
  listAutonomousRuns: (limit: number = 30) =>
    fetchWithTenant(`/agents/runs?limit=${limit}`),
  listAutonomousCommunications: (limit: number = 30) =>
    fetchWithTenant(`/agents/communications?limit=${limit}`),
  listApprovals: (status?: string, domain?: string) => {
    const q = new URLSearchParams();
    if (status) q.append("status", status);
    if (domain) q.append("domain", domain);
    const qs = q.toString();
    return fetchWithTenant(`/approvals${qs ? `?${qs}` : ""}`);
  },
  approveRequest: (approvalId: string, notes?: string, modifiedPayload?: any) =>
    fetchWithTenant(`/approvals/${encodeURIComponent(approvalId)}/approve`, {
      method: "POST",
      body: JSON.stringify({ reviewer_notes: notes, modified_payload: modifiedPayload }),
    }),
  rejectRequest: (approvalId: string, notes?: string) =>
    fetchWithTenant(`/approvals/${encodeURIComponent(approvalId)}/reject`, {
      method: "POST",
      body: JSON.stringify({ reviewer_notes: notes }),
    }),
};
