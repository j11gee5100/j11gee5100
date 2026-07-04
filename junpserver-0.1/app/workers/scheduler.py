from __future__ import annotations

import logging
import time

from app.core.config import settings
from app.db.init_db import init_db
from app.db.session import session_scope
from app.services.approval_service import expire_overdue_approvals
from app.services.jumpserver.client import JumpServerClient, JumpServerClientError
from app.services.metrics_aggregation_service import run_metrics_preaggregation
from app.services.task_retry_service import run_task_refresh_retry_batch
from app.workers.common import bootstrap_worker


logger = logging.getLogger("opspaw.scheduler")


def _parse_csv_codes(raw: str) -> list[str]:
    values: list[str] = []
    for part in (raw or "").split(","):
        code = part.strip().upper()
        if not code:
            continue
        values.append(code)
    return values


def main() -> None:
    ctx = bootstrap_worker(
        worker_name="opspaw.scheduler",
        log_level=settings.app_log_level,
        poll_interval_sec=settings.scheduler_tick_interval_sec,
    )
    client = JumpServerClient()
    init_db()
    logger.info("scheduler worker started")
    last_retry_run_ts = 0.0
    last_metrics_agg_run_ts = 0.0
    last_approval_expire_run_ts = 0.0
    retry_disabled_logged = False
    metrics_disabled_logged = False
    approval_disabled_logged = False

    while not ctx.should_exit:
        now_ts = time.time()
        try:
            if settings.task_refresh_retry_scheduler_enabled:
                retry_disabled_logged = False
                interval_sec = max(30, settings.task_refresh_retry_scheduler_interval_sec)
                if now_ts - last_retry_run_ts >= interval_sec:
                    with session_scope() as session:
                        result = run_task_refresh_retry_batch(
                            session=session,
                            client=client,
                            endpoint="/worker/scheduler/task-refresh-retry",
                            operator_id="scheduler",
                            source_ip="127.0.0.1",
                            task_ids=[],
                            hours=max(1, settings.task_refresh_retry_scheduler_hours),
                            source=settings.task_refresh_retry_scheduler_source,
                            failure_codes=_parse_csv_codes(settings.task_refresh_retry_scheduler_failure_codes),
                            limit=max(1, settings.task_refresh_retry_scheduler_limit),
                            window_size=max(1, settings.task_refresh_retry_scheduler_window_size),
                            max_windows=max(1, settings.task_refresh_retry_scheduler_max_windows),
                            same_asset_max_retries=max(1, settings.task_refresh_retry_same_asset_max_retries),
                            task_cooldown_minutes=max(0, settings.task_refresh_retry_task_cooldown_minutes),
                            dry_run=False,
                            trace_id="scheduler",
                        )
                    logger.info(
                        "scheduler retry batch done audit_id=%s queued=%s matched=%s skipped_rate_limited=%s skipped_asset_guardrail=%s",
                        result.get("audit_id"),
                        result.get("summary", {}).get("queued", 0),
                        result.get("summary", {}).get("matched_by_failure", 0),
                        result.get("summary", {}).get("skipped_rate_limited", 0),
                        result.get("summary", {}).get("skipped_asset_guardrail", 0),
                    )
                    last_retry_run_ts = now_ts
            else:
                if not retry_disabled_logged:
                    logger.info("scheduler retry batch disabled by config")
                    retry_disabled_logged = True

            if settings.metrics_preaggregation_scheduler_enabled:
                metrics_disabled_logged = False
                metrics_interval_sec = max(60, settings.metrics_preaggregation_interval_sec)
                if now_ts - last_metrics_agg_run_ts >= metrics_interval_sec:
                    with session_scope() as session:
                        agg = run_metrics_preaggregation(
                            session=session,
                            hourly_lookback_hours=max(1, settings.metrics_preaggregation_hourly_lookback_hours),
                            daily_lookback_days=max(1, settings.metrics_preaggregation_daily_lookback_days),
                        )
                    logger.info(
                        "scheduler metrics preaggregation done failure_hour_rows=%s retry_hour_item_rows=%s retry_hour_audit_rows=%s",
                        agg.get("failure_summary", {}).get("hour_rows", 0),
                        agg.get("task_retry_summary", {}).get("hour_item_rows", 0),
                        agg.get("task_retry_summary", {}).get("hour_audit_rows", 0),
                    )
                    last_metrics_agg_run_ts = now_ts
            else:
                if not metrics_disabled_logged:
                    logger.info("scheduler metrics preaggregation disabled by config")
                    metrics_disabled_logged = True

            if settings.approval_expire_check_interval_sec > 0:
                approval_disabled_logged = False
                approval_interval_sec = max(15, settings.approval_expire_check_interval_sec)
                if now_ts - last_approval_expire_run_ts >= approval_interval_sec:
                    with session_scope() as session:
                        expire_result = expire_overdue_approvals(
                            session=session,
                            limit=max(1, settings.approval_expire_batch_size),
                            escalation_enabled=settings.approval_escalation_enabled,
                            escalation_after_minutes=max(1, settings.approval_escalation_after_minutes),
                        )
                    logger.info(
                        "scheduler approval expiry done expired=%s failed_tasks=%s escalated=%s",
                        expire_result.get("expired", 0),
                        expire_result.get("failed_tasks", 0),
                        expire_result.get("escalated", 0),
                    )
                    last_approval_expire_run_ts = now_ts
            else:
                if not approval_disabled_logged:
                    logger.info("scheduler approval expiry disabled by config")
                    approval_disabled_logged = True
        except JumpServerClientError as exc:
            logger.error("scheduler jumpserver error: %s", exc)
        except Exception as exc:  # pragma: no cover - worker guard
            logger.exception("scheduler worker unexpected error: %s", exc)
        time.sleep(ctx.poll_interval_sec)
    logger.info("scheduler worker stopped")


if __name__ == "__main__":
    main()
