# ERPNext Parity Completion Plan

**Scope:** the 35 partial and one missing feature identified in `erpnext_modules_outline.md` and verified against the current `rebuild/` codebase.

**Goal:** make the currently isolated master-data and reporting capabilities part of reliable, tenant-safe operational workflows. “Complete” means a user can configure a feature, use it during the relevant transaction, submit it, audit the persisted result, and report on it without recalculating historical records from mutable configuration.

## Evidence and product baseline

The current codebase already contains most of the new masters and endpoints introduced by the earlier parity work: `shared_master.py`, `phase_b.py`, `hr_deep.py`, migrations 032–038, `master_data.py`, and the Enterprise Reports page. The remaining work is chiefly integration, provenance, financial accuracy, and workflow UI.

The proposed behavior follows official ERPNext guidance:

- [Price Lists](https://docs.frappe.io/erpnext/price-lists) are collections of buying/selling item prices that should be selected or fetched during transactions.
- [Pricing Rules](https://docs.frappe.io/erpnext/pricing-rule) are evaluated when transaction inputs change and can adjust rates, discounts, margins, or free items.
- [Purchase Taxes and Charges Templates](https://docs.frappe.io/erpnext/purchase-taxes-and-charges-template) are copied into purchase documents and can affect both payable totals and inventory valuation.
- [Purchase Orders](https://docs.frappe.io/erpnext/purchase-order) carry source-document links, addresses, terms, delivery details, and purchase UOM/conversion information.
- [Loyalty Programs](https://docs.frappe.io/erpnext/loyalty-program) earn and redeem points from submitted invoices; entries must be auditable and reversible on returns/cancellation.
- [Leave Control Panel](https://docs.frappe.io/hr/leave-control-panel) bulk-creates policy assignments or allocations after filtering eligible employees.
- [Stock Projected Quantity](https://docs.frappe.io/erpnext/stock-level-report) includes actual, planned, requested, ordered, and reserved quantities; it must not mix incompatible meanings.

## Non-negotiable design rules

1. **Submitted documents are immutable.** Configuration can change, but a submitted purchase/sales document retains its applied prices, tax rows, terms, shipping, conversion factors, loyalty entries, and source links.
2. **One source of truth for calculations.** The backend calculation engine—not the Next.js client—determines prices, taxes, shipping, loyalty value, totals, and stock conversion.
3. **Tenant safety is enforced at every foreign key lookup.** Any referenced party, master, or source document must have the same `tenant_id`; never rely on an ID alone.
4. **Draft recalculation is explicit and idempotent.** Create/update operations may recalculate a draft. Submission locks a versioned calculation snapshot. A subsequent amendment creates a new draft version, never mutates posted financial history.
5. **Lineage uses real foreign keys.** Avoid reports that infer document links by matching item/date. Add source-line IDs where downstream documents are generated from a parent.
6. **Financial postings stay balanced.** Tax, shipping, loyalty redemption, landed-cost, and asset changes must produce balanced `GeneralLedgerEntry` groups and be covered by invariant tests.
7. **Release behind flags.** Add per-tenant feature flags for commercial calculation, loyalty integration, and the leave control panel. Backfill only after validation in staging.

## Delivery sequence

The work is deliberately ordered by dependency. Do not ship Phase 3 before Phases 1–2: an accurate report cannot be built over missing document lineage or mutable calculations.

1. Phase 0 — contract, migrations, and regression harness.
2. Phase 1 — document enrichment and source lineage.
3. Phase 2 — pricing, UOM, promotions, tax, shipping, terms, and bundles.
4. Phase 3 — loyalty and sales-partner execution.
5. Phase 4 — report correctness and operational-report UX.
6. Phase 5 — leave period and Leave Control Panel.
7. Phase 6 — hardening, backfill, rollout, and acceptance.

## Complete mapping of partial and missing items

### Accounting and reports

- **Customer Ledger Summary — partial.** Replace invoice-status estimates with a party-aware ledger. Add `party_type`, `party_id`, and `party_name_snapshot` to `GeneralLedgerEntry`; populate them for sales invoices, purchase invoices, payments, credit/debit notes, and adjustments. Build a customer ledger endpoint that returns opening balance, dated entries, debit, credit, running balance, and source-document links. Keep the existing summary endpoint as a compatibility aggregate.
- **Supplier Ledger Summary — partial.** Implement the same party-ledger design for suppliers. Do not treat `MATCHED` or `POSTED` as payment; only actual accounting/payment entries settle an open balance.
- **Gross Profit / Profitability — partial.** Persist `cost_rate_at_sale`, `cost_amount`, valuation method, and stock-ledger reference on every submitted delivery/invoice line. The report must use persisted values, label any legacy backfilled value as estimated, and exclude cancelled/reversed lines correctly.
- **Sales Invoice Trends and Purchase Invoice Trends — partial.** Keep the existing endpoints but add period granularity (`day`, `month`, `quarter`, `year`), comparisons, status filters, and chart-ready series. Replace the generic table-only experience with trend charts and drill-through lists.

### Buying

- **Material Request details / terms / external info — partial.** Add requestor, department, project/cost centre, target warehouse, required-by date, external reference/attachments metadata, and terms snapshot. Add line-level UOM, conversion factor, source, and procurement status.
- **Purchase Order detail, tax, contact/address, terms, more info — partial.** Add supplier contact/address, shipping/receiving address, payment terms, Incoterm, shipping rule, terms template/snapshot, tax-template reference/snapshot, currency/exchange rate, target warehouse, and document-level discount. Add source links to RFQ, supplier quotation, and material-request lines.
- **Item Price and Price List — partial.** Existing masters remain, but introduce a deterministic price-resolution service used by RFQ, supplier quotation, PO, quotation, sales order, sales invoice, and POS invoice drafts.
- **Product Bundle — partial.** Support sellable bundle expansion: persist bundle snapshot and component lines at quotation/order/invoice time, reserve/issue stock by component, and reject submission if required components are unavailable.
- **Promotional Scheme — partial.** Route all promotion decisions through the price-resolution service; support percentage/fixed discounts and Buy-X-Get-Y generated free lines with a source-promotion reference.
- **Naming Series — partial.** Turn `NamingSeries` from a CRUD record into an atomic sequence allocator per tenant/document type/fiscal period. Allocation occurs when a draft is first created; cancelled numbers remain auditable and are never reused.
- **Subcontracting Settings — partial.** Add explicit tenant configuration for supplied-item warehouse, over-transfer tolerance, consumption timing, default BOM/routing behavior, and required QA. Validate settings before subcontracting transitions.
- **Purchase Tax Template — partial.** Copy ordered tax rows to PO, receipt, and supplier-invoice snapshots. Support `Actual`, `On Net Total`, `On Previous Row Amount`, `On Previous Row Total`, and `On Item Quantity`; include account, valuation effect, add/deduct direction, reference row, and inclusion flag. Post tax and valuation effects to the ledger on submission.
- **Terms and Conditions — partial.** Let every buying and selling document select a terms template in draft, copy its rendered content into a non-editable snapshot at submission, and preserve the selected template ID for traceability.
- **Supplier-Wise Sales Analytics — partial.** Do not label purchase activity as supplier sales. Either rename the existing report to **Supplier Sourcing Analysis** immediately, or implement supplier attribution for inventory cost layers and build a separate supplier-margin/cost report. Never claim supplier-attributed revenue without a business rule and persisted relationship.
- **Procurement Tracker — partial.** Track `MaterialRequestItem → RFQItem/RFQSupplier → SupplierQuotationItem → PurchaseOrderItem → GoodsReceiptNoteItem → SupplierInvoiceItem` through nullable foreign keys. The tracker should display lineage, quantities, statuses, lead times, exceptions, and links; no item/date heuristic joins.
- **Item-wise Purchase History — partial.** Add a drill-down report with supplier, purchase UOM, converted stock quantity, rate, tax/landed cost, received quantity, rejected quantity, PO/receipt/invoice source, and date/currency filters.

### Selling and stock

- **Sales Order details, tax, terms, more info — partial.** Mirror the purchase-document snapshot pattern: customer contact/billing/shipping address, price list, payment terms, tax/charge rows, shipping rule/charges, terms snapshot, discount, currency/exchange rate, project/cost centre, delivery instructions, and source quotation links.
- **Sales Partner / Rep — partial.** Use the existing `SalesTeam` table as a supported transaction child collection. Add draft APIs and UI for sales orders and invoices; validate contributions total 100%, snapshot commission rate, and post commission payable only at the defined earned event.
- **Loyalty Point Entry — partial.** Link a customer to a program/enrollment; earn points automatically on submitted eligible sales/POS invoices; redeem in draft checkout; reserve/redemption-check transactionally; record expiry, cancellation/return reversals, and accounting entries. Keep manual adjustments as a permissioned audited operation only.
- **Sales Order Analysis — partial.** Persist ordered, delivered, invoiced, returned, cancelled, and outstanding quantities/amounts per line. Base pending-delivery/pending-billing on those fields rather than inference from header status.
- **Quotation Trends / Sales Order Trends / Delivery Note Trends — partial.** Add the same chart and drill-through contract as invoice trends, with separate state-series and conversion-rate series.
- **Item-wise Sales History — partial.** Add customer, sales UOM, converted stock quantity, price-list rate, discount, tax, delivery/invoice source, returns, margin snapshot, and date/currency/territory filters.
- **Shipping Rule — partial.** Evaluate shipping on draft selling/purchase documents after subtotal/taxable base is known. Persist the selected rule and calculated charge as a document charge row, including shipping account/cost centre; recalculate on address/items/quantity changes.
- **UOM conversion — partial.** Apply per-item conversion factors to all commercial and stock lines. Store entered UOM, factor, entered quantity, stock quantity, and rate basis snapshot. Reject zero/invalid conversions and protect submitted documents from later UOM-master edits.
- **Stock Summary — partial.** Publish a dedicated summary endpoint/page instead of treating Stock Balance as equivalent. It should aggregate by item group, warehouse, brand/manufacturer, and include actual/reserved/projected/value metrics with drill-through.
- **Stock Ageing — partial.** Implement persisted FIFO valuation layers: receipt creates a layer, consumption depletes layers transactionally, return restores/reverses deterministically, cancellation reverses entries. The ageing report reads remaining layer quantities only—no receipt chronology approximation.
- **Requested Items to be Transferred — partial.** Add a transfer-request report over submitted `MATERIAL_TRANSFER` requests, showing source/target warehouse, requested/issued/received/short quantities and ageing.
- **Subcontracted raw-material receipt/transfer reports — partial.** Add dedicated reports for supplied-to-subcontractor, consumed, received finished goods, pending return, and ageing of supplied material. Build them from explicit subcontracting stock movements and source references.

### HR

- **Leave Type / Period — partial.** Add a `LeavePeriod` model with name, fiscal year, start/end date, company/tenant, active status, and non-overlap constraints. Update allocations and policy assignments to reference the period while retaining legacy fiscal-year compatibility.
- **Leave Control Panel — missing.** Build an HR bulk-allocation workflow: select period or dates, choose policy or leave type, select carry-forward behavior, filter active employees, preview impact/errors, then create idempotent policy assignments/allocations in a background job with an audit batch record and downloadable result.

## Phase 0 — foundation and safety net

### Deliverables

1. Write an architecture decision record at `docs/adr/039-commercial-calculation-snapshots.md` covering snapshot immutability, source lineage, cancellation/reversal rules, and whether `SalesTeam` remains polymorphic.
2. Add a `FeatureFlag`/tenant-settings capability record for `commercial_calculation_v2`, `loyalty_v2`, `leave_control_panel_v1`, and `reporting_v2`.
3. Create test factories for tenant, party, item, price list, stock, tax rows, document sources, and clock-controlled dates.
4. Add cross-tenant negative tests to every new lookup and document-generation path.
5. Add a reusable `assert_balanced_transaction(transaction_id)` test helper for the ledger.

### Migration approach

Create additive Alembic revisions only. Do not modify 032–038. Each migration must be reversible where data loss is not involved, check for existing constraints before adding them, and be tested against an upgraded copy of production-shaped data.

### Exit criteria

- Existing test suite remains green.
- New migrations upgrade a fresh database and a database already at revision 038.
- No new endpoint accepts a cross-tenant ID.

## Phase 1 — document enrichment and lineage

### Schema

Create revision 039 with additive, nullable fields first:

- `purchase_orders`: contact/address IDs, terms-template ID, rendered terms, payment terms, Incoterm, shipping-rule ID, exchange rate, target warehouse, document discount, and tax/charge totals.
- `purchase_order_items`: `material_request_item_id`, `rfq_item_id`, `supplier_quotation_item_id`, entered UOM, conversion factor, stock quantity, target warehouse, and pricing snapshot fields.
- `sales_orders`: contact/billing/shipping address IDs, source quotation ID, terms-template ID/rendered terms, price-list ID, shipping-rule ID, payment terms, exchange rate, discount and tax/charge totals.
- `sales_order_items`: source quotation-item ID, entered UOM/factor/stock quantity, delivered/invoiced/returned quantities, and pricing snapshot fields.
- downstream receipt, delivery, and invoice item tables: parent-source-line foreign keys sufficient to trace one-to-many partial fulfilment and billing.
- `document_audit_batches` for migrations/backfills and bulk actions.

Use named composite indexes beginning with `tenant_id`, followed by the source ID and status/date used by tracker/report filters. Include `CHECK` constraints for positive factors, non-negative quantities, valid percentages, and date ranges.

### Backend

- Extend Pydantic draft-create/update schemas in `ap.py`, `procurement.py`, and `commercial.py`.
- Add a `source_document_service` that performs permitted draft conversions and updates parent-line progress in one database transaction.
- For every conversion, copy terms/tax/price/UOM snapshots and source metadata; do not re-query live masters after conversion unless the user deliberately recalculates a draft.
- Introduce explicit lifecycle commands: `recalculate_draft`, `submit`, `cancel`, and `amend`. Commands must use row locks for the header and affected source lines.

### Frontend

- Replace raw UUID entry on purchasing/selling forms with searchable tenant-scoped party/contact/address/source selectors.
- Add document tabs: Details, Items, Pricing & Taxes, Addresses, Terms, Source Links, Timeline/Audit.
- Show generated source links and remaining-to-order/receive/bill quantities; prevent invalid quantity entry before submit.

### Acceptance tests

- Convert one material-request line into two POs and verify remaining requested quantity.
- Convert a supplier-quotation line into a PO, then partial GRNs and invoices; verify tracker lineage and no over-receipt beyond setting.
- Convert a quotation into an SO, then partial delivery/invoice; verify pending delivery/billing is exact.
- Confirm submitted terms/addresses/source links do not change when masters are edited afterwards.

## Phase 2 — commercial calculation engine

### Service boundary

Create `src/erp/workflows/commercial/calculation_service.py`. Its input is a tenant-scoped draft header plus normalized lines; its output is a deterministic `CalculationResult` containing line price snapshots, discount/promotion decisions, generated free lines, tax rows, shipping rows, stock quantities, totals, warnings, and an opaque calculation version/hash.

The service must be invoked by draft APIs in `ap.py`, `commercial.py`, billing/POS routes, and any source-document conversion. The client may request a preview but cannot supply a final tax or total.

### Price and promotion rules

1. Validate document context: BUYING/SELLING, party, currency, warehouse, date, price list, and entered UOM.
2. Resolve active item price by item, price list, currency, UOM, validity and priority.
3. Convert rate/quantity with the persisted UOM factor.
4. Evaluate eligible pricing rules and promotions using a single priority/stacking policy. Reject ambiguous equal-priority rules unless explicitly stackable.
5. Generate free-item lines with a source promotion ID and a zero commercial rate; reserve/issue their component stock normally.
6. Persist the chosen source IDs and calculated values on each draft line; replace them only on an explicit recalculation.

Extend existing masters only as required: pricing context (buy/sell, currency, party/group/territory/supplier restrictions, max quantity/value, warehouse, stackability), promotion slabs/free item, price UOM, and effective dates. Include audit fields for disabled/retired records rather than deleting live configuration.

### Tax, shipping, and terms

- Add transaction tax-row tables (typed per document family or a carefully constrained common snapshot table) with calculation base, amount, running total, account, valuation impact, and template source ID.
- Expand the purchase tax model to preserve all required calculation types and valuation/accounting semantics. Add the matching sales-side snapshot contract.
- Add shipping charge rows as part of the tax/charge total and make shipping-rule selection deterministic by address and order value/weight/quantity.
- At submission, post tax/shipping amounts to configured accounts and, when marked for valuation, create stock valuation adjustments exactly once.
- Terms are rendered and copied on draft selection; users with the right permission can edit the draft copy, but not a submitted copy.

### Bundles and UOM

- Add a bundle-expansion service that snapshots component item, quantity, UOM factor and availability. Sales documents display the parent bundle and operationally fulfil components.
- Store `entered_uom_id`, `conversion_factor`, `entered_qty`, `stock_qty`, `rate_per_entered_uom`, and `base_rate_per_stock_uom` for all new transactional lines.

### Acceptance tests

- Correct buying/selling price list and UOM price are selected for the same item.
- A pricing rule changes a draft rate after quantity crosses a threshold and is frozen after submission.
- Buy-X-Get-Y creates exactly one source-linked free line and reverses correctly on cancellation.
- Tax rows with previous-row calculations, inclusive rate, and valuation impact give the expected totals and balanced ledger entries.
- Shipping changes when address/order value changes, and its submitted charge remains fixed.
- Bundle stock is consumed by component and cannot oversell a missing component.

## Phase 3 — loyalty and sales-partner execution

### Loyalty

Create revision 041 after Phase 2:

- Add customer enrollment fields/table, program validity, tier/slab records, expiry policy, and program accounting configuration.
- Add `source_document_type`, `source_document_id`, `reversal_of_entry_id`, expiry date, balance impact, and status to loyalty entries. Enforce idempotency per submitted invoice/POS invoice event.
- Add a `loyalty_service` with `preview_redemption`, `redeem_on_submit`, `earn_on_submit`, `reverse_for_return`, `reverse_for_cancel`, and `expire_points` operations. Use row locks on the customer/program balance to prevent double redemption.
- Surface loyalty selection/redemption in Sales Invoice and POS draft checkout. Add permissioned manual adjustment with reason and audit log.

### Sales partners

- Add SalesTeam child CRUD to draft sales orders and invoices; validate total contribution equals 100 and partner is active in the tenant.
- Snapshot partner commission rate on the document. Define one business event for earning commission (normally submitted invoice or paid invoice) and post it via a balanced transaction.

### Acceptance tests

- Submitted invoice earns exactly once; retrying the request is idempotent.
- POS redemption reduces payable exactly once and rejects insufficient/expired points.
- Return/cancel reverses both earning and redemption correctly.
- Multiple sales partners with valid contribution are reported and commission rate is frozen.

## Phase 4 — report correctness and reporting UX

### Correct the data first

1. **Party ledger:** populate party dimensions on new GL entries. Backfill only when a source document unambiguously identifies the customer/supplier; tag all other historical entries `unattributed` rather than guessing.
2. **Margin:** use cost snapshots from Phase 1/2 for new data. Preserve `is_estimated=true` for legacy rows and let users exclude them.
3. **FIFO:** create persistent `stock_valuation_layers` and `stock_layer_consumptions`; use database locking ordered by receipt date/layer ID to prevent concurrent double consumption.
4. **Projection:** add `planned_qty` from open work orders and `requested_qty` from submitted unconverted material requests. Publish the exact formula and component breakdown.
5. **Procurement:** rebuild tracker exclusively from lineage foreign keys. Provide an exception bucket for legacy/unlinked data.

### Report APIs

Keep `/reports/enterprise/*` paths where possible, but version response schemas through an explicit `schema_version` field. All report APIs must accept a bounded date range, pagination for drill-down rows, CSV export job creation, and filters appropriate to the domain.

- Customer/Supplier Ledger: opening, transaction rows, running balance, source deep link, settlement/aging metadata.
- Gross Profit: recorded revenue, recorded cost, margin, percentage, cost source, estimate flag.
- Trends: period series, prior-period comparison, status series, conversion/cancellation metrics.
- Purchase/Sales history: item/party/UOM/rate/discount/tax/fulfilment/margin drill-down.
- Stock summary/projected/ageing/shortage: warehouse and group filters, explained formula, layer or demand/supply drill-through.
- Transfer and subcontract reports: explicit source links, quantities, statuses, ageing, exception reason.

### Frontend

Replace the single generic Enterprise Reports table for these report types with reusable report components:

- filter bar with saved filter sets;
- KPI strip with definitions/tooltips;
- line/bar chart for trends and conversion;
- sortable/paginated detail grid;
- click-through to source document and audit trail;
- export with a visible “estimated historical data” warning where applicable.

### Acceptance tests

- Ledger running balance equals the GL-party balance at every returned row.
- Margin totals reconcile to recorded invoice revenue and cost snapshots.
- FIFO report returns only remaining layers after issue/return/cancellation sequences.
- Projected quantity agrees with its published components.
- A tracker row can be navigated from MR item through receipt/invoice without heuristic matching.

## Phase 5 — leave period and Leave Control Panel

### Schema and services

Create revision 042:

- `leave_periods`: tenant, name, fiscal year, from/to dates, active, and a non-overlap exclusion/validation policy.
- Add nullable `leave_period_id` to allocations and policy assignments; backfill from fiscal year only when dates are unambiguous.
- `leave_allocation_batches`: submitted-by, filters snapshot, selection snapshot, policy/leave-type choice, carry-forward choice, period/dates, status, summary counts, error artifact, and idempotency key.

Create `leave_control_service.py` to preview selected employees and to execute a batch. It must:

1. reject past periods/dates and inactive/terminated employees;
2. filter by employee fields such as department, designation, grade, location, joining date, and custom safe allow-listed fields;
3. calculate carry-forward and existing allocation conflicts;
4. use an idempotency key and per-employee savepoints;
5. create LeavePolicyAssignment or LeaveAllocation records without duplicates;
6. produce a durable per-employee success/skipped/error result.

### API and UI

- `POST /hr/leave-control/preview`
- `POST /hr/leave-control/batches`
- `GET /hr/leave-control/batches/{id}`
- `GET /hr/leave-control/batches/{id}/results`

Build `/leave-control` as a guided page: dates/period → policy or direct allocation → filters → selected employee preview → confirm → results. Require HR-admin permission and an explicit confirmation when the batch changes more than a configured threshold of employees.

### Acceptance tests

- A policy batch creates allocations only once across a retry.
- Direct allocation respects carry-forward and does not allocate over an existing overlapping period.
- Department/grade filters select the expected employees and exclude inactive staff.
- Partial failures are reported without rolling back valid employee allocations; a retry processes only unresolved entries.

## Phase 6 — rollout and operational readiness

### Backfill policy

- Do not synthesize tax, loyalty, terms, price, shipping, or FIFO snapshots for posted history unless the source values are provably available. Mark legacy report data as estimated/unlinked.
- Backfill direct source relationships only from existing explicit IDs; leave inferred relationships null.
- Rebuild materialized/reporting indexes after backfills in a maintenance window.

### Rollout stages

1. Fresh-database migration and automated test gate.
2. Staging upgrade with production-shaped anonymised data; reconcile representative GL, stock, and report totals.
3. Enable flags for one internal tenant; run purchase-to-pay, quote-to-cash, POS, return, transfer, subcontracting, and leave-control acceptance scripts.
4. Enable for pilot tenants with monitoring and a documented rollback path that disables flags but never rolls back committed financial data.
5. General availability only after data-quality dashboards show no duplicate loyalty entries, unbalanced ledger transactions, invalid source links, or FIFO layer mismatches.

### Definition of done

- All 36 findings in the audit are moved to Complete, or the outline is intentionally amended with an accepted product decision.
- Every calculation and conversion is tested at API/service level, UI level, and with tenant-isolation negatives.
- Migration revision, feature flag, rollback behavior, and support runbook are documented.
- Reports disclose estimation and legacy lineage rather than presenting approximations as exact figures.

## Recommended first release slice

Start with **Phase 1 + the core of Phase 2**: document lineage, contact/address/terms snapshots, UOM persistence, price selection, and tax snapshots. This resolves the largest number of partials and creates correct primitives for procurement tracking, sales-order analysis, margin, stock projection, loyalty, and report accuracy. Shipping, promotions, bundles, loyalty, FIFO layers, and the Leave Control Panel should follow once those transaction foundations are in production.
