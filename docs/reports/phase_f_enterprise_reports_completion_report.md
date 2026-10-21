# Phase F: Enterprise Reports Sprint — Completion Report

**Status:** Implemented 26 report endpoints, a dedicated report workbench, and report query indexes.
**Date:** 2026-10-21
**Plan reference:** `docs/erpnext_modules_implementation_plan.md`, Phase F (F1–F26)

## What changed

- Added 26 tenant-scoped `GET /api/v1/reports/enterprise/{report-name}` endpoints in `src/erp/api/routes/reports.py`. Each accepts optional `from_date`, `to_date`, and `as_of_date`; applicable HR views also accept `month` or `fiscal_year`.
- Added SQL-backed calculations in `src/erp/workflows/reports/enterprise_reports_service.py`. Financial and stock analysis uses grouped SQL, conditional sums, and correlated subqueries; leave balances are computed in one report query instead of the existing HR endpoint's per-allocation query loop.
- Added a selectable 26-report workbench at `/reports/enterprise`, with date filters, summary metrics, and a tabular renderer for row-based reports. Added the route to the application sidebar.
- Added migration `037_enterprise_report_indexes.py`, which creates tenant/date indexes for invoice, order, quotation, and delivery reports plus a tenant/assignee/status index for support performance reports.

## Report coverage and calculation notes

| ID | Endpoint | Implemented output and calculation |
|---|---|---|
| F1 | `/customer-ledger-summary` | Per-customer invoice count, total invoiced, paid invoices, and estimated open amount. |
| F2 | `/supplier-ledger-summary` | Per-supplier invoice count, total invoiced, posted/matched invoices, and estimated open amount. |
| F3 | `/gross-profit-analysis` | Invoice revenue and estimated cost/profit by item and customer. Uses linked delivery-note stock outgoing rates when present; falls back to current standard item rate. Response marks the estimate. |
| F4 | `/sales-invoice-trends` | Monthly invoice counts and totals grouped by status. |
| F5 | `/purchase-invoice-trends` | Monthly supplier invoice counts and totals grouped by match status. |
| F6 | `/purchase-analytics` | Purchase order quantities and amounts by supplier and item for the selected order-date period. |
| F7 | `/purchase-order-analytics` | Purchase order details grouped in a filterable list with status and an overdue flag. The overdue rule is an open order more than 30 days old. |
| F8 | `/supplier-wise-sales-analytics` | Supplier/item sourcing quantities and purchase totals. The response explicitly identifies that this is sourcing context, since the schema does not connect suppliers to sales revenue. |
| F9 | `/procurement-tracker` | Material request quantity and ordered quantity alongside matching item purchase orders and goods receipts/accepted quantities. See linkage constraint below. |
| F10 | `/items-to-be-requested` | Active items whose non-quarantined available quantity is below reorder level, with estimated shortage. |
| F11 | `/sales-analytics` | Invoice-line quantity and revenue by customer and item; territory is derived from an assigned sales partner, otherwise “Unassigned.” |
| F12 | `/sales-order-analysis` | Per-order ordered/shipped quantities and invoiced amount, with pending delivery and billing calculations. Cancelled notes/invoices are excluded. |
| F13 | `/quotation-trends` | Monthly quotation count and amount by quotation status. |
| F14 | `/sales-order-trends` | Monthly sales order count and amount by order status. |
| F15 | `/inactive-customers` | Active customer directory with last non-cancelled invoice date and elapsed days. Customers without sales appear first with a null last-sale date. |
| F16 | `/stock-projected-quantity` | Current on-hand less reservations and open sales demand plus open purchase supply, by active item. |
| F17 | `/stock-ageing` | Positive stock-ledger receipt chronology, incoming rates, current item quantity, and age in days. This is a FIFO chronology estimate, not exact remaining FIFO layers. |
| F18 | `/stock-analytics` | On-hand quantity, reserved quantity, and stock value by item/category using stock-level valuation rates. |
| F19 | `/delivery-note-trends` | Monthly delivery-note counts by status. |
| F20 | `/item-shortage-report` | Items below reorder level, with on-hand, reserved, reorder, and shortage quantities. Shares the same shortage calculation as F10. |
| F21 | `/hr-analytics` | Headcount grouped by employee status and 12-month separation count/rate. |
| F22 | `/leave-balance-summary` | Allocated plus carry-forward leave, approved leave used, and remaining balance by employee and leave type for the requested fiscal year. |
| F23 | `/employee-birthdays` | Active employees with birthdays in the requested month, ordered by day. |
| F24 | `/recruitment-funnel` | Open roles and application/interview counts grouped by status/outcome. |
| F25 | `/support-sla-compliance` | Ticket counts, compliant/breached totals, and compliance percentage by priority for the selected creation-date range. |
| F26 | `/support-agent-performance` | Tickets, resolved count, SLA breaches, average first-response hours, and average resolution hours by assignee. |

The report UI calls these endpoints directly and displays scalar summary values plus tabular rows. Existing `/reports` financial statements, aging, stock operations, and consolidation remain available through their current page.

## Frictions and data limitations

Several reports required explicit definitions because the current schema does not capture the exact ERP facts implied by the plan:

1. **Customer and supplier ledgers are invoice summaries, not full accounting ledgers.** The underlying customer/supplier invoice models do not expose payment allocations or a settled amount. “Settled or posted” and “open balance estimate” are based on document statuses; supplier `MATCHED` is not proof of payment. These figures must not be treated as reconciled AR/AP balances.
2. **Gross profit is estimated.** Invoice lines do not persist historical COGS. Linked delivery-note outgoing stock rates provide the best available historical proxy; current `standard_rate` is the fallback and can differ from actual FIFO/valuation cost.
3. **Territory is not a customer attribute.** F11 derives territory only from a sales partner assigned to the sales invoice. Unassigned invoices show “Unassigned”; customer-level territory segmentation is unavailable.
4. **Supplier-wise sales attribution is not modeled.** No supplier-to-sale relationship exists. F8 therefore reports supplier purchase sourcing activity by item and includes this limitation in its response/UI label.
5. **Procurement requests lack an explicit request-to-PO line link.** F9 associates requests and downstream records by item, so it is a useful tracker but can show multiple POs/receipts for the same item and tenant. It does not claim a unique MR→PO lineage.
6. **Purchase orders have no promised receipt date.** F7 uses a visible 30-day age threshold for open orders as an overdue proxy. A contractual due date should replace this heuristic when the model captures one.
7. **Exact FIFO ageing layers are not persisted.** F17 reports receipt chronology and current item quantity, but cannot calculate remaining quantity by original receipt layer after consumption. The response labels the approximation.
8. **Agent names are not joined.** Support tickets store `assigned_to_id` without an enforced employee/user foreign key, so F26 groups by assignee ID rather than displaying a guaranteed staff name.

The existing support router also already contains SLA/overview analytics, and HR already contains several report routes. Phase F adds a uniform report catalog endpoint for each planned item and reuses those domain facts/calculations where appropriate rather than adding duplicate storage models.

## Query and migration work

The report service applies tenant filters to participating business tables, groups totals in SQL, uses correlated aggregates for sales-order fulfillment, and computes leave balances without a per-row query loop. Migration 037 adds indexes for the date filters used by the new invoice/order/quotation/delivery reports and the support assignee/status grouping. It follows migration 036.

## Verification and remaining constraints

- `python3 -m py_compile` succeeded for the new report service, route module, and migration.
- `git diff --check` succeeded for the Phase F files.
- Frontend `tsc --noEmit -p frontend/tsconfig.json` succeeded.
- Runtime route import and database-backed verification were unavailable in this workspace because the Python environment lacks FastAPI and the application dependencies. No test suite was run.
- The data limitations above are material: the ledger, gross-profit, supplier-sales, procurement-lineage, FIFO-ageing, and overdue outputs are summaries/proxies until the underlying source fields and relationships are modeled.
