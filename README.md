# AI-Native Multi-Agent ERP

Enterprise Resource Planning system with durable operational workflows and tenant-scoped business data.

## Architectural Overview

- **Transactional Core**: PostgreSQL 16 (with Row Level Security and `pgvector`)
- **Event Publishing**: Optional Redpanda/Kafka producer with Transactional Outbox integrations; consumer-driven agent execution is not currently enabled
- **Deterministic Ledger Engine**: Double-entry invariant validation firewall (`SUM(debits) == SUM(credits)`) with monetary autonomy ceilings
- **Multi-Tenancy**: Built-in tenant isolation with `tenant_id` on all operational and ledger entities
- **Immutable Audit**: Cryptographic SHA-256 hash chaining of all operational proposals and agent mutations
- **API Shell**: Async FastAPI service with OpenAPI specification

## Railway deployment

For the backend service, set `ENVIRONMENT=production`, `DEBUG=False`, a unique
`SECRET_KEY`, a unique `WEBHOOK_SIGNING_SECRET`, and `DATABASE_URL` to Railway's
PostgreSQL connection URL. Set `CORS_ALLOWED_ORIGINS` to a JSON list containing
the deployed frontend origin, for example `["https://your-app.vercel.app"]`.
If it is unset, the backend starts with browser access blocked until an origin
is configured. A separate
`POSTGRES_PASSWORD` is optional when that URL already contains a non-default
database password. Do not include a trailing slash or wildcard origin unless
it is part of the actual frontend origin.

## Quickstart

### 1. Configure local environment and start infrastructure
```bash
cp .env.example .env
# Replace the sample PostgreSQL password in .env and both database URLs with a unique local password.
docker compose up -d
```

### 2. Environment Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 3. Run Migrations & Seed Data
```bash
alembic upgrade head
python scripts/seed_chart_of_accounts.py
```

### 4. Start Application
```bash
uvicorn erp.main:app --reload --port 8000
```

DAG workflows are persisted in `dag_execution_records` and can be inspected through the tenant-scoped `GET /api/v1/workflows` endpoints. If a process stops during a workflow, startup marks it `RECOVERY_REQUIRED`. A Finance user or tenant admin can request recovery through `POST /api/v1/workflows/{workflow_id}/recover` with an audit note; the service retries only allowlisted safe nodes and leaves customer order creation or external communication nodes held for review. Customer invoice terms are configurable in days and default to 30.

Recruitment screening is available from `/recruitment`. It stores tenant-scoped job openings and extracted resume text (the uploaded PDF/DOCX binary is discarded), and can generate explainable, evidence-checked screening recommendations and interview email drafts for recruiter review. Screening sends extracted resume text, with email addresses and phone numbers redacted, to the configured LLM provider; configure a provider only when authorized to process candidate data there. AI screening is a decision-support aid only: it does not make hiring decisions, automatically reject applicants, or send email. Recruiters can delete an application and its extracted resume text from the recruitment screen. Configure `LLM_PROVIDER` and its matching API key (`OPENROUTER_API_KEY` or `GEMINI_API_KEY`) to enable screening and draft generation. If the provider remains `openrouter` but only `GEMINI_API_KEY` is configured, recruitment screening automatically uses Gemini. When both keys exist, `LLM_PROVIDER` determines which one is used. Missing model configuration is reported rather than replaced with fabricated results. Apply Alembic migrations through `015_hr_recruitment` to create the recruitment tables.

The retired autonomous supervisor and agent approval-queue tables are removed by migration `014_remove_autonomous_workforce_and_hitl`. Applying it deletes existing supervisor run, communication, and approval-queue history. Financial transaction authorization and audit safeguards remain in place.

Event consumer execution remains disabled until domain handlers are registered. When a consumer is configured, handling attempts and outcomes are persisted; tenant admins can inspect and mark dead-letter events reviewed through `/api/v1/events/dead-letters`. Review records do not replay the event.

Transactional outbox publishing is also disabled by default. To publish committed outbox rows to Kafka, configure `KAFKA_BOOTSTRAP_SERVERS`, set `ENABLE_OUTBOX_DISPATCHER=True`, and restart the API. Each outbox event is published to a topic named by its `event_type`; consumers must deduplicate by the stable `event_id` because a process crash after broker acknowledgement can cause a retry. The dispatcher stays stopped when Kafka is unavailable, and the readiness response reports its state.

### 5. Run Test Suite
```bash
pytest tests/ -v
```
