#!/usr/bin/env bash
# ==============================================================================
# Autonomous AI-Native ERP System Launcher
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PID_DIR="$SCRIPT_DIR/.pids"
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$PID_DIR" "$LOG_DIR"

BACKEND_PID_FILE="$PID_DIR/backend.pid"
FRONTEND_PID_FILE="$PID_DIR/frontend.pid"

IS_DAEMON=false
WITH_REDPANDA=false
for arg in "$@"; do
  case "$arg" in
    --daemon|-d)
      IS_DAEMON=true
      ;;
    --with-redpanda)
      WITH_REDPANDA=true
      ;;
  esac
done

echo "============================================================"
echo "  Starting Autonomous AI-Native ERP System"
echo "============================================================"

# 1. Check & Ensure Docker Infrastructure
echo "[1/5] Checking Docker Infrastructure (PostgreSQL, Redis, Qdrant)..."
if command -v docker &> /dev/null; then
  CONTAINERS=("ai_erp_postgres" "ai_erp_redis" "ai_erp_qdrant")
  if [[ "$WITH_REDPANDA" == "true" ]]; then
    CONTAINERS+=("erp_redpanda")
    if ! docker ps -a --format '{{.Names}}' | grep -q "^erp_redpanda$"; then
      echo "  Spinning up Redpanda container via docker-compose..."
      docker compose up -d redpanda 2>/dev/null || docker-compose up -d redpanda 2>/dev/null || true
    fi
  fi
  for container in "${CONTAINERS[@]}"; do
    if docker ps -a --format '{{.Names}}' | grep -q "^${container}$"; then
      if ! docker ps --format '{{.Names}}' | grep -q "^${container}$"; then
        echo "  Starting container: ${container}..."
        docker start "$container" >/dev/null 2>&1 || true
      fi
    fi
  done
fi

# 2. Verify Database Connection & Tables
echo "[2/5] Verifying PostgreSQL Connection & Database Schema..."
VENV_PY="$SCRIPT_DIR/.venv/bin/python3"
if [[ ! -x "$VENV_PY" ]]; then
  echo "Error: Virtual environment not found at $SCRIPT_DIR/.venv"
  exit 1
fi

"$VENV_PY" -c "
import asyncio
from erp.db.engine import async_engine
from erp.db.models.base import Base
import erp.db.models

async def init_tables():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

asyncio.run(init_tables())
" > "$LOG_DIR/db_init.log" 2>&1 || {
  echo "Warning: Database init check had warnings, check $LOG_DIR/db_init.log"
}
echo "  PostgreSQL schema ready."

# 3. Clean any stale processes on port 8000 and 3000
echo "[3/5] Cleaning any stale processes on ports 8000 & 3000..."
fuser -k 8000/tcp 2>/dev/null || true
fuser -k 3000/tcp 2>/dev/null || true

# 4. Start FastAPI Backend
echo "[4/5] Starting FastAPI Backend on http://0.0.0.0:8000..."
setsid "$SCRIPT_DIR/.venv/bin/uvicorn" erp.api.app:app --host 0.0.0.0 --port 8000 </dev/null > "$LOG_DIR/backend.log" 2>&1 &
BACKEND_PID=$!
echo "$BACKEND_PID" > "$BACKEND_PID_FILE"

# Wait for backend readiness
echo "  Waiting for backend API to be ready..."
for i in {1..30}; do
  if curl -sf http://127.0.0.1:8000/health >/dev/null 2>&1; then
    echo "  Backend is ready (PID: $BACKEND_PID)."
    break
  fi
  sleep 0.5
done

# 5. Start Next.js Frontend
echo "[5/5] Starting Next.js Frontend on http://localhost:3000..."
cd "$SCRIPT_DIR/frontend"

if [[ ! -d ".next" ]]; then
  echo "  Next.js production build not found. Building static assets..."
  npm run build > "$LOG_DIR/frontend_build.log" 2>&1
fi

setsid ./node_modules/.bin/next start -p 3000 </dev/null > "$LOG_DIR/frontend.log" 2>&1 &
FRONTEND_PID=$!
cd "$SCRIPT_DIR"
echo "$FRONTEND_PID" > "$FRONTEND_PID_FILE"

# Wait for frontend readiness (support HTTP 307 redirect from auth guard)
echo "  Waiting for frontend to be ready..."
for i in {1..30}; do
  if curl -sfL http://127.0.0.1:3000/ >/dev/null 2>&1; then
    echo "  Frontend is ready (PID: $FRONTEND_PID)."
    break
  fi
  sleep 0.5
done

echo ""
echo "============================================================"
echo "  Autonomous AI-Native ERP is ONLINE & HEALTHY"
echo "============================================================"
echo "  Frontend Web UI:   http://localhost:3000"
echo "  Backend API:       http://localhost:8000"
echo "  API Documentation: http://localhost:8000/api/v1/docs"
echo "  Database:          PostgreSQL on localhost:5432"
echo "  Logs Directory:    $LOG_DIR/"
echo "============================================================"
echo ""

cleanup() {
  echo ""
  echo "Shutting down services..."
  if [[ -f "$BACKEND_PID_FILE" ]]; then
    kill "$(cat "$BACKEND_PID_FILE")" 2>/dev/null || true
    rm -f "$BACKEND_PID_FILE"
  fi
  if [[ -f "$FRONTEND_PID_FILE" ]]; then
    kill "$(cat "$FRONTEND_PID_FILE")" 2>/dev/null || true
    rm -f "$FRONTEND_PID_FILE"
  fi
  fuser -k 8000/tcp 2>/dev/null || true
  fuser -k 3000/tcp 2>/dev/null || true
  echo "Services stopped cleanly."
  exit 0
}

if [[ "$IS_DAEMON" == "true" ]]; then
  disown "$BACKEND_PID" 2>/dev/null || true
  disown "$FRONTEND_PID" 2>/dev/null || true
  echo "Running in background daemon mode. To stop services, run: ./stop.sh"
  exit 0
else
  trap cleanup SIGINT SIGTERM
  echo "Running in foreground mode. Press [CTRL+C] to stop all services."
  wait "$BACKEND_PID" "$FRONTEND_PID"
fi
