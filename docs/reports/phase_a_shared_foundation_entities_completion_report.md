# Phase A Completion Report: Shared Foundation Entities

**Plan:** `docs/erpnext_modules_implementation_plan.md`  
**Phase:** A — Shared Foundation Entities (first phase in the plan)  
**Status:** Implemented; database/runtime verification remains outstanding  
**Date:** October 21, 2026

## Summary

Phase A adds the cross-module master data layer called for by the implementation plan. It introduces 12 tenant-scoped tables for the 10 planned entity groups, a shared CRUD API, a master-data management page, starter records, document-number allocation, and an Item Group link on inventory items.

Item Group hierarchy is stored using `parent_id`, `lft`, and `rgt`. Item prices and conversion factors use fixed precision numeric columns. Master data API queries are scoped to the authenticated tenant, and the API checks tenant ownership for UUID references between the new entities and existing Items. Contact and Address use the plan's polymorphic `link_doctype` / `link_name` pattern.

## Delivered

### Data model and migration

Added `src/erp/db/models/shared_master.py` and registered the new models in `src/erp/db/models/__init__.py`:

- **ItemGroup** — tenant-unique group names, parent hierarchy, nested-set bounds, group/leaf and active flags.
- **PriceList** — tenant-unique list name, currency, buying/selling context, active flag.
- **ItemPrice** — item and price-list references, `NUMERIC(18,4)` rate, currency, effective dates, nonnegative-rate constraint, and a uniqueness key for the tenant/item/list/effective date.
- **Contact** — name, email, phone, designation, primary/active flags, and dynamic link fields.
- **Address** — billing, shipping, office, and other address types; address fields; dynamic link and primary flag.
- **UOM** — tenant-unique unit names and abbreviations.
- **UOMConversion** — directional conversion factor stored as `NUMERIC(18,8)`, optional item-specific conversion, positive-factor and distinct-unit constraints.
- **NamingSeries** — tenant/document/prefix uniqueness, sequence counter, width, and active flag.
- **TermsAndConditionsTemplate** — reusable terms, name, applicability (`BUYING`, `SELLING`, `BOTH`), and active flag.
- **ProductBundle** and **ProductBundleItem** — bundle SKU and component items, with positive component quantities.
- **IssueType** — tenant-unique support issue type and description.

Added Alembic revision `032_shared_master_entities.py`, following revision `031_stock_ledger_serial_number`. It creates the 12 tables, tenant and lookup indexes, constraints and foreign keys, and the nullable `items.item_group_id` column. The downgrade removes the inventory link before dropping the master tables.

### Inventory integration

`Item` now has a nullable `item_group_id` relation. The inventory create and update request schemas accept the group identifier. Create/update reject a group that is missing, inactive, or owned by another tenant. The inventory listing returns the group ID and name. The inventory create form includes an Item Group selector, and starter leaf groups can be assigned to items.

### API

Added the `/api/v1/master-data` router, registered it in the FastAPI app, and added frontend API client methods. It provides tenant-scoped list, create, get, update, and delete operations for all 12 resources. It rejects unknown or protected payload fields and checks that referenced records belong to the request tenant.

The Item Group endpoints rebuild nested-set `lft`/`rgt` values after hierarchy changes and reject cycles and invalid parent types. Item Price endpoints reject negative rates via the database constraint and reject an effective end date earlier than its start. Naming Series includes an atomic `POST /master-data/naming-series/{id}/next-number` operation, which increments the stored counter and returns the formatted number.

`POST /api/v1/master-data/defaults` is idempotent and seeds common UOMs, a root Item Group with Products / Raw Materials / Services leaf groups, Standard Buying and Standard Selling price lists in the tenant's currency, and common Issue Types. Existing records are preserved.

### Frontend

Added `/master-data`, linked from the sidebar. It provides a resource selector and generic create/edit/delete forms for the Phase A resources, uses reference selectors where records are connected, offers a one-click starter-data action, and exposes a “Reserve next” action for Naming Series. Existing Inventory item creation now supports group assignment.

## Plan deliverables

| Deliverable | Result |
|---|---|
| Alembic migration for the Phase A tables | Implemented: 12 new tables plus `items.item_group_id` |
| CRUD routes | Implemented for all 12 resource tables |
| Frontend management | Implemented at `/master-data`; inventory Item Group selector added |
| Seed data | Implemented as an idempotent tenant-scoped API action |

## Frictions and decisions

1. **Shared entity work crossed into the existing Item workflow.** Creating Item Groups without connecting them to Items would leave the original flat item categorization gap in place. The phase therefore also adds an optional Item foreign key and updates the inventory create/list/update path.
2. **Item Group hierarchy needs derived state.** `lft` and `rgt` cannot be maintained by ordinary CRUD. The API rebuilds nested-set bounds per tenant after group changes and rejects cyclic trees. This is straightforward for the current catalog scale, but a very large hierarchy may warrant a more targeted tree update.
3. **Contact and Address links are polymorphic.** The agreed dynamic link fields avoid hard-coding Supplier/Customer/Employee foreign keys. Since these fields are polymorphic, the database cannot enforce the target's existence as a normal foreign key; API validation of `link_doctype` / `link_name` targets can be added when the supported party types and canonical ID formats are formalized.
4. **Naming Series needs concurrency-safe behavior.** The sequence allocator uses one SQL `UPDATE ... RETURNING` instead of read-then-write so concurrent requests do not intentionally reserve the same counter value.
5. **Environment dependency gap.** Python syntax compilation succeeded, but importing ORM metadata failed because SQLAlchemy is not installed in this checkout (`ModuleNotFoundError`). As a result, the migration was authored but could not be applied here, and database-backed API behavior was not exercised.
6. **Frontend typing caught a dynamic lookup issue.** The first TypeScript check reported two possible undefined index keys in the reference selector. The keys now have explicit fallbacks, and the final TypeScript check passes.

## Validation performed

- `python3 -m py_compile` over the changed Python models, routes, app registration, and Alembic revision — **passed**.
- `frontend/node_modules/.bin/tsc --noEmit -p frontend/tsconfig.json` — **passed**.
- `git diff --check` — **passed**.
- ORM import / metadata introspection — **not available** because SQLAlchemy is missing.
- Alembic upgrade and database CRUD/multi-tenant runtime checks — **not run**; there is no usable SQLAlchemy runtime in the checkout.
- Pytest suite and frontend production build — **not run**.

## Files added or updated

- Added `src/erp/db/models/shared_master.py`
- Updated `src/erp/db/models/__init__.py`
- Updated `src/erp/db/models/inventory.py`
- Added `src/erp/api/routes/master_data.py`
- Updated `src/erp/api/routes/inventory_rop.py`
- Registered the router in `src/erp/api/routes/__init__.py` and `src/erp/api/app.py`
- Added `alembic/versions/032_shared_master_entities.py`
- Added `frontend/src/app/master-data/page.tsx`
- Updated `frontend/src/lib/api.ts`, `frontend/src/components/sidebar.tsx`, and `frontend/src/app/inventory/page.tsx`

## Remaining verification before production use

The phase implementation is complete in source, but the migration still needs to be applied and the CRUD flows exercised against a configured PostgreSQL environment. In particular, validate migration upgrade/downgrade, multi-tenant reference rejection, hierarchy edits, Item Price effective dates, and concurrent Naming Series allocation.
