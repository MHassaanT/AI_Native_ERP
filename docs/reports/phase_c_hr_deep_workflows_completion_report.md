# Phase C Completion Report: HR Deep Workflows

**Plan:** `docs/erpnext_modules_implementation_plan.md`  
**Phase:** C — HR Deep Workflows (C1–C13)  
**Status:** Source implementation complete; migration and database-backed behavior require a configured runtime  
**Date:** October 21, 2026

## Summary

Phase C extends the existing HR foundation with recruitment planning and interview tracking, employee grades and lifecycle changes, confidential grievances, full-and-final settlement, daily work summaries and replies, leave policies/block lists/compensatory leave, six HR reports, and a recruitment funnel dashboard. The implementation adds 20 tables (the plan estimates roughly 17; the additional `LeavePolicyAssignment` table is needed to record policy assignments separately from the generated leave allocations) and links Employee records to grades.

The work includes tenant-scoped APIs in the existing HR router, purpose-specific approval/calculation actions, UI sections in `/workforce` and `/recruitment`, and a standalone `/full-and-final` workflow page.

## Completion by plan item

| Item | Implementation |
|---|---|
| **C1 Staffing Plan** | Added `StaffingPlan` and `StaffingPlanDetail` with fiscal year, workflow status, department/designation planning rows, and nonnegative headcount constraints. CRUD is available in the Recruitment Staffing & Interviews section. |
| **C2 Interview lifecycle** | Added `InterviewRound`, `Interview`, and `InterviewFeedback`. Interviews link to same-tenant applications, rounds, and interviewers; include schedule, duration, status, outcome, and location; feedback carries a bounded 0–5 rating and recommendation. |
| **C3 Recruitment Analytics** | Added `/hr/recruitment/analytics` and a Recruitment Analytics section showing open roles, applications, evaluated applications, and interview status/outcome totals. |
| **C4 Employee Grade** | Added `EmployeeGrade` with unique tenant grade code and validated optional salary bands. Employee now has a nullable grade reference; the employee information report includes grade name. |
| **C5 Promotion** | Added promotion history with from/to designation and grade, effective date, reason, status, and approver. Approval checks current snapshot values; approved promotions update the employee immediately when effective, while future-dated changes remain recorded for later application. |
| **C6 Transfer** | Added department and reporting-manager transfer history with approval. Approval checks the prior department and updates the employee immediately for effective transfers. |
| **C7 Grievance** | Added tenant-managed `GrievanceType` and `EmployeeGrievance`, with priority, ownership, resolution, confidentiality flag, and status. Grievance list/write access is restricted to `TENANT_ADMIN` and `HR_MANAGER`. |
| **C8 Full & Final** | Added statement headers and earning/deduction lines. Recalculation derives totals and net payable from line items; submission and HR Manager approval advance the state; marking paid requires all separation checklist tasks complete and closes the separation while setting the employee to `LEFT` / inactive. |
| **C9 Daily Work Summary** | Added employee/day summaries and employee replies. A tenant-unique employee/date key prevents duplicate daily summaries. |
| **C10 Leave Policy** | Added `LeavePolicy`, detail rows, and assignment records. The bulk assignment action checks selected active employees and creates annual `LeaveAllocation` records for configured leave types. |
| **C11 Leave Block List** | Added block-list headers and dates, with optional leave-type and department scope. Leave application submission now rejects requests overlapping an active applicable block-list date. |
| **C12 Compensatory Leave** | Added requests with a maximum two-day amount, unique employee/work date, and approval. Approval requires a same-tenant PRESENT or HALF_DAY attendance record on the stated work date. |
| **C13 HR Reports** | Added Exits, Birthdays, Employee Information, HR Analytics, Leave Balance Summary, and Holiday Workers endpoints and a report viewer in Workforce. |

## Data model and migration

Added `src/erp/db/models/hr_deep.py` and registered its entities in `src/erp/db/models/__init__.py`. New tables are:

- `staffing_plans`, `staffing_plan_details`
- `interview_rounds`, `interviews`, `interview_feedback`
- `employee_grades`, `employee_promotions`, `employee_transfers`
- `grievance_types`, `employee_grievances`
- `full_and_final_statements`, `full_and_final_statement_items`
- `daily_work_summaries`, `daily_work_summary_replies`
- `leave_policies`, `leave_policy_details`, `leave_policy_assignments`
- `leave_block_lists`, `leave_block_list_dates`, `compensatory_leave_requests`

Migration `034_hr_deep_workflows.py` follows `033_buying_selling_enhancements.py`. It adds tenant indexes, foreign keys, uniqueness constraints, status/range checks, and `employees.employee_grade_id`. Interview-to-application uses a composite tenant FK, preventing cross-tenant references at the database layer. APIs also check tenant ownership for other connected records.

## API and workflow details

The existing `/hr` router now includes tenant-scoped generic list/create/update/delete routes under `/hr/deep/{resource}` for all Phase C entities. Input coercion handles UUIDs, ISO dates, timezone-aware datetimes, and `Decimal` values; system fields and primary keys cannot be set. Connected record references are validated against the current tenant.

Specific workflow actions provide behavior beyond record CRUD:

- `POST /hr/deep/leave-policy-assignments/apply` assigns one active policy to selected active employees and creates matching leave allocations for the chosen year. Duplicate allocation or assignment conflicts are rejected.
- Existing `POST /hr/leaves/applications` checks active block lists before creating a request.
- Promotion and transfer approval endpoints verify HR Manager access, same-tenant approver and employee records, and current from-state before changing the employee record.
- Compensatory leave approval checks attendance and HR Manager access.
- Full-and-final endpoints recalculate, submit, approve, and mark paid. Generic CRUD cannot directly change protected workflow statuses or settlement totals.
- Marking a settlement paid checks the separation checklist, completes separation, and marks the employee inactive/LEFT.
- Confidential grievance records and approval/settlement actions require `TENANT_ADMIN` or `HR_MANAGER`.

The six HR report routes are `/hr/reports/exits`, `/birthdays`, `/employee-information`, `/analytics`, `/leave-balance-summary`, and `/holiday-workers`. The recruitment funnel summary is `/hr/recruitment/analytics`.

## Frontend

- Added **Staffing & Interviews** and **Recruitment Analytics** sections to `/recruitment`; the existing candidate screening experience remains under its own section.
- Added **HR Workflows & Reports** to `/workforce`, with record management for Phase C resources and a report selector/table.
- Added `/full-and-final` with statement and item management plus recalculate, submit, approve, and mark-paid actions.
- Added the Full & Final Settlement route to the sidebar.

The HR workbench is a shared record editor. Foreign-key fields are UUID inputs, so users need to copy IDs from the related records. The leave policy assignment screen accepts a list of employee UUIDs.

## Frictions, design choices, and known limits

1. **Table count differs from the estimate.** The plan says “~17 new tables,” but its listed parent/detail entities total 19 tables. `LeavePolicyAssignment` was added as a twentieth table because an assignment record and its generated entitlements have different lifecycles.
2. **The leave calendar is implicit.** There is no Leave Period or tenant Holiday Calendar entity in the Phase C checklist. Policy assignment therefore uses January 1–December 31 for the selected fiscal year, and the Holiday Workers report requires the caller to provide the date being treated as a holiday. A tenant-specific fiscal/holiday calendar should replace these assumptions before broader use.
3. **Policy assignment is explicit-user selection.** Bulk assignment accepts employee IDs; filtering or automatic assignment by grade/department is not implemented. Carry-forward limit is stored on policy detail, while initial allocations begin with zero carried days; calculation of actual carry-forward from prior years is a separate workflow.
4. **Future lifecycle changes need a scheduler.** Approved promotions/transfers update the current employee when effective immediately. Future-dated records are retained as approved history, but no scheduled job applies them on their effective date.
5. **Full & Final does not post payment accounting.** The statement calculates a net figure and records workflow status. Marking paid updates HR exit state but does not create a payroll disbursement, bank transaction, or GL entry.
6. **Recruitment funnel semantics are limited by existing candidate statuses.** The dashboard counts READY/EVALUATED applications and interview outcomes; it does not yet model offer, hire, or rejection transitions on CandidateApplication.
7. **Verification environment lacks SQLAlchemy.** Python syntax and TypeScript checks are available, but ORM metadata import, migration upgrade/downgrade, PostgreSQL constraint behavior, and database-backed workflows cannot be verified in this checkout.

## Validation performed

- `python3 -m py_compile` over changed HR models, model registration, HR routes, and migration — **passed**.
- `frontend/node_modules/.bin/tsc --noEmit -p frontend/tsconfig.json` — **passed**.
- `git diff --check` — **passed**.
- Alembic migration and PostgreSQL workflow verification — **not run**; SQLAlchemy is not installed in the active environment.
- Pytest suite and frontend production build — **not run**.

## Remaining verification before production use

Apply and downgrade migration `034` on PostgreSQL. Then verify cross-tenant references, staffing/interview CRUD, policy assignment rollback when one employee conflicts, block-list date boundaries, promotion and transfer snapshots, concurrent settlement approvals, outstanding separation tasks, compensatory leave attendance requirements, and all six report filters. Define tenant leave periods and holiday calendars, add scheduled application of future lifecycle changes, connect settlement payment to payroll/accounting, and align HR authorization with the organization’s final role model.
