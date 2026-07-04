from __future__ import annotations

from datetime import datetime, timezone

from app.models import AssetProjection, AuditLink, Execution, Task
from app.core.config import settings
from app.services.orchestrator_service import run_orchestrator_tick
from app.services.jumpserver.client import JumpServerClientError
from app.services.jumpserver.schemas import CommandExecutionResponse


class FakeOrchestratorClient:
    def __init__(self):
        self.created = 0

    def create_command_execution(self, request):
        self.created += 1
        assert request.command == "hostname"
        assert request.run_as == "su-local-1"
        assert request.hosts == ["asset-local-1"]
        return CommandExecutionResponse(id=f"jms-{self.created}", is_finished=False, result="")

    def get_command_execution(self, execution_id: str):
        assert execution_id.startswith("jms-")
        return CommandExecutionResponse(id=execution_id, is_finished=True, result="ok")

    def list_audit_relations(self, limit=200, offset=0):
        assert limit == 200
        assert offset == 0
        return {
            "results": [
                {"id": "audit-1", "command_execution": "jms-1"},
                {"id": "audit-2", "command_execution": "jms-2"},
            ]
        }


class FakeUpstreamErrorClient(FakeOrchestratorClient):
    def create_command_execution(self, request):
        raise JumpServerClientError("upstream failed")


class FakePermissionDeniedCreateClient(FakeOrchestratorClient):
    def create_command_execution(self, request):
        raise JumpServerClientError("jumpserver POST /api/v1/ops/jobs/ failed status=403 body=forbidden")


class FakeIntAuditRelationClient(FakeOrchestratorClient):
    def list_audit_relations(self, limit=200, offset=0):
        assert limit == 200
        assert offset == 0
        return {
            "results": [
                {"id": 7, "commandexecution": "jms-1"},
            ]
        }


class FakeRunningClient:
    def get_command_execution(self, execution_id: str):
        return CommandExecutionResponse(id=execution_id, is_finished=False, result={})

    def create_command_execution(self, request):
        raise AssertionError("unexpected create call")


class FakeFinishedFailedClient(FakeOrchestratorClient):
    def get_command_execution(self, execution_id: str):
        return CommandExecutionResponse(
            id=execution_id,
            is_finished=True,
            result={"is_success": False, "summary": {"error": "no permission"}},
        )


class FakeFinishedDarkFailureClient(FakeOrchestratorClient):
    def get_command_execution(self, execution_id: str):
        return CommandExecutionResponse(
            id=execution_id,
            is_finished=True,
            result={
                "is_success": False,
                "status": {"value": "failed", "label": "失败"},
                "summary": {
                    "dark": {
                        "opspaw-dev-host-01": "shell: Failed to connect to host 10.10.10.10:22",
                    }
                },
            },
        )


class FakeAutoRefreshClient(FakeOrchestratorClient):
    def list_assets_page(self, search=None, limit=50, offset=0, extra_params=None):
        class Asset:
            def __init__(self, asset_id: str, hostname: str, ip: str):
                self.id = asset_id
                self.hostname = hostname
                self.ip = ip
                self.address = ""

        if offset != 0:
            return [], 1
        if search == "asset-local-1":
            return [Asset("asset-local-1", "refreshed-host", "10.0.0.88")], 1
        return [], 0

    def list_asset_system_users(self, asset_id: str):
        class User:
            id = "su-local-1"
            name = "root"
            username = "root"

        return [User()]


class FakeAutoRefreshNotFoundClient(FakeOrchestratorClient):
    def list_assets_page(self, search=None, limit=50, offset=0, extra_params=None):
        return [], 0

    def list_asset_system_users(self, asset_id: str):
        return []


def _seed_asset_projection(
    db_session,
    *,
    jms_asset_id: str = "asset-local-1",
    status: str = "active",
    freshness_status: str = "fresh",
) -> AssetProjection:
    asset = AssetProjection(
        jms_asset_id=jms_asset_id,
        hostname=f"host-{jms_asset_id}",
        ip="10.0.0.1",
        status=status,
        freshness_status=freshness_status,
    )
    db_session.add(asset)
    db_session.flush()
    return asset


def test_orchestrator_tick_runs_pending_task_and_finishes_execution(db_session):
    _seed_asset_projection(db_session, jms_asset_id="asset-local-1", status="active", freshness_status="fresh")
    task = Task(
        trace_id="trace-1",
        source="api",
        status="pending",
        risk_level="readonly",
        idempotency_key="idempotency-1",
        command="hostname",
        target_asset_id="asset-local-1",
        run_as_system_user_id="su-local-1",
        reason="test",
    )
    db_session.add(task)
    db_session.commit()

    client = FakeOrchestratorClient()

    first = run_orchestrator_tick(session=db_session, client=client)
    db_session.commit()
    assert first["created_executions"] == 1
    assert first["finished_executions"] == 0

    second = run_orchestrator_tick(session=db_session, client=client)
    db_session.commit()
    assert second["finished_executions"] == 1
    assert second["created_audit_links"] == 1

    stored_task = db_session.query(Task).filter(Task.id == task.id).one()
    stored_execution = db_session.query(Execution).filter(Execution.task_id == task.id).one()
    stored_audit = db_session.query(AuditLink).filter(AuditLink.execution_id == stored_execution.id).one()

    assert stored_task.status == "success"
    assert stored_execution.status == "success"
    assert stored_execution.jms_execution_id == "jms-1"
    assert stored_audit.jms_audit_relation_id == "audit-1"


def test_orchestrator_tick_marks_pending_task_failed_when_upstream_errors(db_session):
    _seed_asset_projection(db_session, jms_asset_id="asset-local-1", status="active", freshness_status="fresh")
    task = Task(
        trace_id="trace-upstream-1",
        source="api",
        status="pending",
        risk_level="readonly",
        idempotency_key="idempotency-upstream-1",
        command="hostname",
        target_asset_id="asset-local-1",
        run_as_system_user_id="su-local-1",
        reason="test",
    )
    db_session.add(task)
    db_session.commit()

    result = run_orchestrator_tick(session=db_session, client=FakeUpstreamErrorClient())
    db_session.commit()

    assert result["created_executions"] == 0
    stored_task = db_session.query(Task).filter(Task.id == task.id).one()
    assert stored_task.status == "failed"
    assert stored_task.reason.startswith("[UPSTREAM_ERROR]")


def test_orchestrator_tick_marks_pending_task_failed_when_permission_denied(db_session):
    _seed_asset_projection(db_session, jms_asset_id="asset-local-1", status="active", freshness_status="fresh")
    task = Task(
        trace_id="trace-permission-1",
        source="api",
        status="pending",
        risk_level="readonly",
        idempotency_key="idempotency-permission-1",
        command="hostname",
        target_asset_id="asset-local-1",
        run_as_system_user_id="su-local-1",
        reason="test",
    )
    db_session.add(task)
    db_session.commit()

    result = run_orchestrator_tick(session=db_session, client=FakePermissionDeniedCreateClient())
    db_session.commit()

    assert result["created_executions"] == 0
    stored_task = db_session.query(Task).filter(Task.id == task.id).one()
    assert stored_task.status == "failed"
    assert stored_task.reason.startswith("[PERMISSION_DENIED]")


def test_orchestrator_tick_marks_stale_running_execution_failed(db_session):
    task = Task(
        trace_id="trace-timeout-1",
        source="api",
        status="executing",
        risk_level="readonly",
        idempotency_key="idempotency-timeout-1",
        command="hostname",
        target_asset_id="asset-local-1",
        run_as_system_user_id="su-local-1",
        reason="test",
    )
    db_session.add(task)
    db_session.flush()

    execution = Execution(
        task_id=task.id,
        jms_execution_id="jms-timeout-1",
        status="running",
        result_summary="",
        started_at=datetime(2000, 1, 1, tzinfo=timezone.utc),
    )
    db_session.add(execution)
    db_session.commit()

    result = run_orchestrator_tick(session=db_session, client=FakeRunningClient())
    db_session.commit()

    assert result["finished_executions"] == 1
    stored_task = db_session.query(Task).filter(Task.id == task.id).one()
    stored_execution = db_session.query(Execution).filter(Execution.id == execution.id).one()
    assert stored_task.status == "failed"
    assert stored_task.reason.startswith("[EXECUTION_TIMEOUT]")
    assert stored_execution.status == "failed"


def test_orchestrator_tick_ingests_int_audit_relation_id(db_session):
    _seed_asset_projection(db_session, jms_asset_id="asset-local-1", status="active", freshness_status="fresh")
    task = Task(
        trace_id="trace-int-audit-1",
        source="api",
        status="pending",
        risk_level="readonly",
        idempotency_key="idempotency-int-audit-1",
        command="hostname",
        target_asset_id="asset-local-1",
        run_as_system_user_id="su-local-1",
        reason="test",
    )
    db_session.add(task)
    db_session.commit()

    client = FakeIntAuditRelationClient()
    first = run_orchestrator_tick(session=db_session, client=client)
    db_session.commit()
    assert first["created_executions"] == 1

    second = run_orchestrator_tick(session=db_session, client=client)
    db_session.commit()
    assert second["finished_executions"] == 1
    assert second["created_audit_links"] == 1

    stored_execution = db_session.query(Execution).filter(Execution.task_id == task.id).one()
    stored_audit = db_session.query(AuditLink).filter(AuditLink.execution_id == stored_execution.id).one()
    assert stored_audit.jms_audit_relation_id == "7"


def test_orchestrator_tick_marks_finished_execution_failed_when_upstream_reports_failure(db_session):
    _seed_asset_projection(db_session, jms_asset_id="asset-local-1", status="active", freshness_status="fresh")
    task = Task(
        trace_id="trace-failed-finish-1",
        source="api",
        status="pending",
        risk_level="readonly",
        idempotency_key="idempotency-failed-finish-1",
        command="hostname",
        target_asset_id="asset-local-1",
        run_as_system_user_id="su-local-1",
        reason="test",
    )
    db_session.add(task)
    db_session.commit()

    client = FakeFinishedFailedClient()
    first = run_orchestrator_tick(session=db_session, client=client)
    db_session.commit()
    assert first["created_executions"] == 1

    second = run_orchestrator_tick(session=db_session, client=client)
    db_session.commit()
    assert second["finished_executions"] == 1

    stored_task = db_session.query(Task).filter(Task.id == task.id).one()
    stored_execution = db_session.query(Execution).filter(Execution.task_id == task.id).one()
    assert stored_task.status == "failed"
    assert stored_task.reason.startswith("[PERMISSION_DENIED]")
    assert stored_execution.status == "failed"
    assert stored_execution.result_summary.startswith("[PERMISSION_DENIED]")


def test_orchestrator_tick_extracts_dark_failure_details(db_session):
    _seed_asset_projection(db_session, jms_asset_id="asset-local-1", status="active", freshness_status="fresh")
    task = Task(
        trace_id="trace-dark-failure-1",
        source="api",
        status="pending",
        risk_level="readonly",
        idempotency_key="idempotency-dark-failure-1",
        command="hostname",
        target_asset_id="asset-local-1",
        run_as_system_user_id="su-local-1",
        reason="test",
    )
    db_session.add(task)
    db_session.commit()

    client = FakeFinishedDarkFailureClient()
    first = run_orchestrator_tick(session=db_session, client=client)
    db_session.commit()
    assert first["created_executions"] == 1

    second = run_orchestrator_tick(session=db_session, client=client)
    db_session.commit()
    assert second["finished_executions"] == 1

    stored_task = db_session.query(Task).filter(Task.id == task.id).one()
    stored_execution = db_session.query(Execution).filter(Execution.task_id == task.id).one()
    assert stored_task.status == "failed"
    assert stored_task.reason.startswith("[CONNECTIVITY_ERROR]")
    assert "opspaw-dev-host-01" in stored_task.reason
    assert "10.10.10.10:22" in stored_task.reason
    assert stored_execution.status == "failed"
    assert stored_execution.result_summary.startswith("[CONNECTIVITY_ERROR]")
    assert "opspaw-dev-host-01" in stored_execution.result_summary


def test_orchestrator_tick_blocks_stale_asset_from_execution(db_session):
    _seed_asset_projection(db_session, jms_asset_id="asset-local-1", status="active", freshness_status="stale")
    task = Task(
        trace_id="trace-stale-asset-1",
        source="api",
        status="pending",
        risk_level="readonly",
        idempotency_key="idempotency-stale-asset-1",
        command="hostname",
        target_asset_id="asset-local-1",
        run_as_system_user_id="su-local-1",
        reason="test",
    )
    db_session.add(task)
    db_session.commit()

    result = run_orchestrator_tick(session=db_session, client=FakeOrchestratorClient())
    db_session.commit()

    assert result["created_executions"] == 0
    stored_task = db_session.query(Task).filter(Task.id == task.id).one()
    assert stored_task.status == "failed"
    assert stored_task.reason.startswith("[ASSET_STALE]")


def test_orchestrator_tick_blocks_expired_asset_from_execution(db_session):
    _seed_asset_projection(db_session, jms_asset_id="asset-local-1", status="active", freshness_status="expired")
    task = Task(
        trace_id="trace-expired-asset-1",
        source="api",
        status="pending",
        risk_level="readonly",
        idempotency_key="idempotency-expired-asset-1",
        command="hostname",
        target_asset_id="asset-local-1",
        run_as_system_user_id="su-local-1",
        reason="test",
    )
    db_session.add(task)
    db_session.commit()

    result = run_orchestrator_tick(session=db_session, client=FakeOrchestratorClient())
    db_session.commit()

    assert result["created_executions"] == 0
    stored_task = db_session.query(Task).filter(Task.id == task.id).one()
    assert stored_task.status == "failed"
    assert stored_task.reason.startswith("[ASSET_EXPIRED]")


def test_orchestrator_tick_auto_refreshes_stale_asset_when_enabled(db_session, monkeypatch):
    monkeypatch.setattr(settings, "execution_gate_auto_refresh_enabled", True)
    monkeypatch.setattr(settings, "execution_gate_refresh_search_limit", 20)
    _seed_asset_projection(db_session, jms_asset_id="asset-local-1", status="active", freshness_status="stale")
    task = Task(
        trace_id="trace-auto-refresh-1",
        source="api",
        status="pending",
        risk_level="readonly",
        idempotency_key="idempotency-auto-refresh-1",
        command="hostname",
        target_asset_id="asset-local-1",
        run_as_system_user_id="su-local-1",
        reason="test",
    )
    db_session.add(task)
    db_session.commit()

    result = run_orchestrator_tick(session=db_session, client=FakeAutoRefreshClient())
    db_session.commit()

    assert result["created_executions"] == 1
    stored_task = db_session.query(Task).filter(Task.id == task.id).one()
    stored_asset = db_session.query(AssetProjection).filter(AssetProjection.jms_asset_id == "asset-local-1").one()
    stored_execution = db_session.query(Execution).filter(Execution.task_id == task.id).one()
    assert stored_task.status == "executing"
    assert stored_asset.freshness_status == "fresh"
    assert stored_asset.hostname == "refreshed-host"
    assert stored_execution.status == "running"


def test_orchestrator_tick_auto_refresh_not_found_marks_asset_not_found(db_session, monkeypatch):
    monkeypatch.setattr(settings, "execution_gate_auto_refresh_enabled", True)
    _seed_asset_projection(db_session, jms_asset_id="asset-local-1", status="active", freshness_status="expired")
    task = Task(
        trace_id="trace-auto-refresh-2",
        source="api",
        status="pending",
        risk_level="readonly",
        idempotency_key="idempotency-auto-refresh-2",
        command="hostname",
        target_asset_id="asset-local-1",
        run_as_system_user_id="su-local-1",
        reason="test",
    )
    db_session.add(task)
    db_session.commit()

    result = run_orchestrator_tick(session=db_session, client=FakeAutoRefreshNotFoundClient())
    db_session.commit()

    assert result["created_executions"] == 0
    stored_task = db_session.query(Task).filter(Task.id == task.id).one()
    assert stored_task.status == "failed"
    assert stored_task.reason.startswith("[ASSET_NOT_FOUND]")
