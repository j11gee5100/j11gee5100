#!/usr/bin/env bash
set -Eeuo pipefail
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DB_PATH="${OPSPAW_DB_PATH:-$APP_DIR/.local-state/opspaw-dev-18080.db}"
LOG_PATH="${OPSPAW_LOG_PATH:-/tmp/opspaw-local-api.log}"
PID_PATH="${OPSPAW_PID_PATH:-/tmp/opspaw-local-api.pid}"
mkdir -p "$(dirname "$DB_PATH")"
cd "$APP_DIR"
setsid env DATABASE_URL="sqlite:////$DB_PATH" \
  python3 -m uvicorn app.api.main:app --host 0.0.0.0 --port 18080 \
  > "$LOG_PATH" 2>&1 < /dev/null &
echo $! > "$PID_PATH"
echo "started pid=$(cat "$PID_PATH") db=$DB_PATH log=$LOG_PATH"
