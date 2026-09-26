export interface AgentStateMap {
  [agentId: string]: "RUNNING" | "IDLE" | "KILLED" | "PREEMPTED";
}

export interface DAGNode {
  task_id: string;
  name: string;
  agent_id: string;
  dependencies: string[];
  status: "PENDING" | "READY" | "RUNNING" | "COMPLETED" | "FAILED" | "PREEMPTED";
  error_message?: string;
}

export interface LineEvaluation {
  item_code: string;
  is_sku_matched: boolean;
  invoice_qty: number;
  grn_qty: number;
  is_qty_compliant: boolean;
  invoice_unit_price: number;
  po_unit_price: number;
  price_variance_percentage: number;
  is_price_compliant: boolean;
  is_line_matched: boolean;
  discrepancy_reason?: string;
}

export interface ThreeWayMatchResult {
  invoice_id: string;
  invoice_number: string;
  is_matched: boolean;
  matching_status: "MATCHED" | "DISPUTED" | "UNMATCHED";
  tolerance_summary: {
    is_fully_matched: boolean;
    overall_variance_percentage: number;
    discrepancies: string[];
    line_evaluations: LineEvaluation[];
  };
  ledger_result?: {
    transaction_id: string;
    total_volume: number;
    lines_committed: number;
  };
}

export interface BankFeedCandidate {
  order_id: string;
  order_number: string;
  customer_name: string;
  order_amount: number;
  amount_difference: number;
  semantic_similarity: number;
  composite_confidence: number;
  match_status: "AUTO_MATCH" | "AMBIGUOUS" | "NO_MATCH";
}

export interface BankReconResult {
  transaction_id: string;
  amount: number;
  is_auto_cleared: boolean;
  matched_order_number?: string;
  confidence_score: number;
  reconciliation_worklist_item?: {
    counterparty: string;
    remittance_info: string;
    candidates: BankFeedCandidate[];
  };
}

export interface GLEntry {
  entry_id: string;
  transaction_id: string;
  posting_date: string;
  account_code: string;
  cost_center: string;
  debit_amount: number;
  credit_amount: number;
  currency: string;
  source_document_type: string;
  source_document_id: string;
}

export interface ROPEvaluation {
  item_code: string;
  daily_demand_mean: number;
  daily_demand_std: number;
  lead_time_mean_days: number;
  lead_time_std_days: number;
  z_score: number;
  lead_time_demand: number;
  safety_stock: number;
  reorder_point: number;
}

export interface ScheduledOperation {
  job_id: string;
  operation_id: string;
  operation_name: string;
  workstation_code: string;
  duration_minutes: number;
  start_minute: number;
  end_minute: number;
}

export interface ScheduleResult {
  solver_status: string;
  makespan_minutes: number;
  solve_time_seconds: number;
  operations: ScheduledOperation[];
  workstation_schedules: Record<string, ScheduledOperation[]>;
}

export interface WorkstationTelemetryFrame {
  workstation_code: string;
  timestamp: string;
  vibration_rms_mm_s: number;
  bearing_temp_c: number;
  motor_power_kw: number;
  rpm: number;
}

// Phase 4: Workforce Types
export interface ShiftTradeRequest {
  trade_id?: string;
  requesting_employee: string;
  target_employee: string;
  shift_role: string;
  required_certification?: string;
  target_previous_shift_end: string;
  target_proposed_shift_start: string;
  target_current_weekly_hours: number;
  shift_duration_hours?: number;
}

export interface ShiftTradeResult {
  trade_id: string;
  is_approved: boolean;
  rest_interval_hours: number;
  projected_weekly_hours: number;
  is_rest_compliant: boolean;
  is_hours_compliant: boolean;
  is_certification_compliant: boolean;
  rejection_reasons: string[];
  confirmation_message: string;
}

export interface ExpenseAuditRequest {
  claim_id?: string;
  employee_code: string;
  expense_category: string;
  claim_date: string;
  total_amount: number;
  contains_alcohol: boolean;
  receipt_text: string;
  receipt_image_hash?: string;
}

export interface ExpenseAuditResult {
  claim_id: string;
  is_compliant: boolean;
  is_auto_approved: boolean;
  policy_violations: string[];
  audit_summary: string;
  ledger_commit?: {
    transaction_id: string;
    total_volume: number;
    lines_committed: number;
  };
}

export interface OperatorCertification {
  employee_code: string;
  certification_code: string;
  certification_name: string;
  expires_at: string;
}

// Phase 4: Commercial & Revenue Types
export interface DynamicPricingRequest {
  sku: string;
  bom_material_cost: number;
  machine_depreciation?: number;
  direct_labor?: number;
  freight?: number;
  target_markup_multiplier?: number;
}

export interface DynamicPricingEvaluation {
  sku: string;
  bom_raw_material_cost: number;
  machine_depreciation_cost: number;
  direct_labor_cost: number;
  dynamic_freight_cost: number;
  total_landed_cost: number;
  minimum_margin_floor: number;
  minimum_floor_price: number;
  proposed_unit_price: number;
  computed_margin_percentage: number;
  is_margin_defended: boolean;
  requires_price_escalation: boolean;
}

export interface BOMCostRollupResult {
  parent_sku: string;
  old_raw_material_cost: number;
  new_raw_material_cost: number;
  cost_increase_percentage: number;
  requires_quote_revaluation: boolean;
}

export interface QuoteInvalidationNotice {
  quote_number: string;
  customer_name: string;
  sku: string;
  old_quoted_price: number;
  old_margin_percentage: number;
  new_landed_cost: number;
  new_margin_with_old_price: number;
  is_invalidated: boolean;
  new_adjusted_price?: number;
  customer_adjustment_notice?: string;
}

export interface QuoteLineItem {
  item_code: string;
  description: string;
  quantity: number;
  unit_price: number;
  line_total: number;
}

export interface QuotationData {
  quote_number: string;
  customer_name: string;
  customer_email?: string;
  quote_date?: string;
  valid_until_date: string;
  promised_delivery_date: string;
  currency?: string;
  items: QuoteLineItem[];
  subtotal: number;
  tax_amount?: number;
  total_amount: number;
  margin_percentage?: number;
}

// Phase 4: SOC 2 & Mesh Coordination Types
export interface AuditBlockVerification {
  block_index: number;
  log_id: string;
  agent_id: string;
  trace_id: string;
  previous_hash: string;
  record_hash: string;
  is_valid: boolean;
  tamper_reason?: string;
}

export interface SOC2ComplianceReport {
  audit_id: string;
  evaluated_at: string;
  total_blocks_verified: number;
  is_chain_unbroken: boolean;
  tampered_blocks_count: number;
  compliance_certification: string;
  merkle_root_hash: string;
  verified_blocks: AuditBlockVerification[];
}

export interface MeshExecutionSummary {
  execution_id: string;
  event_type: string;
  initiating_agent: string;
  participating_agents: string[];
  tasks_dispatched: number;
  tasks_completed: number;
  is_compliance_verified: boolean;
  status: string;
  output_summary: Record<string, any>;
}

// Stage 1 & 2: Setup Wizard Types
export interface CountryInfo {
  country_name: string;
  country_code: string;
  currency: string;
  currency_symbol: string;
  timezone: string;
  fiscal_year_start: string;
  fiscal_year_end: string;
}

export interface IndustryInfo {
  name: string;
  default_modules: string[];
  cost_centers_count: number;
  warehouses_count: number;
  valuation_method: string;
}

export interface ModuleCatalogItem {
  slug: string;
  name: string;
  icon: string;
  description: string;
}

export interface SetupStatus {
  tenant_id: string;
  company_name: string;
  is_complete: boolean;
  setup_completed_at?: string;
  country?: string;
  industry?: string;
  currency?: string;
  enabled_modules: string[];
}

export interface CompleteSetupPayload {
  country: string;
  industry: string;
  currency: string;
  timezone: string;
  fiscal_year_start?: string;
  fiscal_year_end?: string;
  company_size: string;
  chart_of_accounts: string;
  enabled_modules: string[];
  generate_demo_data: boolean;
}

export interface CompleteSetupResponse {
  success: boolean;
  message: string;
  access_token: string;
  token_type: string;
  provisioned_summary: {
    accounts_count: number;
    cost_centers_count: number;
    warehouses_count: number;
    fiscal_periods_count: number;
    modules_count: number;
    demo_data_seeded: boolean;
  };
}

// Stage 3: In-App Module Onboarding Types
export interface OnboardingStepItem {
  step_id: string;
  step_key: string;
  step_title: string;
  step_description?: string;
  action_type: "CREATE_ENTRY" | "VIEW_REPORT" | "CONFIGURE_SETTING" | "VIEW_DOCS";
  reference_entity?: string;
  target_route?: string;
  is_complete: boolean;
  completed_at?: string;
  sort_order: number;
}

export interface OnboardingModuleProgress {
  module_slug: string;
  module_name: string;
  module_description: string;
  icon: string;
  is_complete: boolean;
  total_steps: number;
  completed_steps: number;
  steps: OnboardingStepItem[];
}

export interface OnboardingOverview {
  overall_progress_pct: number;
  total_steps: number;
  completed_steps: number;
  is_all_complete: boolean;
  modules: OnboardingModuleProgress[];
}
