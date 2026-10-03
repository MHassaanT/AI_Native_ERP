# ERPNext Complete Functionality Report
## Comprehensive Feature Inventory — Every Module, Every Function

> **Purpose:** This report catalogs *every single functionality* in ERPNext (reference codebase), organized by module. It serves as the definitive specification for ensuring the AI Native ERP rebuild achieves feature parity.
>
> **Source:** Exhaustive analysis of the ERPNext source code at `/home/hassaan/Desktop/Projects/AI_ERP/refrence/erpnext/`

> [!IMPORTANT]
> ERPNext contains **21 core modules** with **400+ DocTypes**, **160+ Reports**, **50+ Dashboard Charts**, **40+ Number Cards**, and **12+ Interactive Pages**. The HR/Payroll module was separated into a standalone HRMS app in v14 and is covered separately from web research.

---

## Table of Contents

1. [Accounts & Finance](#1-accounts--finance)
2. [Selling](#2-selling)
3. [Buying / Procurement](#3-buying--procurement)
4. [Stock / Inventory](#4-stock--inventory)
5. [Manufacturing](#5-manufacturing)
6. [CRM](#6-crm)
7. [Support / Helpdesk](#7-support--helpdesk)
8. [Projects](#8-projects)
9. [Assets](#9-assets)
10. [Quality Management](#10-quality-management)
11. [Maintenance](#11-maintenance)
12. [Subcontracting](#12-subcontracting)
13. [Setup & Organization](#13-setup--organization)
14. [Banking (Dedicated App)](#14-banking-dedicated-app)
15. [Regional / Localization](#15-regional--localization)
16. [Telephony & Communication](#16-telephony--communication)
17. [Portal / E-Commerce](#17-portal--e-commerce)
18. [Integrations](#18-integrations)
19. [EDI (Electronic Data Interchange)](#19-edi)
20. [Bulk Transactions](#20-bulk-transactions)
21. [Utilities](#21-utilities)
22. [HR & Payroll (HRMS — Separate App)](#22-hr--payroll-hrms)
23. [Cross-Cutting Architecture (Controllers)](#23-cross-cutting-architecture)

---

## 1. Accounts & Finance

### 1.1 Core Transaction Documents (Submittable)

| # | DocType | Description |
|---|---------|-------------|
| 1 | **Sales Invoice** | Customer billing document — Accounts Receivable, revenue recognition, output taxes, COGS posting, deferred revenue, multi-currency, POS mode, returns (Credit Notes), timesheet billing |
| 2 | **Purchase Invoice** | Vendor billing — Accounts Payable, input taxes, expense/asset GL entries, returns (Debit Notes), landed cost integration |
| 3 | **Payment Entry** | Core payment processor — customer receipts, supplier payments, internal transfers, deductions, advance allocation, multi-currency exchange gain/loss |
| 4 | **Journal Entry** | Manual double-entry voucher — adjustments, openings, transfers, corrections, inter-company, depreciation, write-offs |
| 5 | **POS Invoice** | Specialized retail checkout invoice — fast entry, barcode scanning, multi-mode payments (Cash, Card, Loyalty), offline capable |
| 6 | **Period Closing Voucher** | Year-end P&L transfer to Equity/Reserves, opening balance generation |
| 7 | **Payment Request** | Generates online payment collection links via email/SMS |
| 8 | **Payment Order** | Batches payment entries into consolidated bank disbursement files |
| 9 | **Dunning** | Payment reminder notices for overdue invoices — dunning fees, interest calculations |
| 10 | **Share Transfer** | Equity share issue, transfer, redemption between shareholders |
| 11 | **Exchange Rate Revaluation** | Period-end revaluation of foreign currency balances to unrealized gain/loss |
| 12 | **Invoice Discounting** | Short-term bank financing against pledged unpaid sales invoices |
| 13 | **Unreconcile Payment** | Detach and unallocate reconciled payments from invoices |

### 1.2 POS (Point of Sale) System

| # | Feature | Description |
|---|---------|-------------|
| 1 | **POS Profile** | Terminal configuration — default warehouse, price list, cash accounts, layout, allowed item groups, customer groups |
| 2 | **POS Opening Entry** | Shift opening — opening cash float, assigned cashier |
| 3 | **POS Closing Entry** | Shift reconciliation — expected vs collected amounts per payment method |
| 4 | **POS Invoice Merge Log** | Consolidates POS invoices into standard Sales Invoices |
| 5 | **POS Settings** | Global POS configuration |
| 6 | **POS Page (Interactive)** | Full retail cash register UI — barcode scanning, quick customer lookup, discounts, multi-mode payments, receipt printing |

### 1.3 Master Data & Configuration

| # | DocType | Description |
|---|---------|-------------|
| 1 | **Account** | Hierarchical chart of accounts tree (Asset, Liability, Equity, Income, Expense) |
| 2 | **Account Category** | Flexible financial report layout mapping |
| 3 | **Cost Center** | Hierarchical departmental/project cost tracking |
| 4 | **Finance Book** | Parallel reporting under different standards (IFRS vs Tax vs GAAP) |
| 5 | **Fiscal Year** | Accounting year definitions with company linkage |
| 6 | **Accounting Period** | Sub-annual periods with lock capabilities |
| 7 | **Accounting Dimension** | Custom dimensions (Branch, Department, Project) across transactions |
| 8 | **Mode of Payment** | Payment methods (Cash, Card, Bank Transfer, Cheque) |
| 9 | **Payment Term** | Credit terms (e.g., 100% after 30 days) |
| 10 | **Payment Terms Template** | Installment schedule groupings |
| 11 | **Tax Category** | Classification tags (Domestic, Inter-State, Export) |
| 12 | **Tax Rule** | Automated tax template selection based on party/address |
| 13 | **Tax Withholding Category** | TDS/withholding tax rules, thresholds, rates |
| 14 | **Tax Withholding Group** | Groups withholding categories for compliance |
| 15 | **Sales Taxes and Charges Template** | Predefined sales tax calculation templates |
| 16 | **Purchase Taxes and Charges Template** | Predefined purchase tax templates |
| 17 | **Item Tax Template** | Item-specific tax percentage overrides |
| 18 | **Shipping Rule** | Freight/shipping charges based on weight or value |
| 19 | **Pricing Rule** | Complex rule engine — trade discounts, quantity breaks, margins, free items |
| 20 | **Promotional Scheme** | Multi-tier pricing and promotional discount schemes |
| 21 | **Coupon Code** | Promotional redemption codes |
| 22 | **Loyalty Program** | Customer loyalty tiers, earn rates, conversion, expiry |
| 23 | **Cheque Print Template** | Physical cheque printing layout configuration |

### 1.4 Banking & Reconciliation

| # | Feature | Description |
|---|---------|-------------|
| 1 | **Bank** | Financial institution directory |
| 2 | **Bank Account** | Account records with GL links, IBAN, SWIFT |
| 3 | **Bank Transaction** | Individual statement transactions (imported or manual) |
| 4 | **Bank Transaction Rule** | Automated classification/matching rules using conditions |
| 5 | **Bank Reconciliation Tool** | Interactive matching of statement vs ERP vouchers |
| 6 | **Bank Clearance** | Manual clearance date setting for cheques/vouchers |
| 7 | **Bank Statement Import** | CSV/OFX/QIF/CAMT.053 statement file upload |
| 8 | **Bank Guarantee** | Bank guarantee contract tracking (validity, margin, amounts) |
| 9 | **Payment Reconciliation** | Match unlinked payments/credit notes against invoices |
| 10 | **Process Payment Reconciliation** | Automated batch reconciliation |

### 1.5 Budgeting

| # | Feature | Description |
|---|---------|-------------|
| 1 | **Budget** | Allocations per Cost Center/Project with warning/stopping thresholds |
| 2 | **Budget Distribution** | Monthly percentage splits for annual budgets |
| 3 | **Cost Center Allocation** | Distribute expenses from source to destination cost centers |

### 1.6 Subscriptions

| # | Feature | Description |
|---|---------|-------------|
| 1 | **Subscription** | Recurring customer contracts with billing cycles |
| 2 | **Subscription Plan** | Billing frequency, cost, trial periods |
| 3 | **Process Subscription** | Automated periodic invoice generation |

### 1.7 Share Management

| # | Feature | Description |
|---|---------|-------------|
| 1 | **Shareholder** | Company shareholders registry |
| 2 | **Share Transfer** | Share issue/transfer/redemption |
| 3 | **Share Type** | Classes of equity shares |
| 4 | **Share Balance** | Current shareholding positions |

### 1.8 Tools & Utilities

| # | Feature | Description |
|---|---------|-------------|
| 1 | **Chart of Accounts Importer** | Upload custom CoA from CSV/Excel |
| 2 | **Opening Invoice Creation Tool** | Bulk-create opening invoices with historical balances |
| 3 | **Process Deferred Accounting** | Background amortization of deferred revenue/expense |
| 4 | **Process Statement of Accounts** | Generate and auto-email Statements of Accounts with aging |
| 5 | **Repost Accounting Ledger** | Recalculate and repost GL entries for selected vouchers |
| 6 | **Repost Payment Ledger** | Recalculate payment ledger entries |
| 7 | **Ledger Health Monitor** | Background auditing for ledger integrity issues |
| 8 | **Ledger Merge** | Merge historical transactions of GL accounts |
| 9 | **Bisect Accounting Statements** | Diagnostic utility to isolate balance mismatches |

### 1.9 Reports (55+ Reports)

**Financial Statements:**
- Balance Sheet
- Profit and Loss Statement
- Cash Flow Statement
- Trial Balance / Trial Balance for Party / Simple Trial Balance
- Consolidated Financial Statement / Consolidated Trial Balance
- Custom Financial Statement (user-defined templates)
- Financial Ratios

**Ledgers & Registers:**
- General Ledger
- Customer Ledger Summary / Supplier Ledger Summary
- Sales Register / Purchase Register
- Item-wise Sales Register / Item-wise Purchase Register
- Payment Ledger
- Voucher-Wise Balance

**Receivables & Payables:**
- Accounts Receivable / Summary
- Accounts Payable / Summary
- Customer Credit Balance

**Profitability:**
- Gross Profit
- Gross and Net Profit Report
- Profitability Analysis (multi-dimensional)
- Sales Invoice Trends / Purchase Invoice Trends

**Taxation:**
- Tax Withholding Details
- TDS Computation Summary

**Budget & Variance:**
- Budget Variance Report

**Banking:**
- Bank Clearance Summary
- Bank Reconciliation Statement
- Cheques And Deposits Incorrectly Cleared

**Other:**
- Deferred Revenue and Expense
- Delivered Items To Be Billed / Billed Items To Be Received / Received Items To Be Billed
- Dimension-Wise Accounts Balance Report
- Payment Period Based On Invoice Date
- Sales Partners Commission / Sales Payment Summary
- Inactive Sales Items
- POS Register
- Share Ledger / Share Balance
- General And Payment Ledger Comparison
- Invalid Ledger Entries / Calculated Discount Mismatch
- Account Balance

### 1.10 Dashboards & Visualizations

**Module Dashboards:** Accounts Dashboard, Payments Dashboard
**Charts (7):** Profit and Loss, Incoming/Outgoing Bills, AR/AP Ageing, Budget Variance, Bank Balance
**Number Cards (4):** Total Incoming/Outgoing Bills, Total Incoming/Outgoing Payments
**Workspaces (4):** Accounting, Financial Reports, Invoicing, Payments

---

## 2. Selling

### 2.1 Core Transaction Documents

| # | DocType | Description |
|---|---------|-------------|
| 1 | **Sales Order** | Central customer order — stock reservation, manufacturing triggers, procurement triggers, delivery, billing, payment schedules, proforma support, inter-company, drop-ship |
| 2 | **Quotation** | Commercial estimate — dynamic party (Customer/Lead/Prospect), validity tracking, loss reasons, competitor tracking, coupon codes |
| 3 | **Proforma Invoice** | Preliminary bill for advance payments/customs — linked to Sales Order |
| 4 | **Product Bundle** | Sales kits — parent non-stock item with stock component deduction on delivery |
| 5 | **Installation Note** | Field service document — product installation tracking, serial numbers, warranty activation |

### 2.2 Master Data

| # | DocType | Description |
|---|---------|-------------|
| 1 | **Customer** | Core customer entity — commercial, taxation, delivery, accounting, loyalty, credit limits, enforcement rules, portal users, sales governance |
| 2 | **Party Specific Item** | Enforces sales restrictions or dedicated catalogs per customer/group |
| 3 | **Industry Type** | Customer business sector categorization |
| 4 | **Sales Partner Type** | Partner categorization (Dealer, Reseller, Agent) |

### 2.3 Configuration

| # | Feature | Description |
|---|---------|-------------|
| 1 | **Selling Settings** | Customer naming, pricing controls, rate integrity, transaction controls, proforma settings, commission tracking, UTM, discount accounting |
| 2 | **SMS Center** | Bulk SMS dispatch to filtered recipient lists |

### 2.4 Reports (23 Reports)

- Sales Order Analysis / Sales Analytics / Sales Order Trends
- Item-wise Sales History
- Customer Credit Balance / Customer Acquisition and Loyalty
- Inactive Customers / Customers Without Any Sales Transactions
- Customer-wise Item Price
- Lost Quotations / Quotation Trends
- Payment Terms Status for Sales Order
- Pending SO Items For Purchase Request
- Available Stock for Packing Items
- Address And Contacts
- Sales Person Commission Summary / Transaction Summary / Target Variance
- Sales Partner Commission Summary / Transaction Summary / Target Variance
- Territory-wise Sales / Territory Target Variance

### 2.5 Interactive Pages

- **Point of Sale (POS)** — Full retail cash register interface
- **Sales Funnel** — Interactive pipeline conversion visualization

### 2.6 Dashboards

**Charts (4):** Item-wise Annual Sales, Sales Order Analysis, Sales Order Trends, Top Customers
**Number Cards (7):** Active Customers, Annual Sales, Average SO Value, SO Count, SOs to Bill, SOs to Deliver, Total Sales Amount
**Print Formats (15):** Multiple layouts for POS, Proforma, Quotation, Sales Order (Standard, Bordered, Classic, Modern, with Images)

---

## 3. Buying / Procurement

### 3.1 Core Transaction Documents

| # | DocType | Description |
|---|---------|-------------|
| 1 | **Purchase Order** | Procurement agreement — subcontracting, drop-shipping, multi-currency, barcode scanning, payment terms, inter-company |
| 2 | **Request for Quotation** | Multi-vendor bid request — email integration, opportunity linkage |
| 3 | **Supplier Quotation** | Vendor quote record — proposed rates, validity, lead times |

### 3.2 Master Data

| # | DocType | Description |
|---|---------|-------------|
| 1 | **Supplier** | Vendor entity — billing defaults, banking, tax rules, hold/freeze rules, scorecard flags, transporter flag, inter-company |
| 2 | **Buying Settings** | Global buying rules — process enforcement, rate integrity, tolerances, subcontracting defaults |

### 3.3 Supplier Scorecard System (8 DocTypes)

| # | Feature | Description |
|---|---------|-------------|
| 1 | **Supplier Scorecard** | Master scorecard configuration with period, weighting function, standings |
| 2 | **Supplier Scorecard Criteria** | KPI definitions (On-Time Delivery, Quality, Price) with formulas |
| 3 | **Supplier Scorecard Period** | Periodic evaluation runs with computed scores |
| 4 | **Supplier Scorecard Variable** | Dynamic operational data variables |
| 5 | **Supplier Scorecard Standing** | Performance tiers (Preferred, Standard, At-Risk, Blacklisted) |
| 6 | Scoring Criteria / Standing / Variable child tables | Linking components within scorecards |

### 3.4 Reports (10 Reports)

- Item-wise Purchase History
- Procurement Tracker (Material Request → PO → PR → PI lifecycle)
- Purchase Analytics / Purchase Order Analysis / Purchase Order Trends
- Requested Items to Order and Receive
- Subcontract Order Summary / Subcontracted Item To Be Received / Subcontracted Raw Materials To Be Transferred
- Supplier Quotation Comparison (side-by-side vendor bid comparison)

### 3.5 Dashboards

**Charts (4):** Material Request Analysis, PO Analysis, PO Trends, Top Suppliers
**Number Cards (7):** Active Suppliers, Annual Purchase, Average Order Value, PO Count, POs to Bill, POs to Receive, Total Purchase Amount
**Print Formats (12):** PO layouts (7 including Drop Shipping), RFQ layouts (5)

---

## 4. Stock / Inventory

### 4.1 Core Transaction Documents

| # | DocType | Description |
|---|---------|-------------|
| 1 | **Delivery Note** | Customer dispatch — inventory reduction, COGS accounting, status tracking |
| 2 | **Purchase Receipt** | Goods Receipt Note (GRN) — accepted/rejected qty, serial/batch, perpetual inventory GL |
| 3 | **Stock Entry** | Universal movement — Material Issue/Receipt/Transfer, Manufacture, Repack, Subcontracting, Disassembly |
| 4 | **Stock Reconciliation** | Physical count adjustment — override system balances, Opening Stock |
| 5 | **Material Request** | Internal requisition — Purchase, Transfer, Issue, Manufacture, Customer Provided |
| 6 | **Pick List** | Warehouse picking — location-level picking for SO/WO/MR fulfillment, barcode scanning |
| 7 | **Packing Slip** | Carton/package packing linked to Delivery Notes |
| 8 | **Delivery Trip** | Multi-stop route dispatch — Google Maps integration, distance, stop tracking |
| 9 | **Shipment** | Carrier integration — parcel dimensions, tracking URLs, AWBs, carrier rates |
| 10 | **Landed Cost Voucher** | Capitalize freight/customs/insurance into item valuation |

### 4.2 Item Master & Catalog (25 DocTypes)

| # | Feature | Description |
|---|---------|-------------|
| 1 | **Item** | Master product/service record — variants, serial/batch tracking, valuation method, shelf life, lead time, safety stock, reorder levels, barcodes |
| 2 | **Item Attribute** | Variant attributes (Size, Color, Voltage) with numeric ranges |
| 3 | **Item Variant Settings** | Template-to-variant field synchronization |
| 4 | **Item Alternative** | Allowable replacement items (bidirectional) |
| 5 | **Item Manufacturer** | Manufacturer Part Number (MPN) mapping |
| 6 | **Item Price** | Price per Price List with date validity, packing units, batch pricing |
| 7 | **Price List** | Price list headers (Standard Buying/Selling, Wholesale) |
| 8 | **Customs Tariff Number** | HSN/SAC codes for shipping and tax |
| 9 | **UOM Category** | Unit groupings (Length, Mass, Volume) |
| 10 | **Manufacturer** | External brand/manufacturer registry |

### 4.3 Warehousing & Stock Management

| # | Feature | Description |
|---|---------|-------------|
| 1 | **Warehouse** | Hierarchical storage locations (nested tree) with GL account links |
| 2 | **Warehouse Type** | Storage categories (Stores, Transit, WIP, FG, Scrap, Rejected) |
| 3 | **Inventory Dimension** | Custom tracking dimensions across stock transactions |
| 4 | **Bin** | Real-time stock cache per Item-Warehouse (actual, ordered, reserved, projected qty) |
| 5 | **Putaway Rule** | Warehouse capacity management with priority ranking |
| 6 | **Stock Reservation Entry** | Inventory reservation locks for SO/WO/Production Plans |

### 4.4 Serial & Batch Tracking

| # | Feature | Description |
|---|---------|-------------|
| 1 | **Serial No** | Individual unit tracking — status, warranty, AMC contracts |
| 2 | **Batch** | Lot/batch tracking — manufacturing date, expiry, source voucher |
| 3 | **Serial and Batch Bundle** | Modern grouping across stock transactions with auto-allocation |

### 4.5 Stock Valuation & Ledger

| # | Feature | Description |
|---|---------|-------------|
| 1 | **Stock Ledger Entry** | Immutable inventory transaction ledger |
| 2 | **Stock Closing Entry** | Period closing with frozen balance snapshots |
| 3 | **Repost Item Valuation** | Background recalculation for backdated transactions |
| 4 | **Stock Settings** | Global controls — valuation method, negative stock, tolerances, reservation, quality enforcement |
| 5 | **Stock Entry Type** | Configurable templates for stock movements |

### 4.6 Quality Inspection (in Stock)

| # | Feature | Description |
|---|---------|-------------|
| 1 | **Quality Inspection** | QA inspection on receipt/delivery/production — sample size, readings, pass/fail |
| 2 | **Quality Inspection Template** | Reusable quality checklists |
| 3 | **Quality Inspection Parameter** | Test parameters with groups |

### 4.7 Reports (52 Reports)

**Inventory Balance & Valuation (13):**
- Stock Ledger / Stock Balance / Warehouse Wise Stock Balance / Total Stock Summary
- Item Balance / Stock Projected Qty / Stock Ageing
- Warehouse Wise Item Balance Age and Value / Stock Analytics
- Stock and Account Value Comparison / COGS By Item Group
- Item Wise Consumption / Product Bundle Balance

**Serial & Batch (13):**
- Serial No and Batch Traceability / Serial No Ledger / Serial No Status
- Available Serial No / Serial and Batch Summary / Available Batch Report
- Batch-Wise Balance History / Batch Item Expiry Status / Batch Split Tree
- Negative Batch Report / Serial No Warranty Expiry / Serial No Service Contract Expiry

**Planning & Shortage (6):**
- Item Shortage Report / Reserved Stock / Items To Be Requested
- Itemwise Recommended Reorder Level
- Requested Items To Be Transferred / Material Requests Without Supplier Quotations

**Pricing & Trends (11):**
- Item Price Stock / Item Prices / Item Wise Price List Rate
- Item Variant Details / Item Where Used / BOM Search
- Purchase Receipt Trends / Delivery Note Trends
- Delayed Item Report / Delayed Order Report / Landed Cost Report

**Diagnostics (9):**
- FIFO Queue vs Qty Comparison / Incorrect Balance Qty
- Incorrect Serial and Batch Bundle / Incorrect Serial No Valuation
- Incorrect Stock Value Report / Stock Ledger Invariant Check
- Stock Ledger Variance / Stock Qty vs Batch Qty / Stock Qty vs Serial No Count

### 4.8 Dashboards & Pages

**Interactive Pages (2):** Stock Balance, Warehouse Capacity Summary
**Item Dashboard:** Real-time stock levels per item
**Charts (6):** Delivery Trends, Item Shortage, Oldest Items, Purchase Receipt Trends, Stock Value by Item Group, Warehouse-wise Stock Value
**Number Cards (3):** Total Active Items, Total Stock Value, Total Warehouses
**Print Formats (8):** Delivery Note (6 layouts), Pick List, Purchase Receipt Bundle Print

---

## 5. Manufacturing

### 5.1 Bill of Materials (BOM) — 12 DocTypes

| # | Feature | Description |
|---|---------|-------------|
| 1 | **BOM** | Central BoM — raw materials, sub-assemblies, operations, scrap, co-products, costing, process loss, quality inspection |
| 2 | **BOM Item** | Raw material/component line items with operation linking |
| 3 | **BOM Explosion Item** | Auto-generated flattened multi-level raw material view |
| 4 | **BOM Operation** | Operation steps — workstation, duration, costs, warehouse movements |
| 5 | **BOM Secondary Item** | Co-Products, By-Products, Scrap, Additional Finished Goods |
| 6 | **BOM Creator** | Interactive tree-based multi-level BOM builder |
| 7 | **BOM Update Tool** | Global sub-assembly BOM replacement and cost recalculation |
| 8 | **BOM Update Log** | Async job logs for BOM updates |

### 5.2 Production Planning & Scheduling — 13 DocTypes

| # | Feature | Description |
|---|---------|-------------|
| 1 | **Production Plan** | MRP engine — consolidates SO/MR demands, generates Work Orders and procurement plans |
| 2 | **Master Production Schedule (MPS)** | Long-term demand management balancing actual vs forecasted demand |
| 3 | **Sales Forecast** | Demand projection tool with time bucket items |
| 4 | **Production Plan Schedule** | Persisted time blocks from finite capacity scheduling |
| 5 | **Finite Capacity Scheduling Engine** | Advanced scheduler (Epicor Kinetic model) — Forward/Backward, Finite/Infinite modes, capability-based workstation selection, topological graph sorting |

### 5.3 Shop Floor Execution — 12 DocTypes

| # | Feature | Description |
|---|---------|-------------|
| 1 | **Work Order** | Manufacturing order — qty to manufacture, status tracking, serial/batch, planned/actual costs, warehouse routing |
| 2 | **Job Card** | Workstation-level dispatch — operator time, machine time, raw material consumption, sub-operations, quality inspection, corrective actions |
| 3 | **Downtime Entry** | Machine downtime capture — stop reasons, duration |

### 5.4 Masters & Configuration

| # | Feature | Description |
|---|---------|-------------|
| 1 | **Workstation** | Machine/work center — capacity, status, hourly rate, operating hours, holiday list |
| 2 | **Workstation Type** | Capability categories (CNC, Assembly, etc.) |
| 3 | **Operation** | Manufacturing process catalog — work instructions, sub-operations, batch sizes |
| 4 | **Routing** | Reusable operation sequences |
| 5 | **Plant Floor** | Physical factory floor grouping with live visual layouts |
| 6 | **Blanket Order** | Long-term recurring contracts (Selling/Purchasing) |
| 7 | **Manufacturing Settings** | Global config — capacity planning, backflush, BOM costing, overproduction tolerances |

### 5.5 Interactive Pages (4)

1. **Shop Floor MES Console** — Operator view (workstation queue, work instructions, timer, QI) + Manager board (Kanban, OEE, progress bars)
2. **Production Plan Visualizer** — Real-time execution dashboard with Gantt blocks
3. **BOM Comparison Tool** — Side-by-side BOM diff
4. **Visual Plant Floor** — Interactive machine layout with live status

### 5.6 Reports (21 Reports)

- BOM Explorer / BOM Operations Time / BOM Stock Analysis / BOM Variance Report
- Completed Work Orders / Open Work Orders / Work Orders in Progress
- Cost of Poor Quality Report / Downtime Analysis
- Exponential Smoothing Forecasting / MRP Report
- Issued Items Against Work Order / Work Order Consumed Materials / Work Order Stock Report
- Job Card Summary / Process Loss Report / Production Analytics
- Production Plan Summary / Production Planning Report
- Quality Inspection Summary / Work Order Summary

### 5.7 Dashboards

**Charts (8):** Produced Quantity, Completed Operation, WO Analysis, Pending WO, QI Analysis, Downtime Analysis, WO Qty Analysis, Job Card Analysis
**Number Cards (7):** Open/WIP Work Orders, Monthly Completed/Total WO, Ongoing Job Card, Monthly QI, Manufactured Items Value

---

## 6. CRM

### 6.1 Core Pipeline (8 DocTypes)

| # | Feature | Description |
|---|---------|-------------|
| 1 | **Lead** | Prospective customer tracking — qualification, UTM attribution, 1-click conversion |
| 2 | **Opportunity** | Qualified sales deals — sales stage, deal value, probability, competitor tracking, lost reasons |
| 3 | **Prospect** | B2B organization profile — aggregates Leads and Opportunities under corporate umbrella |
| 4 | **Sales Stage** | Configurable pipeline milestones |
| 5 | **Opportunity Type / Lost Reason** | Classification masters |
| 6 | **Competitor** | Market competitor directory |
| 7 | **Market Segment** | Target market classification |

### 6.2 Campaigns & Marketing

| # | Feature | Description |
|---|---------|-------------|
| 1 | **Campaign** | Marketing campaign registry |
| 2 | **Email Campaign** | Automated drip-email execution engine |

### 6.3 Contracts

| # | Feature | Description |
|---|---------|-------------|
| 1 | **Contract** | Formal commercial agreements — templates, e-signing, fulfilment tracking |
| 2 | **Contract Template** | Reusable boilerplate with Jinja2 templating |

### 6.4 Appointments

| # | Feature | Description |
|---|---------|-------------|
| 1 | **Appointment** | Customer booking — scheduling, portal verification, calendar events |
| 2 | **Appointment Booking Settings** | Self-service config — slot duration, concurrent agents, availability |

### 6.5 Settings & Integration

- **CRM Settings** — Auto-creation, duplicate checks, Frappe CRM sync
- **Frappe CRM API** — REST sync bridge with external Frappe CRM

### 6.6 Reports (9 Reports)

- Campaign Efficiency / First Response Time for Opportunity
- Lead Conversion Time / Lead Details / Lead Owner Efficiency
- Lost Opportunity / Opportunity Summary by Sales Stage
- Prospects Engaged But Not Converted / Sales Pipeline Analytics

### 6.7 Dashboards

**Charts (7):** Incoming Leads, Lead Source, Opportunities via Campaigns, Opportunity Trends, Territory-wise counts/sales, Won Opportunities
**Number Cards (4):** New Lead, New Opportunity, Open Opportunity, Won Opportunity

---

## 7. Support / Helpdesk

### 7.1 Core Documents

| # | Feature | Description |
|---|---------|-------------|
| 1 | **Issue** | Customer ticket — priority, type, SLA tracking (response/resolution), email threading, portal submission |
| 2 | **Warranty Claim** | Warranty/AMC repair tracking — serial number, complaint, resolution |

### 7.2 Service Level Agreements

| # | Feature | Description |
|---|---------|-------------|
| 1 | **Service Level Agreement** | SLA commitments — priority matrices, working hours, holiday lists, paused statuses, fulfilment criteria |
| 2 | **Issue Priority** | Priority levels (Low, Medium, High, Urgent) |
| 3 | **Issue Type** | Ticket categories (Bug, Feature Request, Hardware Fault) |
| 4 | **Service Day** | Operating day/time definitions |

### 7.3 Configuration

- **Support Settings** — Auto-close, SLA enablement, portal greeting, search API
- **Support Search Source** — Unified knowledge base search configuration
- **Web Form (Issues)** — Customer portal self-service ticket submission

### 7.4 Reports (4 Reports)

- First Response Time for Issues / Issue Analytics / Issue Summary
- Support Hour Distribution (heatmap by hour/day)

### 7.5 Dashboards

**Chart (1):** Issues Opened
**Number Cards (3):** Open Issues, Overdue Issues, Resolved Issues

---

## 8. Projects

### 8.1 Core Documents (15 DocTypes)

| # | Feature | Description |
|---|---------|-------------|
| 1 | **Project** | Project master — tasks, milestones, status tracking, % complete, costing, billing |
| 2 | **Task** | Work item — dependencies, assignments, priority, status, progress, time tracking |
| 3 | **Timesheet** | Employee time logging — billable hours, activity tracking, cost calculation |
| 4 | **Activity Type** | Time activity categories |
| 5 | **Activity Cost** | Activity rates per employee |
| 6 | **Project Template** | Reusable project templates |
| 7 | **Project Type** | Project classification |
| 8 | **Project Update** | Progress update records |
| 9 | **Task Depends On** | Task dependency linking |

### 8.2 Reports (5 Reports)

- Project Profitability / Project Summary / Project Billing Summary
- Daily Timesheet Summary / Timesheet Details

### 8.3 Dashboards

**Number Cards (3):** Active Projects, Open Tasks, Overdue Tasks
**Dashboard Charts (2):** Project wise Billing, Task Completion

---

## 9. Assets

### 9.1 Core Documents (26 DocTypes)

| # | Feature | Description |
|---|---------|-------------|
| 1 | **Asset** | Fixed asset master — purchase, depreciation, valuation, insurance, warranty |
| 2 | **Asset Category** | Asset classification with depreciation policies |
| 3 | **Asset Depreciation Schedule** | Multi-method depreciation schedules |
| 4 | **Asset Capitalization** | Convert stock items or WIP into fixed assets |
| 5 | **Asset Movement** | Transfer assets between locations/custodians |
| 6 | **Asset Value Adjustment** | Manual value impairment or revaluation |
| 7 | **Asset Repair** | Maintenance repair tracking with cost capitalization |
| 8 | **Asset Maintenance** | Planned maintenance schedules |
| 9 | **Asset Maintenance Log** | Maintenance execution logs |
| 10 | **Asset Maintenance Team** | Technician team assignments |
| 11 | **Asset Shift Factor** | Shift-based depreciation adjustments |
| 12 | **Asset Shift Allocation** | Shift assignment to assets |
| 13 | **Asset Activity** | Activity logging for assets |
| 14 | **Asset Location** | Hierarchical location tree |
| 15 | **Asset Finance Book** | Per-finance-book depreciation configuration |
| 16 | **Asset Composite** | Group asset management (one record → multiple items) |

### 9.2 Reports (3 Reports)

- Asset Depreciation Ledger
- Asset Depreciations and Balances
- Fixed Asset Register

### 9.3 Dashboards

**Number Cards (3):** Total Assets, Assets in Use, Total Depreciation
**Dashboard Charts (3):** Category-wise Value, Depreciation Trend, Asset Status

---

## 10. Quality Management

### 10.1 Core Documents (16 DocTypes)

| # | Feature | Description |
|---|---------|-------------|
| 1 | **Quality Procedure** | Standard operating procedures (hierarchical tree) |
| 2 | **Quality Goal** | Measurable quality objectives with targets |
| 3 | **Quality Review** | Periodic review of quality goals |
| 4 | **Quality Action** | Corrective/Preventive actions (CAPA) |
| 5 | **Non Conformance** | Non-conformance records with root cause |
| 6 | **Quality Feedback** | Customer/internal feedback collection |
| 7 | **Quality Feedback Parameter** | Feedback measurement parameters |
| 8 | **Quality Feedback Template** | Reusable feedback forms |
| 9 | **Quality Meeting** | Meeting records with minutes |
| 10 | **Quality Meeting Agenda** | Meeting agenda items |
| 11 | **Quality Meeting Minutes** | Individual minutes entries |

### 10.2 Reports (1 Report)

- Quality Procedure Tree

### 10.3 Dashboards

**Number Cards (3):** Open Non Conformances, Pending Actions, Quality Reviews
**Dashboard Chart (1):** Quality Feedback Trends

---

## 11. Maintenance

### 11.1 Core Documents (5 DocTypes)

| # | Feature | Description |
|---|---------|-------------|
| 1 | **Maintenance Schedule** | Planned preventive maintenance schedules with item/serial tracking |
| 2 | **Maintenance Schedule Item** | Individual maintenance items with periodicity |
| 3 | **Maintenance Schedule Detail** | Scheduled maintenance dates |
| 4 | **Maintenance Visit** | On-site maintenance/service visit records |
| 5 | **Maintenance Visit Purpose** | Visit objectives and completion status |

### 11.2 Reports (1 Report)

- Pending Maintenance Schedules

---

## 12. Subcontracting

### 12.1 Core Documents (13 DocTypes)

| # | Feature | Description |
|---|---------|-------------|
| 1 | **Subcontracting BOM** | Dedicated BoM for subcontracting workflows |
| 2 | **Subcontracting Order** | Outward subcontracting — FG items, service items, raw material tracking |
| 3 | **Subcontracting Receipt** | Receipt of processed goods — raw material consumption, valuation |
| 4 | **Subcontracting Inward Order** | Inward job-work (company as subcontractor) — customer items, services |
| 5 | Child tables (9) | Order Items, Service Items, Supplied Items, Receipt Items, Inward Order Items/Received/Secondary/Service |

### 12.2 Dashboards

**Charts (1):** Subcontracting Order trends
**Number Cards (3):** Active Subcontracted Items, Inward Order Count, Outward Order Count

---

## 13. Setup & Organization

### 13.1 Core Organization (40 DocTypes)

| # | Feature | Description |
|---|---------|-------------|
| 1 | **Company** | Legal entity — CoA, warehouses, defaults, parent/subsidiary hierarchy |
| 2 | **Branch** | Physical office locations |
| 3 | **Department** | Organizational divisions (nested tree) |
| 4 | **Designation** | Job titles |
| 5 | **Employee** | Core personnel record — personal details, department, reporting manager, bank |
| 6 | **Employee Group** | Batch employee groups |
| 7 | **Customer Group** | Hierarchical customer segmentation tree |
| 8 | **Supplier Group** | Hierarchical supplier classification tree |
| 9 | **Territory** | Geographical sales territory tree |
| 10 | **Item Group** | Product catalog classification tree |
| 11 | **Sales Person** | Hierarchical sales team — commission, targets |
| 12 | **Sales Partner** | Channel partners — commission, referral codes, targets |
| 13 | **Brand** | Product brand master |
| 14 | **UOM** | Units of Measure |
| 15 | **UOM Conversion Factor** | Cross-unit conversion ratios |
| 16 | **Currency Exchange** | Daily FX rates |
| 17 | **Terms and Conditions** | Legal terms templates with Jinja2 support |
| 18 | **Incoterm** | International commercial terms (FOB, CIF, etc.) |
| 19 | **Holiday List** | Annual working calendar with weekly offs |
| 20 | **Global Defaults** | System-wide defaults (company, currency, country) |
| 21 | **Authorization Rule** | Transaction approval rules based on thresholds |
| 22 | **Party Type** | Dynamic party entity registry |
| 23 | **Email Digest** | Automated periodic financial/operational summaries |
| 24 | **Transaction Deletion Record** | Company transaction cleanup utility |
| 25 | **Driver / Vehicle** | Fleet management |

### 13.2 Setup Wizard

- Automated first-time provisioning: Company, CoA, Warehouses, Cost Centers, Fiscal Year
- Country-specific tax template generation
- Standard fixtures: UOMs, Currencies, Sales Stages, Industry Types, Designations

### 13.3 Workspaces

- **Home** — Default landing with P&L chart, Annual Sales/Purchase, Stock Value
- **ERPNext Settings** — Admin control room with links to all module settings

---

## 14. Banking (Dedicated App)

> Built as a modern SPA (React 19, Vite, Tailwind, Radix UI, TanStack, Jotai)

### 14.1 Features

| # | Feature | Description |
|---|---------|-------------|
| 1 | **Interactive Bank Reconciliation** | Split-view: unreconciled transactions ↔ matching vouchers, ranked by relevance |
| 2 | **Bank Account Carousel** | Visual bank selection with institution logo detection |
| 3 | **Real-Time Balance KPI** | ERP GL Balance vs Statement Closing Balance comparison |
| 4 | **In-line Transaction Actions** | Match & Reconcile, Record Payment, Create Bank Entry, Transfer Funds |
| 5 | **Automated Matching Rules** | Create/edit/evaluate regex/keyword rules for auto-classification |
| 6 | **AI/CV PDF Statement Importer** | Upload CSV or password-protected PDF with bounding-box visual extraction |
| 7 | **Action Log** | Session reconciliation audit with single-click undo |
| 8 | **Incorrectly Cleared Entries** | Auto-flag transactions with mismatched clearance dates |
| 9 | **Keyboard Shortcuts** | Power-user navigation |

---

## 15. Regional / Localization

### 15.1 Country-Specific Features

| # | Country/Region | Features |
|---|----------------|----------|
| 1 | **India** | TDS/TCS, Lower Deduction Certificates, GST |
| 2 | **Italy** | Full FatturaPA electronic invoicing (XML generation, digital signatures, SDI integration) |
| 3 | **UAE** | VAT 201 Return, Emirate-level accounts, FTA compliance, Tax Invoice formats |
| 4 | **South Africa** | VAT accounts and templates |
| 5 | **USA** | IRS 1099 vendor configuration, form generation |
| 6 | **Turkey** | Localized Chart of Accounts |
| 7 | **Australia** | GST setup |

### 15.2 DocTypes (5)

- Import Supplier Invoice, Lower Deduction Certificate, South Africa VAT Settings, UAE VAT Account, UAE VAT Settings

### 15.3 Reports (4)

- Electronic Invoice Register, IRS 1099, UAE VAT 201, VAT Audit Report

### 15.4 Print Formats (5)

- Detailed/Simplified Tax Invoice, IRS 1099 Form, Purchase E-Invoice, Tax Invoice

### 15.5 Address Templates

- Localized formats for: Bosnia, Croatia, Denmark, Germany, Luxembourg, Sweden, Switzerland, Taiwan, USA

---

## 16. Telephony & Communication

### 16.1 Telephony (5 DocTypes)

| # | Feature | Description |
|---|---------|-------------|
| 1 | **Call Log** | Inbound/outbound call tracking — caller, duration, status, recording URL, CRM links |
| 2 | **Incoming Call Settings** | Call routing configuration with schedules |
| 3 | **Incoming Call Handling Schedule** | Day/time routing windows |
| 4 | **Telephony Call Type** | Call categorization (Sales, Support, Consultation) |
| 5 | **Voice Call Settings** | User-level telephony config — device, greetings |

### 16.2 Communication (2 DocTypes)

| # | Feature | Description |
|---|---------|-------------|
| 1 | **Communication Medium** | Channel configuration (Voice, Email, Chat) |
| 2 | **Communication Medium Timeslot** | Day/time routing to employee groups |

---

## 17. Portal / E-Commerce

### 17.1 Features (2 DocTypes + Utils)

| # | Feature | Description |
|---|---------|-------------|
| 1 | **Website Attribute** | Item attributes as website catalog filters |
| 2 | **Website Filter Field** | Custom portal catalog filter fields |
| 3 | **Portal User Management** | Auto-assign Customer/Supplier roles, auto-create party records for portal registrations |

---

## 18. Integrations

### 18.1 Plaid Banking Integration

| # | Feature | Description |
|---|---------|-------------|
| 1 | **Plaid Settings** | API configuration — Client ID, Secret, Environment |
| 2 | **Plaid Connector** | Link tokens, access tokens, automatic hourly bank transaction sync |

### 18.2 Utilities

- Webhook HMAC signature verification
- Dynamic parcel tracking URL generation

---

## 19. EDI

### 19.1 DocTypes (2)

| # | Feature | Description |
|---|---------|-------------|
| 1 | **Code List** | Standard EDI code registries (UN/ECE, ISO, PEPPOL) |
| 2 | **Common Code** | Individual standardized codes linked to ERPNext records |

---

## 20. Bulk Transactions

### 20.1 DocTypes (2)

| # | Feature | Description |
|---|---------|-------------|
| 1 | **Bulk Transaction Log** | Virtual DocType — date-aggregated overview of bulk operations |
| 2 | **Bulk Transaction Log Detail** | Individual document conversion attempt logs with retry |

### 20.2 Features

- Async bulk document conversion (SO→SI, SO→DN, PO→PR, PO→PI)
- Database savepoint atomicity per document
- Failed transaction retry mechanism

---

## 21. Utilities

### 21.1 DocTypes (4)

| # | Feature | Description |
|---|---------|-------------|
| 1 | **Rename Tool** | Bulk record renaming via CSV upload |
| 2 | **Video** | Video content tracking (YouTube/Vimeo) with interaction stats |
| 3 | **Video Settings** | YouTube API credentials and tracking frequency |
| 4 | **Portal User** | Child table linking website users to parties |

### 21.2 Reports (1)

- YouTube Interactions

### 21.3 Web Forms (1)

- Addresses web form for portal users

---

## 22. HR & Payroll (HRMS — Separate App)

> [!WARNING]
> HR and Payroll were separated into a standalone `hrms` app in ERPNext v14. The reference codebase only contains stubs. Features below are sourced from web research and the user's screenshots.

### 22.1 Employee Management

| # | Feature | Description |
|---|---------|-------------|
| 1 | Employee Master | Personal details, employment history, education, bank accounts, emergency contacts |
| 2 | Employee Group | Batch grouping for operations |
| 3 | Employee Onboarding/Separation | Lifecycle workflows with checklists |
| 4 | Employee Promotion/Transfer | Career progression tracking |
| 5 | Employee Skill Map | Skills inventory and assessment |
| 6 | Employee Grievance | Internal grievance tracking |

### 22.2 Recruitment

| # | Feature | Description |
|---|---------|-------------|
| 1 | Job Opening | Position postings with requirements |
| 2 | Job Applicant | Application tracking |
| 3 | Job Offer | Offer letter generation |
| 4 | Staffing Plan | Workforce demand planning |
| 5 | Interview | Multi-round interview scheduling |
| 6 | Appointment Letter | Formal appointment generation |

### 22.3 Attendance & Shift Management

| # | Feature | Description |
|---|---------|-------------|
| 1 | Attendance | Daily attendance marking |
| 2 | Attendance Request | Self-service attendance correction |
| 3 | Employee Checkin | Biometric/manual check-in records |
| 4 | Shift Type | Shift definitions (day, night, flexible) |
| 5 | Shift Assignment | Employee-shift mapping |
| 6 | Shift Request | Self-service shift change requests |

### 22.4 Leave Management

| # | Feature | Description |
|---|---------|-------------|
| 1 | Leave Application | Leave requests with approval workflow |
| 2 | Leave Allocation | Annual leave balance allocation |
| 3 | Leave Type | Leave category definitions |
| 4 | Leave Policy | Policy templates per employee grade |
| 5 | Compensatory Leave Request | Overtime leave compensation |
| 6 | Leave Encashment | Leave balance cash-out |
| 7 | Leave Block List | Restricted leave periods |
| 8 | Holiday List | Company holiday calendar |

### 22.5 Payroll

| # | Feature | Description |
|---|---------|-------------|
| 1 | Salary Structure | Compensation framework with components |
| 2 | Salary Slip | Monthly pay computation |
| 3 | Payroll Entry | Batch salary processing |
| 4 | Salary Component | Earnings/deductions definitions |
| 5 | Additional Salary | One-time additional payments |
| 6 | Employee Tax Exemption | Tax saving declarations |
| 7 | Payroll Settings | Global payroll configuration |

### 22.6 Expense Claims & Loans

| # | Feature | Description |
|---|---------|-------------|
| 1 | Expense Claim | Employee reimbursement requests |
| 2 | Expense Claim Type | Expense categories |
| 3 | Employee Advance | Cash advance management |
| 4 | Loan Application | Employee loan requests |
| 5 | Loan | Loan disbursement and repayment tracking |

### 22.7 Performance

| # | Feature | Description |
|---|---------|-------------|
| 1 | Appraisal | Employee performance evaluations |
| 2 | Appraisal Template | Evaluation criteria templates |
| 3 | Goal | Individual/team goal setting |
| 4 | KRA (Key Result Area) | Performance measurement areas |

### 22.8 Training

| # | Feature | Description |
|---|---------|-------------|
| 1 | Training Program | Training course definitions |
| 2 | Training Event | Scheduled training sessions |
| 3 | Training Result | Participant completion records |
| 4 | Training Feedback | Post-training evaluations |

### 22.9 HR Reports (from user screenshot)

- Monthly Attendance Sheet / Recruitment Analytics
- Employee Analytics / Employee Information / Employee Birthday
- Employee Leave Balance / Leave Balance Summary
- Employee Advance Summary / Employee Exits
- Employees Working on a Holiday / Daily Work Summary Replies

---

## 23. Cross-Cutting Architecture (Controllers)

> These are the base classes and engines that power ALL transactional documents across modules.

### 23.1 Core Controller Classes (19 files)

| # | Controller | Purpose |
|---|-----------|---------|
| 1 | **AccountsController** | GL Entry generation, currency exchange, payment terms, advances, tax withholding, deferred accounting |
| 2 | **BuyingController** | Supplier pricing, purchase tax calc, landed cost, item valuation |
| 3 | **SellingController** | Customer pricing rules, commissions, shipping rules, packing lists |
| 4 | **StockController** | SLE reposting, valuation (FIFO/Moving Avg), serial/batch, perpetual inventory GL |
| 5 | **SubcontractingController** | BOM explosion, raw material reservations, vendor transfers, scrap, service cost capitalization |
| 6 | **Taxes and Totals Engine** | Centralized tax calculation — line-item taxes, compound/cumulative, discounts, shipping, multi-currency, rounding |
| 7 | **Budget Controller** | Budget validation against Cost Centers/Projects |
| 8 | **Status Updater** | % billed/delivered/ordered/received across transaction pipelines |
| 9 | **Sales and Purchase Return** | Credit/Debit Note business logic |
| 10 | **Item Variant Engine** | Variant generation and attribute combination |
| 11 | **Ledger Preview** | Simulates GL and Stock entries before submission |
| 12 | **Trends Engine** | Base analytical engine for periodic trend reports |

---

## Summary Statistics

| Category | Count |
|----------|-------|
| **Total Modules** | 21 core + HRMS + Banking App |
| **Total DocTypes** | ~400+ |
| **Total Reports** | ~160+ |
| **Total Dashboard Charts** | ~50+ |
| **Total Number Cards** | ~40+ |
| **Total Interactive Pages** | 12+ |
| **Total Print Formats** | 80+ |
| **Total Workspaces** | 15+ |

---

> [!CAUTION]
> **The AI Native ERP rebuild currently implements only a fraction of these features.** Key gaps identified include: comprehensive Accounts module (POS, banking, subscriptions, shares, budgeting), full Selling cycle (proforma invoices, product bundles, installation notes), Supplier Scorecard system, complete Stock management (serial/batch bundles, putaway rules, stock reservation, 52 reports), Manufacturing MES/scheduling, CRM (contracts, appointments, campaigns), Support SLA system, Assets depreciation, Quality Management, HR/Payroll (entire module), and all Regional/Localization features.
