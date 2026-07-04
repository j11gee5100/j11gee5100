from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.failure import infer_failure_code, strip_failure_prefix
from app.models import Execution, Task, TaskRetryAudit, TaskRetryAuditItem
from app.services.jumpserver.client import JumpServerClient
from app.services.orchestrator_service import run_orchestrator_tick
from app.services.sync_service import refresh_asset_once


RETRYABLE_FAILURE_CODES = {"ASSET_STALE", "ASSET_EXPIRED", "ASSET_NOT_FOUND", "ASSET_INACTIVE"}


def normalize_retry_failure_codes(values: list[str]) -> set[str]:
    if not values:
        return set(RETRYABLE_FAILURE_CODES)
    normalized: set[str] = set()
    for raw in values:
        code = (raw or "").strip().upper()
        if code in RETRYABLE_FAILURE_CODES:
            normalized.add(code)
    if not normalized:
        return set(RETRYABLE_FAILURE_CODES)
    return normalized


def _compact_json(payload: object, max_len: int) -> str:
    raw = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    if len(raw) <= max_len:
        return raw
    return raw[: max_len - 3] + "..."


def _insert_task_retry_audit(
    *,
    session: Session,
    endpoint: str,
    operator_id: str,
    source_ip: str,
    dry_run: bool,
    effective_hours: int,
    source_filter: str,
    failure_codes: list[str],
    window_size: int,
    max_windows: int,
    same_asset_max_retries: int,
    summary: dict,
    filters: dict,
) -> TaskRetryAudit:
    item = TaskRetryAudit(
        endpoint=endpoint[:128],
        operator_id=operator_id[:64],
        source_ip=source_ip[:64],
        trace_id="",
        dry_run=dry_run,
        effective_hours=effective_hours,
        source_filter=(source_filter or "")[:32],
        failure_codes_csv=",".join(failure_codes)[:512],
        window_size=window_size,
        max_windows=max_windows,
        same_asset_max_retries=same_asset_max_retries,
        requested=int(summary.get("requested", 0) or 0),
        missing_tasks=int(summary.get("missing_tasks", 0) or 0),
        matched_by_failure=int(summary.get("matched_by_failure", 0) or 0),
        queued=int(summary.get("queued", 0) or 0),
        skipped_non_retryable=int(summary.get("skipped_non_retryable", 0) or 0),
        skipped_in_progress=int(summary.get("skipped_in_progress", 0) or 0),
        skipped_asset_not_found=int(summary.get("skipped_asset_not_found", 0) or 0),
        skipped_rate_limited=int(summary.get("skipped_rate_limited", 0) or 0),
        skipped_asset_guardrail=int(summary.get("skipped_asset_guardrail", 0) or 0),
        filters_json=_compact_json(filters, max_len=4096),
        summary_json=_compact_json(summary, max_len=4096),
    )
    session.add(item)
    session.flush()
    return item


def _insert_task_retry_audit_items(*, session: Session, audit_id: str, items: list[dict]) -> int:
    inserted = 0
    for payload in items:
        task_id = str(payload.get("task_id") or "")[:36]
        if not task_id:
            continue
        item = TaskRetryAuditItem(
            audit_id=audit_id,
            task_id=task_id,
            target_asset_id=str(payload.get("target_asset_id") or "")[:64],
            source=str(payload.get("source") or "")[:32],
            action=str(payload.get("action") or "")[:48],
            failure_code=str(payload.get("failure_code") or "")[:32],
            final_status=str(payload.get("final_status") or "")[:32],
            final_failure_code=str(payload.get("final_failure_code") or "")[:32],
            message=str(payload.get("message") or "")[:1024],
        )
        session.add(item)
        inserted += 1
    if inserted:
        session.flush()
    return inserted


def run_task_refresh_retry_batch(
    *,
    session: Session,
    client: JumpServerClient,
    endpoint: str,
    operator_id: str,
    source_ip: str,
    task_ids: list[str],
    hours: int,
    source: str,
    failure_codes: list[str],
    limit: int,
    window_size: int,
    max_windows: int,
    same_asset_max_retries: int,
    task_cooldown_minutes: int,
    dry_run: bool,
    trace_id: str,
) -> dict:
    requested_task_ids: list[str] = []
    seen_task_ids: set[str] = set()
    for raw in task_ids:
        task_id = (raw or "").strip()
        if not task_id or task_id in seen_task_ids:
            continue
        seen_task_ids.add(task_id)
        requested_task_ids.append(task_id)

    effective_codes = normalize_retry_failure_codes(failure_codes)
    max_hours_guard = max(1, settings.task_refresh_retry_max_hours)
    effective_hours = min(max(1, hours), max_hours_guard)
    source_filter = (source or "").strip()

    configured_window_size = max(1, settings.task_refresh_retry_window_size)
    configured_max_windows = max(1, settings.task_refresh_retry_max_windows_per_request)
    configured_same_asset_max = max(1, settings.task_refresh_retry_same_asset_max_retries)
    configured_task_cooldown_minutes = max(0, settings.task_refresh_retry_task_cooldown_minutes)

    requested_window_size = window_size or configured_window_size
    requested_max_windows = max_windows or configured_max_windows
    requested_same_asset_max = same_asset_max_retries or configured_same_asset_max
    requested_task_cooldown_minutes = task_cooldown_minutes or configured_task_cooldown_minutes

    effective_window_size = max(1, min(requested_window_size, configured_window_size))
    effective_max_windows = max(1, min(requested_max_windows, configured_max_windows))
    effective_same_asset_max = max(1, min(requested_same_asset_max, configured_same_asset_max))
    effective_task_cooldown_minutes = max(0, min(requested_task_cooldown_minutes, configured_task_cooldown_minutes))
    apply_capacity = effective_window_size * effective_max_windows

    stmt = select(Task).where(Task.status == "failed")
    now_utc = datetime.now(timezone.utc)
    since = now_utc - timedelta(hours=effective_hours)

    query_limit = limit
    if requested_task_ids:
        stmt = stmt.where(Task.id.in_(requested_task_ids))
        query_limit = max(limit, len(requested_task_ids))
    else:
        stmt = stmt.where(Task.updated_at >= since)
        if source_filter:
            stmt = stmt.where(Task.source == source_filter)

    tasks = list(session.scalars(stmt.order_by(Task.updated_at.desc(), Task.id.desc()).limit(query_limit)))
    task_map = {task.id: task for task in tasks}
    ordered_tasks = tasks
    if requested_task_ids:
        ordered_tasks = [task_map[task_id] for task_id in requested_task_ids if task_id in task_map]

    response_items: list[dict] = []
    missing_task_ids: list[str] = []
    if requested_task_ids:
        for task_id in requested_task_ids:
            if task_id in task_map:
                continue
            missing_task_ids.append(task_id)
            response_items.append(
                {
                    "task_id": task_id,
                    "action": "missing",
                    "status": "missing",
                    "message": "task not found",
                }
            )

    matched_by_failure = 0
    in_progress_skipped = 0
    not_retryable_skipped = 0
    refreshed_not_found = 0
    skipped_rate_limited = 0
    skipped_asset_guardrail = 0
    skipped_task_cooldown = 0
    queued_task_ids: list[str] = []
    queued_in_window: list[str] = []
    queued_by_asset: dict[str, int] = {}
    planned_count = 0
    orchestrator_runs: list[dict] = []

    for task in ordered_tasks:
        failure_code = infer_failure_code(task.reason) or "UNKNOWN"
        item = {
            "task_id": task.id,
            "source": task.source,
            "status": task.status,
            "failure_code": failure_code,
            "target_asset_id": task.target_asset_id,
        }
        if failure_code not in effective_codes:
            not_retryable_skipped += 1
            item["action"] = "skipped_non_retryable"
            item["message"] = f"failure_code={failure_code} not in filter {sorted(effective_codes)}"
            response_items.append(item)
            continue

        matched_by_failure += 1
        running_execution = session.scalar(
            select(Execution).where(Execution.task_id == task.id, Execution.status == "running").limit(1)
        )
        if running_execution:
            in_progress_skipped += 1
            item["action"] = "skipped_in_progress"
            item["message"] = "task has running execution"
            item["execution_id"] = running_execution.id
            response_items.append(item)
            continue

        if effective_task_cooldown_minutes > 0:
            cooldown_since = now_utc - timedelta(minutes=effective_task_cooldown_minutes)
            recent_task_retry_count = int(
                session.scalar(
                    select(func.count())
                    .select_from(TaskRetryAuditItem)
                    .join(TaskRetryAudit, TaskRetryAudit.id == TaskRetryAuditItem.audit_id)
                    .where(
                        TaskRetryAuditItem.task_id == task.id,
                        TaskRetryAuditItem.action.in_(("queued", "would_retry")),
                        TaskRetryAudit.created_at >= cooldown_since,
                    )
                )
                or 0
            )
            if recent_task_retry_count > 0:
                skipped_task_cooldown += 1
                item["action"] = "skipped_task_cooldown"
                item["message"] = (
                    f"task cooldown guardrail hit: task_id={task.id}, "
                    f"cooldown_minutes={effective_task_cooldown_minutes}"
                )
                response_items.append(item)
                continue

        historical_retry_count = int(
            session.scalar(
                select(func.count())
                .select_from(TaskRetryAuditItem)
                .join(TaskRetryAudit, TaskRetryAudit.id == TaskRetryAuditItem.audit_id)
                .where(
                    TaskRetryAuditItem.target_asset_id == task.target_asset_id,
                    TaskRetryAuditItem.action.in_(("queued", "would_retry")),
                    TaskRetryAudit.created_at >= since,
                )
            )
            or 0
        )
        current_asset_count = queued_by_asset.get(task.target_asset_id, 0)
        if historical_retry_count + current_asset_count >= effective_same_asset_max:
            skipped_asset_guardrail += 1
            item["action"] = "skipped_asset_guardrail"
            item["message"] = (
                f"asset retry guardrail hit: target_asset_id={task.target_asset_id}, "
                f"max={effective_same_asset_max}, recent_count={historical_retry_count + current_asset_count}"
            )
            response_items.append(item)
            continue

        if dry_run:
            if planned_count >= apply_capacity:
                skipped_rate_limited += 1
                item["action"] = "deferred_rate_limited"
                item["message"] = (
                    f"rate window exceeded: capacity={apply_capacity} "
                    f"(window_size={effective_window_size}, max_windows={effective_max_windows})"
                )
                response_items.append(item)
                continue
            item["action"] = "would_retry"
            item["message"] = "eligible for refresh-retry"
            planned_count += 1
            queued_by_asset[task.target_asset_id] = current_asset_count + 1
            response_items.append(item)
            continue

        if planned_count >= apply_capacity:
            skipped_rate_limited += 1
            item["action"] = "deferred_rate_limited"
            item["message"] = (
                f"rate window exceeded: capacity={apply_capacity} "
                f"(window_size={effective_window_size}, max_windows={effective_max_windows})"
            )
            response_items.append(item)
            continue

        refresh_result = refresh_asset_once(
            session=session,
            client=client,
            jms_asset_id=task.target_asset_id,
            search_limit=max(1, settings.execution_gate_refresh_search_limit),
        )
        item["refresh_result"] = refresh_result
        if not refresh_result.get("found"):
            refreshed_not_found += 1
            item["action"] = "skipped_asset_not_found"
            item["message"] = f"asset not found on jumpserver: {task.target_asset_id}"
            response_items.append(item)
            continue

        task.status = "pending"
        task.reason = (
            f"batch retry requested after asset refresh; previous_failure_code={failure_code}"
        )[:1024]
        queued_task_ids.append(task.id)
        queued_in_window.append(task.id)
        planned_count += 1
        queued_by_asset[task.target_asset_id] = current_asset_count + 1
        item["action"] = "queued"
        item["message"] = "task reset to pending and queued for retry"
        response_items.append(item)
        if len(queued_in_window) >= effective_window_size:
            tick_result = run_orchestrator_tick(session=session, client=client)
            orchestrator_runs.append(tick_result)
            queued_in_window.clear()

    orchestrator_result = None
    if queued_task_ids and not dry_run:
        if queued_in_window:
            tick_result = run_orchestrator_tick(session=session, client=client)
            orchestrator_runs.append(tick_result)
        session.flush()
        orchestrator_result = {
            "runs": len(orchestrator_runs),
            "created_executions": sum(int(item.get("created_executions", 0) or 0) for item in orchestrator_runs),
            "finished_executions": sum(int(item.get("finished_executions", 0) or 0) for item in orchestrator_runs),
            "created_audit_links": sum(int(item.get("created_audit_links", 0) or 0) for item in orchestrator_runs),
            "window_size": effective_window_size,
        }
        final_task_map = {
            task.id: task for task in session.scalars(select(Task).where(Task.id.in_(queued_task_ids)))
        }
        for item in response_items:
            if item.get("action") != "queued":
                continue
            final_task = final_task_map.get(item["task_id"])
            if not final_task:
                continue
            final_failure_code = infer_failure_code(final_task.reason)
            item["final_status"] = final_task.status
            item["final_failure_code"] = final_failure_code
            item["final_reason"] = strip_failure_prefix(final_task.reason) if final_failure_code else final_task.reason

    summary = {
        "requested": len(requested_task_ids) if requested_task_ids else len(ordered_tasks),
        "missing_tasks": len(missing_task_ids),
        "matched_by_failure": matched_by_failure,
        "queued": len(queued_task_ids) if not dry_run else planned_count,
        "skipped_non_retryable": not_retryable_skipped,
        "skipped_in_progress": in_progress_skipped,
        "skipped_asset_not_found": refreshed_not_found,
        "skipped_rate_limited": skipped_rate_limited,
        "skipped_asset_guardrail": skipped_asset_guardrail,
        "skipped_task_cooldown": skipped_task_cooldown,
    }
    filters = {
        "task_ids": requested_task_ids,
        "hours": effective_hours,
        "source": source_filter or None,
        "failure_codes": sorted(effective_codes),
        "limit": limit,
        "window_size": effective_window_size,
        "max_windows": effective_max_windows,
        "same_asset_max_retries": effective_same_asset_max,
        "task_cooldown_minutes": effective_task_cooldown_minutes,
    }
    audit = _insert_task_retry_audit(
        session=session,
        endpoint=endpoint,
        operator_id=operator_id,
        source_ip=source_ip,
        dry_run=dry_run,
        effective_hours=effective_hours,
        source_filter=source_filter,
        failure_codes=sorted(effective_codes),
        window_size=effective_window_size,
        max_windows=effective_max_windows,
        same_asset_max_retries=effective_same_asset_max,
        summary=summary,
        filters=filters,
    )
    audit.trace_id = (trace_id or "")[:64]
    _insert_task_retry_audit_items(session=session, audit_id=audit.id, items=response_items)

    return {
        "status": "ok",
        "dry_run": dry_run,
        "audit_id": audit.id,
        "filters": filters,
        "summary": summary,
        "missing_task_ids": missing_task_ids,
        "orchestrator_result": orchestrator_result,
        "items": response_items,
    }
