from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models import ApprovalActionAudit, ApprovalRequest, AssetProjection, Execution, Task
from app.services.approval_service import (
    APPROVAL_STATUS_APPROVED,
    APPROVAL_STATUS_PENDING,
    APPROVAL_STATUS_REJECTED,
    expire_overdue_approvals,
)
from app.services.jumpserver.schemas import CommandExecutionResponse
from app.services.orchestrator_service import run_orchestrator_tick


class _NeverCreateClient:
    def create_command_execution(self, request):
        raise AssertionError("create_command_execution should not be called")

    def get_command_execution(self, execution_id: str):
        raise AssertionError("get_command_execution should not be called")

    def list_audit_relations(self, limit=200, offset=0):
        return {"results": []}


class _CreateClient:
    def create_command_execution(self, request):
        return CommandExecutionResponse(id="jms-approval-1", is_finished=False, result="")

    def get_command_execution(self, execution_id: str):
        return CommandExecutionResponse(id=execution_id, is_finished=True, result="ok")

    def list_audit_relations(self, limit=200, offset=0):
        return {"results": []}


def _seed_asset(db_session, jms_asset_id: str = "asset-approval-1"):
    db_session.add(
        AssetProjection(
            jms_asset_id=jms_asset_id,
            hostname=f"host-{jms_asset_id}",
            ip="10.0.0.20",
            status="active",
            freshness_status="fresh",
        )
    )
    db_session.flush()


def _seed_high_risk_task(db_session, *, status: str = "pending", idem: str = "approval-task-1") -> Task:
    task = Task(
        trace_id=f"trace-{idem}",
        source="api",
        status=status,
        risk_level="high-risk",
        idempotency_key=idem,
        command="hostname",
        target_asset_id="asset-approval-1",
        run_as_system_user_id="su-approval-1",
        reason="test",
    )
    db_session.add(task)
    db_session.flush()
    return task


def test_expire_overdue_approvals_marks_task_failed_and_writes_audit(db_session):
    task = _seed_high_risk_task(db_session, status="approval_pending", idem="approval-expire-1")
    db_session.add(
        ApprovalRequest(
            task_id=task.id,
            status=APPROVAL_STATUS_PENDING,
            requested_by="creator",
            source_ip="127.0.0.1",
            requested_at=datetime.now(timezone.utc) - timedelta(hours=2),
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
    )
    db_session.commit()

    result = expire_overdue_approvals(session=db_session, limit=100)
    db_session.commit()

    assert result["expired"] == 1
    assert result["failed_tasks"] == 1

    stored_task = db_session.get(Task, task.id)
    assert stored_task is not None
    assert stored_task.status == "failed"
    assert stored_task.reason.startswith("[APPROVAL_TIMEOUT]")

    approval = db_session.query(ApprovalRequest).filter(ApprovalRequest.task_id == task.id).one()
    assert approval.status == "expired"
    assert approval.decided_by == "system"

    action = db_session.query(ApprovalActionAudit).filter(ApprovalActionAudit.approval_id == approval.id).one()
    assert action.action == "expired"


def test_orchestrator_moves_high_risk_task_to_approval_pending_when_missing_approval(db_session):
    _seed_asset(db_session)
    task = _seed_high_risk_task(db_session, status="pending", idem="approval-orch-1")
    db_session.commit()

    result = run_orchestrator_tick(session=db_session, client=_NeverCreateClient())
    db_session.commit()

    assert result["created_executions"] == 0
    stored_task = db_session.get(Task, task.id)
    assert stored_task is not None
    assert stored_task.status == "approval_pending"
    assert stored_task.reason == "awaiting approval"


def test_orchestrator_runs_high_risk_task_after_approved(db_session):
    _seed_asset(db_session)
    task = _seed_high_risk_task(db_session, status="pending", idem="approval-orch-2")
    db_session.add(
        ApprovalRequest(
            task_id=task.id,
            status=APPROVAL_STATUS_APPROVED,
            requested_by="creator",
            source_ip="127.0.0.1",
            requested_at=datetime.now(timezone.utc) - timedelta(hours=1),
            decided_by="approver",
            decision_reason="approved",
            decided_at=datetime.now(timezone.utc) - timedelta(minutes=30),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
    )
    db_session.commit()

    result = run_orchestrator_tick(session=db_session, client=_CreateClient())
    db_session.commit()

    assert result["created_executions"] == 1
    stored_task = db_session.get(Task, task.id)
    assert stored_task is not None
    assert stored_task.status == "executing"
    execution = db_session.query(Execution).filter(Execution.task_id == task.id).one()
    assert execution.status == "running"


def test_orchestrator_fails_high_risk_task_when_rejected(db_session):
    _seed_asset(db_session)
    task = _seed_high_risk_task(db_session, status="pending", idem="approval-orch-3")
    db_session.add(
        ApprovalRequest(
            task_id=task.id,
            status=APPROVAL_STATUS_REJECTED,
            requested_by="creator",
            source_ip="127.0.0.1",
            requested_at=datetime.now(timezone.utc) - timedelta(hours=1),
            decided_by="approver",
            decision_reason="manual reject",
            decided_at=datetime.now(timezone.utc) - timedelta(minutes=20),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
    )
    db_session.commit()

    result = run_orchestrator_tick(session=db_session, client=_NeverCreateClient())
    db_session.commit()

    assert result["created_executions"] == 0
    stored_task = db_session.get(Task, task.id)
    assert stored_task is not None
    assert stored_task.status == "failed"
    assert stored_task.reason.startswith("[APPROVAL_REJECTED]")


def test_expire_overdue_approvals_supports_escalation_then_expire(db_session):
    task = _seed_high_risk_task(db_session, status="approval_pending", idem="approval-escalate-1")
    approval = ApprovalRequest(
        task_id=task.id,
        status=APPROVAL_STATUS_PENDING,
        requested_by="creator",
        source_ip="127.0.0.1",
        current_level=1,
        max_level=2,
        escalation_count=0,
        requested_at=datetime.now(timezone.utc) - timedelta(hours=1),
        next_escalate_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db_session.add(approval)
    db_session.commit()

    first = expire_overdue_approvals(
        session=db_session,
        limit=100,
        escalation_enabled=True,
        escalation_after_minutes=30,
    )
    db_session.commit()
    assert first["escalated"] == 1
    assert first["expired"] == 0

    stored = db_session.get(ApprovalRequest, approval.id)
    assert stored is not None
    assert stored.current_level == 2
    assert stored.status == "pending"
    assert stored.escalation_count == 1

    stored.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.commit()
    second = expire_overdue_approvals(
        session=db_session,
        limit=100,
        escalation_enabled=True,
        escalation_after_minutes=30,
    )
    db_session.commit()
    assert second["expired"] == 1
    assert second["failed_tasks"] == 1

    final_task = db_session.get(Task, task.id)
    assert final_task is not None
    assert final_task.status == "failed"
    assert final_task.reason.startswith("[APPROVAL_TIMEOUT]")


def test_expire_overdue_approvals_handles_naive_next_escalate_at(db_session):
    task = _seed_high_risk_task(db_session, status="approval_pending", idem="approval-naive-escalate-1")
    # Simulate postgres/driver returning naive datetime.
    naive_next = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1)
    approval = ApprovalRequest(
        task_id=task.id,
        status=APPROVAL_STATUS_PENDING,
        requested_by="creator",
        source_ip="127.0.0.1",
        current_level=1,
        max_level=2,
        escalation_count=0,
        requested_at=datetime.now(timezone.utc) - timedelta(hours=1),
        next_escalate_at=naive_next,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db_session.add(approval)
    db_session.commit()

    result = expire_overdue_approvals(
        session=db_session,
        limit=100,
        escalation_enabled=True,
        escalation_after_minutes=30,
    )
    db_session.commit()

    assert result["escalated"] == 1
    stored = db_session.get(ApprovalRequest, approval.id)
    assert stored is not None
    assert stored.current_level == 2
