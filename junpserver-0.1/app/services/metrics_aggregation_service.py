from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.failure import infer_failure_code, strip_failure_prefix
from app.models import (
    FailureSummaryBucket,
    MetricsPreaggregationRun,
    Task,
    TaskRetryAudit,
    TaskRetryAuditCountBucket,
    TaskRetryAuditItem,
    TaskRetrySummaryBucket,
)


def _as_utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _to_bucket(value: datetime, granularity: str) -> datetime:
    if granularity == "day":
        return value.replace(hour=0, minute=0, second=0, microsecond=0)
    return value.replace(minute=0, second=0, microsecond=0)


def _replace_failure_summary_buckets(
    *,
    session: Session,
    granularity: str,
    since: datetime,
    counts: dict[tuple, int],
) -> int:
    session.execute(
        delete(FailureSummaryBucket).where(
            FailureSummaryBucket.granularity == granularity,
            FailureSummaryBucket.bucket_start >= since,
        )
    )
    inserted = 0
    for key, count in counts.items():
        if count <= 0:
            continue
        bucket_start, source, risk_level, failure_code, unknown_reason = key
        session.add(
            FailureSummaryBucket(
                granularity=granularity,
                bucket_start=bucket_start,
                source=source[:32],
                risk_level=risk_level[:32],
                failure_code=failure_code[:32],
                unknown_reason=unknown_reason[:255],
                count=count,
            )
        )
        inserted += 1
    return inserted


def _replace_task_retry_summary_buckets(
    *,
    session: Session,
    granularity: str,
    since: datetime,
    counts: dict[tuple, int],
) -> int:
    session.execute(
        delete(TaskRetrySummaryBucket).where(
            TaskRetrySummaryBucket.granularity == granularity,
            TaskRetrySummaryBucket.bucket_start >= since,
        )
    )
    inserted = 0
    for key, count in counts.items():
        if count <= 0:
            continue
        bucket_start, source, action, failure_code, operator_id, dry_run = key
        session.add(
            TaskRetrySummaryBucket(
                granularity=granularity,
                bucket_start=bucket_start,
                source=source[:32],
                action=action[:48],
                failure_code=failure_code[:32],
                operator_id=operator_id[:64],
                dry_run=bool(dry_run),
                count=count,
            )
        )
        inserted += 1
    return inserted


def _replace_task_retry_audit_count_buckets(
    *,
    session: Session,
    granularity: str,
    since: datetime,
    counts: dict[tuple, int],
) -> int:
    session.execute(
        delete(TaskRetryAuditCountBucket).where(
            TaskRetryAuditCountBucket.granularity == granularity,
            TaskRetryAuditCountBucket.bucket_start >= since,
        )
    )
    inserted = 0
    for key, count in counts.items():
        if count <= 0:
            continue
        bucket_start, operator_id, dry_run, source_selector = key
        session.add(
            TaskRetryAuditCountBucket(
                granularity=granularity,
                bucket_start=bucket_start,
                operator_id=operator_id[:64],
                dry_run=bool(dry_run),
                source_selector=source_selector[:32],
                count=count,
            )
        )
        inserted += 1
    return inserted


def _aggregate_failure_summary(
    *,
    session: Session,
    now_utc: datetime,
    hourly_lookback_hours: int,
    daily_lookback_days: int,
) -> dict:
    since_hour = now_utc - timedelta(hours=max(1, hourly_lookback_hours))
    since_day = now_utc - timedelta(days=max(1, daily_lookback_days))
    since_all = min(since_hour, since_day)

    rows = list(
        session.execute(
            select(Task.source, Task.risk_level, Task.reason, Task.updated_at).where(
                Task.status == "failed",
                Task.updated_at >= since_all,
            )
        )
    )

    hourly_counts: dict[tuple, int] = defaultdict(int)
    daily_counts: dict[tuple, int] = defaultdict(int)
    for source, risk_level, reason, updated_at in rows:
        ts = _as_utc(updated_at)
        failure_code = infer_failure_code(reason) or "UNKNOWN"
        unknown_reason = strip_failure_prefix(reason) if failure_code == "UNKNOWN" else ""

        if ts >= since_hour:
            bucket = _to_bucket(ts, "hour")
            key = (bucket, source or "unknown", risk_level or "unknown", failure_code, unknown_reason)
            hourly_counts[key] += 1
        if ts >= since_day:
            bucket = _to_bucket(ts, "day")
            key = (bucket, source or "unknown", risk_level or "unknown", failure_code, unknown_reason)
            daily_counts[key] += 1

    hour_inserted = _replace_failure_summary_buckets(
        session=session,
        granularity="hour",
        since=since_hour,
        counts=hourly_counts,
    )
    day_inserted = _replace_failure_summary_buckets(
        session=session,
        granularity="day",
        since=since_day,
        counts=daily_counts,
    )
    return {
        "scanned_failed_tasks": len(rows),
        "hour_rows": hour_inserted,
        "day_rows": day_inserted,
    }


def _aggregate_task_retry_summary(
    *,
    session: Session,
    now_utc: datetime,
    hourly_lookback_hours: int,
    daily_lookback_days: int,
) -> dict:
    since_hour = now_utc - timedelta(hours=max(1, hourly_lookback_hours))
    since_day = now_utc - timedelta(days=max(1, daily_lookback_days))
    since_all = min(since_hour, since_day)

    audits = list(session.scalars(select(TaskRetryAudit).where(TaskRetryAudit.created_at >= since_all)))
    audit_ids = [audit.id for audit in audits]

    items = []
    if audit_ids:
        items = list(
            session.execute(
                select(
                    TaskRetryAuditItem.audit_id,
                    TaskRetryAuditItem.source,
                    TaskRetryAuditItem.action,
                    TaskRetryAuditItem.failure_code,
                    TaskRetryAuditItem.created_at,
                    TaskRetryAudit.operator_id,
                    TaskRetryAudit.dry_run,
                )
                .join(TaskRetryAudit, TaskRetryAudit.id == TaskRetryAuditItem.audit_id)
                .where(TaskRetryAuditItem.audit_id.in_(audit_ids))
            )
        )

    audit_source_map: dict[str, set[str]] = defaultdict(set)
    hourly_item_counts: dict[tuple, int] = defaultdict(int)
    daily_item_counts: dict[tuple, int] = defaultdict(int)
    for audit_id, source, action, failure_code, created_at, operator_id, dry_run in items:
        source_key = (source or "unknown")[:32]
        action_key = (action or "unknown")[:48]
        failure_key = (failure_code or "UNKNOWN")[:32]
        operator_key = (operator_id or "unknown")[:64]
        dry_run_key = bool(dry_run)
        ts = _as_utc(created_at)
        audit_source_map[audit_id].add(source_key)

        if ts >= since_hour:
            bucket = _to_bucket(ts, "hour")
            key = (bucket, source_key, action_key, failure_key, operator_key, dry_run_key)
            hourly_item_counts[key] += 1
        if ts >= since_day:
            bucket = _to_bucket(ts, "day")
            key = (bucket, source_key, action_key, failure_key, operator_key, dry_run_key)
            daily_item_counts[key] += 1

    hourly_audit_counts: dict[tuple, int] = defaultdict(int)
    daily_audit_counts: dict[tuple, int] = defaultdict(int)
    for audit in audits:
        ts = _as_utc(audit.created_at)
        operator_key = (audit.operator_id or "unknown")[:64]
        dry_run_key = bool(audit.dry_run)
        sources = audit_source_map.get(audit.id, set())

        if ts >= since_hour:
            bucket = _to_bucket(ts, "hour")
            hourly_audit_counts[(bucket, operator_key, dry_run_key, "*")] += 1
            for source in sources:
                hourly_audit_counts[(bucket, operator_key, dry_run_key, source)] += 1

        if ts >= since_day:
            bucket = _to_bucket(ts, "day")
            daily_audit_counts[(bucket, operator_key, dry_run_key, "*")] += 1
            for source in sources:
                daily_audit_counts[(bucket, operator_key, dry_run_key, source)] += 1

    hour_item_rows = _replace_task_retry_summary_buckets(
        session=session,
        granularity="hour",
        since=since_hour,
        counts=hourly_item_counts,
    )
    day_item_rows = _replace_task_retry_summary_buckets(
        session=session,
        granularity="day",
        since=since_day,
        counts=daily_item_counts,
    )
    hour_audit_rows = _replace_task_retry_audit_count_buckets(
        session=session,
        granularity="hour",
        since=since_hour,
        counts=hourly_audit_counts,
    )
    day_audit_rows = _replace_task_retry_audit_count_buckets(
        session=session,
        granularity="day",
        since=since_day,
        counts=daily_audit_counts,
    )
    return {
        "scanned_audits": len(audits),
        "scanned_items": len(items),
        "hour_item_rows": hour_item_rows,
        "day_item_rows": day_item_rows,
        "hour_audit_rows": hour_audit_rows,
        "day_audit_rows": day_audit_rows,
    }


def run_metrics_preaggregation(
    *,
    session: Session,
    hourly_lookback_hours: int,
    daily_lookback_days: int,
    now_utc: datetime | None = None,
) -> dict:
    now = _as_utc(now_utc)
    failure = _aggregate_failure_summary(
        session=session,
        now_utc=now,
        hourly_lookback_hours=hourly_lookback_hours,
        daily_lookback_days=daily_lookback_days,
    )
    retry = _aggregate_task_retry_summary(
        session=session,
        now_utc=now,
        hourly_lookback_hours=hourly_lookback_hours,
        daily_lookback_days=daily_lookback_days,
    )
    result = {
        "status": "ok",
        "now": now.isoformat(),
        "hourly_lookback_hours": max(1, hourly_lookback_hours),
        "daily_lookback_days": max(1, daily_lookback_days),
        "failure_summary": failure,
        "task_retry_summary": retry,
    }
    session.add(
        MetricsPreaggregationRun(
            status="ok",
            hourly_lookback_hours=max(1, hourly_lookback_hours),
            daily_lookback_days=max(1, daily_lookback_days),
            failure_hour_rows=int(failure.get("hour_rows", 0) or 0),
            failure_day_rows=int(failure.get("day_rows", 0) or 0),
            retry_hour_item_rows=int(retry.get("hour_item_rows", 0) or 0),
            retry_day_item_rows=int(retry.get("day_item_rows", 0) or 0),
            retry_hour_audit_rows=int(retry.get("hour_audit_rows", 0) or 0),
            retry_day_audit_rows=int(retry.get("day_audit_rows", 0) or 0),
            run_at=now,
        )
    )
    session.flush()
    return result
