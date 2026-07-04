from __future__ import annotations

from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import main as api_main
from app.db.base import Base


EXPECTED_PREFIX = "/api/v1/inference-environments"


@pytest.fixture
def inference_environment_client(monkeypatch):
    session_local = _build_sqlite_session_local()
    monkeypatch.setattr(api_main, "init_db", lambda: None)
    monkeypatch.setattr(api_main, "session_scope", lambda: _override_session_scope(session_local))
    with TestClient(api_main.app) as client:
        yield client


@contextmanager
def _override_session_scope(session_local):
    session = session_local()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _build_sqlite_session_local():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def _assert_collection_payload(payload: dict) -> None:
    assert isinstance(payload["items"], list)
    assert isinstance(payload["total"], int)


def test_device_create_list_update_and_compatibility(inference_environment_client: TestClient):
    create = inference_environment_client.post(
        f"{EXPECTED_PREFIX}/devices",
        json={
            "device_code": "dev-gpu-01",
            "name": "GPU Server 01",
            "hostname": "gpu-01",
            "ip": "10.0.0.11",
            "os_type": "linux",
            "accelerator_vendor": "nvidia-gpu",
            "accelerator_model": "A10",
            "accelerator_count": "1",
            "driver_version": "535.183",
        },
    )
    assert create.status_code == 200
    device = create.json()["item"]
    assert device["device_code"] == "dev-gpu-01"
    assert device["name"] == "GPU Server 01"

    listed = inference_environment_client.get(f"{EXPECTED_PREFIX}/devices?search=gpu-01")
    assert listed.status_code == 200
    payload = listed.json()
    _assert_collection_payload(payload)
    assert payload["items"][0]["device_id"] == device["device_id"]

    updated = inference_environment_client.patch(
        f"{EXPECTED_PREFIX}/devices/{device['device_id']}",
        json={"status": "maintenance", "notes": "driver upgrade window"},
    )
    assert updated.status_code == 200
    assert updated.json()["item"]["status"] == "maintenance"

    spec = inference_environment_client.post(
        f"{EXPECTED_PREFIX}/specs",
        json={
            "name": "gpu-small",
            "runtime": "cuda",
            "accelerator_type": "nvidia-gpu",
            "accelerator_model": "A10",
            "driver_version": "535.183",
        },
    ).json()
    compatibility = inference_environment_client.get(
        f"{EXPECTED_PREFIX}/compatibility?device_id={device['device_id']}&spec_id={spec['spec_id']}"
    )
    assert compatibility.status_code == 200
    assert compatibility.json()["compatible"] is True


def test_create_environment_spec_returns_created_spec(inference_environment_client: TestClient):
    response = inference_environment_client.post(
        f"{EXPECTED_PREFIX}/specs",
        json={
            "name": "gpu-small",
            "runtime": "python",
            "accelerator_type": "nvidia-gpu",
            "python_version": "3.12",
            "framework": "torch",
            "inference_server": "triton",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "gpu-small"
    assert payload["runtime"] == "python"
    assert payload["accelerator_type"] == "nvidia-gpu"
    assert isinstance(payload.get("spec_id"), str)


def test_create_model_deployment_requirement_returns_requirement(inference_environment_client: TestClient):
    response = inference_environment_client.post(
        f"{EXPECTED_PREFIX}/deployment-requirements",
        json={
            "model_id": "model-llm-7b",
            "min_vram_gb": 16,
            "min_ram_gb": 32,
            "required_accelerator_type": "nvidia-gpu",
            "required_cuda_version": "12.4",
            "required_capabilities": ["fp16", "tensor-parallel"],
            "notes": "supports single-node inference",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["model_id"] == "model-llm-7b"
    assert payload["required_accelerator_type"] == "nvidia-gpu"
    assert payload["min_vram_gb"] == 16
    assert isinstance(payload.get("requirement_id"), str)


def test_create_environment_implementation_returns_implementation(inference_environment_client: TestClient):
    response = inference_environment_client.post(
        f"{EXPECTED_PREFIX}/implementations",
        json={
            "implementation_name": "vllm-gpu-prod",
            "spec_id": "spec-gpu-small",
            "device_ids": ["device-gpu-01"],
            "engine": "vllm",
            "engine_version": "0.6.0",
            "endpoint": "http://inference.internal/v1",
            "status": "ready",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["implementation_name"] == "vllm-gpu-prod"
    assert payload["spec_id"] == "spec-gpu-small"
    assert payload["engine"] == "vllm"
    assert payload["device_ids"] == ["device-gpu-01"]
    assert isinstance(payload.get("implementation_id"), str)


def test_create_handover_returns_pending_handover_and_accept_reject(inference_environment_client: TestClient):
    response = inference_environment_client.post(
        f"{EXPECTED_PREFIX}/handovers",
        json={
            "implementation_id": "impl-vllm-gpu-prod",
            "target_owner": "ml-platform-oncall",
            "reason": "capacity rebalancing",
            "artifacts": [
                {"type": "runbook", "uri": "s3://ops/runbooks/inference-handover.md"},
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["implementation_id"] == "impl-vllm-gpu-prod"
    assert payload["target_owner"] == "ml-platform-oncall"
    assert payload["status"] == "pending"
    assert isinstance(payload.get("handover_id"), str)

    accepted = inference_environment_client.post(
        f"{EXPECTED_PREFIX}/handovers/{payload['handover_id']}/accept",
        json={"operator_id": "assembly-a", "reason": "accepted for assembly"},
    )
    assert accepted.status_code == 200
    assert accepted.json()["item"]["status"] == "accepted"
    assert accepted.json()["item"]["accepted_by"] == "assembly-a"

    rejected = inference_environment_client.post(
        f"{EXPECTED_PREFIX}/handovers/{payload['handover_id']}/reject",
        json={"operator_id": "assembly-a", "reason": "regression retest required"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["item"]["status"] == "rejected"
    assert rejected.json()["item"]["rejection_reason"] == "regression retest required"
