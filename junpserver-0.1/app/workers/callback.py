from __future__ import annotations

import logging
import time

from app.core.config import settings
from app.db.init_db import init_db
from app.db.session import session_scope
from app.services.callback_service import run_callback_tick
from app.workers.common import bootstrap_worker


logger = logging.getLogger("opspaw.callback")


def main() -> None:
    ctx = bootstrap_worker(
        worker_name="opspaw.callback",
        log_level=settings.app_log_level,
        poll_interval_sec=settings.callback_retry_interval_sec,
    )
    init_db()
    logger.info("callback worker started")
    while not ctx.should_exit:
        try:
            with session_scope() as session:
                result = run_callback_tick(session=session)
            logger.info(
                "callback tick done created=%s processed=%s delivered=%s retried=%s dead=%s",
                result.get("created_deliveries", 0),
                result.get("processed_deliveries", 0),
                result.get("delivered", 0),
                result.get("retried", 0),
                result.get("dead", 0),
            )
        except Exception as exc:  # pragma: no cover - worker guard
            logger.exception("callback worker unexpected error: %s", exc)
        time.sleep(ctx.poll_interval_sec)
    logger.info("callback worker stopped")


if __name__ == "__main__":
    main()
