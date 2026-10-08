# AI-Native Multi-Agent ERP

Multi-Agent System (MAS) Enterprise Resource Planning architecture with opt-in interval agent scheduling.

## Architectural Overview

- **Transactional Core**: PostgreSQL 16 (with Row Level Security and `pgvector`)
- **Event Publishing**: Optional Redpanda/Kafka producer with Transactional Outbox integrations; consumer-driven agent execution is not currently enabled
- **Deterministic Ledger Engine**: Double-entry invariant validation firewall (`SUM(debits) == SUM(credits)`) with monetary autonomy ceilings
- **Multi-Tenancy**: Built-in tenant isolation with `tenant_id` on all operational and ledger entities
- **Immutable Audit**: Cryptographic SHA-256 hash chaining of all operational proposals and agent mutations
- **API Shell**: Async FastAPI service with OpenAPI specification

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

Interval scheduling is disabled by default. To run agents automatically, set `ENABLE_AGENT_SCHEDULER=True` in `.env`, restart the API, then activate only the tenant agents you intend to run from the Agents page. New agent definitions are provisioned inactive. The current scheduler supports interval schedules; cron and event-driven execution are not enabled by this worker.

DAG workflows are persisted in `dag_execution_records` and can be inspected through the tenant-scoped `GET /api/v1/agents/dags` endpoints. If a process stops during a workflow, startup marks it `RECOVERY_REQUIRED`. A Finance user or tenant admin can request recovery through `POST /api/v1/agents/dags/{dag_id}/recover` with an audit note; the service retries only allowlisted safe nodes and leaves customer order creation or external communication nodes held for review. Customer invoice terms are configurable in days and default to 30.

Event consumer execution remains disabled until domain handlers are registered. When a consumer is configured, handling attempts and outcomes are persisted; tenant admins can inspect and mark dead-letter events reviewed through `/api/v1/events/dead-letters`. Review records do not replay the event.

Transactional outbox publishing is also disabled by default. To publish committed outbox rows to Kafka, configure `KAFKA_BOOTSTRAP_SERVERS`, set `ENABLE_OUTBOX_DISPATCHER=True`, and restart the API. Each outbox event is published to a topic named by its `event_type`; consumers must deduplicate by the stable `event_id` because a process crash after broker acknowledgement can cause a retry. The dispatcher stays stopped when Kafka is unavailable, and the readiness response reports its state.

### 5. Run Test Suite
```bash
pytest tests/ -v
```
