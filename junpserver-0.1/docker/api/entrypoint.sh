#!/usr/bin/env bash
set -euo pipefail

python - <<'PY'
from app.db.init_db import init_db
init_db()
print('database schema initialized')
PY

exec "$@"
