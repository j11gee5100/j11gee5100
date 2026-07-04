from __future__ import annotations

import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.db.init_db import init_db


def main() -> int:
    init_db()
    print("database schema initialized")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

