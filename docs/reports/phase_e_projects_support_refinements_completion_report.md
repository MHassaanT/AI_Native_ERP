# Phase E Completion Report: Projects & Support Refinements

**Plan phase:** Phase E — Projects & Support Refinements  
**Plan reference:** `docs/erpnext_modules_implementation_plan.md`  
**Status:** Implemented; the migration has not been applied to a live database.

## Summary

Phase E completes the missing project classification, activity costing, progress update, and support reporting workflows. Project updates were already represented by a `ProjectUpdate` model, but there was no project API or UI to create or review them. Projects now expose a dated update timeline and allow users to record progress and blockers. Activity types and effective-dated rates can be configured and used when logging timesheets. The CRM/support workspace now includes workload, SLA, and warranty report views backed by tenant-scoped endpoints.

## Plan checklist

| Item | Implementation |
|---|---|
| E1 — `ProjectType` | Added tenant-scoped project type master, create/list endpoints, project assignment, and a selector in project creation. |
| E2 — Project Update UI & Activity Timeline | Added create/list integration for existing `ProjectUpdate` records, update history in project details, and manual progress/blocker reporting. |
| E3 — `ActivityType` + `ActivityCost` | Added activity master and effective-dated rates, endpoints and a Projects page configuration tab. Timesheet entry can select an activity and use its matching rates. |
| E4 — Support Reports | Added overview and SLA-performance endpoints plus a Support Reports tab in the CRM page showing tickets, priorities, statuses, response/resolution measures, breaches, and warranty claims. |

## Implementation details

### Project types and updates

- `ProjectType` is a tenant-scoped master with a unique name, description, and active flag. Projects can optionally reference a type. Project creation checks that a selected type is active and belongs to the current tenant.
- `POST /projects/{project_id}/updates` records sender email, progress percentage, notes, blockers, and timestamp. Progress is constrained to 0–100. The service updates the project’s progress and most recent summary; a 100% update marks the project complete, and lowering a previously completed project below 100% returns it to in-progress.
- Project detail responses include update history ordered newest first. The project drawer displays an activity timeline and form for recording new updates.

### Activity types and costs

- `ActivityType` is a tenant-scoped activity catalog.
- `ActivityCost` stores billing and costing rates with effective dates and optional employee scope. Timesheet logging resolves an employee-specific rate first, then a default activity rate, when explicit rates are not sent.
- `Timesheet.activity_type_id` is nullable so existing records and older clients can continue using the existing free-text `activity_type`. New activity selections retain the activity name in that legacy field while recording the normalized ID.
- The Projects page adds a configuration tab to create project/activity types and default rates. The timesheet form uses configured activity types and rates when available.

### Support reports

- `GET /support/reports/overview` reports issue counts by status and priority, open ticket count, current open SLA breach count, average first-response and resolution hours, average age of open tickets, and warranty claim counts by status.
- `GET /support/reports/sla` groups response and resolution samples and deadline breaches by priority.
- Both endpoints accept optional inclusive `from_date` and `to_date` filters. The CRM Support Reports tab displays these results for the current all-time range.
- Response and resolution durations are elapsed wall-clock hours from ticket creation. Open-ticket SLA breach counts are evaluated against current time; closed ticket breach counts in the SLA report use their recorded response/resolution timestamps.

## Schema and files

- Added Alembic revision `036_projects_support_refinements.py` after Phase D revision 035.
- Added `project_types`, `activity_types`, and `activity_costs` tables; added nullable `projects.project_type_id` and `timesheets.activity_type_id` foreign keys.
- Extended project ORM registration, project services, project routes, and support routes.
- Updated `frontend/src/lib/api.ts`, `frontend/src/app/projects/page.tsx`, and `frontend/src/app/crm/page.tsx`.
- No new support tables were needed; support reports aggregate the existing issue and warranty claim records.

## Frictions and implementation decisions

1. **Project updates had storage but no workflow.** The pre-existing `ProjectUpdate` table was not connected to the project service, API, or page. The new endpoints reuse it, so this work does not duplicate update history or require a migration for that table.
2. **Timesheets used a free-text activity label.** To preserve older entries and clients, the implementation adds a nullable activity ID rather than replacing the existing label. Existing rows remain unlinked until edited; new entries can use effective-dated activity rates.
3. **Rate fallback preserves the old entry flow.** Explicit timesheet rates still work. If no explicit rate is sent, the service looks for an employee-specific rate and then an activity default; if no configured rate exists, it retains the previous 100 billing / 50 costing defaults.
4. **Support timing is elapsed time.** The reports measure ordinary elapsed hours; SLA business calendars, holiday schedules, and business-hour pauses are not modeled in this phase.
5. **Full-chain offline migration generation still has a legacy blocker.** The existing revision 002 calls SQLAlchemy inspection on Alembic’s offline mock connection. Revision 036 itself generated PostgreSQL SQL directly (13 statements), and Alembic history recognizes it as head. No database migration was applied.

## Verification performed

- Python compilation succeeded for the updated models, project/support routes, project workflow, and migration.
- SQLAlchemy `configure_mappers()` succeeded for the registered ORM model set.
- `frontend/node_modules/.bin/tsc --noEmit` completed successfully.
- `git diff --check` completed successfully.
- `alembic history --verbose` confirmed revision 036 follows revision 035 and is the current head.
- Direct PostgreSQL offline generation of revision 036 succeeded and produced 13 SQL statements.
- No integration tests or live database migration were run.
