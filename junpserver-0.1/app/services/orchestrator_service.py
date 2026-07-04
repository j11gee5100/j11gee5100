from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.failure import format_failure_reason, infer_failure_code
from app.models import ApprovalRequest, AssetProjection, AuditLink, Execution, Task
from app.services.approval_service import (
    APPROVAL_STATUS_APPROVED,
    APPROVAL_STATUS_EXPIRED,
    APPROVAL_STATUS_PENDING,
    APPROVAL_STATUS_REJECTED,
    is_approval_required,
)
from app.services.jumpserver.client import JumpServerClient, JumpServerClientError
from app.services.jumpserver.schemas import CommandExecutionRequest
from app.services.sync_service import refresh_asset_once


def _pick_pending_tasks(session: Session, limit: int = 5) -> list[Task]:
    stmt = (
        select(Task)
        .where(Task.status == "pending")
        .order_by(Task.created_at.asc())
        .limit(limit)
    )
    return list(session.scalars(stmt))


def _pick_running_executions(session: Session, limit: int = 20) -> list[Execution]:
    stmt = (
        select(Execution)
        .where(Execution.status == "running")
        .order_by(Execution.started_at.asc())
        .limit(limit)
    )
    return list(session.scalars(stmt))


def _mark_task_failed(task: Task, reason: str, code: str = "UNKNOWN") -> None:
    task.status = "failed"
    task.reason = format_failure_reason(code, reason)[:1024]


def _resolve_target_asset_projection(session: Session, target_asset_id: str) -> AssetProjection | None:
    if not target_asset_id:
        return None
    by_local_id = session.get(AssetProjection, target_asset_id)
    if by_local_id:
        return by_local_id
    return session.scalar(select(AssetProjection).where(AssetProjection.jms_asset_id == target_asset_id))


def _validate_asset_execution_gate(session: Session, task: Task) -> tuple[bool, str, str]:
    projection = _resolve_target_asset_projection(session=session, target_asset_id=task.target_asset_id)
    if not projection:
        return False, "ASSET_NOT_FOUND", f"asset projection not found for target_asset_id={task.target_asset_id}"

    if projection.status != "active":
        return (
            False,
            "ASSET_INACTIVE",
            f"asset is inactive for execution: jms_asset_id={projection.jms_asset_id}",
        )

    freshness = (projection.freshness_status or "").strip().lower()
    if freshness == "expired":
        return (
            False,
            "ASSET_EXPIRED",
            f"asset freshness expired: jms_asset_id={projection.jms_asset_id}; refresh sync required",
        )
    if freshness == "stale":
        return (
            False,
            "ASSET_STALE",
            f"asset freshness stale: jms_asset_id={projection.jms_asset_id}; refresh sync required",
        )
    return True, "", ""


def _attempt_asset_gate_auto_refresh(
    *,
    session: Session,
    client: JumpServerClient,
    task: Task,
    fail_code: str,
    fail_reason: str,
) -> tuple[bool, str, str]:
    if not settings.execution_gate_auto_refresh_enabled:
        return False, fail_code, fail_reason
    if fail_code not in {"ASSET_STALE", "ASSET_EXPIRED"}:
        return False, fail_code, fail_reason

    try:
        refresh_result = refresh_asset_once(
            session=session,
            client=client,
            jms_asset_id=task.target_asset_id,
            search_limit=max(1, settings.execution_gate_refresh_search_limit),
        )
    except JumpServerClientError as exc:
        return (
            False,
            fail_code,
            f"{fail_reason}; auto refresh failed: {exc}",
        )
    except Exception as exc:  # pragma: no cover - defensive guard
        return (
            False,
            fail_code,
            f"{fail_reason}; auto refresh error: {exc}",
        )

    if not refresh_result.get("found"):
        return (
            False,
            "ASSET_NOT_FOUND",
            f"asset not found on jumpserver during auto refresh: target_asset_id={task.target_asset_id}",
        )

    is_allowed, refreshed_fail_code, refreshed_fail_reason = _validate_asset_execution_gate(
        session=session,
        task=task,
    )
    if is_allowed:
        return True, "", ""
    return False, refreshed_fail_code, refreshed_fail_reason


def _result_to_text(value: object | None) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False)
    except TypeError:
        return str(value)


def _normalize_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _extract_result_error_message(result: object | None) -> str:
    if isinstance(result, dict):
        summary = result.get("summary")
        if isinstance(summary, dict):
            error = summary.get("error")
            if isinstance(error, str) and error.strip():
                return error.strip()
            dark = summary.get("dark")
            if isinstance(dark, dict):
                for host, detail in dark.items():
                    if isinstance(detail, str) and detail.strip():
                        if isinstance(host, str) and host.strip():
                            return f"{host}: {detail.strip()}"
                        return detail.strip()
            failures = summary.get("failures")
            if isinstance(failures, dict):
                for host, detail in failures.items():
                    if isinstance(detail, str) and detail.strip():
                        if isinstance(host, str) and host.strip():
                            return f"{host}: {detail.strip()}"
                        return detail.strip()
        for key in ("error", "message", "detail"):
            value = result.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        status = result.get("status")
        if isinstance(status, dict):
            label = status.get("label")
            if isinstance(label, str) and label.strip():
                return label.strip()
            value = status.get("value")
            if isinstance(value, str) and value.strip():
                return value.strip()
        if isinstance(status, str) and status.strip():
            return status.strip()
    if isinstance(result, str) and result.strip():
        return result.strip()
    return "jumpserver execution failed"


def _result_success_hint(result: object | None) -> bool | None:
    if isinstance(result, dict):
        is_success = result.get("is_success")
        if isinstance(is_success, bool):
            return is_success

        status = result.get("status")
        if isinstance(status, dict):
            value = status.get("value")
            if isinstance(value, str):
                lowered = value.lower().strip()
                if lowered in ("success", "successful"):
                    return True
                if lowered in ("failed", "failure", "timeout", "error"):
                    return False
        elif isinstance(status, str):
            lowered = status.lower().strip()
            if lowered in ("success", "successful"):
                return True
            if lowered in ("failed", "failure", "timeout", "error"):
                return False

        state = result.get("state")
        if isinstance(state, str):
            uppered = state.upper().strip()
            if uppered in ("SUCCESS", "SUCCEEDED"):
                return True
            if uppered in ("FAILED", "FAILURE", "TIMEOUT", "ERROR"):
                return False
    return None


def _is_execution_stale(execution: Execution, now_utc: datetime) -> bool:
    timeout_sec = settings.jumpserver_execution_timeout_sec
    if timeout_sec <= 0:
        return False
    started = _normalize_utc(execution.started_at)
    if started is None:
        return False
    age = (now_utc - started).total_seconds()
    return age >= timeout_sec


def _extract_items(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        data = payload.get("results")
        if isinstance(data, list):
            return data
        data = payload.get("data")
        if isinstance(data, list):
            return data
    return []


def _extract_relation_id(item: dict) -> str:
    for key in ("id", "uuid", "pk"):
        value = item.get(key)
        if isinstance(value, str) and value:
            return value
        if isinstance(value, int):
            return str(value)
    return ""


def _collect_execution_candidates(item: dict) -> set[str]:
    candidates: set[str] = set()
    for key, value in item.items():
        if "execution" not in key.lower():
            continue
        if isinstance(value, str) and value:
            candidates.add(value)
        elif isinstance(value, dict):
            for nested_key in ("id", "uuid"):
                nested_val = value.get(nested_key)
                if isinstance(nested_val, str) and nested_val:
                    candidates.add(nested_val)
    return candidates


def _ingest_audit_links(session: Session, client: JumpServerClient, task: Task, execution: Execution) -> int:
    created = 0
    try:
        payload = client.list_audit_relations(limit=200, offset=0)
    except Exception:
        return 0

    for item in _extract_items(payload):
        if not isinstance(item, dict):
            continue

        relation_id = _extract_relation_id(item)
        if not relation_id:
            continue

        candidates = _collect_execution_candidates(item)
        if execution.jms_execution_id not in candidates:
            continue

        existing = session.scalar(
            select(AuditLink).where(AuditLink.jms_audit_relation_id == relation_id)
        )
        if existing:
            continue

        session.add(
            AuditLink(
                task_id=task.id,
                execution_id=execution.id,
                jms_audit_relation_id=relation_id,
                trace_id=task.trace_id,
            )
        )
        created += 1

    session.flush()
    return created


def run_orchestrator_tick(session: Session, client: JumpServerClient) -> dict[str, int]:
    created_exec_count = 0
    finished_exec_count = 0
    audit_links_created = 0
    now_utc = datetime.now(timezone.utc)

    for execution in _pick_running_executions(session):
        try:
            status_resp = client.get_command_execution(execution.jms_execution_id)
        except JumpServerClientError as exc:
            inferred_code = infer_failure_code(str(exc)) or "UPSTREAM_ERROR"
            execution.result_summary = format_failure_reason(inferred_code, str(exc))[:2048]
            continue
        normalized = _result_to_text(status_resp.result)
        if normalized:
            execution.result_summary = normalized
        if not status_resp.is_finished:
            if not _is_execution_stale(execution, now_utc):
                continue
            execution.status = "failed"
            execution.finished_at = now_utc
            if not execution.result_summary:
                execution.result_summary = format_failure_reason(
                    "EXECUTION_TIMEOUT",
                    "jumpserver execution timeout",
                )
            task = session.get(Task, execution.task_id)
            if task and task.status in ("pending", "planning", "executing"):
                _mark_task_failed(task, "jumpserver execution timeout", code="EXECUTION_TIMEOUT")
            finished_exec_count += 1
            continue

        task = session.get(Task, execution.task_id)
        success_hint = _result_success_hint(status_resp.result)
        if success_hint is False:
            failed_reason = _extract_result_error_message(status_resp.result)
            failed_code = infer_failure_code(failed_reason) or "EXECUTION_FAILED"
            execution.status = "failed"
            execution.finished_at = now_utc
            execution.result_summary = format_failure_reason(failed_code, failed_reason)[:2048]
            if task and task.status in ("pending", "planning", "executing"):
                _mark_task_failed(task, failed_reason, code=failed_code)
            finished_exec_count += 1
            continue

        execution.status = "success"
        execution.finished_at = now_utc
        if task:
            task.status = "success"
            audit_links_created += _ingest_audit_links(session, client, task, execution)
        finished_exec_count += 1

    for task in _pick_pending_tasks(session):
        task.status = "planning"
        if is_approval_required(task.risk_level):
            approval = session.scalar(select(ApprovalRequest).where(ApprovalRequest.task_id == task.id))
            if not approval or approval.status == APPROVAL_STATUS_PENDING:
                task.status = "approval_pending"
                task.reason = "awaiting approval"
                continue
            if approval.status == APPROVAL_STATUS_REJECTED:
                _mark_task_failed(task, approval.decision_reason or "approval rejected", code="APPROVAL_REJECTED")
                continue
            if approval.status == APPROVAL_STATUS_EXPIRED:
                _mark_task_failed(task, approval.decision_reason or "approval timeout", code="APPROVAL_TIMEOUT")
                continue
            if approval.status != APPROVAL_STATUS_APPROVED:
                _mark_task_failed(
                    task,
                    f"unexpected approval status={approval.status}",
                    code="APPROVAL_REJECTED",
                )
                continue

        if not task.command or not task.target_asset_id or not task.run_as_system_user_id:
            _mark_task_failed(
                task,
                "missing required fields: command/target_asset_id/run_as_system_user_id",
                code="VALIDATION_ERROR",
            )
            continue

        is_allowed, fail_code, fail_reason = _validate_asset_execution_gate(session=session, task=task)
        if not is_allowed:
            refreshed_allowed, refreshed_fail_code, refreshed_fail_reason = _attempt_asset_gate_auto_refresh(
                session=session,
                client=client,
                task=task,
                fail_code=fail_code,
                fail_reason=fail_reason,
            )
            if refreshed_allowed:
                is_allowed = True
            else:
                fail_code = refreshed_fail_code
                fail_reason = refreshed_fail_reason
        if not is_allowed:
            _mark_task_failed(task, fail_reason, code=fail_code)
            continue

        task.status = "executing"
        req = CommandExecutionRequest(
            command=task.command,
            run_as=task.run_as_system_user_id,
            hosts=[task.target_asset_id],
        )
        try:
            execution_resp = client.create_command_execution(req)
        except JumpServerClientError as exc:
            inferred_code = infer_failure_code(str(exc)) or "UPSTREAM_ERROR"
            _mark_task_failed(task, str(exc), code=inferred_code)
            continue
        except Exception as exc:  # pragma: no cover - defensive guard
            _mark_task_failed(task, str(exc), code="INTERNAL_ERROR")
            continue
        if not execution_resp.id:
            _mark_task_failed(task, "jumpserver execution id is empty", code="UPSTREAM_BAD_RESPONSE")
            continue

        execution_status = "success" if execution_resp.is_finished else "running"
        execution = Execution(
            task_id=task.id,
            jms_execution_id=execution_resp.id,
            status=execution_status,
            result_summary=_result_to_text(execution_resp.result),
        )
        session.add(execution)
        if execution_resp.is_finished:
            execution.finished_at = now_utc
            task.status = "success"
            audit_links_created += _ingest_audit_links(session, client, task, execution)
        session.flush()
        created_exec_count += 1

    return {
        "created_executions": created_exec_count,
        "finished_executions": finished_exec_count,
        "created_audit_links": audit_links_created,
    }
