from __future__ import annotations

import logging
import time

from app.core.config import settings
from app.db.init_db import init_db
from app.db.session import session_scope
from app.services.jumpserver.client import JumpServerClient, JumpServerClientError
from app.services.orchestrator_service import run_orchestrator_tick
from app.workers.common import bootstrap_worker


logger = logging.getLogger("opspaw.orchestrator")


def main() -> None:
    ctx = bootstrap_worker(
        worker_name="opspaw.orchestrator",
        log_level=settings.app_log_level,
        poll_interval_sec=settings.worker_poll_interval_sec,
    )
    client = JumpServerClient()
    init_db()
    logger.info("orchestrator worker started")
    while not ctx.should_exit:
        try:
            with session_scope() as session:
                result = run_orchestrator_tick(session=session, client=client)
            logger.info(
                "orchestrator tick done created_executions=%s finished_executions=%s created_audit_links=%s",
                result["created_executions"],
                result["finished_executions"],
                result.get("created_audit_links", 0),
            )
        except JumpServerClientError as exc:
            logger.error("jumpserver orchestrator error: %s", exc)
        except Exception as exc:  # pragma: no cover - worker guard
            logger.exception("orchestrator worker unexpected error: %s", exc)
        time.sleep(ctx.poll_interval_sec)
    logger.info("orchestrator worker stopped")


if __name__ == "__main__":
    main()
