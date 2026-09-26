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
    throw new Error(err.detail || "Request failed");
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
  getAgentStates: () => fetchWithTenant("/agents/states"),
  dispatchRFQ: (data: { customer_name: string; inquiry_text: string }) =>
    fetchWithTenant("/agents/dispatch-rfq", { method: "POST", body: JSON.stringify(data) }),
  getLatestDag: () => fetchWithTenant("/agents/dags/latest"),
  getDag: (dagId: string) => fetchWithTenant(`/agents/dags/${encodeURIComponent(dagId)}`),
  listDags: () => fetchWithTenant("/agents/dags"),
  arbitrateAgentCollision: (proposals: any[]) =>
    fetchWithTenant("/agents/arbitrate", { method: "POST", body: JSON.stringify({ proposals }) }),

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

  // --- Production Scheduling ---
  getWorkstations: () => fetchWithTenant("/production/workstations"),
  createWorkstation: (data: any) =>
    fetchWithTenant("/production/workstations", { method: "POST", body: JSON.stringify(data) }),
  getWorkOrders: () => fetchWithTenant("/production/work-orders"),
  createWorkOrder: (data: any) =>
    fetchWithTenant("/production/work-orders", { method: "POST", body: JSON.stringify(data) }),
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
};

