#!/usr/bin/env bash
set -e

echo "============================================================"
echo "  Starting AI-Native ERP Backend Container"
echo "============================================================"

# 1. Run database migrations
echo "[1/2] Running database schema migrations (Alembic)..."
alembic upgrade head || {
  echo "Alembic upgrade warning. Attempting fallback table initialization..."
  python -c "
import asyncio
from erp.db.engine import async_engine
from erp.db.models.base import Base
import erp.db.models

async def init():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

asyncio.run(init())
print('Tables initialized via fallback.')
" || echo "Database init warning (non-fatal if database is already provisioned)."
}

# 2. Start Uvicorn server
PORT="${PORT:-8000}"
WORKERS="${WEB_CONCURRENCY:-2}"

echo "[2/2] Launching Uvicorn ASGI Server on port ${PORT} with ${WORKERS} worker(s)..."
exec uvicorn erp.api.app:app \
  --host 0.0.0.0 \
  --port "${PORT}" \
  --workers "${WORKERS}" \
  --proxy-headers \
  --forwarded-allow-ips "*"
