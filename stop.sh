#!/usr/bin/env bash
# ==============================================================================
# Autonomous AI-Native ERP System Stopper
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_DIR="$SCRIPT_DIR/.pids"

echo "Stopping Autonomous AI-Native ERP services..."

if [[ -f "$PID_DIR/backend.pid" ]]; then
  PID=$(cat "$PID_DIR/backend.pid" 2>/dev/null || true)
  if [[ -n "$PID" ]]; then
    echo "  Stopping Backend (PID: $PID)..."
    kill "$PID" 2>/dev/null || true
  fi
  rm -f "$PID_DIR/backend.pid"
fi

if [[ -f "$PID_DIR/frontend.pid" ]]; then
  PID=$(cat "$PID_DIR/frontend.pid" 2>/dev/null || true)
  if [[ -n "$PID" ]]; then
    echo "  Stopping Frontend (PID: $PID)..."
    kill "$PID" 2>/dev/null || true
  fi
  rm -f "$PID_DIR/frontend.pid"
fi

# Clean any lingering bindings on ports 8000 and 3000
fuser -k 8000/tcp 2>/dev/null || true
fuser -k 3000/tcp 2>/dev/null || true

echo "All ERP services have been shut down cleanly."
