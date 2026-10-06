#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_DIR="$SCRIPT_DIR/.pids"

process_matches() {
  local pid="$1"
  local marker="$2"
  [[ -r "/proc/$pid/cmdline" ]] || return 1
  local command_line
  command_line="$(tr '\0' ' ' <"/proc/$pid/cmdline" 2>/dev/null || true)"
  [[ "$command_line" == *"$marker"* ]]
}

stop_service() {
  local name="$1"
  local file="$2"
  local marker="$3"
  [[ -f "$file" ]] || return 0

  local pid
  pid="$(cat "$file" 2>/dev/null || true)"
  if [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null && process_matches "$pid" "$marker"; then
    echo "Stopping $name (PID $pid)..."
    local process_group
    process_group="$(ps -o pgid= -p "$pid" 2>/dev/null | tr -d ' ' || true)"
    if [[ "$process_group" == "$pid" ]]; then
      kill -- "-$pid" 2>/dev/null || true
    else
      kill "$pid" 2>/dev/null || true
    fi
    for _ in $(seq 1 20); do
      if [[ "$process_group" == "$pid" ]]; then
        if ! kill -0 -- "-$pid" 2>/dev/null; then break; fi
      elif ! kill -0 "$pid" 2>/dev/null || ! process_matches "$pid" "$marker"; then
        break
      fi
      sleep 0.25
    done
    if [[ "$process_group" == "$pid" ]] && kill -0 -- "-$pid" 2>/dev/null; then
      kill -9 -- "-$pid" 2>/dev/null || true
    elif [[ "$process_group" != "$pid" ]] && kill -0 "$pid" 2>/dev/null && process_matches "$pid" "$marker"; then
      kill -9 "$pid" 2>/dev/null || true
    fi
  else
    echo "$name is not running (removing stale PID file)."
  fi
  rm -f "$file"
}

echo "Stopping ERP application services..."
stop_service "frontend" "$PID_DIR/frontend.pid" "next dev"
stop_service "backend" "$PID_DIR/backend.pid" "uvicorn erp.api.app:app"
echo "Application services stopped. PostgreSQL and Redis containers remain running."
