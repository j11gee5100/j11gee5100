from __future__ import annotations

import json
from datetime import datetime, timezone

from app.core.config import settings
from app.models import CallbackDelivery, CallbackHook, Task
from app.services.callback_service import run_callback_tick


def test_callback_tick_enqueues_and_delivers_success(db_session, monkeypatch):
    monkeypatch.setattr(settings, "callback_block_private_networks", True)
    monkeypatch.setattr(settings, "callback_allowed_hosts", "")
    monkeypatch.setattr(settings, "callback_allowed_domain_suffixes", "example.com")
    monkeypatch.setattr(settings, "callback_allowed_cidrs", "")

    task = Task(
        trace_id="trace-callback-1",
        source="api",
        status="success",
        risk_level="readonly",
        idempotency_key="callback-task-1",
        command="hostname",
        target_asset_id="asset-1",
        run_as_system_user_id="su-1",
        reason="ok",
    )
    db_session.add(task)
    db_session.flush()

    hook = CallbackHook(
        task_id=task.id,
        callback_url="https://example.com/opspaw/callback",
        callback_secret="top-secret",
        status="active",
    )
    db_session.add(hook)
    db_session.commit()

    sent = {}

    def fake_sender(url: str, body: str, headers: dict[str, str], timeout_sec: int):
        sent["url"] = url
        sent["body"] = body
        sent["headers"] = headers
        sent["timeout_sec"] = timeout_sec
        return 200, "ok"

    result = run_callback_tick(session=db_session, sender=fake_sender)
    db_session.commit()

    assert result["created_deliveries"] == 1
    assert result["processed_deliveries"] == 1
    assert result["delivered"] == 1
    assert result["retried"] == 0
    assert result["dead"] == 0

    delivery = db_session.query(CallbackDelivery).filter(CallbackDelivery.task_id == task.id).one()
    assert delivery.status == "success"
    assert delivery.attempts == 1
    payload = json.loads(delivery.payload_json)
    assert payload["task_id"] == task.id
    assert sent["url"] == "https://example.com/opspaw/callback"
    assert sent["headers"]["X-OpsPaw-Event-Type"] == "task_finalized"
    assert sent["headers"]["X-OpsPaw-Signature"].startswith("sha256=")
    assert sent["headers"]["X-OpsPaw-Signature-Timestamp"]
    assert sent["headers"]["X-OpsPaw-Signature-Nonce"]


def test_callback_tick_marks_dead_after_max_attempts(db_session, monkeypatch):
    monkeypatch.setattr(settings, "callback_block_private_networks", True)
    monkeypatch.setattr(settings, "callback_allowed_hosts", "")
    monkeypatch.setattr(settings, "callback_allowed_domain_suffixes", "example.com")
    monkeypatch.setattr(settings, "callback_allowed_cidrs", "")

    task = Task(
        trace_id="trace-callback-2",
        source="api",
        status="failed",
        risk_level="readonly",
        idempotency_key="callback-task-2",
        command="hostname",
        target_asset_id="asset-2",
        run_as_system_user_id="su-2",
        reason="failed",
    )
    db_session.add(task)
    db_session.flush()

    hook = CallbackHook(
        task_id=task.id,
        callback_url="https://example.com/opspaw/callback",
        callback_secret="",
        status="active",
    )
    db_session.add(hook)
    db_session.flush()

    delivery = CallbackDelivery(
        task_id=task.id,
        hook_id=hook.id,
        event_type="task_finalized",
        status="pending",
        attempts=0,
        max_attempts=1,
        next_retry_at=datetime.now(timezone.utc),
        payload_json="{}",
    )
    db_session.add(delivery)
    db_session.commit()

    def failing_sender(url: str, body: str, headers: dict[str, str], timeout_sec: int):
        return 500, "callback failed"

    result = run_callback_tick(session=db_session, sender=failing_sender)
    db_session.commit()

    assert result["created_deliveries"] == 0
    assert result["processed_deliveries"] == 1
    assert result["delivered"] == 0
    assert result["retried"] == 0
    assert result["dead"] == 1

    stored = db_session.get(CallbackDelivery, delivery.id)
    assert stored is not None
    assert stored.status == "dead"
    assert stored.attempts == 1
    assert stored.last_http_status == 500


def test_callback_tick_blocks_private_destination_when_not_whitelisted(db_session, monkeypatch):
    monkeypatch.setattr(settings, "callback_block_private_networks", True)
    monkeypatch.setattr(settings, "callback_allowed_hosts", "")
    monkeypatch.setattr(settings, "callback_allowed_domain_suffixes", "")
    monkeypatch.setattr(settings, "callback_allowed_cidrs", "")

    task = Task(
        trace_id="trace-callback-3",
        source="api",
        status="success",
        risk_level="readonly",
        idempotency_key="callback-task-3",
        command="hostname",
        target_asset_id="asset-3",
        run_as_system_user_id="su-3",
        reason="ok",
    )
    db_session.add(task)
    db_session.flush()

    hook = CallbackHook(
        task_id=task.id,
        callback_url="http://127.0.0.1:9000/opspaw/callback",
        callback_secret="",
        status="active",
    )
    db_session.add(hook)
    db_session.commit()

    sender_calls = {"count": 0}

    def fake_sender(url: str, body: str, headers: dict[str, str], timeout_sec: int):
        sender_calls["count"] += 1
        return 200, "ok"

    result = run_callback_tick(session=db_session, sender=fake_sender)
    db_session.commit()

    assert result["created_deliveries"] == 1
    assert result["processed_deliveries"] == 1
    assert result["delivered"] == 0
    assert result["dead"] == 1
    assert sender_calls["count"] == 0

    delivery = db_session.query(CallbackDelivery).filter(CallbackDelivery.task_id == task.id).one()
    assert delivery.status == "dead"
    assert "callback blocked" in delivery.last_error
