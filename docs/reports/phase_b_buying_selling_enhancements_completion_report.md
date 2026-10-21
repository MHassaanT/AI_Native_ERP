# Phase B Completion Report: Buying & Selling Enhancements

**Plan:** `docs/erpnext_modules_implementation_plan.md`  
**Phase:** B — Buying & Selling Enhancements (B1–B10)  
**Status:** Source implementation complete; database and end-to-end runtime verification remain outstanding  
**Date:** October 21, 2026

## Summary

Phase B adds tenant-scoped supplier grouping, purchase tax templates, shipping rules, manufacturer records, pricing and promotion rules, sales partner/team tracking, loyalty programs and point entries, Delivery Note access, and stock/buying settings. The work includes migration `033_buying_selling_enhancements`, API operations in the existing master-data and commercial/AP routes, management screens, and contextual shortcuts from Procurement, Commercial, Inventory, and POS.

The implementation provides configurable records and calculation/workflow endpoints. Several of these capabilities are currently explicit previews or standalone operations; they are not yet automatically applied to all sales, POS, stock, and accounting document flows. Those integration limits are detailed below.

## Completion by plan item

| Item | Implementation |
|---|---|
| **B1 Supplier Group hierarchy** | Added tenant-unique `SupplierGroup` with parent, group/leaf, active, and nested-set fields. Create/update rebuilds `lft`/`rgt`; invalid parent references and cycles are rejected. Supplier creation accepts an active tenant-owned group. |
| **B2 Purchase tax template** | Added `PurchaseTaxesAndChargesTemplate` and ordered detail rows with charge type, account head, description, rate, checks, and tenant scoping. `POST /master-data/purchase-taxes/calculate` calculates Actual, On Net Total, and On Previous Row Amount rows using `Decimal`. |
| **B3 Shipping rules** | Added destination-aware, priority-ordered `ShippingRule` and value/weight/quantity conditions. `POST /master-data/shipping/quote` returns the first applicable rule and computes fixed, per-unit, or percentage charges. |
| **B4 Item Manufacturer** | Added tenant-scoped manufacturer records linked to Items, including manufacturer part number, default flag, and active flag. Exposed through master-data CRUD. |
| **B5 Promotions and pricing** | Added `PromotionalScheme` and `PricingRule`, including validity windows, item/item-group applicability, minimum quantity, priority, discount bounds, and Buy X Get Y quantities. Evaluation endpoints return a matching price/discount or free quantity. |
| **B6 Sales partners and team** | Added tenant-scoped `SalesPartner` and document-linked `SalesTeam` assignments with bounded commission/contribution percentages. API rejects contribution totals above 100% and provides assignments by document. |
| **B7 Loyalty** | Added `LoyaltyProgram` and immutable earn/redeem `LoyaltyPointEntry` records. APIs calculate balance, earn points from an eligible amount, and redeem against available balance. Invoice-based earns are idempotent; duplicate invoice redemptions are rejected. |
| **B8 Delivery Note UI/workflow** | Added a Delivery Note listing page with customer, item count, invoice state, and action to create an invoice using the existing delivery-to-invoice workflow. Added entry points from Commercial and Inventory. |
| **B9 Stock settings** | Added tenant settings for automatic material-request preference, negative-stock preference, valuation method, default warehouse, and stock UOM, surfaced on the settings page. |
| **B10 Buying settings** | Added over-receipt and over-billing tolerances, backflush basis, and default buying/selling price-list values. Goods Receipt checks cumulative received quantity per PO line; supplier invoice creation checks subtotal against the PO tolerance. Settings validation checks tolerance ranges, enumerated values, and tenant-owned warehouse/active price-list context. |

## Data model and migration

Added `src/erp/db/models/phase_b.py` with 12 tables: `supplier_groups`, `purchase_taxes_and_charges_templates`, `purchase_taxes_and_charges_template_details`, `shipping_rules`, `shipping_rule_conditions`, `item_manufacturers`, `promotional_schemes`, `pricing_rules`, `sales_partners`, `sales_teams`, `loyalty_programs`, and `loyalty_point_entries`. Phase B fields were added to `TenantSettings`; `Supplier` gained an optional `supplier_group_id` relation. Models are registered from `src/erp/db/models/__init__.py`.

Migration `033_buying_selling_enhancements.py` follows Phase A migration `032_shared_master_entities.py`. It creates the tables, tenant/lookup indexes, uniqueness/check constraints, supplier group FK, and settings columns. Model and migration constraints were compared during final review; a missing migration check for purchase-tax charge types was added.

## API and workflow details

The existing `/master-data` API now exposes CRUD for the Phase B resources. The generic CRUD layer performs tenant scoping, payload field validation, UUID/date/numeric conversion, and tenant ownership checks for connected records. Dedicated operations add behavior that generic CRUD alone would not provide:

- Supplier Group nested-set rebuild and hierarchy validation.
- Purchase tax calculation in row order; “previous row” is based on the immediately preceding row's calculated amount.
- Shipping quote matching by destination and configured condition range.
- Pricing evaluation using the applicable Item Price or item standard rate, then the highest-priority applicable rule.
- Promotion evaluation for discounts or Buy X Get Y quantities.
- Loyalty balance and append-only earn/redeem entries, with customer-row locking around mutations.
- Operational settings retrieval/update, including validation of tenant-owned defaults.

The AP routes validate Supplier Group ownership and enforce configured PO receipt/billing tolerances. The Commercial routes list Delivery Notes and reuse the existing invoice-from-delivery action. No duplicate Delivery Note entity or replacement fulfillment workflow was introduced.

## Frontend

- Extended `/master-data` with CRUD forms and reference selectors for Phase B entities.
- Added `/operational-settings` for stock and buying preferences/tolerances.
- Added `/delivery-notes` for listing and invoicing eligible deliveries.
- Added `/loyalty` for selecting a customer/program, viewing balance, and recording earns/redemptions.
- Added contextual shortcuts in Procurement, Commercial, Inventory, and POS, plus sidebar links to dedicated screens.
- Added Supplier Group selection to supplier creation in Accounts Payable.

The management links lead to the shared master-data workspace rather than selecting a specific resource tab automatically. The new screens are separate routes, with contextual links from the existing module pages.

## Frictions, design choices, and known limits

1. **Shared master-data API expansion.** The master-data router already handled Phase A resources, so Phase B resources were added to its common tenant-scoped CRUD registry instead of creating overlapping route families. Calculations and workflows have dedicated endpoints.
2. **Hierarchy maintenance.** Supplier groups use nested-set bounds in addition to parent IDs. The API rebuilds the tenant's tree after changes and rejects cycles; this is simple and correct for current catalog sizes but rewrites all bounds for that tenant on each hierarchy change.
3. **Document integrations remain selective.** Purchase receipt and invoice tolerances are enforced when those documents reference a PO. The over-billing check currently compares invoice subtotal with PO subtotal, rather than matching invoice quantities and values line by line. Receipts do validate cumulatively by PO item line.
4. **Settings are not all behavior switches yet.** `allow_negative_stock`, `auto_material_request`, and `backflush_based_on` are persisted and configurable, but are not yet enforced across every stock movement/replenishment/manufacturing path. The settings UI therefore describes configured intent; these switches need workflow-wide integration before being treated as operational controls.
5. **Pricing and shipping are callable calculations.** Pricing, promotions, purchase taxes, and shipping have explicit evaluation/preview endpoints, but are not automatically applied to every Commercial/POS/PO document submission. Loyalty is similarly managed through its own workflow screen and API rather than being automatically earned/redeemed during POS invoice posting.
6. **Commission tracking is attribution only.** Sales Team assignments and effective commission rates can be recorded and retrieved. Commission accrual, settlement, and accounting postings are outside this phase implementation.
7. **Environment database dependency.** As documented in Phase A, SQLAlchemy is unavailable in this checkout's active Python environment. Source syntax and frontend typing can be checked, but ORM metadata import, Alembic upgrade/downgrade, and PostgreSQL-backed behavior cannot be verified here.

## Validation performed

- `python3 -m py_compile` over changed Phase B models, routes, and migration — **passed**.
- `frontend/node_modules/.bin/tsc --noEmit -p frontend/tsconfig.json` — **passed**.
- `git diff --check` — **passed**.
- Alembic migration upgrade/downgrade and database-backed API/transaction checks — **not run**; SQLAlchemy/PostgreSQL runtime is unavailable in this checkout.
- Pytest suite and frontend production build — **not run**.

## Files added or updated

- Added `src/erp/db/models/phase_b.py` and updated model registration, `onboarding.py`, and `purchasing.py`.
- Added `alembic/versions/033_buying_selling_enhancements.py`.
- Added `src/erp/api/routes/master_data.py`; updated AP and Commercial routes.
- Updated `frontend/src/app/master-data/page.tsx`, `accounts-payable/page.tsx`, sidebar, and API client.
- Added `frontend/src/app/operational-settings/page.tsx`, `delivery-notes/page.tsx`, `loyalty/page.tsx`, and `frontend/src/components/phase-b-shortcuts.tsx`.
- Updated Procurement, Commercial, Inventory, and POS pages with contextual Phase B navigation.

## Remaining verification before production use

Apply and downgrade the migration on PostgreSQL, then exercise tenant isolation, Supplier Group moves/deletes, tax row ordering, overlapping shipping/pricing rules, simultaneous loyalty redemptions, receipt accumulation across multiple GRNs, and invoice tolerance boundaries. Before enabling the corresponding controls in production, integrate negative-stock and automatic material request settings into their complete workflows, apply pricing/tax/shipping results during document submission, and connect loyalty earn/redeem to POS invoice posting.
