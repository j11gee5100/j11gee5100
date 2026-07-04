from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import main as api_main
from app.db.base import Base
from app.models import FailureSummaryBucket, MetricsPreaggregationRun, Task


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


def _build_sqlite_session_local():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def _create_client(session_local, monkeypatch) -> TestClient:
    monkeypatch.setattr(api_main, "init_db", lambda: None)
    monkeypatch.setattr(api_main, "session_scope", _override_session_scope(session_local))
    return TestClient(api_main.app)


def test_command_template_and_task_policy_flow(monkeypatch):
    session_local = _build_sqlite_session_local()
    with _create_client(session_local, monkeypatch) as client:
        create_template = client.post(
            "/api/v1/templates/commands",
            headers={"x-operator-id": "alice"},
            json={
                "template_id": "tpl-usermod",
                "name": "Usermod Wheel",
                "description": "append user to wheel group",
                "command": "usermod -aG wheel app",
                "risk_level": "high-risk",
                "enabled": True,
            },
        )
        assert create_template.status_code == 200
        template = create_template.json()["item"]
        assert template["template_id"] == "tpl-usermod"
        assert template["risk_level"] == "high-risk"

        task_create = client.post(
            "/api/v1/tasks",
            headers={"x-operator-id": "alice"},
            json={
                "command_template_id": "tpl-usermod",
                "target_asset_id": "asset-1",
                "run_as_system_user_id": "su-1",
                "risk_level": "readonly",
                "idempotency_key": "gov-task-1",
            },
        )
        assert task_create.status_code == 200
        payload = task_create.json()
        assert payload["status"] == "approval_pending"
        assert payload["approval_required"] is True
        assert payload["risk_level_final"] == "high-risk"
        assert payload["command_template_id"] == "tpl-usermod"

        audits = client.get("/api/v1/governance/audits?entity_type=template")
        assert audits.status_code == 200
        audit_payload = audits.json()
        assert audit_payload["total"] >= 1
        assert audit_payload["items"][0]["entity_type"] == "template"


def test_policy_blacklist_rule_create_update_and_evaluate(monkeypatch):
    session_local = _build_sqlite_session_local()
    with _create_client(session_local, monkeypatch) as client:
        create_rule = client.post(
            "/api/v1/policies/command-blacklist",
            headers={"x-operator-id": "bob"},
            json={
                "pattern": "danger-cmd",
                "description": "custom dangerous command",
                "hard_block": True,
                "enabled": True,
            },
        )
        assert create_rule.status_code == 200
        rule = create_rule.json()["item"]
        assert rule["pattern"] == "danger-cmd"
        rule_id = rule["rule_id"]

        blocked = client.post(
            "/api/v1/policies/evaluate",
            json={"command": "echo ok && danger-cmd", "requested_risk_level": "readonly"},
        )
        assert blocked.status_code == 200
        blocked_payload = blocked.json()
        assert blocked_payload["allowed"] is False
        assert blocked_payload["block_reason"] is not None

        updated = client.patch(
            f"/api/v1/policies/command-blacklist/{rule_id}",
            headers={"x-operator-id": "bob"},
            json={"enabled": False},
        )
        assert updated.status_code == 200
        assert updated.json()["item"]["enabled"] is False

        allowed = client.post(
            "/api/v1/policies/evaluate",
            json={"command": "echo ok && danger-cmd", "requested_risk_level": "readonly"},
        )
        assert allowed.status_code == 200
        assert allowed.json()["allowed"] is True


def test_dashboard_overview_and_failure_detail(monkeypatch):
    session_local = _build_sqlite_session_local()
    seed = session_local()
    now = datetime.now(timezone.utc)
    hour_bucket = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
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
            run_at=now - timedelta(minutes=1),
        )
    )
    seed.add(
        FailureSummaryBucket(
            granularity="hour",
            bucket_start=hour_bucket,
            source="api",
            risk_level="readonly",
            failure_code="CONNECTIVITY_ERROR",
            unknown_reason="",
            count=3,
        )
    )
    seed.add(
        Task(
            trace_id="trace-dash-1",
            source="api",
            status="failed",
            risk_level="readonly",
            idempotency_key="dash-task-1",
            command="hostname",
            target_asset_id="asset-d1",
            run_as_system_user_id="su-d1",
            reason="[CONNECTIVITY_ERROR] timeout",
            updated_at=now - timedelta(minutes=10),
        )
    )
    seed.add(
        Task(
            trace_id="trace-dash-2",
            source="api",
            status="failed",
            risk_level="readonly",
            idempotency_key="dash-task-2",
            command="hostname",
            target_asset_id="asset-d2",
            run_as_system_user_id="su-d2",
            reason="[PERMISSION_DENIED] forbidden",
            updated_at=now - timedelta(minutes=9),
        )
    )
    seed.commit()
    seed.close()

    monkeypatch.setattr(api_main.settings, "metrics_preaggregation_max_lag_minutes", 30)
    with _create_client(session_local, monkeypatch) as client:
        overview = client.get("/api/v1/dashboard/overview?hours=24&source=api&top_n=3")
        assert overview.status_code == 200
        overview_payload = overview.json()
        assert overview_payload["alerts"]["level"] in ("ok", "warn")
        assert overview_payload["failure_summary"]["total_failed"] >= 3
        assert overview_payload["remediation_cards"]
        assert overview_payload["remediation_cards"][0]["failure_code"] == "CONNECTIVITY_ERROR"

        detail = client.get("/api/v1/dashboard/failures/CONNECTIVITY_ERROR/detail?hours=24&source=api&limit=10")
        assert detail.status_code == 200
        detail_payload = detail.json()
        assert detail_payload["failure_code"] == "CONNECTIVITY_ERROR"
        assert detail_payload["recent_failed_tasks"]
        assert all(item["source"] == "api" for item in detail_payload["recent_failed_tasks"])


def test_manual_escalate_approval(monkeypatch):
    session_local = _build_sqlite_session_local()
    monkeypatch.setattr(api_main.settings, "approval_escalation_enabled", True)
    monkeypatch.setattr(api_main.settings, "approval_max_levels", 3)
    monkeypatch.setattr(api_main.settings, "approval_escalation_after_minutes", 15)

    with _create_client(session_local, monkeypatch) as client:
        created = client.post(
            "/api/v1/tasks",
            headers={"x-operator-id": "creator"},
            json={
                "command": "hostname",
                "target_asset_id": "asset-esc-1",
                "run_as_system_user_id": "su-esc-1",
                "risk_level": "high-risk",
                "idempotency_key": "approval-escalate-api-1",
            },
        )
        assert created.status_code == 200
        approval_id = created.json()["approval_id"]

        escalated = client.post(
            f"/api/v1/approvals/{approval_id}/escalate",
            headers={"x-operator-id": "approver-l1"},
            json={"reason": "needs L2 review"},
        )
        assert escalated.status_code == 200
        approval = escalated.json()["approval"]
        assert approval["status"] == "pending"
        assert approval["current_level"] == 2
        assert approval["max_level"] == 3

        pending_l2 = client.get("/api/v1/approvals/pending?current_level=2")
        assert pending_l2.status_code == 200
        ids = {item["approval_id"] for item in pending_l2.json()["items"]}
        assert approval_id in ids
