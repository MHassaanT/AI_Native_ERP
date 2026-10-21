# Phase D Completion Report: Payroll & Assets Enhancements

**Plan phase:** Phase D — Payroll & Assets Enhancements  
**Plan reference:** `docs/erpnext_modules_implementation_plan.md`  
**Status:** Implemented; database migration has not been applied to a live database.

## Executive summary

Phase D adds the planned payroll tax, period, one-time compensation, retention bonus, maintenance team, and asset revaluation workflows. Tax withholding now derives from tenant-configured annual progressive brackets and is recorded separately on each salary slip. Additional salary and vested retention bonus items flow into generated slips and are linked back to their source records. Asset maintenance teams can contain employee members, and carrying-value adjustments produce balanced general-ledger entries and refresh unposted depreciation schedules.

The work includes migration `035_payroll_assets_enhancements`, API endpoints, workflow logic, and controls in the existing `/workforce` payroll tab and `/assets` page.

## Plan checklist

| Item | Implementation |
|---|---|
| D1 — `IncomeTaxSlab` + rates | Added tenant-scoped slab and progressive rate band models, create/list API, date/currency matching, and band validation. |
| D2 — `PayrollPeriod` | Added period create/list/close API, overlap rejection, and a closed-period guard during slip generation. Exact matching open periods are linked to slips. |
| D3 — `AdditionalSalary` | Added queued one-time earnings or deductions, taxable flag, payroll-date matching, slip linking, and submitted-slip settlement status. |
| D4 — `RetentionBonus` | Added employee bonus records with vesting date and taxable flag; due items become earning lines on matching slips. |
| D5 — Income tax in slips | Added annualized monthly taxable earnings computation, progressive marginal band calculation, monthly withholding, slip field, and deduction line. |
| D6 — `AssetMaintenanceTeam` + members | Added tenant-scoped team and member models, create/list APIs, and maintenance page controls. |
| D7 — `AssetValueAdjustment` | Added before/after audit record, revaluation endpoint, balanced gain/loss journal, carrying value update, and future depreciation schedule refresh. |

## Implementation deep dive

### Payroll domain and calculation behavior

- `IncomeTaxSlab` stores a tax-year label, currency, effective date range, and active flag. `IncomeTaxSlabRate` stores each lower/upper threshold, marginal rate, and cumulative fixed tax at that threshold.
- Slab creation validates that bands begin at zero, are contiguous and non-overlapping, and end with an uncapped band. It also rejects inverted effective dates and malformed band bounds.
- On slip generation, the service chooses the active slab effective on the posting date whose currency matches the assigned salary structure. Taxable earning components and taxable additional earnings/bonuses form taxable monthly pay. The service annualizes that amount by multiplying by 12, finds the highest applicable bracket, applies its cumulative base tax plus marginal rate above the bracket threshold, then withholds one-twelfth of the result.
- The computed withholding is recorded in `SalarySlip.income_tax`, included in `total_deductions`, and added as a named deduction item. Configured salary components with tax codes (`TAX`, `INCOME-TAX`, or `INCOME_TAX`) are skipped when a matching slab is active to avoid duplicate withholding.
- Payroll periods cannot overlap another open period. A period is linked to a slip when its dates exactly match the generated slip range. Closing an exact matching period prevents further slip generation for that range.
- Pending additional salary records whose payroll date falls inside the slip range are added once as earning or deduction lines. Retention bonuses are added when the vesting date falls inside the range. Both records are linked to the generated slip; successful slip submission marks linked records paid.

### Asset workflows

- Maintenance teams store a name, description, active state, and employee membership rows with optional roles. Team creation rejects blank names and duplicate employees in a team.
- Revaluation requires a live asset, a reason, and a non-negative target book value no lower than accumulated depreciation. A no-op value change is rejected.
- The adjustment record captures previous value, new value, signed delta, date, reason, status, and journal transaction. Positive adjustments debit the fixed asset account and credit revaluation gain; negative adjustments debit revaluation loss and credit the fixed asset account.
- The asset carrying value and gross asset amount move by the signed adjustment while accumulated depreciation remains unchanged. Unposted future depreciation rows are recalculated from the adjusted book value using the asset category’s method; posted schedule rows are retained.

### User interface

- `/workforce` payroll tab now provides tax slab configuration, payroll period creation and closure, one-time additional pay, retention bonus entry, queued item counts, and an income-tax column on salary slips.
- `/assets` now includes a Maintenance & Value tab for team creation and adjustment history. Asset detail includes a value adjustment form alongside existing lifecycle actions.
- The API client includes wrappers for all new payroll and asset endpoints.

## Migration and touched areas

- Added Alembic revision `035_payroll_assets_enhancements.py`, following `034_hr_deep_workflows`.
- Extended payroll and asset ORM models and registered the new model exports.
- Extended payroll and asset routes and workflow services.
- Updated `frontend/src/lib/api.ts`, `frontend/src/app/workforce/page.tsx`, and `frontend/src/app/assets/page.tsx`.

The migration creates tax slab/rate, payroll period, additional salary, retention bonus, maintenance team/member, and asset value adjustment tables; adds `income_tax` and `payroll_period_id` to salary slips; and adds tenant indexes, uniqueness constraints, status checks, and monetary/date checks.

## Frictions and decisions

1. **Tax policy is tenant-configured rather than embedded.** The implementation avoids assuming a jurisdiction’s tax brackets. Each tenant configures thresholds, rates, and cumulative base tax. The current UI supplies USD as the slab currency and accepts rate bands as JSON; additional currencies can be created through the API.
2. **Tax withholding follows the existing monthly payroll model.** Taxable earnings are annualized as monthly taxable pay × 12 and annual tax is divided by 12. This matches the existing monthly batch payroll assumption; other payroll frequencies do not yet prorate withholding by their actual period count.
3. **One-time additions are consumed at slip generation.** They are marked included/earned and linked to a draft slip to prevent duplicate generation. A cancellation/reversal workflow for a draft slip is outside this phase, so operators should correct a draft through the existing payroll lifecycle before attempting to regenerate the same period.
4. **Asset revaluation changes future depreciation schedules.** The implementation updates unposted schedules, retaining posted history. Full prospective schedule policy may vary by accounting jurisdiction, so schedule treatment should be confirmed for deployments using specialized revaluation accounting.
5. **The full migration chain has a pre-existing offline-generation blocker.** `alembic upgrade head --sql` stops in legacy revision `002_multi_tenant_auth_and_certs.py`, which calls SQLAlchemy inspection on Alembic’s offline mock connection. The Phase D migration itself was invoked directly under PostgreSQL offline operations and generated SQL successfully. No live migration was applied.
6. **ORM configuration exposed an incomplete relationship in the preceding HR phase.** `LeavePolicy.details` referred to `LeavePolicyDetail.policy`, but the reverse relationship was missing. I added the matching relationship so full ORM mapper configuration succeeds; this is a small prerequisite repair discovered while checking the new payroll model graph.

## Verification performed

- `python3 -m py_compile` succeeded for all changed Python models, routes, services, and the new migration.
- `frontend/node_modules/.bin/tsc --noEmit` completed successfully.
- `git diff --check` completed successfully.
- `alembic history --verbose` confirmed `035_payroll_assets_enhancements` is the migration head and follows revision 034.
- SQLAlchemy `configure_mappers()` succeeded for the complete registered model set after repairing the HR policy reverse relationship.
- Direct PostgreSQL offline generation of the Phase D migration succeeded and produced 23 SQL statements.
- No integration tests or live database migration were run.

## Remaining limits

- Tax rules are intentionally configurable and require the tenant to enter jurisdiction-approved rates and tax-year dates.
- The payroll UI’s rate-band editor is JSON-based; it validates server-side but does not yet provide a visual bracket builder.
- The asset team UI accepts an optional employee UUID for membership rather than loading an employee picker.
- Cross-currency payroll tax conversion and non-monthly annualization are not included.
- General-ledger entries use the existing account-code conventions; deployments must ensure the revaluation gain/loss accounts are present in their chart of accounts.
