from __future__ import annotations

import httpx
import pytest

from app.core.config import settings
from app.services.jumpserver.client import JumpServerClient, JumpServerClientError
from app.services.jumpserver.schemas import CommandExecutionRequest


def test_list_assets_reads_results_list():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/perms/users/assets/"
        return httpx.Response(
            status_code=200,
            json={"count": 1, "results": [{"id": "a1", "hostname": "srv-1"}]},
        )

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport, base_url="http://test") as mock_client:
        client = JumpServerClient(base_url="http://test", client=mock_client)
        assets = client.list_assets(limit=10, offset=0)

    assert len(assets) == 1
    assert assets[0].id == "a1"
    assert assets[0].hostname == "srv-1"


def test_list_asset_system_users_handles_plain_list():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/perms/users/assets/":
            return httpx.Response(status_code=200, json={"count": 0, "results": []})
        assert request.url.path == "/api/v1/perms/users/assets/asset-1/system-users/"
        return httpx.Response(status_code=200, json=[{"id": "u1", "name": "root"}])

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport, base_url="http://test") as mock_client:
        client = JumpServerClient(base_url="http://test", client=mock_client)
        users = client.list_asset_system_users("asset-1")

    assert len(users) == 1
    assert users[0].id == "u1"
    assert users[0].name == "root"


def test_list_assets_supports_v4_my_assets_endpoint():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/perms/users/assets/":
            return httpx.Response(status_code=404, json={"detail": "not found"})
        if request.url.path == "/api/v1/perms/users/my/assets/":
            return httpx.Response(
                status_code=200,
                json={"count": 1, "results": [{"id": "a2", "name": "srv-v4", "address": "10.0.0.2"}]},
            )
        raise AssertionError(f"unexpected path: {request.url.path}")

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport, base_url="http://test") as mock_client:
        client = JumpServerClient(base_url="http://test", client=mock_client)
        assets = client.list_assets(limit=10, offset=0)

    assert len(assets) == 1
    assert assets[0].id == "a2"
    assert assets[0].hostname == "srv-v4"
    assert assets[0].ip == "10.0.0.2"


def test_list_assets_supports_v4_assets_fallback():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/perms/users/assets/":
            return httpx.Response(status_code=404, json={"detail": "not found"})
        if request.url.path == "/api/v1/perms/users/my/assets/":
            return httpx.Response(status_code=404, json={"detail": "not found"})
        if request.url.path == "/api/v1/assets/assets/":
            return httpx.Response(
                status_code=200,
                json={"count": 1, "results": [{"id": "a3", "name": "srv-fallback", "address": "10.0.0.3"}]},
            )
        raise AssertionError(f"unexpected path: {request.url.path}")

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport, base_url="http://test") as mock_client:
        client = JumpServerClient(base_url="http://test", client=mock_client)
        assets = client.list_assets(limit=10, offset=0)

    assert len(assets) == 1
    assert assets[0].id == "a3"
    assert assets[0].hostname == "srv-fallback"
    assert assets[0].ip == "10.0.0.3"


def test_list_assets_fallbacks_to_admin_assets_when_my_assets_empty():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/perms/users/assets/":
            return httpx.Response(status_code=404, json={"detail": "not found"})
        if request.url.path == "/api/v1/perms/users/my/assets/":
            return httpx.Response(status_code=200, json={"count": 0, "results": []})
        if request.url.path == "/api/v1/assets/assets/":
            return httpx.Response(
                status_code=200,
                json={"count": 1, "results": [{"id": "a4", "name": "srv-admin", "address": "10.0.0.4"}]},
            )
        raise AssertionError(f"unexpected path: {request.url.path}")

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport, base_url="http://test") as mock_client:
        client = JumpServerClient(base_url="http://test", client=mock_client)
        assets = client.list_assets(limit=10, offset=0)

    assert len(assets) == 1
    assert assets[0].id == "a4"
    assert assets[0].hostname == "srv-admin"
    assert assets[0].ip == "10.0.0.4"


def test_list_asset_system_users_supports_v4_accounts():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/perms/users/assets/":
            return httpx.Response(status_code=404, json={"detail": "not found"})
        if request.url.path == "/api/v1/perms/users/my/assets/":
            return httpx.Response(status_code=200, json={"count": 0, "results": []})
        if request.url.path == "/api/v1/accounts/accounts/":
            assert request.url.params.get("asset_id") == "asset-v4-1"
            assert request.url.params.get("limit") == "200"
            assert request.url.params.get("offset") == "0"
            return httpx.Response(
                status_code=200,
                json={
                    "count": 1,
                    "results": [{"id": "acct-1", "name": "root-dev", "username": "root"}],
                },
            )
        raise AssertionError(f"unexpected path: {request.url.path}")

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport, base_url="http://test") as mock_client:
        client = JumpServerClient(base_url="http://test", client=mock_client)
        users = client.list_asset_system_users("asset-v4-1")

    assert len(users) == 1
    assert users[0].id == "acct-1"
    assert users[0].name == "root-dev"
    assert users[0].username == "root"


def test_create_command_execution_uses_expected_payload():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/perms/users/assets/":
            return httpx.Response(status_code=200, json={"count": 0, "results": []})
        assert request.method == "POST"
        assert request.url.path == "/api/v1/ops/command-executions/"
        payload = request.read().decode("utf-8")
        assert '"command":"hostname"' in payload
        assert '"run_as":"su-1"' in payload
        assert '"hosts":["a-1"]' in payload
        assert "asset_id" not in payload
        return httpx.Response(status_code=200, json={"id": "e1", "is_finished": False})

    transport = httpx.MockTransport(handler)
    req = CommandExecutionRequest(command="hostname", run_as="su-1", hosts=["a-1"])
    with httpx.Client(transport=transport, base_url="http://test") as mock_client:
        client = JumpServerClient(base_url="http://test", client=mock_client)
        execution = client.create_command_execution(req)

    assert execution.id == "e1"
    assert execution.is_finished is False


def test_list_command_executions_for_pending_diagnosis():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/perms/users/assets/":
            return httpx.Response(status_code=200, json={"count": 0, "results": []})
        assert request.method == "GET"
        assert request.url.path == "/api/v1/ops/command-executions/"
        assert request.url.params.get("limit") == "5"
        assert request.url.params.get("offset") == "0"
        return httpx.Response(
            status_code=200,
            json={"count": 1, "results": [{"id": "exec-1", "is_finished": False}]},
        )

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport, base_url="http://test") as mock_client:
        client = JumpServerClient(base_url="http://test", client=mock_client)
        payload = client.list_command_executions(limit=5, offset=0)

    assert payload["count"] == 1
    assert payload["results"][0]["id"] == "exec-1"


def test_create_command_execution_supports_v4_jobs():
    run_as_id = "11111111-1111-1111-1111-111111111111"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/perms/users/assets/":
            return httpx.Response(status_code=404, json={"detail": "not found"})
        if request.url.path == "/api/v1/perms/users/my/assets/":
            return httpx.Response(status_code=200, json={"count": 0, "results": []})
        if request.url.path == "/api/v1/accounts/accounts/" and request.method == "GET":
            return httpx.Response(
                status_code=200,
                json={"count": 1, "results": [{"id": run_as_id, "name": "root-dev", "username": "root"}]},
            )
        if request.url.path == "/api/v1/ops/jobs/" and request.method == "POST":
            payload = request.read().decode("utf-8")
            assert '"instant":true' in payload
            assert '"is_periodic":false' in payload
            assert '"type":"adhoc"' in payload
            assert '"module":"shell"' in payload
            assert '"args":"hostname"' in payload
            assert '"runas":"root"' in payload
            return httpx.Response(status_code=201, json={"task_id": "exec-v4-1"})
        raise AssertionError(f"unexpected request: {request.method} {request.url.path}")

    transport = httpx.MockTransport(handler)
    req = CommandExecutionRequest(command="hostname", run_as=run_as_id, hosts=["asset-v4-1"])
    with httpx.Client(transport=transport, base_url="http://test") as mock_client:
        client = JumpServerClient(base_url="http://test", client=mock_client)
        execution = client.create_command_execution(req)

    assert execution.id == "exec-v4-1"
    assert execution.is_finished is False
    assert execution.log_url == "/api/v1/ops/ansible/job-execution/exec-v4-1/log/"


def test_get_command_execution_supports_v4_task_detail():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/perms/users/assets/":
            return httpx.Response(status_code=404, json={"detail": "not found"})
        if request.url.path == "/api/v1/perms/users/my/assets/":
            return httpx.Response(status_code=200, json={"count": 0, "results": []})
        if request.url.path == "/api/v1/ops/job-execution/task-detail/exec-v4-2/":
            return httpx.Response(
                status_code=200,
                json={
                    "status": {"value": "failed", "label": "failed"},
                    "is_finished": True,
                    "is_success": False,
                    "summary": {"error": "no permission"},
                },
            )
        raise AssertionError(f"unexpected request: {request.method} {request.url.path}")

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport, base_url="http://test") as mock_client:
        client = JumpServerClient(base_url="http://test", client=mock_client)
        execution = client.get_command_execution("exec-v4-2")

    assert execution.id == "exec-v4-2"
    assert execution.is_finished is True
    assert execution.result["summary"]["error"] == "no permission"


def test_list_command_executions_supports_v4_job_executions():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/perms/users/assets/":
            return httpx.Response(status_code=404, json={"detail": "not found"})
        if request.url.path == "/api/v1/perms/users/my/assets/":
            return httpx.Response(status_code=200, json={"count": 0, "results": []})
        if request.url.path == "/api/v1/ops/job-executions/":
            return httpx.Response(
                status_code=200,
                json={
                    "count": 1,
                    "results": [
                        {
                            "id": "exec-v4-3",
                            "is_finished": True,
                            "summary": {"error": "network"},
                        }
                    ],
                },
            )
        raise AssertionError(f"unexpected request: {request.method} {request.url.path}")

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport, base_url="http://test") as mock_client:
        client = JumpServerClient(base_url="http://test", client=mock_client)
        payload = client.list_command_executions(limit=5, offset=0)

    assert payload["count"] == 1
    assert payload["results"][0]["id"] == "exec-v4-3"
    assert payload["results"][0]["is_finished"] is True
    assert payload["results"][0]["result"]["error"] == "network"


def test_get_health():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/api/v1/health/"
        return httpx.Response(status_code=200, json={"status": True, "db_status": True})

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport, base_url="http://test") as mock_client:
        client = JumpServerClient(base_url="http://test", client=mock_client)
        payload = client.get_health()

    assert payload["status"] is True


def test_get_public_settings():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/api/v1/settings/public/"
        return httpx.Response(
            status_code=200,
            json={"SECURITY_COMMAND_EXECUTION": True, "SECURITY_COMMAND_BLACKLIST": ["shutdown"]},
        )

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport, base_url="http://test") as mock_client:
        client = JumpServerClient(base_url="http://test", client=mock_client)
        payload = client.get_public_settings()

    assert payload["SECURITY_COMMAND_EXECUTION"] is True
    assert payload["SECURITY_COMMAND_BLACKLIST"] == ["shutdown"]


def test_list_assets_updated_since_page_uses_configured_param(monkeypatch):
    monkeypatch.setattr(settings, "jumpserver_incremental_updated_at_param", "date_updated__gte")
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        assert request.url.path == "/api/v1/perms/users/assets/"
        if calls["count"] == 1:
            assert request.url.params.get("limit") == "1"
            assert request.url.params.get("offset") == "0"
            return httpx.Response(status_code=200, json={"count": 0, "results": []})
        assert request.url.params.get("date_updated__gte") == "2026-04-02T00:00:00+00:00"
        return httpx.Response(
            status_code=200,
            json={"count": 1, "results": [{"id": "a-ts-1", "hostname": "srv-ts", "updated_at": "2026-04-02T01:00:00+00:00"}]},
        )

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport, base_url="http://test") as mock_client:
        client = JumpServerClient(base_url="http://test", client=mock_client)
        assets, total = client.list_assets_updated_since_page(
            updated_since="2026-04-02T00:00:00+00:00",
            limit=10,
            offset=0,
        )

    assert total == 1
    assert len(assets) == 1
    assert assets[0].updated_at == "2026-04-02T01:00:00+00:00"


def test_list_assets_updated_since_page_fallbacks_on_400(monkeypatch):
    monkeypatch.setattr(settings, "jumpserver_incremental_updated_at_param", "unsupported_param")
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        assert request.url.path == "/api/v1/perms/users/assets/"
        if calls["count"] == 1:
            assert request.url.params.get("limit") == "1"
            assert request.url.params.get("offset") == "0"
            return httpx.Response(status_code=200, json={"count": 0, "results": []})
        if request.url.params.get("unsupported_param"):
            return httpx.Response(status_code=400, json={"detail": "invalid filter"})
        if request.url.params.get("updated_at__gte"):
            return httpx.Response(
                status_code=200,
                json={"count": 1, "results": [{"id": "a-ts-2", "hostname": "srv-ts-2"}]},
            )
        raise AssertionError(f"unexpected params: {request.url.params}")

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport, base_url="http://test") as mock_client:
        client = JumpServerClient(base_url="http://test", client=mock_client)
        assets, total = client.list_assets_updated_since_page(
            updated_since="2026-04-02T00:00:00+00:00",
            limit=10,
            offset=0,
        )

    assert total == 1
    assert len(assets) == 1
    assert assets[0].id == "a-ts-2"


def test_get_command_execution_v4_falls_back_to_job_executions_when_task_detail_404():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/perms/users/assets/":
            return httpx.Response(status_code=404, json={"detail": "not found"})
        if request.url.path == "/api/v1/perms/users/my/assets/":
            return httpx.Response(status_code=200, json={"count": 0, "results": []})
        if request.url.path == "/api/v1/ops/job-execution/task-detail/exec-v4-fallback/":
            return httpx.Response(status_code=404, json={"detail": "not found"})
        if request.url.path == "/api/v1/ops/job-executions/exec-v4-fallback/":
            return httpx.Response(
                status_code=200,
                json={"id": "exec-v4-fallback", "is_finished": True, "summary": {"ok": True}},
            )
        raise AssertionError(f"unexpected request: {request.method} {request.url.path}")

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport, base_url="http://test") as mock_client:
        client = JumpServerClient(base_url="http://test", client=mock_client)
        execution = client.get_command_execution("exec-v4-fallback")

    assert execution.id == "exec-v4-fallback"
    assert execution.is_finished is True
    assert execution.result["summary"]["ok"] is True


def test_list_asset_system_users_v4_supports_pagination():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/perms/users/assets/":
            return httpx.Response(status_code=404, json={"detail": "not found"})
        if request.url.path == "/api/v1/perms/users/my/assets/":
            return httpx.Response(status_code=200, json={"count": 0, "results": []})
        if request.url.path == "/api/v1/accounts/accounts/":
            calls["count"] += 1
            if calls["count"] == 1:
                assert request.url.params.get("offset") == "0"
                return httpx.Response(
                    status_code=200,
                    json={
                        "count": 201,
                        "results": [{"id": f"acct-{i}", "username": f"user-{i}"} for i in range(200)],
                    },
                )
            assert request.url.params.get("offset") == "200"
            return httpx.Response(
                status_code=200,
                json={
                    "count": 201,
                    "results": [{"id": "acct-200", "username": "user-200"}],
                },
            )
        raise AssertionError(f"unexpected request: {request.method} {request.url.path}")

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport, base_url="http://test") as mock_client:
        client = JumpServerClient(base_url="http://test", client=mock_client)
        users = client.list_asset_system_users("asset-v4-paging")

    assert len(users) == 201
    assert users[0].id == "acct-0"
    assert users[-1].id == "acct-200"


def test_create_command_execution_v4_accepts_id_when_task_id_absent():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/perms/users/assets/":
            return httpx.Response(status_code=404, json={"detail": "not found"})
        if request.url.path == "/api/v1/perms/users/my/assets/":
            return httpx.Response(status_code=200, json={"count": 0, "results": []})
        if request.url.path == "/api/v1/ops/jobs/" and request.method == "POST":
            return httpx.Response(status_code=201, json={"id": "job-v4-id-1"})
        raise AssertionError(f"unexpected request: {request.method} {request.url.path}")

    transport = httpx.MockTransport(handler)
    req = CommandExecutionRequest(command="hostname", run_as="root", hosts=["asset-v4-1"])
    with httpx.Client(transport=transport, base_url="http://test") as mock_client:
        client = JumpServerClient(base_url="http://test", client=mock_client)
        execution = client.create_command_execution(req)

    assert execution.id == "job-v4-id-1"
    assert execution.is_finished is False


def test_list_assets_normalizes_updated_at_from_date_updated():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/perms/users/assets/":
            return httpx.Response(status_code=404, json={"detail": "not found"})
        if request.url.path == "/api/v1/perms/users/my/assets/":
            return httpx.Response(
                status_code=200,
                json={
                    "count": 1,
                    "results": [
                        {
                            "id": "asset-updated-1",
                            "name": "srv-updated",
                            "address": "10.0.0.8",
                            "date_updated": "2026-04-03T08:00:00+00:00",
                        }
                    ],
                },
            )
        raise AssertionError(f"unexpected request: {request.method} {request.url.path}")

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport, base_url="http://test") as mock_client:
        client = JumpServerClient(base_url="http://test", client=mock_client)
        assets = client.list_assets(limit=10, offset=0)

    assert len(assets) == 1
    assert assets[0].updated_at == "2026-04-03T08:00:00+00:00"


def test_list_assets_updated_since_page_raises_when_all_params_unsupported(monkeypatch):
    monkeypatch.setattr(settings, "jumpserver_incremental_updated_at_param", "unsupported_param")
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        assert request.url.path == "/api/v1/perms/users/assets/"
        if calls["count"] == 1:
            return httpx.Response(status_code=200, json={"count": 0, "results": []})
        return httpx.Response(status_code=400, json={"detail": "unsupported filter"})

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport, base_url="http://test") as mock_client:
        client = JumpServerClient(base_url="http://test", client=mock_client)
        with pytest.raises(JumpServerClientError) as exc:
            client.list_assets_updated_since_page(
                updated_since="2026-04-03T00:00:00+00:00",
                limit=10,
                offset=0,
            )
    assert "unsupported" in str(exc.value).lower()
    assert "tried params" in str(exc.value).lower()
