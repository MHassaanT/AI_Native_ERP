#!/usr/bin/env bash
# Start the local ERP development stack.
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PID_DIR="$SCRIPT_DIR/.pids"
LOG_DIR="$SCRIPT_DIR/logs"
BACKEND_PID_FILE="$PID_DIR/backend.pid"
FRONTEND_PID_FILE="$PID_DIR/frontend.pid"
VENV_PY="$SCRIPT_DIR/.venv/bin/python"
FRONTEND_BIN="$SCRIPT_DIR/frontend/node_modules/.bin/next"

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
IS_DAEMON=false
WITH_REDPANDA=false

for arg in "$@"; do
  case "$arg" in
    --daemon|-d) IS_DAEMON=true ;;
    --with-redpanda) WITH_REDPANDA=true ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

mkdir -p "$PID_DIR" "$LOG_DIR"

fail() {
  echo "Error: $*" >&2
  exit 1
}

port_is_free() {
  "$VENV_PY" - "$1" <<'PY'
import socket
import sys

with socket.socket() as sock:
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind(("0.0.0.0", int(sys.argv[1])))
    except OSError:
        raise SystemExit(1)
PY
}

process_matches() {
  local pid="$1"
  local marker="$2"
  [[ -r "/proc/$pid/cmdline" ]] || return 1
  local command_line
  command_line="$(tr '\0' ' ' <"/proc/$pid/cmdline" 2>/dev/null || true)"
  [[ "$command_line" == *"$marker"* ]]
}

stop_managed_process() {
  local pid="$1"
  local marker="$2"
  if [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null && process_matches "$pid" "$marker"; then
    local process_group
    process_group="$(ps -o pgid= -p "$pid" 2>/dev/null | tr -d ' ' || true)"
    if [[ "$process_group" == "$pid" ]]; then
      kill -- "-$pid" 2>/dev/null || true
    else
      kill "$pid" 2>/dev/null || true
    fi
  fi
}

remove_stale_pid_file() {
  local file="$1"
  local marker="$2"
  [[ -f "$file" ]] || return 0
  local pid
  pid="$(cat "$file" 2>/dev/null || true)"
  if [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null && process_matches "$pid" "$marker"; then
    fail "A service process from this launcher may still be running (PID $pid, recorded in $file). Stop it with ./stop.sh first."
  fi
  rm -f "$file"
}

cleanup() {
  local exit_code=$?
  trap - EXIT INT TERM
  for pid_file in "$FRONTEND_PID_FILE" "$BACKEND_PID_FILE"; do
    if [[ -f "$pid_file" ]]; then
      local pid
      pid="$(cat "$pid_file" 2>/dev/null || true)"
      local marker="uvicorn erp.api.app:app"
      [[ "$pid_file" == "$FRONTEND_PID_FILE" ]] && marker="next dev"
      stop_managed_process "$pid" "$marker"
      rm -f "$pid_file"
    fi
  done
  if [[ "$exit_code" -ne 0 ]]; then
    echo "Startup failed. See $LOG_DIR/backend.log and $LOG_DIR/frontend.log." >&2
  fi
  exit "$exit_code"
}

echo "============================================================"
echo "  Starting AI-Native ERP development stack"
echo "============================================================"

[[ -x "$VENV_PY" ]] || fail "Python environment missing at .venv. Create it and install this project first (see README.md)."
[[ -x "$FRONTEND_BIN" ]] || fail "Frontend dependencies missing. Run npm ci in frontend/ first."

remove_stale_pid_file "$BACKEND_PID_FILE" "uvicorn erp.api.app:app"
remove_stale_pid_file "$FRONTEND_PID_FILE" "next dev"

for port in "$BACKEND_PORT" "$FRONTEND_PORT"; do
  port_is_free "$port" || fail "Port $port is already in use. Stop its service or set BACKEND_PORT / FRONTEND_PORT to unused ports."
done

echo "[1/4] Starting PostgreSQL and Redis with Docker Compose..."
command -v docker >/dev/null 2>&1 || fail "Docker is required to start PostgreSQL and Redis."
docker compose up -d postgres redis || fail "Docker Compose could not start PostgreSQL and Redis. Check that Docker is running and your user can access it."
if [[ "$WITH_REDPANDA" == "true" ]]; then
  echo "      Starting Redpanda event streaming..."
  docker compose up -d redpanda redpanda-console || fail "Docker Compose could not start Redpanda."
fi

echo "[2/4] Checking database connectivity and initializing schema..."
PYTHONPATH="$SCRIPT_DIR/src${PYTHONPATH:+:$PYTHONPATH}" "$VENV_PY" - <<'PY' >"$LOG_DIR/db_init.log" 2>&1 || fail "Database initialization failed. Check $LOG_DIR/db_init.log."
import asyncio

from erp.db.engine import async_engine
from erp.db.models.base import Base
import erp.db.models  # noqa: F401 - register all ORM models


async def init_tables():
    last_error = None
    for _ in range(30):
        try:
            async with async_engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            return
        except Exception as error:
            last_error = error
            await asyncio.sleep(1)
    raise RuntimeError("Database did not become ready within 30 seconds") from last_error


asyncio.run(init_tables())
PY

trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

echo "[3/4] Starting FastAPI on http://localhost:$BACKEND_PORT..."
setsid env PYTHONPATH="$SCRIPT_DIR/src${PYTHONPATH:+:$PYTHONPATH}" \
  "$VENV_PY" -m uvicorn erp.api.app:app --host 0.0.0.0 --port "$BACKEND_PORT" \
  </dev/null >"$LOG_DIR/backend.log" 2>&1 &
BACKEND_PID=$!
echo "$BACKEND_PID" >"$BACKEND_PID_FILE"

backend_ready=false
for _ in $(seq 1 60); do
  if curl -fsS --max-time 2 "http://127.0.0.1:$BACKEND_PORT/health" >/dev/null 2>&1; then
    backend_ready=true
    break
  fi
  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then break; fi
  sleep 0.5
done
if [[ "$backend_ready" != "true" ]]; then
  tail -40 "$LOG_DIR/backend.log" >&2 || true
  fail "Backend did not become ready on port $BACKEND_PORT."
fi

echo "[4/4] Starting Next.js development server on http://localhost:$FRONTEND_PORT..."
cd "$SCRIPT_DIR/frontend"
setsid env BACKEND_API_URL="${BACKEND_API_URL:-http://127.0.0.1:$BACKEND_PORT}" \
  "$FRONTEND_BIN" dev --hostname 0.0.0.0 -p "$FRONTEND_PORT" \
  </dev/null >"$LOG_DIR/frontend.log" 2>&1 &
FRONTEND_PID=$!
cd "$SCRIPT_DIR"
echo "$FRONTEND_PID" >"$FRONTEND_PID_FILE"

frontend_ready=false
for _ in $(seq 1 60); do
  if curl -sS --max-time 3 -o /dev/null "http://127.0.0.1:$FRONTEND_PORT/" 2>/dev/null; then
    frontend_ready=true
    break
  fi
  if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then break; fi
  sleep 0.5
done
if [[ "$frontend_ready" != "true" ]]; then
  tail -40 "$LOG_DIR/frontend.log" >&2 || true
  fail "Frontend did not become ready on port $FRONTEND_PORT."
fi

echo ""
echo "============================================================"
echo "  AI-Native ERP is running"
echo "============================================================"
echo "  Frontend:    http://localhost:$FRONTEND_PORT"
echo "  Backend API: http://localhost:$BACKEND_PORT"
echo "  API docs:    http://localhost:$BACKEND_PORT/api/v1/docs"
echo "  PostgreSQL:  localhost:5432"
echo "  Redis:       localhost:6379"
echo "  Logs:        $LOG_DIR/"
echo "============================================================"

if [[ "$IS_DAEMON" == "true" ]]; then
  disown "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
  trap - EXIT INT TERM
  echo "Services are running in the background. Stop them with ./stop.sh."
  exit 0
fi

echo "Foreground mode. Press Ctrl+C to stop both app servers."

while true; do
  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo "Backend process exited. Check $LOG_DIR/backend.log." >&2
    exit 1
  fi
  if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
    echo "Frontend process exited. Check $LOG_DIR/frontend.log." >&2
    exit 1
  fi
  sleep 1
done
