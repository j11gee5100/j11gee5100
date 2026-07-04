from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Callable

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.callback_security import evaluate_callback_url_policy
from app.core.failure import infer_failure_code, strip_failure_prefix
from app.models import CallbackDelivery, CallbackHook, Execution, Task


_TERMINAL_TASK_STATUSES = ("success", "failed", "canceled")
_DELIVERY_PENDING_STATUSES = ("pending", "retrying")


class CallbackDeliveryError(Exception):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _build_task_callback_payload(session: Session, task: Task) -> dict:
    failure_code = infer_failure_code(task.reason)
    reason = strip_failure_prefix(task.reason) if failure_code else task.reason

    latest_execution = session.scalar(
        select(Execution)
        .where(Execution.task_id == task.id)
        .order_by(Execution.created_at.desc())
        .limit(1)
    )

    payload = {
        "event_type": "task_finalized",
        "task_id": task.id,
        "status": task.status,
        "failure_code": failure_code,
        "reason": reason,
        "source": task.source,
        "risk_level": task.risk_level,
        "target_asset_id": task.target_asset_id,
        "run_as_system_user_id": task.run_as_system_user_id,
        "trace_id": task.trace_id,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
        "timestamp": _utcnow().isoformat(),
    }
    if latest_execution:
        payload.update(
            {
                "execution_id": latest_execution.id,
                "jms_execution_id": latest_execution.jms_execution_id,
                "execution_status": latest_execution.status,
                "execution_finished_at": latest_execution.finished_at.isoformat()
                if latest_execution.finished_at
                else None,
            }
        )
    return payload


def _enqueue_terminal_task_deliveries(session: Session) -> int:
    created = 0
    hook_stmt = select(CallbackHook).where(CallbackHook.status == "active")
    hooks = list(session.scalars(hook_stmt))
    for hook in hooks:
        task = session.get(Task, hook.task_id)
        if not task or task.status not in _TERMINAL_TASK_STATUSES:
            continue

        existing = session.scalar(
            select(CallbackDelivery).where(
                CallbackDelivery.task_id == task.id,
                CallbackDelivery.event_type == "task_finalized",
            )
        )
        if existing:
            continue

        payload = _build_task_callback_payload(session, task)
        session.add(
            CallbackDelivery(
                task_id=task.id,
                hook_id=hook.id,
                event_type="task_finalized",
                status="pending",
                attempts=0,
                max_attempts=max(1, settings.callback_max_attempts),
                next_retry_at=_utcnow(),
                payload_json=json.dumps(payload, ensure_ascii=False),
            )
        )
        created += 1
    if created:
        session.flush()
    return created


def _compute_signature(secret: str, body: str, timestamp: str, nonce: str) -> str:
    signing_payload = f"{timestamp}.{nonce}.{body}"
    digest = hmac.new(secret.encode("utf-8"), signing_payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _default_sender(url: str, body: str, headers: dict[str, str], timeout_sec: int) -> tuple[int, str]:
    try:
        response = httpx.post(url, content=body.encode("utf-8"), headers=headers, timeout=timeout_sec)
    except httpx.HTTPError as exc:  # pragma: no cover - network guard
        raise CallbackDeliveryError(str(exc)) from exc
    return response.status_code, response.text


def _build_retry_delay_sec(attempts: int) -> int:
    base = max(1, settings.callback_retry_base_sec)
    exponent = max(0, attempts - 1)
    return min(base * (2**exponent), 300)


def _pick_due_deliveries(session: Session, limit: int) -> list[CallbackDelivery]:
    now_utc = _utcnow()
    stmt = (
        select(CallbackDelivery)
        .where(CallbackDelivery.status.in_(_DELIVERY_PENDING_STATUSES))
        .where(
            (CallbackDelivery.next_retry_at.is_(None))
            | (CallbackDelivery.next_retry_at <= now_utc)
        )
        .order_by(CallbackDelivery.created_at.asc())
        .limit(limit)
    )
    return list(session.scalars(stmt))


def run_callback_tick(
    session: Session,
    sender: Callable[[str, str, dict[str, str], int], tuple[int, str]] | None = None,
) -> dict[str, int]:
    created = _enqueue_terminal_task_deliveries(session)

    processed = 0
    delivered = 0
    retried = 0
    dead = 0
    sender_fn = sender or _default_sender
    due = _pick_due_deliveries(session, limit=max(1, settings.callback_batch_size))

    for delivery in due:
        processed += 1
        hook = session.get(CallbackHook, delivery.hook_id)
        if not hook or hook.status != "active":
            delivery.status = "dead"
            delivery.last_error = "callback hook inactive or missing"
            delivery.next_retry_at = None
            dead += 1
            continue

        task = session.get(Task, delivery.task_id)
        trace_id = task.trace_id if task else ""
        body = delivery.payload_json or "{}"
        policy = evaluate_callback_url_policy(hook.callback_url, resolve_dns=True)
        if not policy.allowed:
            delivery.status = "dead"
            delivery.last_http_status = None
            delivery.last_error = f"callback blocked: {policy.reason}"[:1024]
            delivery.next_retry_at = None
            dead += 1
            continue

        sign_timestamp = str(int(_utcnow().timestamp()))
        sign_nonce = f"{delivery.id}-{delivery.attempts + 1}-{uuid.uuid4().hex[:8]}"
        headers = {
            "Content-Type": "application/json",
            "X-OpsPaw-Delivery-Id": delivery.id,
            "X-OpsPaw-Event-Type": delivery.event_type,
            "X-OpsPaw-Signature-Timestamp": sign_timestamp,
            "X-OpsPaw-Signature-Nonce": sign_nonce,
        }
        if trace_id:
            headers["X-Trace-Id"] = trace_id
        if hook.callback_secret:
            headers["X-OpsPaw-Signature"] = _compute_signature(
                hook.callback_secret,
                body,
                sign_timestamp,
                sign_nonce,
            )

        delivery.attempts += 1
        now_utc = _utcnow()
        try:
            status_code, response_text = sender_fn(
                hook.callback_url,
                body,
                headers,
                max(1, settings.callback_http_timeout_sec),
            )
        except Exception as exc:
            status_code = None
            response_text = str(exc)

        if status_code is not None and 200 <= status_code < 300:
            delivery.status = "success"
            delivery.last_http_status = status_code
            delivery.last_error = ""
            delivery.next_retry_at = None
            delivered += 1
            continue

        delivery.last_http_status = status_code
        trimmed_error = (response_text or "callback failed").strip()
        delivery.last_error = trimmed_error[:1024]
        if delivery.attempts >= max(1, delivery.max_attempts):
            delivery.status = "dead"
            delivery.next_retry_at = None
            dead += 1
        else:
            delay_sec = _build_retry_delay_sec(delivery.attempts)
            delivery.status = "retrying"
            delivery.next_retry_at = now_utc + timedelta(seconds=delay_sec)
            retried += 1

    if created or processed:
        session.flush()
    return {
        "created_deliveries": created,
        "processed_deliveries": processed,
        "delivered": delivered,
        "retried": retried,
        "dead": dead,
    }
