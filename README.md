# AI-Native Multi-Agent ERP

Autonomous, event-driven Multi-Agent System (MAS) Enterprise Resource Planning architecture.

## Architectural Overview

- **Transactional Core**: PostgreSQL 16 (with Row Level Security and `pgvector`)
- **Event Streaming**: Redpanda (Kafka API compatible) with Transactional Outbox pattern
- **Deterministic Ledger Engine**: Double-entry invariant validation firewall (`SUM(debits) == SUM(credits)`) with monetary autonomy ceilings
- **Multi-Tenancy**: Built-in tenant isolation with `tenant_id` on all operational and ledger entities
- **Immutable Audit**: Cryptographic SHA-256 hash chaining of all operational proposals and agent mutations
- **API Shell**: Async FastAPI service with OpenAPI specification

## Quickstart

### 1. Start Infrastructure
```bash
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

### 5. Run Test Suite
```bash
pytest tests/ -v
```
