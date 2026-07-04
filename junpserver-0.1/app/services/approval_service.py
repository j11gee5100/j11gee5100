from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.failure import format_failure_reason
from app.models import ApprovalActionAudit, ApprovalRequest, Task


APPROVAL_STATUS_PENDING = "pending"
APPROVAL_STATUS_APPROVED = "approved"
APPROVAL_STATUS_REJECTED = "rejected"
APPROVAL_STATUS_EXPIRED = "expired"


def is_approval_required(risk_level: str | None) -> bool:
    return (risk_level or "").strip().lower() == "high-risk"


def _normalize_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _record_approval_action(
    *,
    session: Session,
    approval_id: str,
    task_id: str,
    action: str,
    operator_id: str,
    source_ip: str,
    reason: str,
) -> None:
    session.add(
        ApprovalActionAudit(
            approval_id=approval_id,
            task_id=task_id,
            action=action[:24],
            operator_id=(operator_id or "unknown")[:64],
            source_ip=(source_ip or "unknown")[:64],
            reason=(reason or "")[:1024],
        )
    )


def get_approval_by_task_id(session: Session, task_id: str) -> ApprovalRequest | None:
    return session.scalar(select(ApprovalRequest).where(ApprovalRequest.task_id == task_id))


def create_or_get_task_approval(
    *,
    session: Session,
    task: Task,
    requested_by: str,
    source_ip: str,
    timeout_hours: int,
    escalation_enabled: bool,
    escalation_after_minutes: int,
    max_levels: int,
) -> tuple[ApprovalRequest, bool]:
    existing = get_approval_by_task_id(session, task.id)
    if existing:
        return existing, False

    now_utc = datetime.now(timezone.utc)
    approval = ApprovalRequest(
        task_id=task.id,
        status=APPROVAL_STATUS_PENDING,
        requested_by=(requested_by or "unknown")[:64],
        source_ip=(source_ip or "unknown")[:64],
        current_level=1,
        max_level=max(1, max_levels),
        escalation_count=0,
        requested_at=now_utc,
        expires_at=now_utc + timedelta(hours=max(1, timeout_hours)),
        next_escalate_at=(
            now_utc + timedelta(minutes=max(1, escalation_after_minutes))
            if escalation_enabled and max(1, max_levels) > 1 and escalation_after_minutes > 0
            else None
        ),
    )
    session.add(approval)
    session.flush()
    _record_approval_action(
        session=session,
        approval_id=approval.id,
        task_id=task.id,
        action="created",
        operator_id=requested_by or "unknown",
        source_ip=source_ip or "unknown",
        reason="approval request created for high-risk task",
    )
    return approval, True


def _get_task(session: Session, task_id: str) -> Task | None:
    return session.get(Task, task_id)


def approve_task_approval(
    *,
    session: Session,
    approval: ApprovalRequest,
    operator_id: str,
    source_ip: str,
    reason: str,
) -> tuple[bool, str]:
    if approval.status != APPROVAL_STATUS_PENDING:
        return False, f"approval status={approval.status} cannot be approved"

    now_utc = datetime.now(timezone.utc)
    approval.status = APPROVAL_STATUS_APPROVED
    approval.decided_by = (operator_id or "unknown")[:64]
    approval.decision_reason = (reason or "approved")[:1024]
    approval.decided_at = now_utc

    task = _get_task(session, approval.task_id)
    if task and task.status in ("approval_pending", "pending"):
        task.status = "pending"
        task.reason = "approval granted"

    _record_approval_action(
        session=session,
        approval_id=approval.id,
        task_id=approval.task_id,
        action="approved",
        operator_id=operator_id or "unknown",
        source_ip=source_ip or "unknown",
        reason=reason or "approved",
    )
    return True, "approved"


def reject_task_approval(
    *,
    session: Session,
    approval: ApprovalRequest,
    operator_id: str,
    source_ip: str,
    reason: str,
) -> tuple[bool, str]:
    if approval.status != APPROVAL_STATUS_PENDING:
        return False, f"approval status={approval.status} cannot be rejected"

    now_utc = datetime.now(timezone.utc)
    rejection_reason = (reason or "approval rejected").strip() or "approval rejected"
    approval.status = APPROVAL_STATUS_REJECTED
    approval.decided_by = (operator_id or "unknown")[:64]
    approval.decision_reason = rejection_reason[:1024]
    approval.decided_at = now_utc

    task = _get_task(session, approval.task_id)
    if task and task.status in ("approval_pending", "pending", "planning"):
        task.status = "failed"
        task.reason = format_failure_reason("APPROVAL_REJECTED", rejection_reason)[:1024]

    _record_approval_action(
        session=session,
        approval_id=approval.id,
        task_id=approval.task_id,
        action="rejected",
        operator_id=operator_id or "unknown",
        source_ip=source_ip or "unknown",
        reason=rejection_reason,
    )
    return True, "rejected"


def escalate_task_approval(
    *,
    session: Session,
    approval: ApprovalRequest,
    operator_id: str,
    source_ip: str,
    reason: str,
    escalation_after_minutes: int,
) -> tuple[bool, str]:
    if approval.status != APPROVAL_STATUS_PENDING:
        return False, f"approval status={approval.status} cannot be escalated"
    if approval.current_level >= max(1, approval.max_level):
        return False, f"approval already at max level={approval.max_level}"

    now_utc = datetime.now(timezone.utc)
    approval.current_level += 1
    approval.escalation_count += 1
    approval.next_escalate_at = now_utc + timedelta(minutes=max(1, escalation_after_minutes))
    _record_approval_action(
        session=session,
        approval_id=approval.id,
        task_id=approval.task_id,
        action="escalated",
        operator_id=operator_id or "unknown",
        source_ip=source_ip or "unknown",
        reason=(reason or f"manual escalate to level {approval.current_level}")[:1024],
    )
    return True, "escalated"


def expire_overdue_approvals(
    *,
    session: Session,
    limit: int = 200,
    escalation_enabled: bool = False,
    escalation_after_minutes: int = 30,
) -> dict[str, int]:
    now_utc = datetime.now(timezone.utc)
    conditions = [ApprovalRequest.expires_at <= now_utc]
    if escalation_enabled:
        conditions.append(ApprovalRequest.next_escalate_at <= now_utc)

    stmt = (
        select(ApprovalRequest)
        .where(
            ApprovalRequest.status == APPROVAL_STATUS_PENDING,
            or_(*conditions),
        )
        .order_by(ApprovalRequest.expires_at.asc(), ApprovalRequest.id.asc())
        .limit(max(1, limit))
    )
    approvals = list(session.scalars(stmt))
    expired = 0
    failed_tasks = 0
    escalated = 0
    for approval in approvals:
        approval_next_escalate_at = _normalize_utc(approval.next_escalate_at)
        can_escalate = (
            escalation_enabled
            and approval.current_level < max(1, approval.max_level)
            and approval_next_escalate_at is not None
            and approval_next_escalate_at <= now_utc
        )
        if can_escalate:
            approval.current_level += 1
            approval.escalation_count += 1
            approval.next_escalate_at = now_utc + timedelta(minutes=max(1, escalation_after_minutes))
            _record_approval_action(
                session=session,
                approval_id=approval.id,
                task_id=approval.task_id,
                action="escalated",
                operator_id="system",
                source_ip="127.0.0.1",
                reason=f"approval escalated to level {approval.current_level}",
            )
            escalated += 1
            continue

        approval.status = APPROVAL_STATUS_EXPIRED
        approval.decided_by = "system"
        approval.decision_reason = "approval timeout"
        approval.decided_at = now_utc
        approval.next_escalate_at = None

        task = _get_task(session, approval.task_id)
        if task and task.status in ("approval_pending", "pending", "planning"):
            task.status = "failed"
            task.reason = format_failure_reason("APPROVAL_TIMEOUT", "approval timeout")[:1024]
            failed_tasks += 1

        _record_approval_action(
            session=session,
            approval_id=approval.id,
            task_id=approval.task_id,
            action="expired",
            operator_id="system",
            source_ip="127.0.0.1",
            reason="approval timeout",
        )
        expired += 1

    if expired:
        session.flush()
    if escalated and not expired:
        session.flush()
    return {"expired": expired, "failed_tasks": failed_tasks, "escalated": escalated}
