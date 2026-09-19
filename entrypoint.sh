#!/usr/bin/env bash
set -e

echo "============================================================"
echo "  Starting AI-Native ERP Backend Container"
echo "============================================================"

# 1. Run database migrations and ensure all tables exist
echo "[1/3] Running database schema migrations (Alembic)..."
alembic upgrade head || echo "Alembic upgrade warning (will verify tables via ORM)."

echo "[2/3] Verifying and synchronizing all ORM tables..."
python -c "
import asyncio
from erp.db.engine import async_engine
from erp.db.models.base import Base
import erp.db.models

async def init():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

asyncio.run(init())
print('PostgreSQL ORM tables verified and synchronized.')
" || echo "Warning: Table sync encountered an issue, proceeding..."


# 2. Start Uvicorn server & dual-port bridge
PORT="${PORT:-8080}"
WORKERS="${WEB_CONCURRENCY:-1}"

# If socat is available, bridge 8000 and 8080 so both ports answer requests seamlessly
if command -v socat >/dev/null 2>&1; then
  if [ "$PORT" = "8080" ]; then
    socat TCP-LISTEN:8000,fork,reuseaddr TCP:127.0.0.1:8080 &
  elif [ "$PORT" = "8000" ]; then
    socat TCP-LISTEN:8080,fork,reuseaddr TCP:127.0.0.1:8000 &
  fi
fi

echo "[3/3] Launching Uvicorn ASGI Server on port ${PORT} with ${WORKERS} worker(s)..."
exec uvicorn erp.api.app:app \
  --host 0.0.0.0 \
  --port "${PORT}" \
  --workers "${WORKERS}" \
  --proxy-headers \
  --forwarded-allow-ips "*"
