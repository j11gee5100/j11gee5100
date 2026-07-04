from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import main as api_main
from app.db.base import Base
from app.models import (
    AssetProjection,
    AuditLink,
    CallbackDelivery,
    CallbackHook,
    CallbackReplayAudit,
    Execution,
    FailureSummaryBucket,
    MetricsPreaggregationRun,
    SyncSnapshot,
    Task,
    TaskRetryAuditCountBucket,
    TaskRetryAudit,
    TaskRetryAuditItem,
    TaskRetrySummaryBucket,
)
from app.services.jumpserver.client import JumpServerClientError


def _override_session_scope(session_local):
    @contextmanager
    def _scope():
        session = session_local()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    return _scope


def _create_client(session_local, monkeypatch) -> TestClient:
    monkeypatch.setattr(api_main, "init_db", lambda: None)
    monkeypatch.setattr(api_main, "session_scope", _override_session_scope(session_local))
    return TestClient(api_main.app)


def _build_sqlite_session_local():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def test_task_execution_query_returns_error_fields(monkeypatch):
    session_local = _build_sqlite_session_local()
    seed = session_local()
    task = Task(
        trace_id="trace-api-1",
        source="api",
        status="failed",
        risk_level="safe-write",
        idempotency_key="task-exec-query-1",
        command="hostname",
        target_asset_id="asset-1",
        run_as_system_user_id="su-1",
        reason="[EXECUTION_TIMEOUT] jumpserver execution timeout",
    )
    seed.add(task)
    seed.flush()

    execution = Execution(
        task_id=task.id,
        jms_execution_id="jms-exec-1",
        status="failed",
        result_summary="[EXECUTION_TIMEOUT] jumpserver execution timeout",
        started_at=datetime.now(timezone.utc) - timedelta(minutes=2),
        finished_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    seed.add(execution)
    seed.flush()

    seed.add(
        AuditLink(
            task_id=task.id,
            execution_id=execution.id,
            jms_audit_relation_id="audit-rel-1",
            trace_id=task.trace_id,
        )
    )
    seed.commit()
    seed.close()

    with _create_client(session_local, monkeypatch) as client:
        response = client.get(f"/api/v1/tasks/{task.id}/executions")
        assert response.status_code == 200
        payload = response.json()
        assert payload["task_id"] == task.id
        assert len(payload["items"]) == 1
        first = payload["items"][0]
        assert first["execution_id"] == execution.id
        assert first["jms_execution_id"] == "jms-exec-1"
        assert first["failure_code"] == "EXECUTION_TIMEOUT"
        assert first["error_message"] == "jumpserver execution timeout"
        assert first["audit_relation_ids"] == ["audit-rel-1"]


def test_execution_query_supports_jms_execution_id_lookup(monkeypatch):
    session_local = _build_sqlite_session_local()
    seed = session_local()
    task = Task(
        trace_id="trace-api-2",
        source="web",
        status="failed",
        risk_level="readonly",
        idempotency_key="task-exec-query-2",
        command="uptime",
        target_asset_id="asset-2",
        run_as_system_user_id="su-2",
        reason="jumpserver POST /api/v1/ops/command-executions/ failed status=400",
    )
    seed.add(task)
    seed.flush()

    execution = Execution(
        task_id=task.id,
        jms_execution_id="jms-upstream-err-1",
        status="failed",
        result_summary="jumpserver POST /api/v1/ops/command-executions/ failed status=400",
        started_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        finished_at=datetime.now(timezone.utc),
    )
    seed.add(execution)
    seed.commit()
    seed.close()

    with _create_client(session_local, monkeypatch) as client:
        response = client.get("/api/v1/executions/jms-upstream-err-1")
        assert response.status_code == 200
        payload = response.json()
        assert payload["execution_id"] == execution.id
        assert payload["task_id"] == task.id
        assert payload["failure_code"] == "UPSTREAM_ERROR"
        assert payload["error_message"] == "jumpserver POST /api/v1/ops/command-executions/ failed status=400"


def test_list_executions_supports_filters(monkeypatch):
    session_local = _build_sqlite_session_local()
    seed = session_local()
    task_api = Task(
        trace_id="trace-exec-list-1",
        source="api",
        status="failed",
        risk_level="safe-write",
        idempotency_key="exec-list-1",
        command="hostname",
        target_asset_id="asset-1",
        run_as_system_user_id="su-1",
        reason="[EXECUTION_TIMEOUT] jumpserver execution timeout",
    )
    task_web = Task(
        trace_id="trace-exec-list-2",
        source="web",
        status="success",
        risk_level="readonly",
        idempotency_key="exec-list-2",
        command="uptime",
        target_asset_id="asset-2",
        run_as_system_user_id="su-2",
        reason="ok",
    )
    seed.add_all([task_api, task_web])
    seed.flush()

    failed_execution = Execution(
        task_id=task_api.id,
        jms_execution_id="jms-list-1",
        status="failed",
        result_summary="[EXECUTION_TIMEOUT] jumpserver execution timeout",
        started_at=datetime.now(timezone.utc) - timedelta(minutes=6),
        finished_at=datetime.now(timezone.utc) - timedelta(minutes=5),
    )
    success_execution = Execution(
        task_id=task_web.id,
        jms_execution_id="jms-list-2",
        status="success",
        result_summary="ok",
        started_at=datetime.now(timezone.utc) - timedelta(minutes=3),
        finished_at=datetime.now(timezone.utc) - timedelta(minutes=2),
    )
    seed.add_all([failed_execution, success_execution])
    seed.flush()

    seed.add(
        AuditLink(
            task_id=task_api.id,
            execution_id=failed_execution.id,
            jms_audit_relation_id="audit-list-1",
            trace_id=task_api.trace_id,
        )
    )
    seed.commit()
    seed.close()

    with _create_client(session_local, monkeypatch) as client:
        response = client.get("/api/v1/executions?status=failed&source=api")
        assert response.status_code == 200
        payload = response.json()
        assert payload["total"] == 1
        assert len(payload["items"]) == 1
        item = payload["items"][0]
        assert item["execution_id"] == failed_execution.id
        assert item["failure_code"] == "EXECUTION_TIMEOUT"
        assert item["audit_relation_ids"] == ["audit-list-1"]


def test_jumpserver_capabilities_endpoint_returns_probe_result(monkeypatch):
    session_local = _build_sqlite_session_local()

    class _FakeJumpServerClient:
        def get_api_mode(self):
            return "v4"

        def get_health(self):
            return {"status": True}

        def get_public_settings(self):
            return {
                "SECURITY_COMMAND_EXECUTION": False,
                "SECURITY_COMMAND_BLACKLIST": ["rm -rf /", "shutdown"],
            }

        def list_command_executions(self, limit=50, offset=0):
            raise JumpServerClientError("jumpserver GET /api/v1/ops/job-executions/ failed status=403")

    monkeypatch.setattr(api_main, "JumpServerClient", _FakeJumpServerClient)

    with _create_client(session_local, monkeypatch) as client:
        response = client.get("/api/v1/integrations/jumpserver/capabilities")
        assert response.status_code == 200
        payload = response.json()
        assert payload["reachable"] is True
        assert payload["api_mode"] == "v4"
        assert payload["command_execution_enabled"] is False
        assert payload["command_blacklist_count"] == 2
        assert payload["execution_query_accessible"] is False
        assert "status=403" in payload["execution_query_error"]


def test_jumpserver_permission_check_reports_missing_required_check(monkeypatch):
    session_local = _build_sqlite_session_local()

    class _FakeJumpServerClient:
        def get_api_mode(self):
            return "v4"

        def list_assets(self, limit=50, offset=0):
            return [SimpleNamespace(id="asset-1")]

        def list_asset_system_users(self, asset_id):
            raise JumpServerClientError("jumpserver GET /api/v1/accounts/accounts/ failed status=403")

        def list_command_executions(self, limit=50, offset=0):
            return {"count": 3, "results": []}

        def get_public_settings(self):
            return {"SECURITY_COMMAND_EXECUTION": True}

    monkeypatch.setattr(api_main, "JumpServerClient", _FakeJumpServerClient)

    with _create_client(session_local, monkeypatch) as client:
        response = client.get("/api/v1/integrations/jumpserver/permission-check")
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "degraded"
        assert payload["overall_required_ok"] is False

        by_name = {item["name"]: item for item in payload["checks"]}
        assert by_name["list_assets"]["ok"] is True
        assert by_name["list_asset_system_users"]["ok"] is False
        assert "status=403" in by_name["list_asset_system_users"]["error"]
        assert by_name["list_command_executions"]["ok"] is True


def test_admin_refresh_single_asset_forbidden_when_debug_disabled(monkeypatch):
    monkeypatch.setattr(api_main.settings, "app_allow_admin_debug_endpoints", False)
    session_local = _build_sqlite_session_local()

    with _create_client(session_local, monkeypatch) as client:
        response = client.post("/api/v1/admin/sync/assets/asset-1/refresh")
        assert response.status_code == 403
        payload = response.json()
        assert payload["code"] == "FORBIDDEN"


def test_admin_refresh_single_asset_success(monkeypatch):
    monkeypatch.setattr(api_main.settings, "app_allow_admin_debug_endpoints", True)
    session_local = _build_sqlite_session_local()

    class _FakeJumpServerClient:
        pass

    def _fake_refresh(session, client, jms_asset_id):
        assert session is not None
        assert isinstance(client, _FakeJumpServerClient)
        assert jms_asset_id == "asset-1"
        return {
            "found": True,
            "asset_id": "local-asset-1",
            "jms_asset_id": "asset-1",
            "users": 2,
            "relations_active": 2,
            "relations_inactivated": 1,
        }

    monkeypatch.setattr(api_main, "JumpServerClient", _FakeJumpServerClient)
    monkeypatch.setattr(api_main, "refresh_asset_once", _fake_refresh)

    with _create_client(session_local, monkeypatch) as client:
        response = client.post("/api/v1/admin/sync/assets/asset-1/refresh")
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "ok"
        assert payload["result"]["found"] is True
        assert payload["result"]["jms_asset_id"] == "asset-1"


def test_admin_refresh_single_asset_not_found(monkeypatch):
    monkeypatch.setattr(api_main.settings, "app_allow_admin_debug_endpoints", True)
    session_local = _build_sqlite_session_local()

    class _FakeJumpServerClient:
        pass

    monkeypatch.setattr(api_main, "JumpServerClient", _FakeJumpServerClient)
    monkeypatch.setattr(
        api_main,
        "refresh_asset_once",
        lambda session, client, jms_asset_id: {
            "found": False,
            "jms_asset_id": jms_asset_id,
            "users": 0,
            "relations_active": 0,
            "relations_inactivated": 0,
        },
    )

    with _create_client(session_local, monkeypatch) as client:
        response = client.post("/api/v1/admin/sync/assets/asset-missing/refresh")
        assert response.status_code == 404
        payload = response.json()
        assert payload["code"] == "ASSET_NOT_FOUND"


def test_admin_refresh_retry_task_forbidden_when_debug_disabled(monkeypatch):
    monkeypatch.setattr(api_main.settings, "app_allow_admin_debug_endpoints", False)
    session_local = _build_sqlite_session_local()

    with _create_client(session_local, monkeypatch) as client:
        response = client.post("/api/v1/admin/tasks/task-1/refresh-retry")
        assert response.status_code == 403
        assert response.json()["code"] == "FORBIDDEN"


def test_admin_refresh_retry_task_not_retryable_failure_code(monkeypatch):
    monkeypatch.setattr(api_main.settings, "app_allow_admin_debug_endpoints", True)
    session_local = _build_sqlite_session_local()
    seed = session_local()
    task = Task(
        trace_id="trace-refresh-retry-1",
        source="api",
        status="failed",
        risk_level="readonly",
        idempotency_key="refresh-retry-1",
        command="hostname",
        target_asset_id="asset-1",
        run_as_system_user_id="su-1",
        reason="[PERMISSION_DENIED] upstream denied",
    )
    seed.add(task)
    seed.commit()
    seed.close()

    with _create_client(session_local, monkeypatch) as client:
        response = client.post(f"/api/v1/admin/tasks/{task.id}/refresh-retry")
        assert response.status_code == 409
        payload = response.json()
        assert payload["code"] == "TASK_NOT_RETRYABLE"
        assert payload["failure_code"] == "PERMISSION_DENIED"


def test_admin_refresh_retry_task_success(monkeypatch):
    monkeypatch.setattr(api_main.settings, "app_allow_admin_debug_endpoints", True)
    session_local = _build_sqlite_session_local()
    seed = session_local()
    task = Task(
        trace_id="trace-refresh-retry-2",
        source="api",
        status="failed",
        risk_level="readonly",
        idempotency_key="refresh-retry-2",
        command="hostname",
        target_asset_id="asset-expired-1",
        run_as_system_user_id="su-expired-1",
        reason="[ASSET_EXPIRED] refresh required",
    )
    seed.add(task)
    seed.commit()
    task_id = task.id
    seed.close()

    class _FakeJumpServerClient:
        pass

    def _fake_refresh(session, client, jms_asset_id, search_limit=20):
        assert isinstance(client, _FakeJumpServerClient)
        assert jms_asset_id == "asset-expired-1"
        return {
            "found": True,
            "asset_id": "local-asset-1",
            "jms_asset_id": "asset-expired-1",
            "users": 1,
            "relations_active": 1,
            "relations_inactivated": 0,
        }

    def _fake_tick(session, client):
        assert isinstance(client, _FakeJumpServerClient)
        stored = session.get(Task, task_id)
        stored.status = "success"
        stored.reason = "ok"
        return {"created_executions": 1, "finished_executions": 0, "created_audit_links": 0}

    monkeypatch.setattr(api_main, "JumpServerClient", _FakeJumpServerClient)
    monkeypatch.setattr(api_main, "refresh_asset_once", _fake_refresh)
    monkeypatch.setattr(api_main, "run_orchestrator_tick", _fake_tick)

    with _create_client(session_local, monkeypatch) as client:
        response = client.post(f"/api/v1/admin/tasks/{task_id}/refresh-retry")
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "ok"
        assert payload["previous_failure_code"] == "ASSET_EXPIRED"
        assert payload["refresh_result"]["found"] is True
        assert payload["task"]["status"] == "success"
        assert payload["task"]["failure_code"] is None


def test_admin_batch_refresh_retry_forbidden_when_debug_disabled(monkeypatch):
    monkeypatch.setattr(api_main.settings, "app_allow_admin_debug_endpoints", False)
    session_local = _build_sqlite_session_local()
    with _create_client(session_local, monkeypatch) as client:
        response = client.post("/api/v1/admin/tasks/refresh-retry/batch", json={})
        assert response.status_code == 403
        assert response.json()["code"] == "FORBIDDEN"


def test_admin_batch_refresh_retry_dry_run_filters_by_asset_failure(monkeypatch):
    monkeypatch.setattr(api_main.settings, "app_allow_admin_debug_endpoints", True)
    session_local = _build_sqlite_session_local()
    seed = session_local()
    task_asset = Task(
        trace_id="trace-refresh-batch-1",
        source="api",
        status="failed",
        risk_level="readonly",
        idempotency_key="refresh-batch-1",
        command="hostname",
        target_asset_id="asset-a",
        run_as_system_user_id="su-a",
        reason="[ASSET_EXPIRED] refresh required",
    )
    task_perm = Task(
        trace_id="trace-refresh-batch-2",
        source="api",
        status="failed",
        risk_level="readonly",
        idempotency_key="refresh-batch-2",
        command="hostname",
        target_asset_id="asset-b",
        run_as_system_user_id="su-b",
        reason="[PERMISSION_DENIED] denied",
    )
    seed.add_all([task_asset, task_perm])
    seed.commit()
    seed.close()

    with _create_client(session_local, monkeypatch) as client:
        response = client.post(
            "/api/v1/admin/tasks/refresh-retry/batch",
            json={"hours": 24, "limit": 20, "dry_run": True},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "ok"
        assert payload["summary"]["matched_by_failure"] == 1
        assert payload["summary"]["queued"] == 1

        by_task = {item["task_id"]: item for item in payload["items"]}
        assert by_task[task_asset.id]["action"] == "would_retry"
        assert by_task[task_perm.id]["action"] == "skipped_non_retryable"
        assert payload["audit_id"]


def test_admin_batch_refresh_retry_apply_success(monkeypatch):
    monkeypatch.setattr(api_main.settings, "app_allow_admin_debug_endpoints", True)
    session_local = _build_sqlite_session_local()
    task_id = "task-refresh-apply-1"
    monkeypatch.setattr(api_main, "JumpServerClient", lambda: object())
    monkeypatch.setattr(
        api_main,
        "run_task_refresh_retry_batch",
        lambda **kwargs: {
            "status": "ok",
            "dry_run": False,
            "audit_id": "audit-apply-1",
            "filters": {"task_ids": [task_id], "hours": 24, "source": None, "failure_codes": ["ASSET_STALE"], "limit": 20},
            "summary": {
                "requested": 2,
                "missing_tasks": 1,
                "matched_by_failure": 1,
                "queued": 1,
                "skipped_non_retryable": 0,
                "skipped_in_progress": 0,
                "skipped_asset_not_found": 0,
                "skipped_rate_limited": 0,
                "skipped_asset_guardrail": 0,
            },
            "missing_task_ids": ["task-missing-1"],
            "orchestrator_result": {
                "runs": 1,
                "created_executions": 1,
                "finished_executions": 0,
                "created_audit_links": 0,
                "window_size": 5,
            },
            "items": [
                {"task_id": "task-missing-1", "action": "missing"},
                {"task_id": task_id, "action": "queued", "final_status": "success"},
            ],
        },
    )

    with _create_client(session_local, monkeypatch) as client:
        response = client.post(
            "/api/v1/admin/tasks/refresh-retry/batch",
            json={"task_ids": [task_id, "task-missing-1"], "limit": 20},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["summary"]["missing_tasks"] == 1
        assert payload["summary"]["queued"] == 1
        assert payload["audit_id"]
        assert payload["orchestrator_result"]["created_executions"] == 1
        assert payload["orchestrator_result"]["runs"] == 1

        by_task = {item["task_id"]: item for item in payload["items"]}
        assert by_task["task-missing-1"]["action"] == "missing"
        assert by_task[task_id]["action"] == "queued"
        assert by_task[task_id]["final_status"] == "success"


def test_admin_batch_refresh_retry_applies_rate_limit_window_in_dry_run(monkeypatch):
    monkeypatch.setattr(api_main.settings, "app_allow_admin_debug_endpoints", True)
    monkeypatch.setattr(api_main.settings, "task_refresh_retry_window_size", 1)
    monkeypatch.setattr(api_main.settings, "task_refresh_retry_max_windows_per_request", 1)
    session_local = _build_sqlite_session_local()
    seed = session_local()
    tasks = [
        Task(
            trace_id=f"trace-refresh-rate-{idx}",
            source="api",
            status="failed",
            risk_level="readonly",
            idempotency_key=f"refresh-rate-{idx}",
            command="hostname",
            target_asset_id=f"asset-rate-{idx}",
            run_as_system_user_id=f"su-rate-{idx}",
            reason="[ASSET_EXPIRED] refresh required",
        )
        for idx in range(1, 4)
    ]
    seed.add_all(tasks)
    seed.commit()
    seed.close()

    with _create_client(session_local, monkeypatch) as client:
        response = client.post(
            "/api/v1/admin/tasks/refresh-retry/batch",
            json={"hours": 24, "limit": 20, "dry_run": True},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["summary"]["queued"] == 1
        assert payload["summary"]["skipped_rate_limited"] == 2
        actions = [item["action"] for item in payload["items"]]
        assert actions.count("would_retry") == 1
        assert actions.count("deferred_rate_limited") == 2


def test_admin_batch_refresh_retry_enforces_same_asset_guardrail(monkeypatch):
    monkeypatch.setattr(api_main.settings, "app_allow_admin_debug_endpoints", True)
    monkeypatch.setattr(api_main.settings, "task_refresh_retry_same_asset_max_retries", 1)
    session_local = _build_sqlite_session_local()
    seed = session_local()
    first = Task(
        trace_id="trace-refresh-guardrail-1",
        source="api",
        status="failed",
        risk_level="readonly",
        idempotency_key="refresh-guardrail-1",
        command="hostname",
        target_asset_id="asset-guardrail",
        run_as_system_user_id="su-guardrail-1",
        reason="[ASSET_STALE] stale projection",
    )
    second = Task(
        trace_id="trace-refresh-guardrail-2",
        source="api",
        status="failed",
        risk_level="readonly",
        idempotency_key="refresh-guardrail-2",
        command="hostname",
        target_asset_id="asset-guardrail",
        run_as_system_user_id="su-guardrail-2",
        reason="[ASSET_EXPIRED] expired projection",
    )
    seed.add_all([first, second])
    seed.commit()
    seed.close()

    with _create_client(session_local, monkeypatch) as client:
        response = client.post(
            "/api/v1/admin/tasks/refresh-retry/batch",
            json={"task_ids": [first.id, second.id], "dry_run": True},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["summary"]["queued"] == 1
        assert payload["summary"]["skipped_asset_guardrail"] == 1
        by_task = {item["task_id"]: item for item in payload["items"]}
        assert by_task[first.id]["action"] == "would_retry"
        assert by_task[second.id]["action"] == "skipped_asset_guardrail"


def test_admin_batch_refresh_retry_audits_query(monkeypatch):
    monkeypatch.setattr(api_main.settings, "app_allow_admin_debug_endpoints", True)
    session_local = _build_sqlite_session_local()
    seed = session_local()
    task = Task(
        trace_id="trace-refresh-audit-1",
        source="api",
        status="failed",
        risk_level="readonly",
        idempotency_key="refresh-audit-1",
        command="hostname",
        target_asset_id="asset-audit-1",
        run_as_system_user_id="su-audit-1",
        reason="[ASSET_EXPIRED] refresh required",
    )
    seed.add(task)
    seed.commit()
    seed.close()

    with _create_client(session_local, monkeypatch) as client:
        trigger = client.post(
            "/api/v1/admin/tasks/refresh-retry/batch",
            json={"task_ids": [task.id], "dry_run": True},
            headers={"X-Operator-Id": "tester-audit"},
        )
        assert trigger.status_code == 200
        audit_id = trigger.json()["audit_id"]

        listing = client.get("/api/v1/admin/tasks/refresh-retry/audits?operator_id=tester-audit")
        assert listing.status_code == 200
        payload = listing.json()
        assert payload["total"] >= 1
        first_item = payload["items"][0]
        assert first_item["audit_id"] == audit_id
        assert first_item["operator_id"] == "tester-audit"

        detail = client.get(f"/api/v1/admin/tasks/refresh-retry/audits/{audit_id}")
        assert detail.status_code == 200
        detail_payload = detail.json()
        assert detail_payload["audit"]["audit_id"] == audit_id
        assert detail_payload["total_items"] >= 1
        assert any(item["task_id"] == task.id for item in detail_payload["items"])


def test_admin_batch_refresh_retry_enforces_task_cooldown_guardrail(monkeypatch):
    monkeypatch.setattr(api_main.settings, "app_allow_admin_debug_endpoints", True)
    monkeypatch.setattr(api_main.settings, "task_refresh_retry_task_cooldown_minutes", 60)
    session_local = _build_sqlite_session_local()
    seed = session_local()

    task = Task(
        trace_id="trace-refresh-cooldown-1",
        source="api",
        status="failed",
        risk_level="readonly",
        idempotency_key="refresh-cooldown-1",
        command="hostname",
        target_asset_id="asset-cooldown-1",
        run_as_system_user_id="su-cooldown-1",
        reason="[ASSET_EXPIRED] refresh required",
    )
    seed.add(task)
    seed.flush()

    audit = TaskRetryAudit(
        endpoint="/api/v1/admin/tasks/refresh-retry/batch",
        operator_id="tester",
        source_ip="127.0.0.1",
        trace_id="trace-old-audit",
        dry_run=True,
        effective_hours=24,
        source_filter="api",
        failure_codes_csv="ASSET_EXPIRED",
        window_size=5,
        max_windows=1,
        same_asset_max_retries=2,
        requested=1,
        missing_tasks=0,
        matched_by_failure=1,
        queued=1,
        skipped_non_retryable=0,
        skipped_in_progress=0,
        skipped_asset_not_found=0,
        skipped_rate_limited=0,
        skipped_asset_guardrail=0,
    )
    seed.add(audit)
    seed.flush()
    seed.add(
        TaskRetryAuditItem(
            audit_id=audit.id,
            task_id=task.id,
            target_asset_id=task.target_asset_id,
            source=task.source,
            action="queued",
            failure_code="ASSET_EXPIRED",
            final_status="pending",
            final_failure_code="",
            message="previous retry queued",
        )
    )
    seed.commit()
    seed.close()

    with _create_client(session_local, monkeypatch) as client:
        response = client.post(
            "/api/v1/admin/tasks/refresh-retry/batch",
            json={"task_ids": [task.id], "dry_run": True},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["summary"]["queued"] == 0
        assert payload["summary"]["skipped_task_cooldown"] == 1
        item = payload["items"][0]
        assert item["action"] == "skipped_task_cooldown"


def test_admin_task_refresh_retry_audit_export_json_and_csv(monkeypatch):
    monkeypatch.setattr(api_main.settings, "app_allow_admin_debug_endpoints", True)
    session_local = _build_sqlite_session_local()
    seed = session_local()
    audit = TaskRetryAudit(
        endpoint="/api/v1/admin/tasks/refresh-retry/batch",
        operator_id="exporter",
        source_ip="127.0.0.1",
        trace_id="trace-export",
        dry_run=True,
        effective_hours=24,
        source_filter="api",
        failure_codes_csv="ASSET_EXPIRED,ASSET_STALE",
        window_size=5,
        max_windows=1,
        same_asset_max_retries=2,
        requested=2,
        missing_tasks=0,
        matched_by_failure=1,
        queued=1,
        skipped_non_retryable=1,
        skipped_in_progress=0,
        skipped_asset_not_found=0,
        skipped_rate_limited=0,
        skipped_asset_guardrail=0,
    )
    seed.add(audit)
    seed.flush()
    seed.add(
        TaskRetryAuditItem(
            audit_id=audit.id,
            task_id="task-export-1",
            target_asset_id="asset-export-1",
            source="api",
            action="queued",
            failure_code="ASSET_EXPIRED",
            final_status="pending",
            final_failure_code="",
            message="queued by export test",
        )
    )
    seed.commit()
    seed.close()

    with _create_client(session_local, monkeypatch) as client:
        as_json = client.get(f"/api/v1/admin/tasks/refresh-retry/audits/{audit.id}/export?format=json")
        assert as_json.status_code == 200
        payload = as_json.json()
        assert payload["audit"]["audit_id"] == audit.id
        assert payload["total_items"] == 1

        as_csv = client.get(f"/api/v1/admin/tasks/refresh-retry/audits/{audit.id}/export?format=csv")
        assert as_csv.status_code == 200
        assert "text/csv" in as_csv.headers["content-type"]
        assert "task_id,target_asset_id" in as_csv.text
        assert "task-export-1" in as_csv.text


def test_sync_snapshots_latest_and_list(monkeypatch):
    session_local = _build_sqlite_session_local()
    seed = session_local()
    now = datetime.now(timezone.utc)
    first = SyncSnapshot(
        source="jumpserver",
        snapshot_type="sync_tick",
        offset=0,
        next_offset=1,
        page_size=50,
        fetched_assets=50,
        fetched_system_users=60,
        fetched_relations=60,
        upstream_total_assets=120,
        local_total_assets=None,
        local_total_system_users=None,
        local_total_relations=None,
        consistency_status="skipped",
        consistency_delta_assets=None,
        checksum="abc",
        detail="cycle not completed",
        created_at=now - timedelta(minutes=1),
    )
    second = SyncSnapshot(
        source="jumpserver",
        snapshot_type="sync_tick",
        offset=100,
        next_offset=0,
        page_size=50,
        fetched_assets=20,
        fetched_system_users=20,
        fetched_relations=20,
        upstream_total_assets=120,
        local_total_assets=120,
        local_total_system_users=120,
        local_total_relations=120,
        consistency_status="ok",
        consistency_delta_assets=0,
        checksum="def",
        detail="consistent",
        created_at=now,
    )
    seed.add_all([first, second])
    seed.commit()
    seed.close()

    with _create_client(session_local, monkeypatch) as client:
        latest_resp = client.get("/api/v1/sync/snapshots/latest")
        assert latest_resp.status_code == 200
        latest_payload = latest_resp.json()
        assert latest_payload["item"]["snapshot_id"] == second.id
        assert latest_payload["item"]["consistency_status"] == "ok"

        list_resp = client.get("/api/v1/sync/snapshots?limit=5")
        assert list_resp.status_code == 200
        list_payload = list_resp.json()
        assert list_payload["source"] == "jumpserver"
        assert len(list_payload["items"]) == 2
        assert list_payload["items"][0]["snapshot_id"] == second.id
        assert list_payload["items"][1]["snapshot_id"] == first.id


def test_list_assets_projection_supports_filters(monkeypatch):
    session_local = _build_sqlite_session_local()
    seed = session_local()
    now = datetime.now(timezone.utc)
    seed.add_all(
        [
            AssetProjection(
                jms_asset_id="asset-a-1",
                hostname="web-a1",
                ip="10.1.1.1",
                status="active",
                freshness_status="fresh",
                sync_at=now - timedelta(minutes=2),
            ),
            AssetProjection(
                jms_asset_id="asset-b-1",
                hostname="db-b1",
                ip="10.1.1.2",
                status="active",
                freshness_status="stale",
                sync_at=now - timedelta(hours=2),
            ),
            AssetProjection(
                jms_asset_id="asset-c-1",
                hostname="legacy-c1",
                ip="10.1.1.3",
                status="inactive",
                freshness_status="expired",
                sync_at=now - timedelta(days=1),
            ),
        ]
    )
    seed.commit()
    seed.close()

    with _create_client(session_local, monkeypatch) as client:
        resp = client.get("/api/v1/assets?status=active&freshness_status=stale&search=db-b1")
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["total"] == 1
        assert len(payload["items"]) == 1
        assert payload["items"][0]["jms_asset_id"] == "asset-b-1"
        assert payload["items"][0]["freshness_status"] == "stale"


def test_cancel_task_succeeds_for_pending(monkeypatch):
    session_local = _build_sqlite_session_local()
    seed = session_local()
    task = Task(
        trace_id="trace-cancel-1",
        source="api",
        status="pending",
        risk_level="readonly",
        idempotency_key="cancel-1",
        command="hostname",
        target_asset_id="asset-1",
        run_as_system_user_id="su-1",
        reason="initial",
    )
    seed.add(task)
    seed.commit()
    seed.close()

    with _create_client(session_local, monkeypatch) as client:
        response = client.post(f"/api/v1/tasks/{task.id}/cancel", json={"reason": "manual cancel"})
        assert response.status_code == 200
        payload = response.json()
        assert payload["task_id"] == task.id
        assert payload["status"] == "canceled"
        assert payload["already_canceled"] is False
        assert payload["reason"] == "manual cancel"

        task_resp = client.get(f"/api/v1/tasks/{task.id}")
        assert task_resp.status_code == 200
        task_payload = task_resp.json()
        assert task_payload["status"] == "canceled"
        assert task_payload["failure_code"] == "CANCELED"
        assert task_payload["reason"] == "manual cancel"


def test_cancel_task_returns_conflict_for_executing(monkeypatch):
    session_local = _build_sqlite_session_local()
    seed = session_local()
    task = Task(
        trace_id="trace-cancel-2",
        source="api",
        status="executing",
        risk_level="readonly",
        idempotency_key="cancel-2",
        command="hostname",
        target_asset_id="asset-2",
        run_as_system_user_id="su-2",
        reason="running",
    )
    seed.add(task)
    seed.commit()
    seed.close()

    with _create_client(session_local, monkeypatch) as client:
        response = client.post(f"/api/v1/tasks/{task.id}/cancel", json={"reason": "cancel try"})
        assert response.status_code == 409
        payload = response.json()
        assert payload["code"] == "TASK_NOT_CANCELABLE"
        assert payload["status"] == "executing"


def test_cancel_task_is_idempotent_for_already_canceled(monkeypatch):
    session_local = _build_sqlite_session_local()
    seed = session_local()
    task = Task(
        trace_id="trace-cancel-3",
        source="api",
        status="canceled",
        risk_level="readonly",
        idempotency_key="cancel-3",
        command="hostname",
        target_asset_id="asset-3",
        run_as_system_user_id="su-3",
        reason="[CANCELED] previous cancel",
    )
    seed.add(task)
    seed.commit()
    seed.close()

    with _create_client(session_local, monkeypatch) as client:
        response = client.post(f"/api/v1/tasks/{task.id}/cancel")
        assert response.status_code == 200
        payload = response.json()
        assert payload["task_id"] == task.id
        assert payload["status"] == "canceled"
        assert payload["already_canceled"] is True
        assert payload["reason"] == "previous cancel"


def test_create_task_with_callback_url_registers_hook(monkeypatch):
    session_local = _build_sqlite_session_local()

    with _create_client(session_local, monkeypatch) as client:
        response = client.post(
            "/api/v1/tasks",
            json={
                "command": "hostname",
                "target_asset_id": "asset-cb-1",
                "run_as_system_user_id": "su-cb-1",
                "reason": "callback task",
                "risk_level": "readonly",
                "source": "api",
                "idempotency_key": "task-callback-create-1",
                "callback_url": "https://example.com/opspaw/callback",
                "callback_secret": "secret-1",
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["callback_registered"] is True
        task_id = payload["task_id"]

        callbacks_resp = client.get(f"/api/v1/tasks/{task_id}/callbacks")
        assert callbacks_resp.status_code == 200
        callbacks_payload = callbacks_resp.json()
        assert callbacks_payload["hook"]["task_id"] == task_id
        assert callbacks_payload["hook"]["callback_url"] == "https://example.com/opspaw/callback"


def test_create_task_with_invalid_callback_url_returns_400(monkeypatch):
    session_local = _build_sqlite_session_local()

    with _create_client(session_local, monkeypatch) as client:
        response = client.post(
            "/api/v1/tasks",
            json={
                "command": "hostname",
                "target_asset_id": "asset-cb-2",
                "run_as_system_user_id": "su-cb-2",
                "reason": "invalid callback",
                "risk_level": "readonly",
                "source": "api",
                "idempotency_key": "task-callback-create-2",
                "callback_url": "ftp://example.com/cb",
            },
        )
        assert response.status_code == 400
        payload = response.json()
        assert payload["code"] == "INVALID_ARGUMENT"


def test_create_task_with_private_callback_url_blocked(monkeypatch):
    monkeypatch.setattr(api_main.settings, "callback_block_private_networks", True)
    monkeypatch.setattr(api_main.settings, "callback_allowed_hosts", "")
    monkeypatch.setattr(api_main.settings, "callback_allowed_domain_suffixes", "")
    monkeypatch.setattr(api_main.settings, "callback_allowed_cidrs", "")
    session_local = _build_sqlite_session_local()

    with _create_client(session_local, monkeypatch) as client:
        response = client.post(
            "/api/v1/tasks",
            json={
                "command": "hostname",
                "target_asset_id": "asset-cb-3",
                "run_as_system_user_id": "su-cb-3",
                "reason": "private callback",
                "risk_level": "readonly",
                "source": "api",
                "idempotency_key": "task-callback-create-3",
                "callback_url": "http://127.0.0.1:9000/cb",
            },
        )
        assert response.status_code == 400
        payload = response.json()
        assert payload["code"] == "CALLBACK_URL_BLOCKED"


def test_create_task_with_whitelisted_private_callback_url_is_allowed(monkeypatch):
    monkeypatch.setattr(api_main.settings, "callback_block_private_networks", True)
    monkeypatch.setattr(api_main.settings, "callback_allowed_hosts", "127.0.0.1")
    monkeypatch.setattr(api_main.settings, "callback_allowed_domain_suffixes", "")
    monkeypatch.setattr(api_main.settings, "callback_allowed_cidrs", "")
    session_local = _build_sqlite_session_local()

    with _create_client(session_local, monkeypatch) as client:
        response = client.post(
            "/api/v1/tasks",
            json={
                "command": "hostname",
                "target_asset_id": "asset-cb-4",
                "run_as_system_user_id": "su-cb-4",
                "reason": "whitelisted private callback",
                "risk_level": "readonly",
                "source": "api",
                "idempotency_key": "task-callback-create-4",
                "callback_url": "http://127.0.0.1:9000/cb",
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["callback_registered"] is True


def test_admin_replay_dead_callback_delivery(monkeypatch):
    monkeypatch.setattr(api_main.settings, "app_allow_admin_debug_endpoints", True)
    session_local = _build_sqlite_session_local()
    seed = session_local()

    task = Task(
        trace_id="trace-callback-replay-1",
        source="api",
        status="failed",
        risk_level="readonly",
        idempotency_key="callback-replay-1",
        command="hostname",
        target_asset_id="asset-r1",
        run_as_system_user_id="su-r1",
        reason="failed",
    )
    seed.add(task)
    seed.flush()

    hook = CallbackHook(
        task_id=task.id,
        callback_url="https://example.com/opspaw/callback",
        callback_secret="",
        status="active",
    )
    seed.add(hook)
    seed.flush()

    delivery = CallbackDelivery(
        task_id=task.id,
        hook_id=hook.id,
        event_type="task_finalized",
        status="dead",
        attempts=3,
        max_attempts=8,
        next_retry_at=None,
        last_http_status=500,
        last_error="upstream 500",
        payload_json="{}",
    )
    seed.add(delivery)
    seed.commit()
    seed.close()

    with _create_client(session_local, monkeypatch) as client:
        response = client.post(
            f"/api/v1/admin/callback/deliveries/{delivery.id}/replay",
            json={"reset_attempts": True},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "ok"
        assert payload["item"]["delivery_id"] == delivery.id
        assert payload["item"]["status"] == "pending"
        assert payload["item"]["attempts"] == 0


def test_admin_replay_success_callback_delivery_returns_conflict(monkeypatch):
    monkeypatch.setattr(api_main.settings, "app_allow_admin_debug_endpoints", True)
    session_local = _build_sqlite_session_local()
    seed = session_local()

    task = Task(
        trace_id="trace-callback-replay-2",
        source="api",
        status="success",
        risk_level="readonly",
        idempotency_key="callback-replay-2",
        command="hostname",
        target_asset_id="asset-r2",
        run_as_system_user_id="su-r2",
        reason="ok",
    )
    seed.add(task)
    seed.flush()

    hook = CallbackHook(
        task_id=task.id,
        callback_url="https://example.com/opspaw/callback",
        callback_secret="",
        status="active",
    )
    seed.add(hook)
    seed.flush()

    delivery = CallbackDelivery(
        task_id=task.id,
        hook_id=hook.id,
        event_type="task_finalized",
        status="success",
        attempts=1,
        max_attempts=8,
        next_retry_at=None,
        last_http_status=200,
        last_error="",
        payload_json="{}",
    )
    seed.add(delivery)
    seed.commit()
    seed.close()

    with _create_client(session_local, monkeypatch) as client:
        response = client.post(f"/api/v1/admin/callback/deliveries/{delivery.id}/replay")
        assert response.status_code == 409
        payload = response.json()
        assert payload["code"] == "DELIVERY_NOT_REPLAYABLE"


def test_admin_list_callback_deliveries_supports_filters(monkeypatch):
    monkeypatch.setattr(api_main.settings, "app_allow_admin_debug_endpoints", True)
    session_local = _build_sqlite_session_local()
    seed = session_local()

    task = Task(
        trace_id="trace-callback-list-1",
        source="api",
        status="failed",
        risk_level="readonly",
        idempotency_key="callback-list-1",
        command="hostname",
        target_asset_id="asset-list-1",
        run_as_system_user_id="su-list-1",
        reason="failed",
    )
    seed.add(task)
    seed.flush()

    hook = CallbackHook(
        task_id=task.id,
        callback_url="https://example.com/opspaw/callback",
        callback_secret="",
        status="active",
    )
    seed.add(hook)
    seed.flush()

    dead = CallbackDelivery(
        task_id=task.id,
        hook_id=hook.id,
        event_type="task_finalized",
        status="dead",
        attempts=8,
        max_attempts=8,
        next_retry_at=None,
        last_http_status=500,
        last_error="upstream timeout 500",
        payload_json="{}",
    )
    retrying = CallbackDelivery(
        task_id=task.id,
        hook_id=hook.id,
        event_type="task_started",
        status="retrying",
        attempts=2,
        max_attempts=8,
        next_retry_at=datetime.now(timezone.utc),
        last_http_status=502,
        last_error="upstream bad gateway",
        payload_json="{}",
    )
    seed.add_all([dead, retrying])
    seed.commit()
    seed.close()

    with _create_client(session_local, monkeypatch) as client:
        response = client.get("/api/v1/admin/callback/deliveries?status=dead&error_contains=timeout")
        assert response.status_code == 200
        payload = response.json()
        assert payload["total"] == 1
        assert len(payload["items"]) == 1
        assert payload["items"][0]["delivery_id"] == dead.id
        assert payload["items"][0]["status"] == "dead"


def test_admin_batch_replay_callback_deliveries_by_filter(monkeypatch):
    monkeypatch.setattr(api_main.settings, "app_allow_admin_debug_endpoints", True)
    session_local = _build_sqlite_session_local()
    seed = session_local()

    task = Task(
        trace_id="trace-callback-batch-1",
        source="api",
        status="failed",
        risk_level="readonly",
        idempotency_key="callback-batch-1",
        command="hostname",
        target_asset_id="asset-batch-1",
        run_as_system_user_id="su-batch-1",
        reason="failed",
    )
    seed.add(task)
    seed.flush()

    hook = CallbackHook(
        task_id=task.id,
        callback_url="https://example.com/opspaw/callback",
        callback_secret="",
        status="active",
    )
    seed.add(hook)
    seed.flush()

    dead = CallbackDelivery(
        task_id=task.id,
        hook_id=hook.id,
        event_type="task_finalized",
        status="dead",
        attempts=8,
        max_attempts=8,
        next_retry_at=None,
        last_http_status=500,
        last_error="upstream timeout 500",
        payload_json="{}",
    )
    success = CallbackDelivery(
        task_id=task.id,
        hook_id=hook.id,
        event_type="task_started",
        status="success",
        attempts=1,
        max_attempts=8,
        next_retry_at=None,
        last_http_status=200,
        last_error="",
        payload_json="{}",
    )
    seed.add_all([dead, success])
    seed.commit()
    seed.close()

    with _create_client(session_local, monkeypatch) as client:
        dry_run_resp = client.post(
            "/api/v1/admin/callback/deliveries/replay",
            json={"delivery_ids": [dead.id, success.id], "dry_run": True},
        )
        assert dry_run_resp.status_code == 200
        dry_run_payload = dry_run_resp.json()
        assert dry_run_payload["dry_run"] is True
        assert dry_run_payload["matched"] == 2
        assert dry_run_payload["replayed"] == 0
        assert dry_run_payload["skipped_non_replayable"] == 1

        replay_resp = client.post(
            "/api/v1/admin/callback/deliveries/replay",
            json={"status": "dead", "reset_attempts": True},
        )
        assert replay_resp.status_code == 200
        replay_payload = replay_resp.json()
        assert replay_payload["dry_run"] is False
        assert replay_payload["matched"] == 1
        assert replay_payload["replayed"] == 1
        assert replay_payload["skipped_non_replayable"] == 0
        assert replay_payload["items"][0]["delivery_id"] == dead.id
        assert replay_payload["items"][0]["status"] == "pending"
        assert replay_payload["items"][0]["attempts"] == 0


def test_admin_batch_replay_callback_deliveries_guardrail(monkeypatch):
    monkeypatch.setattr(api_main.settings, "app_allow_admin_debug_endpoints", True)
    monkeypatch.setattr(api_main.settings, "callback_replay_max_apply", 1)
    session_local = _build_sqlite_session_local()
    seed = session_local()

    task = Task(
        trace_id="trace-callback-batch-guardrail-1",
        source="api",
        status="failed",
        risk_level="readonly",
        idempotency_key="callback-batch-guardrail-1",
        command="hostname",
        target_asset_id="asset-batch-g1",
        run_as_system_user_id="su-batch-g1",
        reason="failed",
    )
    seed.add(task)
    seed.flush()

    hook = CallbackHook(
        task_id=task.id,
        callback_url="https://example.com/opspaw/callback",
        callback_secret="",
        status="active",
    )
    seed.add(hook)
    seed.flush()

    d1 = CallbackDelivery(
        task_id=task.id,
        hook_id=hook.id,
        event_type="task_finalized",
        status="dead",
        attempts=8,
        max_attempts=8,
        next_retry_at=None,
        last_http_status=500,
        last_error="timeout 1",
        payload_json="{}",
    )
    d2 = CallbackDelivery(
        task_id=task.id,
        hook_id=hook.id,
        event_type="task_started",
        status="dead",
        attempts=5,
        max_attempts=8,
        next_retry_at=None,
        last_http_status=500,
        last_error="timeout 2",
        payload_json="{}",
    )
    seed.add_all([d1, d2])
    seed.commit()
    seed.close()

    with _create_client(session_local, monkeypatch) as client:
        response = client.post(
            "/api/v1/admin/callback/deliveries/replay",
            headers={"x-operator-id": "tester-guardrail"},
            json={"status": "dead", "reset_attempts": True},
        )
        assert response.status_code == 400
        payload = response.json()
        assert payload["code"] == "CALLBACK_REPLAY_LIMIT_EXCEEDED"
        assert payload["replayable"] == 2

        verify = client.get("/api/v1/admin/callback/deliveries?status=dead&limit=10")
        assert verify.status_code == 200
        verify_payload = verify.json()
        assert verify_payload["total"] == 2

        audits = client.get("/api/v1/admin/callback/replay-audits?operator_id=tester-guardrail&limit=10")
        assert audits.status_code == 200
        audits_payload = audits.json()
        assert audits_payload["total"] >= 1
        assert audits_payload["items"][0]["blocked_by_guardrail"] is True


def test_admin_list_callback_replay_audits(monkeypatch):
    monkeypatch.setattr(api_main.settings, "app_allow_admin_debug_endpoints", True)
    session_local = _build_sqlite_session_local()
    seed = session_local()

    seed.add_all(
        [
            CallbackReplayAudit(
                endpoint="/api/v1/admin/callback/deliveries/replay",
                operator_id="alice",
                source_ip="127.0.0.1",
                trace_id="trace-audit-1",
                dry_run=True,
                matched=5,
                replayed=0,
                skipped_non_replayable=1,
                blocked_by_guardrail=False,
                guardrail_reason="",
                filters_json="{}",
                delivery_ids_json="[]",
            ),
            CallbackReplayAudit(
                endpoint="/api/v1/admin/callback/deliveries/{delivery_id}/replay",
                operator_id="bob",
                source_ip="127.0.0.1",
                trace_id="trace-audit-2",
                dry_run=False,
                matched=1,
                replayed=1,
                skipped_non_replayable=0,
                blocked_by_guardrail=False,
                guardrail_reason="",
                filters_json="{}",
                delivery_ids_json="[]",
            ),
        ]
    )
    seed.commit()
    seed.close()

    with _create_client(session_local, monkeypatch) as client:
        response = client.get("/api/v1/admin/callback/replay-audits?operator_id=alice&limit=10")
        assert response.status_code == 200
        payload = response.json()
        assert payload["total"] == 1
        assert len(payload["items"]) == 1
        assert payload["items"][0]["operator_id"] == "alice"
        assert payload["items"][0]["dry_run"] is True


def test_failure_summary_is_dashboard_ready(monkeypatch):
    session_local = _build_sqlite_session_local()
    seed = session_local()
    now = datetime.now(timezone.utc)
    failed_timeout = Task(
        trace_id="trace-metric-1",
        source="api",
        status="failed",
        risk_level="readonly",
        idempotency_key="metric-1",
        command="hostname",
        target_asset_id="asset-1",
        run_as_system_user_id="su-1",
        reason="[EXECUTION_TIMEOUT] jumpserver execution timeout",
        updated_at=now - timedelta(minutes=10),
    )
    failed_legacy = Task(
        trace_id="trace-metric-2",
        source="api",
        status="failed",
        risk_level="safe-write",
        idempotency_key="metric-2",
        command="df -h",
        target_asset_id="asset-2",
        run_as_system_user_id="su-2",
        reason="jumpserver POST /api/v1/ops/command-executions/ failed status=502",
        updated_at=now - timedelta(minutes=5),
    )
    failed_unknown = Task(
        trace_id="trace-metric-3",
        source="web",
        status="failed",
        risk_level="high-risk",
        idempotency_key="metric-3",
        command="free -m",
        target_asset_id="asset-3",
        run_as_system_user_id="su-3",
        reason="external smoke",
        updated_at=now - timedelta(minutes=3),
    )
    success = Task(
        trace_id="trace-metric-4",
        source="api",
        status="success",
        risk_level="readonly",
        idempotency_key="metric-4",
        command="whoami",
        target_asset_id="asset-4",
        run_as_system_user_id="su-4",
        reason="ok",
        updated_at=now - timedelta(minutes=1),
    )
    seed.add_all([failed_timeout, failed_legacy, failed_unknown, success])
    seed.commit()
    seed.close()

    with _create_client(session_local, monkeypatch) as client:
        response = client.get("/api/v1/metrics/failures/summary?hours=24")
        assert response.status_code == 200
        payload = response.json()
        assert payload["total_failed"] == 3

        by_code = {item["failure_code"]: item["count"] for item in payload["by_failure_code"]}
        assert by_code["EXECUTION_TIMEOUT"] == 1
        assert by_code["UPSTREAM_ERROR"] == 1
        assert by_code["UNKNOWN"] == 1

        by_source = {item["source"]: item["count"] for item in payload["by_source"]}
        assert by_source["api"] == 2
        assert by_source["web"] == 1

        unknown_samples = {item["reason"]: item["count"] for item in payload["unknown_reason_samples"]}
        assert unknown_samples["external smoke"] == 1


def test_task_retry_summary_is_dashboard_ready(monkeypatch):
    session_local = _build_sqlite_session_local()
    seed = session_local()
    now = datetime.now(timezone.utc)

    audit_apply = TaskRetryAudit(
        endpoint="/api/v1/admin/tasks/refresh-retry/batch",
        operator_id="alice",
        source_ip="127.0.0.1",
        trace_id="trace-retry-metric-1",
        dry_run=False,
        effective_hours=24,
        source_filter="",
        failure_codes_csv="ASSET_STALE,ASSET_EXPIRED",
        window_size=5,
        max_windows=1,
        same_asset_max_retries=2,
        requested=2,
        missing_tasks=0,
        matched_by_failure=2,
        queued=1,
        skipped_non_retryable=0,
        skipped_in_progress=0,
        skipped_asset_not_found=0,
        skipped_rate_limited=0,
        skipped_asset_guardrail=0,
        filters_json="{}",
        summary_json='{"skipped_task_cooldown":1}',
        created_at=now - timedelta(hours=2),
    )
    audit_dry = TaskRetryAudit(
        endpoint="/api/v1/admin/tasks/refresh-retry/batch",
        operator_id="bob",
        source_ip="127.0.0.1",
        trace_id="trace-retry-metric-2",
        dry_run=True,
        effective_hours=24,
        source_filter="",
        failure_codes_csv="ASSET_EXPIRED",
        window_size=5,
        max_windows=1,
        same_asset_max_retries=2,
        requested=1,
        missing_tasks=0,
        matched_by_failure=1,
        queued=1,
        skipped_non_retryable=0,
        skipped_in_progress=0,
        skipped_asset_not_found=0,
        skipped_rate_limited=0,
        skipped_asset_guardrail=0,
        filters_json="{}",
        summary_json="{}",
        created_at=now - timedelta(hours=1),
    )
    seed.add_all([audit_apply, audit_dry])
    seed.flush()

    seed.add_all(
        [
            TaskRetryAuditItem(
                audit_id=audit_apply.id,
                task_id="task-retry-metric-1",
                target_asset_id="asset-a",
                source="api",
                action="queued",
                failure_code="ASSET_STALE",
                final_status="executing",
                final_failure_code="",
                message="queued",
                created_at=now - timedelta(hours=2, minutes=5),
            ),
            TaskRetryAuditItem(
                audit_id=audit_apply.id,
                task_id="task-retry-metric-2",
                target_asset_id="asset-a",
                source="api",
                action="skipped_task_cooldown",
                failure_code="ASSET_STALE",
                final_status="failed",
                final_failure_code="ASSET_STALE",
                message="cooldown",
                created_at=now - timedelta(hours=2, minutes=2),
            ),
            TaskRetryAuditItem(
                audit_id=audit_dry.id,
                task_id="task-retry-metric-3",
                target_asset_id="asset-b",
                source="web",
                action="would_retry",
                failure_code="ASSET_EXPIRED",
                final_status="failed",
                final_failure_code="ASSET_EXPIRED",
                message="dry-run",
                created_at=now - timedelta(hours=1, minutes=3),
            ),
        ]
    )
    seed.commit()
    seed.close()

    with _create_client(session_local, monkeypatch) as client:
        response = client.get("/api/v1/metrics/task-retry/summary?hours=24")
        assert response.status_code == 200
        payload = response.json()
        assert payload["audit_total"] == 2
        assert payload["item_total"] == 3

        by_action = {item["action"]: item["count"] for item in payload["by_action"]}
        assert by_action["queued"] == 1
        assert by_action["would_retry"] == 1
        assert by_action["skipped_task_cooldown"] == 1

        by_code = {item["failure_code"]: item["count"] for item in payload["by_failure_code"]}
        assert by_code["ASSET_STALE"] == 2
        assert by_code["ASSET_EXPIRED"] == 1

        by_source = {item["source"]: item["count"] for item in payload["by_source"]}
        assert by_source["api"] == 2
        assert by_source["web"] == 1

        assert len(payload["audit_by_hour"]) == 2
        assert sum(item["total"] for item in payload["by_hour"]) == 3


def test_task_retry_summary_supports_source_and_dry_run_filters(monkeypatch):
    session_local = _build_sqlite_session_local()
    seed = session_local()
    now = datetime.now(timezone.utc)

    audit_apply = TaskRetryAudit(
        endpoint="/api/v1/admin/tasks/refresh-retry/batch",
        operator_id="alice",
        source_ip="127.0.0.1",
        trace_id="trace-retry-filter-1",
        dry_run=False,
        effective_hours=24,
        source_filter="",
        failure_codes_csv="ASSET_STALE",
        window_size=5,
        max_windows=1,
        same_asset_max_retries=2,
        requested=1,
        missing_tasks=0,
        matched_by_failure=1,
        queued=1,
        skipped_non_retryable=0,
        skipped_in_progress=0,
        skipped_asset_not_found=0,
        skipped_rate_limited=0,
        skipped_asset_guardrail=0,
        filters_json="{}",
        summary_json="{}",
        created_at=now - timedelta(minutes=50),
    )
    audit_dry = TaskRetryAudit(
        endpoint="/api/v1/admin/tasks/refresh-retry/batch",
        operator_id="alice",
        source_ip="127.0.0.1",
        trace_id="trace-retry-filter-2",
        dry_run=True,
        effective_hours=24,
        source_filter="",
        failure_codes_csv="ASSET_EXPIRED",
        window_size=5,
        max_windows=1,
        same_asset_max_retries=2,
        requested=1,
        missing_tasks=0,
        matched_by_failure=1,
        queued=1,
        skipped_non_retryable=0,
        skipped_in_progress=0,
        skipped_asset_not_found=0,
        skipped_rate_limited=0,
        skipped_asset_guardrail=0,
        filters_json="{}",
        summary_json="{}",
        created_at=now - timedelta(minutes=30),
    )
    seed.add_all([audit_apply, audit_dry])
    seed.flush()
    seed.add_all(
        [
            TaskRetryAuditItem(
                audit_id=audit_apply.id,
                task_id="task-retry-filter-1",
                target_asset_id="asset-c",
                source="api",
                action="queued",
                failure_code="ASSET_STALE",
                final_status="executing",
                final_failure_code="",
                message="queued",
                created_at=now - timedelta(minutes=49),
            ),
            TaskRetryAuditItem(
                audit_id=audit_dry.id,
                task_id="task-retry-filter-2",
                target_asset_id="asset-d",
                source="api",
                action="would_retry",
                failure_code="ASSET_EXPIRED",
                final_status="failed",
                final_failure_code="ASSET_EXPIRED",
                message="dry-run",
                created_at=now - timedelta(minutes=29),
            ),
        ]
    )
    seed.commit()
    seed.close()

    with _create_client(session_local, monkeypatch) as client:
        response = client.get("/api/v1/metrics/task-retry/summary?hours=24&source=api&include_dry_run=false")
        assert response.status_code == 200
        payload = response.json()
        assert payload["audit_total"] == 1
        assert payload["item_total"] == 1
        assert payload["include_dry_run"] is False
        assert payload["source_filter"] == "api"

        by_action = {item["action"]: item["count"] for item in payload["by_action"]}
        assert by_action["queued"] == 1
        assert "would_retry" not in by_action


def test_failure_summary_uses_preaggregated_buckets(monkeypatch):
    session_local = _build_sqlite_session_local()
    seed = session_local()
    now = datetime.now(timezone.utc)
    bucket = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
    seed.add_all(
        [
            FailureSummaryBucket(
                granularity="hour",
                bucket_start=bucket,
                source="api",
                risk_level="readonly",
                failure_code="CONNECTIVITY_ERROR",
                unknown_reason="",
                count=3,
            ),
            FailureSummaryBucket(
                granularity="hour",
                bucket_start=bucket,
                source="api",
                risk_level="safe-write",
                failure_code="UNKNOWN",
                unknown_reason="custom failure text",
                count=1,
            ),
        ]
    )
    seed.commit()
    seed.close()

    with _create_client(session_local, monkeypatch) as client:
        response = client.get("/api/v1/metrics/failures/summary?hours=24&source=api")
        assert response.status_code == 200
        payload = response.json()
        assert payload["data_mode"] == "preaggregated_hour"
        assert payload["total_failed"] == 4
        by_code = {item["failure_code"]: item["count"] for item in payload["by_failure_code"]}
        assert by_code["CONNECTIVITY_ERROR"] == 3
        assert by_code["UNKNOWN"] == 1
        unknown_samples = {item["reason"]: item["count"] for item in payload["unknown_reason_samples"]}
        assert unknown_samples["custom failure text"] == 1


def test_task_retry_summary_uses_preaggregated_buckets(monkeypatch):
    session_local = _build_sqlite_session_local()
    seed = session_local()
    now = datetime.now(timezone.utc)
    bucket = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
    seed.add_all(
        [
            TaskRetrySummaryBucket(
                granularity="hour",
                bucket_start=bucket,
                source="api",
                action="queued",
                failure_code="ASSET_STALE",
                operator_id="alice",
                dry_run=False,
                count=2,
            ),
            TaskRetrySummaryBucket(
                granularity="hour",
                bucket_start=bucket,
                source="api",
                action="skipped_task_cooldown",
                failure_code="ASSET_STALE",
                operator_id="alice",
                dry_run=False,
                count=1,
            ),
            TaskRetryAuditCountBucket(
                granularity="hour",
                bucket_start=bucket,
                operator_id="alice",
                dry_run=False,
                source_selector="*",
                count=2,
            ),
            TaskRetryAuditCountBucket(
                granularity="hour",
                bucket_start=bucket,
                operator_id="alice",
                dry_run=False,
                source_selector="api",
                count=2,
            ),
        ]
    )
    seed.commit()
    seed.close()

    with _create_client(session_local, monkeypatch) as client:
        response = client.get(
            "/api/v1/metrics/task-retry/summary?hours=24&source=api&operator_id=alice&include_dry_run=false"
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["data_mode"] == "preaggregated_hour"
        assert payload["item_total"] == 3
        assert payload["audit_total"] == 2
        by_action = {item["action"]: item["count"] for item in payload["by_action"]}
        assert by_action["queued"] == 2
        assert by_action["skipped_task_cooldown"] == 1


def test_failure_remediation_template_endpoint(monkeypatch):
    session_local = _build_sqlite_session_local()
    with _create_client(session_local, monkeypatch) as client:
        response = client.get(
            "/api/v1/metrics/failures/remediation-template?failure_code=connectivity_error&source=api&risk_level=safe-write"
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["requested_failure_code"] == "CONNECTIVITY_ERROR"
        assert payload["matched"] is True
        assert payload["source_filter"] == "api"
        assert payload["risk_level_filter"] == "safe-write"
        assert payload["template"]["failure_code"] == "CONNECTIVITY_ERROR"
        assert payload["template"]["recommended_actions"]
        assert payload["template"]["context_hints"]


def test_failure_remediation_template_unknown_fallback(monkeypatch):
    session_local = _build_sqlite_session_local()
    with _create_client(session_local, monkeypatch) as client:
        response = client.get("/api/v1/metrics/failures/remediation-template?failure_code=not_exists")
        assert response.status_code == 200
        payload = response.json()
        assert payload["requested_failure_code"] == "NOT_EXISTS"
        assert payload["matched"] is False
        assert payload["template"]["failure_code"] == "UNKNOWN"


def test_admin_run_metrics_preaggregation_debug_gate(monkeypatch):
    session_local = _build_sqlite_session_local()
    monkeypatch.setattr(api_main.settings, "app_allow_admin_debug_endpoints", False)
    with _create_client(session_local, monkeypatch) as client:
        forbidden = client.post("/api/v1/admin/metrics/preaggregation/run")
        assert forbidden.status_code == 403
        assert forbidden.json()["code"] == "FORBIDDEN"

    monkeypatch.setattr(api_main.settings, "app_allow_admin_debug_endpoints", True)
    monkeypatch.setattr(
        api_main,
        "run_metrics_preaggregation",
        lambda **kwargs: {"status": "ok", "failure_summary": {"hour_rows": 1}, "task_retry_summary": {"hour_item_rows": 2}},
    )
    with _create_client(session_local, monkeypatch) as client:
        ok = client.post("/api/v1/admin/metrics/preaggregation/run")
        assert ok.status_code == 200
        payload = ok.json()
        assert payload["status"] == "ok"
        assert payload["result"]["failure_summary"]["hour_rows"] == 1


def test_failure_remediation_with_task_context(monkeypatch):
    session_local = _build_sqlite_session_local()
    seed = session_local()
    task = Task(
        trace_id="trace-remediation-task-1",
        source="api",
        status="failed",
        risk_level="readonly",
        idempotency_key="remediation-task-1",
        command="hostname",
        target_asset_id="asset-rem-1",
        run_as_system_user_id="su-rem-1",
        reason="shell: Failed to connect to host 10.0.0.1 port 22: Connection timed out",
    )
    seed.add(task)
    seed.commit()
    seed.close()

    with _create_client(session_local, monkeypatch) as client:
        response = client.get(f"/api/v1/metrics/failures/remediation?task_id={task.id}")
        assert response.status_code == 200
        payload = response.json()
        assert payload["resolved_from"] == "task"
        assert payload["template"]["failure_code"] == "CONNECTIVITY_ERROR"
        assert payload["context"]["task_id"] == task.id
        assert payload["template"]["context_hints"]


def test_failure_remediation_with_execution_context(monkeypatch):
    session_local = _build_sqlite_session_local()
    seed = session_local()
    task = Task(
        trace_id="trace-remediation-exec-1",
        source="web",
        status="failed",
        risk_level="safe-write",
        idempotency_key="remediation-exec-1",
        command="uptime",
        target_asset_id="asset-rem-2",
        run_as_system_user_id="su-rem-2",
        reason="[PERMISSION_DENIED] denied",
    )
    seed.add(task)
    seed.flush()
    execution = Execution(
        task_id=task.id,
        jms_execution_id="jms-remediation-1",
        status="failed",
        result_summary="[ASSET_EXPIRED] refresh required",
    )
    seed.add(execution)
    seed.commit()
    seed.close()

    with _create_client(session_local, monkeypatch) as client:
        response = client.get("/api/v1/metrics/failures/remediation?execution_id=jms-remediation-1")
        assert response.status_code == 200
        payload = response.json()
        assert payload["resolved_from"] == "execution"
        assert payload["template"]["failure_code"] == "ASSET_EXPIRED"
        assert payload["context"]["execution_id"] == execution.id
        assert payload["context"]["task_id"] == task.id


def test_failure_remediation_requires_at_least_one_input(monkeypatch):
    session_local = _build_sqlite_session_local()
    with _create_client(session_local, monkeypatch) as client:
        response = client.get("/api/v1/metrics/failures/remediation")
        assert response.status_code == 400
        assert response.json()["code"] == "INVALID_ARGUMENT"


def test_preaggregation_status_reports_health(monkeypatch):
    session_local = _build_sqlite_session_local()
    seed = session_local()
    now = datetime.now(timezone.utc)
    bucket = now.replace(minute=0, second=0, microsecond=0)
    seed.add_all(
        [
            MetricsPreaggregationRun(
                status="ok",
                hourly_lookback_hours=72,
                daily_lookback_days=30,
                failure_hour_rows=1,
                failure_day_rows=1,
                retry_hour_item_rows=1,
                retry_day_item_rows=1,
                retry_hour_audit_rows=1,
                retry_day_audit_rows=1,
                run_at=now,
            ),
            FailureSummaryBucket(
                granularity="hour",
                bucket_start=bucket,
                source="api",
                risk_level="readonly",
                failure_code="CONNECTIVITY_ERROR",
                unknown_reason="",
                count=1,
            ),
            TaskRetrySummaryBucket(
                granularity="hour",
                bucket_start=bucket,
                source="api",
                action="queued",
                failure_code="ASSET_STALE",
                operator_id="alice",
                dry_run=False,
                count=1,
            ),
            TaskRetryAuditCountBucket(
                granularity="hour",
                bucket_start=bucket,
                operator_id="alice",
                dry_run=False,
                source_selector="*",
                count=1,
            ),
        ]
    )
    seed.commit()
    seed.close()

    monkeypatch.setattr(api_main.settings, "metrics_preaggregation_max_lag_minutes", 180)
    with _create_client(session_local, monkeypatch) as client:
        response = client.get("/api/v1/metrics/preaggregation/status?granularity=hour")
        assert response.status_code == 200
        payload = response.json()
        assert payload["healthy"] is True
        assert payload["run_lag_minutes"] is not None
        assert payload["latest"]["failure_summary_bucket"] is not None


def test_preaggregation_alerts_levels(monkeypatch):
    session_local = _build_sqlite_session_local()
    seed = session_local()
    now = datetime.now(timezone.utc)
    seed.add(
        MetricsPreaggregationRun(
            status="ok",
            hourly_lookback_hours=72,
            daily_lookback_days=30,
            failure_hour_rows=1,
            failure_day_rows=1,
            retry_hour_item_rows=1,
            retry_day_item_rows=1,
            retry_hour_audit_rows=1,
            retry_day_audit_rows=1,
            run_at=now - timedelta(minutes=5),
        )
    )
    seed.commit()
    seed.close()

    monkeypatch.setattr(api_main.settings, "metrics_preaggregation_max_lag_minutes", 30)
    with _create_client(session_local, monkeypatch) as client:
        ok_resp = client.get("/api/v1/metrics/preaggregation/alerts?granularity=hour")
        assert ok_resp.status_code == 200
        assert ok_resp.json()["level"] == "ok"

    # Make it stale to trigger critical.
    seed = session_local()
    seed.query(MetricsPreaggregationRun).delete()
    seed.add(
        MetricsPreaggregationRun(
            status="ok",
            hourly_lookback_hours=72,
            daily_lookback_days=30,
            failure_hour_rows=1,
            failure_day_rows=1,
            retry_hour_item_rows=1,
            retry_day_item_rows=1,
            retry_hour_audit_rows=1,
            retry_day_audit_rows=1,
            run_at=now - timedelta(minutes=80),
        )
    )
    seed.commit()
    seed.close()

    monkeypatch.setattr(api_main.settings, "metrics_preaggregation_max_lag_minutes", 30)
    with _create_client(session_local, monkeypatch) as client:
        crit_resp = client.get("/api/v1/metrics/preaggregation/alerts?granularity=hour")
        assert crit_resp.status_code == 200
        crit = crit_resp.json()
        assert crit["level"] == "critical"
        assert crit["status"]["healthy"] is False


def test_audits_summary_is_dashboard_ready(monkeypatch):
    session_local = _build_sqlite_session_local()
    seed = session_local()
    now = datetime.now(timezone.utc)

    task_a = Task(
        trace_id="trace-audit-summary-1",
        source="api",
        status="failed",
        risk_level="readonly",
        idempotency_key="audit-summary-1",
        command="hostname",
        target_asset_id="asset-1",
        run_as_system_user_id="su-1",
        reason="[CONNECTIVITY_ERROR] timeout",
        created_at=now - timedelta(minutes=30),
    )
    task_b = Task(
        trace_id="trace-audit-summary-2",
        source="web",
        status="success",
        risk_level="safe-write",
        idempotency_key="audit-summary-2",
        command="uptime",
        target_asset_id="asset-2",
        run_as_system_user_id="su-2",
        reason="ok",
        created_at=now - timedelta(minutes=20),
    )
    seed.add_all([task_a, task_b])
    seed.flush()

    exec_a = Execution(
        task_id=task_a.id,
        jms_execution_id="jms-audit-summary-1",
        status="failed",
        result_summary="[CONNECTIVITY_ERROR] timeout",
        created_at=now - timedelta(minutes=28),
    )
    exec_b = Execution(
        task_id=task_b.id,
        jms_execution_id="jms-audit-summary-2",
        status="success",
        result_summary="ok",
        created_at=now - timedelta(minutes=18),
    )
    seed.add_all([exec_a, exec_b])
    seed.flush()

    seed.add_all(
        [
            AuditLink(
                task_id=task_a.id,
                execution_id=exec_a.id,
                jms_audit_relation_id="audit-summary-link-1",
                trace_id=task_a.trace_id,
                created_at=now - timedelta(minutes=27),
            ),
            AuditLink(
                task_id=task_b.id,
                execution_id=exec_b.id,
                jms_audit_relation_id="audit-summary-link-2",
                trace_id=task_b.trace_id,
                created_at=now - timedelta(minutes=17),
            ),
        ]
    )
    seed.commit()
    seed.close()

    with _create_client(session_local, monkeypatch) as client:
        response = client.get("/api/v1/audits/summary?hours=24")
        assert response.status_code == 200
        payload = response.json()
        assert payload["task_total"] == 2
        assert payload["execution_total"] == 2
        assert payload["audit_link_total"] == 2
        assert payload["failed_task_total"] == 1
        by_source = {item["source"]: item["count"] for item in payload["by_source"]}
        assert by_source["api"] == 1
        assert by_source["web"] == 1
        by_failure = {item["failure_code"]: item["count"] for item in payload["by_failure_code"]}
        assert by_failure["CONNECTIVITY_ERROR"] == 1
        assert payload["by_hour"]


def test_audits_summary_supports_filters(monkeypatch):
    session_local = _build_sqlite_session_local()
    seed = session_local()
    now = datetime.now(timezone.utc)
    task_a = Task(
        trace_id="trace-audit-filter-1",
        source="api",
        status="failed",
        risk_level="readonly",
        idempotency_key="audit-filter-1",
        command="hostname",
        target_asset_id="asset-x",
        run_as_system_user_id="su-x",
        reason="[ASSET_EXPIRED] refresh required",
        created_at=now - timedelta(minutes=10),
    )
    task_b = Task(
        trace_id="trace-audit-filter-2",
        source="web",
        status="failed",
        risk_level="readonly",
        idempotency_key="audit-filter-2",
        command="hostname",
        target_asset_id="asset-y",
        run_as_system_user_id="su-y",
        reason="[ASSET_STALE] stale",
        created_at=now - timedelta(minutes=9),
    )
    seed.add_all([task_a, task_b])
    seed.commit()
    seed.close()

    with _create_client(session_local, monkeypatch) as client:
        response = client.get("/api/v1/audits/summary?hours=24&source=api&asset_id=asset-x")
        assert response.status_code == 200
        payload = response.json()
        assert payload["task_total"] == 1
        assert payload["source_filter"] == "api"
        assert payload["asset_id_filter"] == "asset-x"
        assert payload["by_asset"][0]["asset_id"] == "asset-x"
