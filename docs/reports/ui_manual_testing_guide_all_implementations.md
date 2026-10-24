 # Full UI Manual Testing Guide — ERP Module Implementations

**Project:** AI Native ERP  
**Scope:** Original ERP module phases 1–8, implementation-plan phases A–F, and the ten payroll/project/loyalty/HR/reporting fixes  
**Audience:** Product owner, QA, implementation team  
**Test style:** Manual end-to-end testing through the web UI  
**Status:** Test instructions prepared; no UI test run is claimed by this document  
**Related plan:** `docs/erpnext_modules_implementation_plan.md`

---

## 1. Purpose and coverage

Use this guide to verify the implemented user-facing workflows from a browser, following records as they move between modules. It focuses on observable UI behavior: forms, lists, workflow statuses, calculated values, stock balances, ledger/report results, validation messages, and role-restricted actions.

The guide covers these workspaces:

- Original phases 1–8: billing/POS; buying; stock/logistics; HR/payroll; manufacturing/MES; CRM/support; assets/quality/maintenance/projects; subcontracting/reports/consolidation/FX.
- Parity phases A–F: shared master data; buying and selling enhancements; deep HR workflows; payroll and asset enhancements; projects and support reports; 26 enterprise reports.
- Regression scenarios for payroll periods and tax, salary slip duplication and currency, billable time, project task ownership, invoice-backed loyalty, HR deletion safeguards, and projected stock.

Several reports explicitly disclose that values are estimates or status-based proxies. The expected behavior below includes those limits; the UI should label such data and must not imply more precision than its source records support.

## 2. Test safety and environment setup

### Use a disposable tenant

Run these scenarios in a development or QA environment with a disposable tenant. The workflows can create invoices, change stock, post ledger entries, issue payroll, consume bonus/additional-salary records, close periods, and change employee lifecycle status. Avoid production records. Do not use real payment credentials or submit a live payment.

Create or identify these users if role-based testing is needed:

1. A tenant administrator or equivalent full-access user.
2. An HR manager.
3. A standard user without HR manager privileges.
4. A second tenant/user for tenant-isolation checks.

Use credentials provisioned for your own environment. Do not copy credentials from old completion reports; those may be stale or unsafe.

### Start the application

From the `rebuild/` directory, use the repository's normal development configuration. The usual local addresses are:

- Frontend: `http://localhost:3000`
- Backend/API: `http://localhost:8000`
- API docs (only if needed for diagnostics): `http://localhost:8000/docs`

Before testing, confirm the frontend can sign in and load the sidebar, and that the backend is connected to the intended QA database. Apply database migrations through the repository's normal migration procedure before opening the UI. The latest change in scope adds migration `038_payroll_currency_and_period_guard.py`; verify the database has reached the current Alembic head, particularly before testing salary slip currency and period uniqueness. Do not infer migration success from the frontend compiling.

The phase reports document a pre-existing problem with generating the entire migration chain in offline SQL mode; this does not by itself prove an online migration failure. Use the project's configured database environment and follow the normal online migration process. If migrations fail or the application schema is behind, stop and resolve that before treating any UI failure as a feature defect.

### Prepare reusable test records in the UI

Create a small, clearly named test dataset in this order. Prefix names with something like `QA-UI-<date>` so they are easy to find and clean up.

1. In **Shared Master Data** (`/master-data`), create an item group, UOMs and a conversion, a selling and buying price list, an item price, a supplier group, an issue type, and any terms, tax, shipping, promotion, sales partner, or loyalty records needed for later tests.
2. In **Inventory & Warehouses** (`/inventory`), create at least two active items, a finished good and its components, a template item if testing variants, and two warehouses. Record starting on-hand quantities.
3. In **Commercial & Sales** (`/commercial`), create a customer and a quotation or sales order if required. In **Procurement & Buying** (`/procurement`) or **3-Way Invoice Match** (`/accounts-payable`), create a supplier and purchase-side records.
4. In **Workforce & Shifts** (`/workforce`), create an active employee, department/designation, shift, and leave type/allocation. Add a separate employee if testing employee-specific activity rates or approvers.
5. Configure a tax slab and open payroll period before payroll tests. For currency tests, use a tenant whose base currency differs from the salary structure currency. The current frontend exposes FX revaluation/history under **Reports & Analytics → Group Consolidation & FX**, but does not expose an exchange-rate creation form; a dated rate must be provisioned through approved admin/API tooling before the UI payroll test. Mark rate provisioning as not exposed in UI.
6. Keep a small test ledger: one ordinary sale, one invoice with a different date/status, one partial delivery, one open purchase order, and one partially received order. These support report and projected-quantity comparisons.

If a page does not expose the necessary master or a workflow cannot be reached from a form, record it as a UI coverage gap; do not fabricate success using direct database edits.

## 3. How to record results

For each scenario, capture:

- Tenant, user role, date/time, browser, and app build/branch.
- Starting record IDs/numbers and relevant balances (stock, points, payroll, ledger).
- Steps performed and visible final statuses/calculated values.
- Screenshots of the form, success/error feedback, and downstream list/report.
- Any mismatch, stale data, missing control, unclear label, or unexpectedly permitted action.

Mark each case **Pass**, **Fail**, **Blocked** (environment/data/role issue), or **Not exposed in UI**. For a failure include exact navigation path, inputs, expected result, actual result, and screenshot. Refresh the page before declaring a calculation or list update missing, to distinguish persistence from local state.

---

## 4. Phase-by-phase UI scenarios

### Phase 1 — Billing, receivables, subscriptions, POS

Open **Point of Sale** (`/pos`), **Billing & Subscriptions** (`/billing`), **Plan & Payment** (`/billing/subscription`), **General Ledger** (`/ledger`), and **Reports & Analytics** (`/reports`).

1. **POS shift and split tender:** Open a POS shift/profile, add two items, and tender one sale using two payment methods. Confirm the displayed tender total, change due, receipt, invoice number, and shift totals agree with the sale.
2. **Park and restore cart:** Add multiple lines and a note, park the cart, navigate away or start a fresh cart, then restore the parked cart. Check customer, quantities, prices, and note. Discard a separate parked cart and confirm it no longer appears.
3. **Return and restock:** Use a completed sale/receipt to make a partial return. Check the original sale reference, returned quantity, return receipt, and warehouse stock delta. Confirm the return does not exceed the originally sold quantity.
4. **Close and consolidate shift:** Close a test shift with a known tender amount. Confirm expected variance, close status, and consolidated invoice. Check `/ledger` for the related posting and `/reports` for the financial totals.
5. **Billing tabs:** In `/billing`, exercise **Payment Terms**, **Tax & Charges**, **Dunning & Overdue**, **Budgets & Control**, **Credit Notes**, **Debit Notes**, and **TDS / Withholding** using test records. Confirm installment dates/amounts sum to invoice total, cascading tax rows calculate in order, eligible overdue items appear, budget WARN/STOP behavior is visible, and credit/debit notes create the expected invoice/stock effect.
6. **Subscription lifecycle:** In the subscription page, create a trial or active subscription with multiple plan items. Exercise pause/resume, due billing run, and a mid-cycle plan change. Confirm the invoice/proration is based on the displayed dates and the next billing date advances once. A paused subscription should not bill.
7. **Financial statements:** In `/reports`, visit trial balance, balance sheet, P&L, cash flow, AR/AP aging, stock/MES analytics, and consolidation. Set a narrow date range containing the test transactions. Confirm report filters reload results and the accounting equation/totals are internally consistent.

### Phase 2 — Buying, sourcing, invoices, landed cost, supplier performance

Open **Procurement & Buying** (`/procurement`) and **3-Way Invoice Match** (`/accounts-payable`).

1. **Requisition/replenishment:** Create a material request for an item and quantity. Run auto-replenishment against an item below its reorder threshold. Confirm a draft request is suggested/created without duplicating an already satisfied request.
2. **Request to purchase order:** Convert part of the request to a PO, then convert the remaining quantity if supported. Verify ordered quantities and remaining request quantity. Submit/receive the PO through the available workflow.
3. **RFQ comparison:** Create an RFQ with at least two suppliers, add supplier quotations with different rates/lead times, open the comparison matrix, and award the intended quotation. Confirm one PO is generated for the selected supplier and competitors/RFQ receive the expected state.
4. **Blanket order:** Create a contract with a validity window and quantity/value limit. Release a PO within the limit, then attempt an over-limit or out-of-window drawdown. Confirm allowed drawdown updates progress and the disallowed one is rejected with an understandable message.
5. **GRN and 3-way match:** Receive a PO partially. Compare PO, accepted/rejected GRN quantity, and supplier invoice. Test a matching invoice, a quantity mismatch, and a tolerance boundary. Confirm the UI shows match status/variance and does not silently approve an over-tolerance discrepancy.
6. **Landed cost voucher:** Select one or more accepted GRNs, add a freight/charge line, compare valuation-based and quantity-based apportionment, then submit/post. Check item valuation and ledger posting; make sure total allocated charge equals the entered charge, subject to displayed rounding.
7. **Supplier scorecard:** Evaluate a supplier for a test period. Confirm OTIF, quality, price variance, total score, rank/tier, and any purchasing restriction match the supplied evidence. Check the supplier leaderboard refreshes.
8. **Supplier invoice/AP tabs:** In `/accounts-payable`, inspect invoices, purchase orders, GRNs, and suppliers. Reopen a created record after refresh and verify its status and relationship links persist.

### Phase 3 — Inventory, warehouse logistics, traceability

Open **Inventory & Warehouses** (`/inventory`) and **Delivery Notes** (`/delivery-notes`).

1. **Stock movements:** Submit a material receipt, issue, and warehouse transfer. Verify each source/target quantity and stock ledger entry. Attempt a negative-stock movement when the setting disallows negative stock and confirm it is blocked.
2. **Physical reconciliation:** Enter a counted quantity that differs from book quantity, review the variance, submit, and confirm on-hand and audit/ledger records reflect exactly the variance.
3. **Serials and batches:** Create a batch with manufacture/expiry dates and a serial-tracked item. Register serials, change allowed lifecycle status, and verify duplicate serial registration or invalid status transition is rejected.
4. **Pick/pack and delivery:** Create a pick list for an order, update picked quantities, and create a packing slip/carton. Dispatch a delivery trip with multiple stops and record proof of delivery. Confirm partial/completed stops and delivery quantities are reflected on the delivery note/order.
5. **Reservations and variants:** Reserve inventory against an order and confirm available stock changes. Add a product attribute and generate variants from a template. Confirm generated SKU combinations are distinct and repeated generation does not create unintended duplicates.
6. **Delivery-note workflow:** Create a delivery note from an eligible sales order, partially deliver it, and confirm the remaining quantity remains pending. Link/create an invoice from the delivered quantity if available.

### Phase 4 — Workforce, leave, payroll, advances, expenses

Open **Workforce & Shifts** (`/workforce`) and **Full & Final Settlement** (`/full-and-final`).

1. **Employee/organization/attendance:** Create employee and org records, record present and absent attendance, then inspect employee directory and attendance list after refresh. Confirm late-entry badges and date/time displays use the configured shift.
2. **Leave workflow:** Apply for leave, approve as an authorized user, and confirm status and balance. Attempt a date range blocked by an active leave block list. Confirm a different user/invalid approver cannot approve.
3. **Salary structure and slip:** Create earning/deduction components and a structure, assign it to an employee, then generate a slip for an open period. Check line items, gross, deductions, tax, net, and payment/LWP days. Submit only the intended test slip to GL and confirm the journal balances and appears in `/ledger`.
4. **Payroll period:** Create a payroll period, generate slips, close it, then attempt another slip in that closed period. Confirm the UI prevents generation/submission according to the workflow.
5. **Additional salary/bonus:** Queue a one-time additional earning and a retention bonus with known taxable flags. Generate a slip and verify the sources attach once, the displayed withholding changes consistently with the configured slab, and the source cannot be added twice to another slip.
6. **Advance and expense:** Request/sanction/disburse an employee advance, then inspect advance balance and GL. Submit an expense claim and reimburse it; verify the claim status, payable/bank effects, and employee-level history.
7. **Full and final:** Create a separation, create a full-and-final statement and earning/deduction items, recalculate, submit/approve, and mark paid through the available workflow. Confirm item totals equal statement totals and paid status persists. Test that the UI does not offer deletion for completed/paid records; if it does, attempt it as a standard user and HR manager and verify the action is blocked.

### Phase 5 — Manufacturing, MRP, MES, scheduling

Open **Production & BOM** (`/production`). Create sufficient component stock in advance.

1. **BOM/routing:** Create an operation, routing, and multi-level BOM with raw components and scrap. Open the BOM detail/explosion and compare displayed component/operation/scrap costs with the known inputs.
2. **MRP:** Create a production plan for a finished good with known demand. Inspect gross requirements, on-hand, and shortage. Generate work orders and confirm the work order quantities match the plan.
3. **Work order staging/completion:** Stage material to WIP, then complete/backflush. Verify component stock decreases, finished-good stock increases, status changes once, and GL/stock ledger entries are visible. Attempt an over-completion or repeated completion if UI permits and confirm it is rejected/idempotent.
4. **MES job cards:** Assign an operator, punch in, pause/resume, and complete with good and scrap quantities. Check elapsed time, accepted output, scrap, and linked work order.
5. **Workstations/OEE:** Log downtime, verify workstation status and downtime duration, then resolve it. Confirm OEE inputs update and no open downtime remains after resolution.
6. **CP-SAT scheduler:** Run the scheduler on a small set of jobs and workstations. Review start/end allocations and check no workstation has overlapping jobs. Use a failure/reroute simulation only in the disposable tenant and confirm affected work is rescheduled or a clear infeasibility result is shown.

### Phase 6 — CRM, support, SLA, warranty

Open **CRM & Support Desk** (`/crm`) and **WhatsApp Support** (`/whatsapp`) if that integration is configured.

1. **Lead qualification/conversion:** Create a lead with known company/revenue inputs, qualify it, convert it to an opportunity, then convert a separate lead to customer. Confirm no duplicate customer is created by repeating a conversion.
2. **Opportunity pipeline:** Move an opportunity through stages, inspect pipeline/weighted forecast, and use the quote action. Verify generated quotation references the right customer/opportunity and appears in the commercial workspace.
3. **Campaign/contract:** Create a campaign and drip steps, then review the service contract record. Confirm date order, status, and customer link persist.
4. **Issue/SLA:** Create an urgent ticket. Verify deadlines are set from the applicable SLA. Add an internal note and a public response; verify the note is visibly marked private and does not count as a customer response. Resolve the issue and inspect SLA status.
5. **SLA configuration and reports:** Review priority response/resolution rules and support reports. Use a bounded date range and compare ticket counts, breaches, and durations to the test tickets.
6. **Warranty/RMA:** Register/choose a serial with known warranty dates, verify in-warranty and expired cases, file a claim, and resolve it with an RMA disposition. Confirm linked serial/customer/claim records.
7. **WhatsApp (only when configured):** Pair the test account, send/receive a sandbox message, inspect the ticket/thread, add/remove a test knowledge source, and verify an imported source is tenant-scoped. Do not connect a real customer account for a QA test.

### Phase 7 — Assets, quality, maintenance, projects

Open **Fixed Assets & Dep.** (`/assets`), **Quality Assurance** (`/quality`), **Maintenance Hub** (`/maintenance`), and **Projects & Timesheets** (`/projects`).

1. **Asset lifecycle/depreciation:** Create an asset, select depreciation method/useful life, run or review schedule, post a depreciation period, and inspect ledger. Confirm posted history is retained when value adjustments are made and only eligible future schedules recalculate.
2. **Asset maintenance/value/team:** Create a maintenance team and members, log an asset maintenance event, create a value adjustment, and inspect asset book value and adjustment history.
3. **Inspection/NCR/CAPA:** Configure an inspection template, submit an inspection with a failed reading, open an NCR, create a 5-Whys/CAPA action, assign an owner/due date, and close only after completion evidence. Verify inspection status and defect/action links.
4. **Preventive maintenance:** Create a schedule, generate/complete a visit, and confirm next due date advances according to cadence. Check an overdue schedule remains visible.
5. **Project type/updates:** Configure a project type, create a project using it, record updates with progress and blockers, and inspect the activity timeline after refresh. Try invalid progress outside 0–100 if form validation allows.
6. **Activity costing/timesheets:** Configure an activity type and default rate, then an employee-specific rate. Log hours and confirm the employee-specific rate wins; test an effective-date boundary. Log a nonbillable timesheet and check it increases project cost but not billed total. Confirm a task from a different project cannot be used.
7. **Support report cross-check:** Use the support reports tab and compare values to tickets created in Phase 6.

### Phase 8 — Subcontracting, reports, consolidation, currency

Open **Subcontracting Ops** (`/subcontracting`), **Reports & Analytics** (`/reports`), and **Enterprise Reports** (`/reports/enterprise`).

1. **Subcontracting order:** Create an order for finished goods and component requirements. Issue materials to the vendor warehouse and confirm company/vendor warehouse stock changes. Receive finished goods and inspect component consumption and finished-good quantity. Test partial receipt if supported.
2. **Standard reports:** In `/reports`, test trial balance, P&L, balance sheet, cash flow, aging, stock operations, and consolidation for a period containing your transactions. Record the same dates and totals for repeatability.
3. **Enterprise report catalog:** In `/reports/enterprise`, test all report options using a date range containing your seeded records. Confirm Refresh changes results and each report returns its expected metric/list shape:
   - Accounting: customer ledger summary; supplier ledger summary; gross profit by item/customer; sales invoice trends; purchase invoice trends.
   - Buying: purchase analytics; purchase orders/status/overdue; supplier sourcing by item; MR→PO→GRN tracker; items below reorder level.
   - Selling: sales by item/customer/territory; pending delivery/billing; quotation trends; sales order trends; inactive customers.
   - Stock: projected quantity; stock ageing estimate; stock analytics; delivery note trends; item shortage report.
   - HR: headcount/attrition; leave balance; birthdays; recruitment funnel.
   - Support: SLA compliance; agent performance.
4. **Report sanity checks:** Reconcile report rows to visible source documents. For projected stock use: on-hand − reserved − open undelivered sales + open unreceived purchases. For shortage reports compare available quantity with reorder level. For stock ageing, confirm the page labels it as an estimate. For gross profit, ledger summaries, supplier sourcing, and overdue purchase orders, retain the calculation limitations stated in the Phase F completion report.
5. **Group consolidation and FX:** In `/reports` → **Group Consolidation & FX**, add test company entities and inspect consolidation/eliminations. The screen lists configured rates and has a **Run FX Revaluation** action, but currently lacks a rate-entry control; have an administrator provision a dated FX rate first, then run revaluation and verify the resulting ledger entries balance. Do not use inconsistent dates/rates across test runs.

---

## 5. Regression checklist for the ten recent fixes

Perform these focused cases after the phase suites. They are especially important because each checks a previously identified defect.

1. **Payroll proration for nonstandard periods:** Assign a monthly salary, create a period with a known number of calendar days (for example, a 15-day range), and generate a slip with no absences. Confirm payment days equal the period length and recurring pay is prorated to that period rather than using a fixed 30-day denominator.
2. **LWP crossing period boundaries:** Approve an LWP application that starts before the payroll period or ends after it. Generate a slip for the overlapping period and confirm only the overlapping leave portion is counted. Repeat with a leave application fully outside the period; it must not affect the slip.
3. **Recurring pay versus one-time taxable pay:** Configure a tax slab with at least two brackets. Generate a baseline slip, then a comparable slip with a taxable bonus/additional payment. Confirm the UI shows the tax effect for the bonus under the applicable marginal bracket; confirm non-taxable one-time pay does not increase taxable withholding. Compare same-length periods and identical base pay.
4. **Duplicate/overlapping salary slip:** Generate one active slip, then try an identical period and a partially overlapping period for the same employee. The second generation must be rejected and the first slip must remain unchanged. A cancelled slip should not permanently block a replacement if the workflow allows cancellation.
5. **Payroll currency/GL:** Use a salary structure currency different from the tenant's base currency and a dated exchange rate provisioned before the UI test. Submit a slip to GL. Confirm the slip retains its source currency, GL values use tenant base currency, the displayed rate/date is correct if surfaced, and total debit equals total credit. Repeat without an FX rate and expect a clear rejection rather than a silent 1:1 conversion. Rate creation itself is not currently UI-testable; record that setup as an API/admin prerequisite.
6. **Nonbillable project time:** Record billable and nonbillable timesheets with known rates. Confirm both contribute to project cost while only billable time contributes to the project billed total.
7. **Task/project ownership:** Try selecting or submitting a task belonging to Project B while logging time to Project A. The form should filter it out or reject the entry. Confirm Project B task actual hours are not incremented by a rejected entry.
8. **Invoice-backed loyalty and customer ownership:** Create two customers and issued/paid invoices. In `/loyalty`, select Customer A and confirm only A's invoices are offered. Earn from one invoice; points should equal invoice subtotal × program rate, not a manually entered amount. Repeat the same invoice and confirm points are not duplicated. An invoice in a different currency should be excluded or clearly rejected unless conversion is explicitly supported.
9. **Paid full-and-final protection:** As standard user, inspect a paid statement and attempt available delete controls; it must not be deleted. Repeat as HR manager. Draft statements may follow the configured deletion rule, but submitted/paid history must remain. Confirm the UI reports a clear restriction.
10. **Partial receipts/deliveries in projected quantity:** Set up an open PO and SO for the same item, partially receive the PO and partially deliver the SO. Open **Projected Stock Quantity**. Confirm only unreceived PO quantity is counted as future supply and only undelivered SO quantity is counted as future demand; accepted receipts already in on-hand must not be counted twice.

### Cross-tenant and role isolation

These checks should be done through two browser profiles or separate sessions logged into different test tenants:

- Create an item, employee, invoice, and project in Tenant A. Confirm they do not appear in Tenant B's lists, dropdowns, reports, invoice selector, or autocomplete results.
- Try to open a copied record URL from Tenant A while signed into Tenant B. The UI should show not found/unauthorized and must not disclose record details.
- As a standard user, check access to confidential grievance records and HR approval/deletion controls. Repeat with HR manager/admin. Verify authorization comes from server responses, not only hidden buttons.
- Switch to a second customer and confirm loyalty balance/history is distinct.

## 6. Completion criteria

The UI pass is complete when:

1. Every scenario above is marked Pass, Fail, Blocked, or Not exposed in UI, with no silent omissions.
2. All successful create/update/workflow actions remain correct after refresh and are linked to the intended parent records.
3. Financial postings balance; inventory movements reconcile; projected/report figures match their stated formulas and documented limitations.
4. Invalid, duplicate, cross-tenant, out-of-period, and unauthorized actions show clear errors and leave source records unchanged.
5. Screenshots and record identifiers are attached to a QA run log, and failures are filed with reproduction steps.

Do not mark an integration or external service as UI-verified if it was not configured in the test environment. Mark the relevant scenario Blocked and include the missing setup.

## 7. Known UI-only limits and interpretation notes

- A browser-only pass verifies user-visible behavior; it does not prove database constraints, transaction isolation, or concurrency behavior. For example, duplicate salary slips should be checked by repeated UI attempts, but simultaneous requests still need automated/API concurrency coverage.
- Some workflows depend on tenant settings, tax configuration, chart-of-accounts mappings, inventory setup, external payment/provider credentials, WhatsApp pairing, or valid FX rates. Configure these first and use sandbox credentials. FX rate creation and some deep-HR reference selection (the current workbench asks for UUIDs) are not fully surfaced as UI workflows; provision/copy those references through approved admin tools and mark those setup steps as not exposed in UI.
- The enterprise report workbench is a generic selector/table view. A report returning rows is not by itself evidence the calculation is correct; compare to a small source dataset with hand-calculated expected values.
- Phase F documents known approximations: supplier sales attribution is supplier sourcing by item; gross profit may use current standard rate when historical COGS is unavailable; the procurement tracker can link by item rather than a unique request line; stock ageing is a receipt chronology estimate; and purchase-order overdue status uses a 30-day proxy.
- Run destructive workflows (returns, payroll posting, close, manufacturing backflush, landed costs, FX revaluation) only in a disposable tenant with known starting balances.

## 8. Related completion reports

Use these reports for architecture details, endpoint behavior, and implementation limitations while executing this guide:

- `phase1_billing_subscriptions_pos_completion_report.md`
- `phase2_procurement_buying_completion_report.md`
- `phase3_stock_logistics_completion_report.md`
- `phase4_hrms_payroll_completion_report.md`
- `phase5_manufacturing_mes_completion_report.md`
- `phase6_crm_support_completion_report.md`
- `phase7_assets_quality_maintenance_completion_report.md`
- `phase8_subcontracting_reports_completion_report.md`
- `phase_a_shared_foundation_entities_completion_report.md`
- `phase_b_buying_selling_enhancements_completion_report.md`
- `phase_c_hr_deep_workflows_completion_report.md`
- `phase_d_payroll_assets_enhancements_completion_report.md`
- `phase_e_projects_support_refinements_completion_report.md`
- `phase_f_enterprise_reports_completion_report.md`
