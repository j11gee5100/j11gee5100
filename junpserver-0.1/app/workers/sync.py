from __future__ import annotations

import logging
import time

from app.core.config import settings
from app.db.init_db import init_db
from app.db.session import session_scope
from app.services.jumpserver.client import JumpServerClient, JumpServerClientError
from app.services.sync_service import run_sync_once
from app.workers.common import bootstrap_worker


logger = logging.getLogger("opspaw.sync")


def main() -> None:
    ctx = bootstrap_worker(
        worker_name="opspaw.sync",
        log_level=settings.app_log_level,
        poll_interval_sec=settings.worker_poll_interval_sec,
    )
    client = JumpServerClient()
    init_db()
    logger.info("sync worker started")
    while not ctx.should_exit:
        try:
            with session_scope() as session:
                result = run_sync_once(session=session, client=client)
            logger.info(
                "sync tick done assets=%s users=%s relations=%s offset=%s next_offset=%s strategy=%s requested=%s fallback=%s ineffective_hit=%s ineffective_hits=%s force_full_until=%s inactivated=%s guardrail_blocked=%s guardrail_reason=%s freshness(fresh=%s,stale=%s,expired=%s) cycle_completed=%s consistency_status=%s delta_assets=%s snapshot_id=%s",
                result["assets"],
                result["system_users"],
                result["relations"],
                result.get("offset", 0),
                result.get("next_offset", 0),
                result.get("strategy_used", "unknown"),
                result.get("strategy_requested", "unknown"),
                result.get("strategy_fallback_reason"),
                result.get("timestamp_ineffective_hit"),
                result.get("timestamp_ineffective_hits"),
                result.get("force_full_until"),
                result.get("inactivated_assets", 0),
                result.get("inactivation_guardrail_blocked", False),
                result.get("inactivation_guardrail_reason"),
                result.get("fresh_assets", 0),
                result.get("stale_assets", 0),
                result.get("expired_assets", 0),
                result.get("cycle_completed", False),
                result.get("consistency_status", "unknown"),
                result.get("consistency_delta_assets"),
                result.get("snapshot_id", ""),
            )
        except JumpServerClientError as exc:
            logger.error("jumpserver sync error: %s", exc)
        except Exception as exc:  # pragma: no cover - worker guard
            logger.exception("sync worker unexpected error: %s", exc)
        time.sleep(ctx.poll_interval_sec)
    logger.info("sync worker stopped")


if __name__ == "__main__":
    main()
