from __future__ import annotations

from contextlib import contextmanager

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import main as api_main
from app.db.base import Base


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


def _create_high_risk_task(client: TestClient, *, idem: str, source: str = "api"):
    response = client.post(
        "/api/v1/tasks",
        headers={"x-operator-id": "creator"},
        json={
            "command": "hostname",
            "target_asset_id": "asset-approval-1",
            "run_as_system_user_id": "su-approval-1",
            "risk_level": "high-risk",
            "source": source,
            "idempotency_key": idem,
        },
    )
    assert response.status_code == 200
    return response.json()


def test_create_high_risk_task_requires_approval(monkeypatch):
    session_local = _build_sqlite_session_local()
    monkeypatch.setattr(api_main.settings, "approval_timeout_hours", 12)
    with _create_client(session_local, monkeypatch) as client:
        created = _create_high_risk_task(client, idem="approval-create-1")
        assert created["status"] == "approval_pending"
        assert created["approval_required"] is True
        assert created["approval_id"]
        assert created["approval_status"] == "pending"

        task_resp = client.get(f"/api/v1/tasks/{created['task_id']}")
        assert task_resp.status_code == 200
        task_payload = task_resp.json()
        assert task_payload["status"] == "approval_pending"
        assert task_payload["approval_id"] == created["approval_id"]
        assert task_payload["approval_status"] == "pending"
        assert task_payload["approval_expires_at"] is not None

        approval_resp = client.get(f"/api/v1/tasks/{created['task_id']}/approval")
        assert approval_resp.status_code == 200
        approval_payload = approval_resp.json()
        assert approval_payload["approval"]["approval_id"] == created["approval_id"]
        assert approval_payload["approval"]["status"] == "pending"
        assert any(item["action"] == "created" for item in approval_payload["actions"])


def test_approve_approval_transitions_task_to_pending(monkeypatch):
    session_local = _build_sqlite_session_local()
    with _create_client(session_local, monkeypatch) as client:
        created = _create_high_risk_task(client, idem="approval-approve-1")
        approval_id = created["approval_id"]

        approve = client.post(
            f"/api/v1/approvals/{approval_id}/approve",
            headers={"x-operator-id": "alice"},
            json={"reason": "reviewed and approved"},
        )
        assert approve.status_code == 200
        approve_payload = approve.json()
        assert approve_payload["approval"]["status"] == "approved"
        assert approve_payload["approval"]["decided_by"] == "alice"

        task_resp = client.get(f"/api/v1/tasks/{created['task_id']}")
        assert task_resp.status_code == 200
        task_payload = task_resp.json()
        assert task_payload["status"] == "pending"
        assert task_payload["approval_status"] == "approved"


def test_reject_approval_marks_task_failed(monkeypatch):
    session_local = _build_sqlite_session_local()
    with _create_client(session_local, monkeypatch) as client:
        created = _create_high_risk_task(client, idem="approval-reject-1")
        approval_id = created["approval_id"]

        reject = client.post(
            f"/api/v1/approvals/{approval_id}/reject",
            headers={"x-operator-id": "bob"},
            json={"reason": "unsafe command for current window"},
        )
        assert reject.status_code == 200
        reject_payload = reject.json()
        assert reject_payload["approval"]["status"] == "rejected"
        assert reject_payload["approval"]["decided_by"] == "bob"

        task_resp = client.get(f"/api/v1/tasks/{created['task_id']}")
        assert task_resp.status_code == 200
        task_payload = task_resp.json()
        assert task_payload["status"] == "failed"
        assert task_payload["failure_code"] == "APPROVAL_REJECTED"


def test_cancel_approval_pending_task_marks_approval_expired(monkeypatch):
    session_local = _build_sqlite_session_local()
    with _create_client(session_local, monkeypatch) as client:
        created = _create_high_risk_task(client, idem="approval-cancel-1")

        canceled = client.post(
            f"/api/v1/tasks/{created['task_id']}/cancel",
            json={"reason": "request canceled by operator"},
        )
        assert canceled.status_code == 200
        canceled_payload = canceled.json()
        assert canceled_payload["status"] == "canceled"

        approval_resp = client.get(f"/api/v1/tasks/{created['task_id']}/approval")
        assert approval_resp.status_code == 200
        approval_payload = approval_resp.json()
        assert approval_payload["approval"]["status"] == "expired"
        assert any(item["action"] == "canceled" for item in approval_payload["actions"])


def test_list_approvals_supports_filters(monkeypatch):
    session_local = _build_sqlite_session_local()
    with _create_client(session_local, monkeypatch) as client:
        first = _create_high_risk_task(client, idem="approval-list-1", source="api")
        second = _create_high_risk_task(client, idem="approval-list-2", source="web")

        approve = client.post(
            f"/api/v1/approvals/{first['approval_id']}/approve",
            headers={"x-operator-id": "alice"},
            json={"reason": "ok"},
        )
        assert approve.status_code == 200

        pending = client.get("/api/v1/approvals/pending")
        assert pending.status_code == 200
        pending_payload = pending.json()
        ids = {item["approval_id"] for item in pending_payload["items"]}
        assert second["approval_id"] in ids
        assert first["approval_id"] not in ids

        filtered = client.get("/api/v1/approvals?status=approved&source=api&risk_level=high-risk")
        assert filtered.status_code == 200
        filtered_payload = filtered.json()
        assert filtered_payload["total"] == 1
        assert filtered_payload["items"][0]["approval_id"] == first["approval_id"]
