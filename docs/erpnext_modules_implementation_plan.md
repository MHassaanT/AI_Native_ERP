# ERPNext Modules Implementation Plan for AI Native ERP

**Version:** 1.0.0
**Date:** October 21, 2026
**Author:** AI Agent (Pair Programming with Hassaan Tahir)
**Source Reference:** [`erpnext_modules_outline.md`](file:///home/hassaan/Desktop/Projects/AI_Native_ERP/rebuild/docs/erpnext_modules_outline.md)

---

## Executive Summary

This document provides a comprehensive, feature-by-feature gap analysis between the ERPNext modules outlined in `erpnext_modules_outline.md` and what is currently implemented in the AI Native ERP codebase (`rebuild/`). It then presents a prioritized, phased implementation plan to achieve **complete functional parity** for all outlined ERPNext modules.

### Key Finding

The AI Native ERP platform has already completed an extensive **8-Phase ERPNext Parity Sprint** (documented in [`rebuild/docs/reports/`](file:///home/hassaan/Desktop/Projects/AI_Native_ERP/rebuild/docs/reports/)). The majority of outlined modules have backend models, API routes, business logic services, and frontend pages already in place. However, several **specific sub-features, dedicated UI pages, dedicated reports, and ERPNext-native entities** from the outline are either:

1. **Missing entirely** — not yet modeled or exposed
2. **Partially implemented** — backend exists but no dedicated frontend, or vice versa
3. **Merged into adjacent modules** — functionality exists but is not surfaced as its own standalone ERPNext-equivalent workflow

This plan identifies every gap and provides concrete implementation actions.

---

## Tech Stack Reference

| Layer | Technology |
|---|---|
| **Backend** | Python 3.11+, FastAPI, SQLAlchemy 2.0, PostgreSQL 16, Alembic |
| **Frontend** | Next.js 14 (App Router), React 18, TypeScript, Tailwind CSS |
| **AI/ML** | BAML (Boundary AI Markup Language), Gemini, OR-Tools CP-SAT |
| **Auth** | JWT, Row-Level Security, Multi-Tenancy |
| **Events** | Transactional Outbox, Kafka/Redpanda |
| **State** | Native React state (no Redux/Zustand) |
| **API Client** | Custom `fetchWithTenant()` in [`src/lib/api.ts`](file:///home/hassaan/Desktop/Projects/AI_Native_ERP/rebuild/frontend/src/lib/api.ts) |

### Codebase Conventions (for all new work)

- **Backend Models:** Add to [`src/erp/db/models/`](file:///home/hassaan/Desktop/Projects/AI_Native_ERP/rebuild/src/erp/db/models/) as SQLAlchemy ORM classes inheriting `Base`, `TenantMixin`, `TimestampMixin`
- **API Routes:** Add to [`src/erp/api/routes/`](file:///home/hassaan/Desktop/Projects/AI_Native_ERP/rebuild/src/erp/api/routes/) as FastAPI routers, register in [`__init__.py`](file:///home/hassaan/Desktop/Projects/AI_Native_ERP/rebuild/src/erp/api/routes/__init__.py) and [`app.py`](file:///home/hassaan/Desktop/Projects/AI_Native_ERP/rebuild/src/erp/api/app.py)
- **Business Logic:** Add to [`src/erp/workflows/`](file:///home/hassaan/Desktop/Projects/AI_Native_ERP/rebuild/src/erp/workflows/) in domain-specific subpackages
- **Frontend Pages:** Add to [`frontend/src/app/<module>/page.tsx`](file:///home/hassaan/Desktop/Projects/AI_Native_ERP/rebuild/frontend/src/app/) with `"use client"` directive, register in Sidebar nav groups
- **Migrations:** Generate via `alembic revision --autogenerate`
- **Financial Math:** Use `Decimal` (`NUMERIC(18,4)`) exclusively — no floats in monetary pathways
- **Double-Entry Invariant:** All ledger mutations must satisfy `SUM(Dr) == SUM(Cr)`

---

## Module-by-Module Gap Analysis & Implementation Plan

---

## Module 1: Accounting

### 1.1 Payables

| ERPNext Feature | Current Status | Gap |
|---|---|---|
| **Purchase Invoice** (Purchase Details, Supplier Invoice, Items List, Taxes & Charges, Totals) | ✅ **IMPLEMENTED** — `SupplierInvoice`, `SupplierInvoiceItem` models in [`purchasing.py`](file:///home/hassaan/Desktop/Projects/AI_Native_ERP/rebuild/src/erp/db/models/purchasing.py); AP routes in [`ap.py`](file:///home/hassaan/Desktop/Projects/AI_Native_ERP/rebuild/src/erp/api/routes/ap.py); 3-way matching engine; frontend at [`/accounts-payable`](file:///home/hassaan/Desktop/Projects/AI_Native_ERP/rebuild/frontend/src/app/accounts-payable/page.tsx) | **MINOR** — No standalone "Purchase Invoice" page; it is merged into the AP hub. Consider adding a dedicated tab or alias. |
| **Account Payables** (Aging, Balances) | ✅ **IMPLEMENTED** — AP Aging report (0-30, 31-60, 61-90, 91-120, 120+ day buckets) in [`/reports`](file:///home/hassaan/Desktop/Projects/AI_Native_ERP/rebuild/frontend/src/app/reports/page.tsx) `aging` tab | None |
| **Suppliers** | ✅ **IMPLEMENTED** — `Supplier` model in [`purchasing.py`](file:///home/hassaan/Desktop/Projects/AI_Native_ERP/rebuild/src/erp/db/models/purchasing.py); CRUD via procurement routes; Supplier Scorecards (OTIF, Quality, Price) | **MINOR** — No dedicated standalone Supplier master page; embedded within `/procurement` scorecards tab. Consider a direct `/suppliers` page for quick access. |

### 1.2 Receivables

| ERPNext Feature | Current Status | Gap |
|---|---|---|
| **Sales Invoice** | ✅ **IMPLEMENTED** — `SalesInvoice`, `SalesInvoiceItem` models in [`sales.py`](file:///home/hassaan/Desktop/Projects/AI_Native_ERP/rebuild/src/erp/db/models/sales.py); POS invoices at [`/pos`](file:///home/hassaan/Desktop/Projects/AI_Native_ERP/rebuild/frontend/src/app/pos/page.tsx); billing at [`/billing`](file:///home/hassaan/Desktop/Projects/AI_Native_ERP/rebuild/frontend/src/app/billing/page.tsx) | None |
| **Account Receivables** (Aging) | ✅ **IMPLEMENTED** — AR Aging report in `/reports` aging tab | None |
| **Customers** | ✅ **IMPLEMENTED** — `Customer` model in [`sales.py`](file:///home/hassaan/Desktop/Projects/AI_Native_ERP/rebuild/src/erp/db/models/sales.py); managed via `/commercial` page | **MINOR** — No standalone `/customers` page; embedded in Commercial module |

### 1.3 Financial Reports

| ERPNext Feature | Current Status | Gap |
|---|---|---|
| General Ledger | ✅ IMPLEMENTED | None — dedicated [`/ledger`](file:///home/hassaan/Desktop/Projects/AI_Native_ERP/rebuild/frontend/src/app/ledger/page.tsx) page |
| Customer Ledger Summary | ⚠️ **PARTIAL** | **GAP** — No dedicated customer-level ledger drill-down. AR Aging provides bucket view but not a per-customer transaction journal. |
| Supplier Ledger Summary | ⚠️ **PARTIAL** | **GAP** — Same as above for suppliers. AP Aging exists but no per-supplier transaction journal. |
| Profit and Loss Statement | ✅ IMPLEMENTED | None — `/reports` `profit-loss` tab |
| Balance Sheet | ✅ IMPLEMENTED | None — `/reports` `balance-sheet` tab |
| Consolidated Financial Statement | ✅ IMPLEMENTED | None — `/reports` `consolidation` tab with multi-company elimination entries |
| Cash Flow | ✅ IMPLEMENTED | None — `/reports` `cash-flow` tab |
| Gross Profit / Profitability | ⚠️ **PARTIAL** | **GAP** — P&L shows Gross Profit line but no dedicated Gross Profit Analysis by Item/Customer/Territory breakdown |
| Sales Invoice Trends | ❌ **MISSING** | **GAP** — No time-series trend chart for sales invoices (monthly/quarterly/yearly) |
| Purchase Invoice Trends | ❌ **MISSING** | **GAP** — No time-series trend chart for purchase invoices |

> [!IMPORTANT]
> **Accounting Actions Required:**
> 1. Create **Customer Ledger Summary** report endpoint & frontend tab
> 2. Create **Supplier Ledger Summary** report endpoint & frontend tab
> 3. Create **Gross Profit Analysis** report (by item, customer, territory)
> 4. Create **Sales Invoice Trends** report (monthly/quarterly pivot chart)
> 5. Create **Purchase Invoice Trends** report (monthly/quarterly pivot chart)
> 6. *(Optional UX)* Create standalone `/sales-invoices` and `/purchase-invoices` list pages for direct ERPNext parity

---

## Module 2: Buying

### 2.1 Core Buying Documents

| ERPNext Feature | Current Status | Gap |
|---|---|---|
| **Material Request** (Details, Terms, External Info) | ✅ IMPLEMENTED — `MaterialRequest`, `MaterialRequestItem` models; procurement routes; `/procurement` `requisitions` tab | None |
| **Purchase Order** (Details, Items, Taxes, Totals, Address/Contact, Terms, More Info) | ✅ IMPLEMENTED — `PurchaseOrder`, `PurchaseOrderItem` models; full lifecycle with 3-way matching | **MINOR** — No explicit Address/Contact management on PO. Linked through Supplier master. |
| **Purchase Invoice** | ✅ IMPLEMENTED (as Supplier Invoice) | None |
| **Request for Quotation** | ✅ IMPLEMENTED — `RequestForQuotation`, `RFQItem`, `RFQSupplier` models; `/procurement` `sourcing` tab with comparison matrix | None |
| **Supplier Quotation** | ✅ IMPLEMENTED — `SupplierQuotation`, `SupplierQuotationItem` models; side-by-side vendor bid comparison | None |

### 2.2 Items & Pricing

| ERPNext Feature | Current Status | Gap |
|---|---|---|
| **Item** | ✅ IMPLEMENTED — `Item` model with variants, attributes, serial/batch tracking | None |
| **Item Price** | ⚠️ **PARTIAL** — Items have `standard_rate` but no dedicated multi-price-list `ItemPrice` entity | **GAP** — ERPNext supports multiple price lists per item (buying vs selling, currency-specific). Need `ItemPrice` model. |
| **Price List** | ❌ **MISSING** | **GAP** — No `PriceList` entity for grouping prices by context (Buying, Selling, region, currency) |
| **Product Bundle** | ❌ **MISSING** | **GAP** — No `ProductBundle` entity for selling grouped items as a single SKU. BOMs exist but are manufacturing-oriented, not sales-oriented. |
| **Item Group** | ❌ **MISSING** | **GAP** — Items have no hierarchical group/category classification beyond flat attributes. ERPNext has `ItemGroup` with tree structure. |
| **Promotional Scheme** | ❌ **MISSING** | **GAP** — No pricing rules, discount schemes, or promotional campaigns on items |

### 2.3 Settings

| ERPNext Feature | Current Status | Gap |
|---|---|---|
| Naming Series | ⚠️ **PARTIAL** — Some models use auto-generated codes but no configurable naming series engine | **GAP** — Need a `NamingSeries` configuration model for customizable document numbering |
| Price Defaults | ❌ **MISSING** | **GAP** — No default buying/selling price list configuration |
| Transaction Settings | ⚠️ **PARTIAL** — `TenantSettings` exists but doesn't cover buying-specific toggles | **GAP** — Add buying-specific settings (over-receipt %, over-billing %, backflush settings) |
| Subcontracting Settings | ⚠️ **PARTIAL** — Subcontracting works but no dedicated settings | **MINOR** |
| Purchase Taxes & Charges Template | ❌ **MISSING** | **GAP** — Sales tax templates exist (`SalesTaxesAndChargesTemplate`) but no **purchase-side** tax template |
| Terms & Conditions Template | ❌ **MISSING** | **GAP** — No `TermsAndConditionsTemplate` model for reusable T&C blocks on POs/Quotations |

### 2.4 Supplier Management

| ERPNext Feature | Current Status | Gap |
|---|---|---|
| **Supplier** | ✅ IMPLEMENTED | None |
| **Supplier Group** | ❌ **MISSING** | **GAP** — No hierarchical `SupplierGroup` for categorization |
| **Contact** | ❌ **MISSING** | **GAP** — No standalone `Contact` entity (name, phone, email, designation) linked to suppliers/customers |
| **Address** | ❌ **MISSING** | **GAP** — No standalone `Address` entity (billing/shipping) linked to parties |

### 2.5 Reports

| ERPNext Feature | Current Status | Gap |
|---|---|---|
| Purchase Analytics | ❌ **MISSING** | **GAP** — No purchase analytics (by supplier, item group, time period) |
| Purchase Order Analytics | ⚠️ **PARTIAL** — Item-wise Purchase Register exists | **GAP** — No PO-specific analytics (pending qty, overdue, status breakdown) |
| Supplier-Wise Sales Analytics | ❌ **MISSING** | **GAP** |
| Procurement Tracker | ❌ **MISSING** | **GAP** — No unified procurement pipeline tracker (MR → RFQ → PO → GRN → Invoice) |
| Items to be Requested | ❌ **MISSING** | **GAP** — No report showing items below reorder level needing Material Requests |
| Item-wise Purchase History | ⚠️ **PARTIAL** — Item-wise Purchase Register exists in reports | **MINOR** — Needs a more detailed item-centric view |

> [!IMPORTANT]
> **Buying Actions Required:**
> 1. Create `ItemPrice` model (item, price_list, rate, currency, valid_from/to)
> 2. Create `PriceList` model (name, currency, buying/selling flag, enabled)
> 3. Create `ProductBundle` + `ProductBundleItem` models
> 4. Create `ItemGroup` model with tree hierarchy (parent_id, lft, rgt)
> 5. Create `PromotionalScheme` + `PricingRule` models
> 6. Create `NamingSeries` configurable numbering engine
> 7. Create `PurchaseTaxesAndChargesTemplate` (mirror of sales tax templates)
> 8. Create `TermsAndConditionsTemplate` model
> 9. Create `SupplierGroup` model with hierarchy
> 10. Create `Contact` model (linked to Supplier/Customer via `Dynamic Link`)
> 11. Create `Address` model (linked to Supplier/Customer with billing/shipping type)
> 12. Build 6 buying reports (Purchase Analytics, PO Analytics, Supplier-Wise, Procurement Tracker, Items to Request, Item-wise Purchase History)

---

## Module 3: Selling

### 3.1 Core Selling Documents

| ERPNext Feature | Current Status | Gap |
|---|---|---|
| **Customer** | ✅ IMPLEMENTED — `Customer` model; managed in `/commercial` | **MINOR** — No standalone customer list page |
| **Quotation** | ✅ IMPLEMENTED — `SalesQuotation` model; dynamic pricing engine in `/commercial` | None |
| **Sales Order** (Details, Items, Taxes, Totals, Terms, More Info) | ✅ IMPLEMENTED — `SalesOrder`, `SalesOrderItem` models | **MINOR** — No explicit T&C block on Sales Orders |
| **Sales Invoice** | ✅ IMPLEMENTED — via Billing/POS modules | See Accounting section |
| **Sales Partner / Rep** | ❌ **MISSING** | **GAP** — No `SalesPartner` or `SalesTeam` entity for commission tracking and partner-based selling |

### 3.2 Point of Sale (POS)

| ERPNext Feature | Current Status | Gap |
|---|---|---|
| POS Profile | ✅ IMPLEMENTED — `POSProfile` model | None |
| POS Settings | ⚠️ **PARTIAL** — Basic POS settings exist within profile | **MINOR** — No global POS settings model |
| **Loyalty Point Entry** | ❌ **MISSING** | **GAP** — No loyalty program, loyalty points, or loyalty point entry/redemption system |

### 3.3 Reports

| ERPNext Feature | Current Status | Gap |
|---|---|---|
| Sales Analytics | ❌ **MISSING** | **GAP** — No sales analytics by item group, customer, territory, time period |
| Sales Order Analysis | ❌ **MISSING** | **GAP** — No SO-specific analysis (pending delivery, pending billing, status) |
| Quotation Trends | ❌ **MISSING** | **GAP** — No quotation trend charts |
| Sales Order Trends | ❌ **MISSING** | **GAP** — No sales order trend charts |
| Inactive Customers | ❌ **MISSING** | **GAP** — No report showing customers with no transactions in N days |
| Item-wise Sales History | ⚠️ **PARTIAL** — Item-wise Sales Register exists | **MINOR** — Needs more granular item-centric breakdown |

> [!IMPORTANT]
> **Selling Actions Required:**
> 1. Create `SalesPartner` model (name, commission_rate, territory)
> 2. Create `SalesTeam` model (link table for SO/Invoice → Sales Partner with contribution %)
> 3. Create `LoyaltyProgram`, `LoyaltyPointEntry` models
> 4. Add Terms & Conditions block to Sales Order
> 5. Build 6 selling reports (Sales Analytics, SO Analysis, Quotation Trends, SO Trends, Inactive Customers, Item-wise Sales History)

---

## Module 4: Stock

### 4.1 Items Catalogue

| ERPNext Feature | Current Status | Gap |
|---|---|---|
| Item | ✅ IMPLEMENTED | None |
| Item Group | ❌ **MISSING** | **GAP** — See Buying section |
| Product Bundle | ❌ **MISSING** | **GAP** — See Buying section |
| **Shipping Rule** | ❌ **MISSING** | **GAP** — No `ShippingRule` model for automated freight calculation based on weight/value/destination |
| **Item Manufacturer** | ❌ **MISSING** | **GAP** — No `ItemManufacturer` entity linking items to their manufacturer with part numbers |

### 4.2 Transactions

| ERPNext Feature | Current Status | Gap |
|---|---|---|
| Material Request | ✅ IMPLEMENTED | None |
| Stock Entry | ✅ IMPLEMENTED — Universal entry types: MATERIAL_RECEIPT, ISSUE, TRANSFER, MANUFACTURE | None |
| Delivery Note | ✅ **IMPLEMENTED** — `DeliveryNote`, `DeliveryNoteItem` models exist in [`sales.py`](file:///home/hassaan/Desktop/Projects/AI_Native_ERP/rebuild/src/erp/db/models/sales.py); used in commercial routes for invoice creation from delivery | None |
| Purchase Receipt | ⚠️ **PARTIAL** — `GoodsReceiptNote` (GRN) serves this function | **MINOR** — Functionally equivalent. Consider aliasing in UI as "Purchase Receipt" for ERPNext users. |
| Pick List | ✅ IMPLEMENTED — `PickList`, `PickListItem` models | None |
| Delivery Trip | ✅ IMPLEMENTED — `DeliveryTrip`, `DeliveryStop` models | None |

### 4.3 Reports

| ERPNext Feature | Current Status | Gap |
|---|---|---|
| Stock Ledger | ✅ IMPLEMENTED | None |
| Stock Balance | ✅ IMPLEMENTED | None |
| Stock Projected Qty Summary | ❌ **MISSING** | **GAP** — No projected quantity report (current stock - reserved + ordered - requested) |
| Stock Summary | ⚠️ **PARTIAL** — Stock Balance covers most of this | **MINOR** |
| Stock Ageing | ❌ **MISSING** | **GAP** — No stock aging report (FIFO-based age of items in warehouse) |

### 4.4 Settings

| ERPNext Feature | Current Status | Gap |
|---|---|---|
| Stock Settings | ⚠️ **PARTIAL** — Basic warehouse defaults exist | **GAP** — No full Stock Settings (auto material request, valuation method default, allow negative stock toggle, etc.) |
| UOM | ⚠️ **PARTIAL** — Items have `stock_uom` field but no `UOM` master or `UOMConversion` model | **GAP** — Need `UOM` master table and `UOMConversion` (conversion factors between units) |

### 4.5 Additional Reports

| ERPNext Feature | Current Status | Gap |
|---|---|---|
| Stock Analytics | ❌ **MISSING** | **GAP** |
| Delivery Note Trends | ❌ **MISSING** | **GAP** |
| Purchase Order Analysis | ⚠️ **PARTIAL** — Exists in reports | **MINOR** |
| Item Shortage Report | ❌ **MISSING** | **GAP** — No report showing items where demand > supply |
| Requested Items to be Transferred | ❌ **MISSING** | **GAP** |
| Subcontracted Raw Materials to be Received/Transferred | ⚠️ **PARTIAL** — Subcontracting module tracks this internally | **MINOR** — Need a dedicated report view |

> [!IMPORTANT]
> **Stock Actions Required:**
> 1. Create `ShippingRule` + `ShippingRuleCondition` models
> 2. Create `ItemManufacturer` model
> 3. Create `UOM` master table and `UOMConversion` factor table
> 4. Create `ItemGroup` hierarchy (shared with Buying)
> 5. Add Stock Settings to TenantSettings
> 6. Build stock reports: Projected Qty, Stock Ageing, Stock Analytics, Delivery Note Trends, Item Shortage, Requested Items Transfer

---

## Module 5: Assets

| ERPNext Feature | Current Status | Gap |
|---|---|---|
| **Create Asset** | ✅ IMPLEMENTED — `Asset` model with capitalization | None |
| **Asset Listing** | ✅ IMPLEMENTED — `/assets` `registry` tab | None |
| **Location** | ✅ IMPLEMENTED — `AssetLocation` model; `/assets` `locations` tab | None |
| **Asset Maintenance Team** | ❌ **MISSING** | **GAP** — No `AssetMaintenanceTeam` or `AssetMaintenanceMember` models. Maintenance exists but without team assignment. |
| **Asset Value Adjustment** | ⚠️ **PARTIAL** — Depreciation schedules auto-post GL entries. Manual value adjustment (impairment) is not explicitly modeled. | **GAP** — Need `AssetValueAdjustment` model for recording impairment losses or revaluations outside regular depreciation |

> [!NOTE]
> **Assets Actions Required:**
> 1. Create `AssetMaintenanceTeam` + `AssetMaintenanceMember` models
> 2. Create `AssetValueAdjustment` model with GL posting for impairment
> 3. Link maintenance schedules to maintenance teams

---

## Module 6: HR

### 6.1 Recruitment

| ERPNext Feature | Current Status | Gap |
|---|---|---|
| **Staffing Plan** | ❌ **MISSING** | **GAP** — No `StaffingPlan` model for headcount planning by department/designation |
| **Job Opening** | ✅ IMPLEMENTED — `RecruitmentRole` model; `/recruitment` page | None |
| **Job Applicants** | ✅ IMPLEMENTED — `CandidateApplication` with AI screening | None |
| **Interview** | ❌ **MISSING** | **GAP** — AI generates interview invitations but no `Interview` entity for tracking actual interview sessions |
| **Interview Round** | ❌ **MISSING** | **GAP** — No `InterviewRound` model |
| **Interview Feedback** | ❌ **MISSING** | **GAP** — No `InterviewFeedback` model for structured interviewer evaluations |
| **Recruitment Analytics** | ❌ **MISSING** | **GAP** — No recruitment funnel analytics (applications → screened → interviewed → hired) |

### 6.2 Employee Lifecycle

| ERPNext Feature | Current Status | Gap |
|---|---|---|
| Employee | ✅ IMPLEMENTED — `Employee` model with full lifecycle | None |
| **Employee Grade** | ❌ **MISSING** | **GAP** — No `EmployeeGrade` model for pay band/experience level classification |
| **Employee Promotion** | ❌ **MISSING** | **GAP** — No `EmployeePromotion` model to track designation/grade changes with effective dates |
| **Employee Transfer** | ❌ **MISSING** | **GAP** — No `EmployeeTransfer` model for department/branch/company transfers |

### 6.3 Grievance

| ERPNext Feature | Current Status | Gap |
|---|---|---|
| **Grievance Type** | ❌ **MISSING** | **GAP** — No `GrievanceType` model |
| **Employee Grievance** | ❌ **MISSING** | **GAP** — No `EmployeeGrievance` model for formal complaint tracking and resolution |

### 6.4 Exit

| ERPNext Feature | Current Status | Gap |
|---|---|---|
| **Full and Final Settlement** | ❌ **MISSING** | **GAP** — Employee Separation exists (`EmployeeSeparation` + `SeparationTask`) but no `FullAndFinalStatement` model for computing final dues (salary, leave encashment, gratuity, deductions) |

### 6.5 Daily Work Summary

| ERPNext Feature | Current Status | Gap |
|---|---|---|
| **Daily Work Summary** | ❌ **MISSING** | **GAP** — No `DailyWorkSummary` model |
| **Summary Replies** | ❌ **MISSING** | **GAP** — No `DailyWorkSummaryReply` model for employee responses |

### 6.6 HR Reports

| ERPNext Feature | Current Status | Gap |
|---|---|---|
| Exit Reports | ❌ **MISSING** | **GAP** |
| Birthday Reports | ❌ **MISSING** | **GAP** — Easy to build from Employee.date_of_birth |
| Employee Information Reports | ⚠️ **PARTIAL** — Employee directory exists | **MINOR** |
| HR Analytics | ❌ **MISSING** | **GAP** — No headcount analytics, attrition rate, department-wise breakdowns |

### 6.7 Leaves

| ERPNext Feature | Current Status | Gap |
|---|---|---|
| Leave Type / Period | ✅ IMPLEMENTED — `LeaveType` model | **MINOR** — No explicit `LeavePeriod` model (fiscal-year-based leave cycle) |
| Leave Policy | ❌ **MISSING** | **GAP** — No `LeavePolicy` model for allocating multiple leave types automatically |
| Leave Block List | ❌ **MISSING** | **GAP** — No `LeaveBlockList` for blocking leave on specific dates |
| Leave Allocation | ✅ IMPLEMENTED — `LeaveAllocation` model | None |
| Leave Policy Assignment | ❌ **MISSING** | **GAP** — No bulk assignment of leave policies to employees by grade/department |
| Leave Control Panel | ❌ **MISSING** | **GAP** — No bulk leave allocation UI panel |
| Leave Application | ✅ IMPLEMENTED — `LeaveApplication` model | None |
| **Compensatory Leave Request** | ❌ **MISSING** | **GAP** — No `CompensatoryLeaveRequest` model for employees working on holidays |
| Leave Balance Report | ⚠️ **PARTIAL** — Leave tab shows balances per employee | **MINOR** |
| Leave Balance Summary | ❌ **MISSING** | **GAP** — No cross-employee leave balance summary report |
| Employee Working on Holiday | ❌ **MISSING** | **GAP** — No report |

> [!WARNING]
> **HR is the module with the most gaps.** While the core Employee/Attendance/Leave/Shift framework is solid, ERPNext's HR module has deep sub-workflows (Recruitment lifecycle, Employee lifecycle transitions, Grievance, Full & Final Settlement, Leave Policies) that need dedicated models and UI.
>
> **HR Actions Required (17 new models + 6 reports):**
> 1. Create `StaffingPlan` + `StaffingPlanDetail` models
> 2. Create `Interview`, `InterviewRound`, `InterviewFeedback` models
> 3. Create `EmployeeGrade` model
> 4. Create `EmployeePromotion` model (with designation/grade change history)
> 5. Create `EmployeeTransfer` model (with department/branch change history)
> 6. Create `GrievanceType` + `EmployeeGrievance` models
> 7. Create `FullAndFinalStatement` + `FullAndFinalStatementItem` models
> 8. Create `DailyWorkSummary` + `DailyWorkSummaryReply` models (or integrate AI summary agents)
> 9. Create `LeavePolicy` + `LeavePolicyDetail` models
> 10. Create `LeaveBlockList` + `LeaveBlockListDate` models
> 11. Create `CompensatoryLeaveRequest` model
> 12. Build HR reports (Exits, Birthdays, Analytics, Leave Summary, Holiday Workers)
> 13. Build Recruitment Analytics funnel dashboard

---

## Module 7: Payroll

| ERPNext Feature | Current Status | Gap |
|---|---|---|
| **Salary Component** | ✅ IMPLEMENTED — `SalaryComponent` model | None |
| **Salary Structure** | ✅ IMPLEMENTED — `SalaryStructure`, `SalaryStructureItem` models | None |
| **Income Tax** (Slab) | ⚠️ **PARTIAL** — Tax withholding categories exist in billing but no dedicated `IncomeTaxSlab` for payroll | **GAP** — Need `IncomeTaxSlab` + `IncomeTaxSlabRate` models for progressive tax computation on salaries |
| **Payroll Period** | ⚠️ **PARTIAL** — `PayrollEntry` handles batch runs but no dedicated `PayrollPeriod` model | **GAP** — Need `PayrollPeriod` model defining annual tax computation period |
| **Salary Structure Assignment** | ✅ IMPLEMENTED — `SalaryStructureAssignment` model | None |
| **Salary Slip** | ✅ IMPLEMENTED — `SalarySlip`, `SalarySlipItem` models | None |
| **Additional Salary** | ❌ **MISSING** | **GAP** — No `AdditionalSalary` model for one-time bonuses, ad-hoc earnings/deductions |
| **Retention Bonus** | ❌ **MISSING** | **GAP** — No `RetentionBonus` model |

> [!IMPORTANT]
> **Payroll Actions Required:**
> 1. Create `IncomeTaxSlab` + `IncomeTaxSlabRate` models
> 2. Create `PayrollPeriod` model
> 3. Create `AdditionalSalary` model (link to employee, component, amount, payroll date)
> 4. Create `RetentionBonus` model
> 5. Wire income tax slab computation into salary slip generation

---

## Module 8: Manufacturing

| ERPNext Feature | Current Status | Gap |
|---|---|---|
| **Work Order** | ✅ IMPLEMENTED — `WorkOrder` model | None |
| **Production Plan** | ✅ IMPLEMENTED — `ProductionPlan`, `ProductionPlanItem` with MRP shortage explosion | None |
| **Stock Entry** | ✅ IMPLEMENTED — Universal stock entry with MANUFACTURE type | None |
| **Job Card** | ✅ IMPLEMENTED — `JobCard`, `JobCardTimeLog` models; MES console in `/production` | None |
| **Item** | ✅ IMPLEMENTED | None |
| **Bill of Materials** | ✅ IMPLEMENTED — `BOM`, `BOMItem`, `BOMOperation`, `BOMScrapItem` with multi-level tree explosion and cost rollup | None |
| **Workstation** | ✅ IMPLEMENTED — `Workstation` model | None |
| **Operation** | ✅ IMPLEMENTED — `Operation` model | None |
| **Routing** | ✅ IMPLEMENTED — `Routing`, `RoutingOperation` models | None |

> [!TIP]
> **Manufacturing is 100% complete.** No gaps identified. The AI Native ERP actually exceeds ERPNext here with OR-Tools CP-SAT finite-capacity scheduling, OEE analytics, and IoT telemetry integration.

---

## Module 9: Projects

| ERPNext Feature | Current Status | Gap |
|---|---|---|
| **Project** | ✅ IMPLEMENTED — `Project` model; `/projects` page | None |
| **Task** (Creation, Listing) | ✅ IMPLEMENTED — `ProjectTask` model | None |
| **Project Type** | ❌ **MISSING** | **GAP** — No `ProjectType` model for categorizing projects (Internal, External, etc.) |
| **Project Update** | ✅ **IMPLEMENTED** — `ProjectUpdate` model in [`projects.py`](file:///home/hassaan/Desktop/Projects/AI_Native_ERP/rebuild/src/erp/db/models/projects.py) | None |
| **Time Tracking** | ✅ IMPLEMENTED — `Timesheet` model with billing/costing rates | None |
| **Timesheet** | ✅ IMPLEMENTED | None |
| **Activity Type** | ❌ **MISSING** | **GAP** — No `ActivityType` model for categorizing timesheet activities |
| **Activity Cost** | ❌ **MISSING** | **GAP** — No `ActivityCost` model for per-employee or per-activity-type billing/costing rates |

> [!NOTE]
> **Projects Actions Required:**
> 1. Create `ProjectType` model
> 2. Create `ActivityType` model
> 3. Create `ActivityCost` model (employee × activity_type → billing_rate, costing_rate)

---

## Module 10: Support

| ERPNext Feature | Current Status | Gap |
|---|---|---|
| **Issue** | ✅ IMPLEMENTED — `Issue`, `IssueCommunication` models; CRM tickets tab | None |
| **Issue Type** | ⚠️ **PARTIAL** — Issues have a `priority` field but no dedicated `IssueType` master | **GAP** — Need `IssueType` model for categorization (Bug, Feature Request, Question, etc.) |
| **Maintenance** (Schedule, Visit) | ✅ IMPLEMENTED — `MaintenanceSchedule`, `MaintenanceVisit` models; `/maintenance` page | None |
| **SLA** (Service Level Agreement) | ✅ IMPLEMENTED — `ServiceLevelAgreement`, `ServiceLevelPriority` models; CRM SLAs tab | None |
| **Warranty** (Claims) | ✅ IMPLEMENTED — `WarrantyClaim` model; CRM warranty tab with serial number verification | None |
| **Support Reports** | ⚠️ **PARTIAL** — Ticket counts visible in CRM dashboard | **GAP** — No dedicated support reports (average resolution time, SLA compliance %, agent performance) |

> [!NOTE]
> **Support Actions Required:**
> 1. Create `IssueType` master model
> 2. Build support reports (Resolution Time, SLA Compliance, Agent Performance)

---

## Implementation Phases

### Phase A: Shared Foundation Entities *(Week 1-2)*

These models are referenced by multiple modules and should be built first:

| # | Entity | Used By | Priority |
|---|---|---|---|
| A1 | `ItemGroup` (tree hierarchy) | Buying, Selling, Stock, Reports | 🔴 Critical |
| A2 | `PriceList` | Buying, Selling | 🔴 Critical |
| A3 | `ItemPrice` | Buying, Selling | 🔴 Critical |
| A4 | `Contact` (dynamic link) | Buying, Selling, HR, CRM | 🔴 Critical |
| A5 | `Address` (billing/shipping) | Buying, Selling, Stock | 🔴 Critical |
| A6 | `UOM` + `UOMConversion` | Stock, Manufacturing, Buying | 🔴 Critical |
| A7 | `NamingSeries` | All document types | 🟡 High |
| A8 | `TermsAndConditionsTemplate` | Buying, Selling | 🟡 High |
| A9 | `ProductBundle` + items | Selling, Stock | 🟡 High |
| A10 | `IssueType` | Support | 🟢 Medium |

**Deliverables:**
- Alembic migration for all 10+ new tables
- CRUD API routes for each entity
- Frontend management pages or embedded tabs
- Seed data (default UOMs, common item groups)

---

### Phase B: Buying & Selling Enhancements *(Week 2-3)*

| # | Feature | Module |
|---|---|---|
| B1 | `SupplierGroup` hierarchy | Buying |
| B2 | `PurchaseTaxesAndChargesTemplate` | Buying |
| B3 | `ShippingRule` + conditions | Stock/Selling |
| B4 | `ItemManufacturer` | Stock |
| B5 | `PromotionalScheme` + `PricingRule` | Buying/Selling |
| B6 | `SalesPartner` + `SalesTeam` | Selling |
| B7 | `LoyaltyProgram` + `LoyaltyPointEntry` | Selling/POS |
| B8 | Delivery Note UI & Workflow (uses existing `DeliveryNote` models) | Stock/Selling |
| B9 | Stock Settings in TenantSettings | Stock |
| B10 | Buying Settings in TenantSettings | Buying |

**Deliverables:**
- Alembic migration
- API routes and business logic
- Frontend tabs in existing pages (Procurement, Commercial, Inventory, POS)

---

### Phase C: HR Deep Workflows *(Week 3-5)*

| # | Feature | Sub-module |
|---|---|---|
| C1 | `StaffingPlan` + details | Recruitment |
| C2 | `Interview` + `InterviewRound` + `InterviewFeedback` | Recruitment |
| C3 | Recruitment Analytics dashboard | Recruitment |
| C4 | `EmployeeGrade` | Employee Lifecycle |
| C5 | `EmployeePromotion` | Employee Lifecycle |
| C6 | `EmployeeTransfer` | Employee Lifecycle |
| C7 | `GrievanceType` + `EmployeeGrievance` | Grievance |
| C8 | `FullAndFinalStatement` + items | Exit |
| C9 | `DailyWorkSummary` + replies | Daily Work |
| C10 | `LeavePolicy` + details | Leaves |
| C11 | `LeaveBlockList` + dates | Leaves |
| C12 | `CompensatoryLeaveRequest` | Leaves |
| C13 | HR Reports (6 reports) | Reports |

**Deliverables:**
- Alembic migration for ~17 new tables
- Extended HR routes in [`hr.py`](file:///home/hassaan/Desktop/Projects/AI_Native_ERP/rebuild/src/erp/api/routes/hr.py)
- New tabs in `/workforce` page and `/recruitment` page
- Full & Final Settlement workflow page or tab

---

### Phase D: Payroll & Assets Enhancements *(Week 5-6)*

| # | Feature | Module |
|---|---|---|
| D1 | `IncomeTaxSlab` + rates | Payroll |
| D2 | `PayrollPeriod` | Payroll |
| D3 | `AdditionalSalary` | Payroll |
| D4 | `RetentionBonus` | Payroll |
| D5 | Income tax computation in salary slips | Payroll |
| D6 | `AssetMaintenanceTeam` + members | Assets |
| D7 | `AssetValueAdjustment` | Assets |

**Deliverables:**
- Alembic migration
- Tax slab computation engine
- Extended payroll routes and `/workforce` payroll tab
- Extended assets routes and `/assets` page

---

### Phase E: Projects & Support Refinements *(Week 6-7)*

| # | Feature | Module |
|---|---|---|
| E1 | `ProjectType` | Projects |
| E2 | Project Update UI & Activity Timeline (uses existing `ProjectUpdate` model) | Projects |
| E3 | `ActivityType` + `ActivityCost` | Projects |
| E4 | Support Reports | Support |

**Deliverables:**
- Minor model additions
- Report endpoints
- Frontend tab additions

---

### Phase F: Enterprise Reports Sprint *(Week 7-8)*

Build all missing reports identified across modules:

| # | Report | Module |
|---|---|---|
| F1 | Customer Ledger Summary | Accounting |
| F2 | Supplier Ledger Summary | Accounting |
| F3 | Gross Profit Analysis (by Item/Customer) | Accounting |
| F4 | Sales Invoice Trends (monthly/quarterly) | Accounting |
| F5 | Purchase Invoice Trends | Accounting |
| F6 | Purchase Analytics (by supplier/item/time) | Buying |
| F7 | Purchase Order Analytics (status/overdue) | Buying |
| F8 | Supplier-Wise Sales Analytics | Buying |
| F9 | Procurement Tracker (MR → PO → GRN pipeline) | Buying |
| F10 | Items to be Requested (below reorder) | Buying |
| F11 | Sales Analytics (by item/customer/territory) | Selling |
| F12 | Sales Order Analysis (pending delivery/billing) | Selling |
| F13 | Quotation Trends | Selling |
| F14 | Sales Order Trends | Selling |
| F15 | Inactive Customers | Selling |
| F16 | Stock Projected Qty Summary | Stock |
| F17 | Stock Ageing (FIFO-based) | Stock |
| F18 | Stock Analytics | Stock |
| F19 | Delivery Note Trends | Stock |
| F20 | Item Shortage Report | Stock |
| F21 | HR Analytics (headcount, attrition) | HR |
| F22 | Leave Balance Summary | HR |
| F23 | Employee Birthday Report | HR |
| F24 | Recruitment Funnel Analytics | HR |
| F25 | Support SLA Compliance Report | Support |
| F26 | Support Agent Performance | Support |

**Deliverables:**
- 26 new report API endpoints in [`reports.py`](file:///home/hassaan/Desktop/Projects/AI_Native_ERP/rebuild/src/erp/api/routes/reports.py) or domain-specific route files
- Frontend report tabs/pages
- SQL query optimizations with proper indexes

---

## Summary Statistics

| Metric | Count |
|---|---|
| **Total ERPNext features in outline** | ~120 |
| **Already fully implemented** | ~72 (60%) |
| **Partially implemented (minor gaps)** | ~18 (15%) |
| **Missing / needs new work** | ~30 (25%) |
| **New database models to create** | ~45 |
| **New report endpoints** | ~26 |
| **New/modified frontend pages** | ~8 pages, ~15 new tabs |
| **Estimated total implementation time** | 6-8 weeks |

---

## Verification Plan

### Automated Testing
For each phase:
```bash
# Run backend tests
cd /home/hassaan/Desktop/Projects/AI_Native_ERP/rebuild
python -m pytest tests/ -v --tb=short

# Run Alembic migration verification
alembic upgrade head
alembic check

# Run frontend build verification
cd frontend && npm run build
```

### Manual Verification
- Verify each new model's CRUD operations via API (Swagger at `/docs`)
- Verify each new frontend tab renders correctly with test data
- Verify financial reports balance (DR == CR invariant)
- Verify multi-tenant isolation on all new entities

### Regression Testing
- Re-run all existing Phase 1-8 test suites after each phase
- Verify no breaking changes to existing API contracts

---

## Risk Considerations

> [!CAUTION]
> **Database Migration Complexity:** Adding ~45 new tables requires careful migration planning. Run on a staging database first. Consider batching migrations by phase rather than one massive migration.

> [!WARNING]
> **Contact/Address Dynamic Linking:** The `Contact` and `Address` models need a polymorphic/dynamic link pattern (similar to ERPNext's Dynamic Link) to associate with multiple document types (Supplier, Customer, Employee, Company). Use a `link_doctype` + `link_name` pattern or a dedicated junction table per parent type.

> [!NOTE]
> **AI-Native Enhancement Opportunity:** Many of the missing reports (trends, analytics, forecasts) are prime candidates for AI-powered insights. Consider adding BAML-based natural language summary generation alongside raw tabular reports for an AI-native upgrade beyond vanilla ERPNext parity.
