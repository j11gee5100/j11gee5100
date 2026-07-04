from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import main as api_main
from app.api.routes import auth as auth_routes
from app.api.routes import environment_packages as environment_package_routes
from app.api.routes import mcp as mcp_routes
from app.api.routes import users as user_routes
from app.core.config import settings
from app.db.base import Base
from app.services import environment_package_service
from app.mcp import service as mcp_service


@pytest.fixture
def client(monkeypatch, tmp_path):
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    @contextmanager
    def scope():
        session = SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    monkeypatch.setattr(api_main, "init_db", lambda: None)
    monkeypatch.setattr(environment_package_service, "_SEED_READY", False)
    monkeypatch.setattr(api_main, "session_scope", scope)
    monkeypatch.setattr(auth_routes, "session_scope", scope)
    monkeypatch.setattr(environment_package_routes, "session_scope", scope)
    monkeypatch.setattr(user_routes, "session_scope", scope)
    monkeypatch.setattr(mcp_routes, "session_scope", scope, raising=False)
    monkeypatch.setattr(mcp_service, "session_scope", scope)
    monkeypatch.setattr(settings, "mcp_allowed_package_roots", str(tmp_path / "packages"))
    monkeypatch.setattr(settings, "mcp_toolsets", "profiles,packages_read,bundles_read,audit,packages_write,probe,bundles_write")
    monkeypatch.setattr(settings, "mcp_read_only", False)
    (tmp_path / "packages").mkdir()
    monkeypatch.chdir(tmp_path)
    with TestClient(api_main.app) as c:
        yield c


def auth_headers(client: TestClient, username: str = "zhangsan", password: str = "user123") -> dict:
    login = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def rpc(client: TestClient, method: str, params: dict | None = None, *, headers: dict | None = None, request_id: int = 1):
    return client.post("/mcp", json={"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}}, headers=headers or auth_headers(client))


def call_tool(client: TestClient, name: str, arguments: dict | None = None, *, headers: dict | None = None):
    response = rpc(client, "tools/call", {"name": name, "arguments": arguments or {}}, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert "result" in body
    return body["result"]["structuredContent"]



def test_mcp_client_manifest_and_download_are_public(client: TestClient):
    manifest_response = client.get("/mcp/client/manifest")
    assert manifest_response.status_code == 200
    manifest = manifest_response.json()
    assert manifest["name"] == "opspaw-inference-env-mcp-stdio"
    assert manifest["sha256"]
    assert manifest["download_url"].endswith("/mcp/client/inference_env_mcp_stdio.py")
    assert manifest["launcher_url"].endswith("/mcp/client/inference_env_mcp_launcher.py")
    assert manifest["auto_update"] is True

    client_script = client.get("/mcp/client/inference_env_mcp_stdio.py")
    assert client_script.status_code == 200
    assert "def main()" in client_script.text
    assert "upload_env_package_file" in client_script.text

    launcher_script = client.get("/mcp/client/inference_env_mcp_launcher.py")
    assert launcher_script.status_code == 200
    assert "auto-update" in launcher_script.text or "auto update" in launcher_script.text
    assert "/mcp/client/manifest" in launcher_script.text

def test_mcp_requires_login_token(client: TestClient):
    response = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_REQUIRED"




def test_mcp_rejects_legacy_forged_token(client: TestClient):
    import base64

    forged = base64.urlsafe_b64encode(b"opspaw-dev-token:fake-user-id:zhangsan:user").decode("ascii")
    response = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        headers={"Authorization": f"Bearer {forged}"},
    )
    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_TOKEN"


def test_mcp_revalidates_user_enabled_for_each_request(client: TestClient):
    headers = auth_headers(client, "zhangsan", "user123")
    ok = rpc(client, "tools/list", headers=headers)
    assert ok.status_code == 200

    admin = auth_headers(client, "admin", "admin123")
    users = client.get("/api/v1/users", headers=admin).json()["items"]
    zhangsan = next(item for item in users if item["username"] == "zhangsan")
    disabled = client.patch(f"/api/v1/users/{zhangsan['user_id']}", json={"enabled": False}, headers=admin)
    assert disabled.status_code == 200

    rejected = rpc(client, "tools/list", headers=headers)
    assert rejected.status_code == 401
    assert rejected.json()["code"] == "USER_DISABLED"


def test_mcp_initialize_and_tool_listing(client: TestClient):
    init = rpc(client, "initialize")
    assert init.status_code == 200
    assert init.json()["result"]["serverInfo"]["name"] == "inference-env-delivery-mcp"

    tools = rpc(client, "tools/list")
    names = {tool["name"] for tool in tools.json()["result"]["tools"]}
    assert "list_device_profiles" in names
    assert "register_env_package" in names
    assert "update_delivery_bundle_composition" in names
    assert "build_delivery_bundle_artifact" in names


def test_mcp_resources_and_filtered_packages(client: TestClient):
    profiles_result = call_tool(client, "list_device_profiles", {"enabled": True})
    profile = profiles_result["data"]["items"][0]

    packages_result = call_tool(client, "list_env_packages", {"profile_id": profile["profile_id"], "package_type": "driver"})
    assert packages_result["ok"] is True
    assert all(item["package_type"] == "driver" for item in packages_result["data"]["items"])

    resource = rpc(client, "resources/read", {"uri": "opspaw://inference-env/device-profiles"})
    assert resource.status_code == 200
    assert "contents" in resource.json()["result"]


def test_mcp_register_package_rejects_paths_outside_allowed_roots(client: TestClient, tmp_path: Path):
    profile = call_tool(client, "list_device_profiles", {"enabled": True})["data"]["items"][0]
    denied = call_tool(client, "register_env_package", {
        "package_code": "bad-path",
        "name": "Bad Path",
        "package_type": "custom",
        "version": "1.0",
        "storage_type": "filesystem_path",
        "file_uri": "filesystem:///etc/passwd",
        "device_profile_ids": [profile["profile_id"]],
    })
    assert denied["ok"] is False
    assert denied["error"]["code"] == "FILE_OUTSIDE_ALLOWED_ROOTS"

    allowed_file = tmp_path / "packages" / "libyuv.tar"
    allowed_file.write_text("demo")
    created = call_tool(client, "register_env_package", {
        "package_code": "libyuv-mcp",
        "name": "libyuv MCP",
        "package_type": "system_dependency",
        "version": "1.0",
        "storage_type": "filesystem_path",
        "file_uri": f"filesystem://{allowed_file}",
        "checksum": "sha256-demo",
        "check_script": "command -v cmake",
        "install_script": "make install",
        "verify_script": "test -f /usr/local/include/libyuv.h",
        "device_profile_ids": [profile["profile_id"]],
    })
    assert created["ok"] is True
    assert created["data"]["item"]["package_code"] == "libyuv-mcp"


def test_mcp_create_update_bundle_and_audit(client: TestClient):
    profile = call_tool(client, "list_device_profiles", {"enabled": True})["data"]["items"][0]
    asset_file = Path.cwd() / "packages" / "mcp-bundle-runtime.tar.gz"
    asset_file.write_text("demo runtime")
    registered = call_tool(client, "register_env_package", {
        "package_code": "mcp-bundle-runtime",
        "name": "MCP Bundle Runtime",
        "package_type": "runtime",
        "version": "1.0.0",
        "storage_type": "filesystem_path",
        "file_uri": f"filesystem://{asset_file}",
        "file_name": asset_file.name,
        "checksum": "sha256-demo",
        "install_script": "echo install",
        "verify_script": "echo verify",
        "device_profile_ids": [profile["profile_id"]],
    })
    assert registered["ok"] is True
    packages = call_tool(client, "list_env_packages", {"profile_id": profile["profile_id"]})["data"]["items"]
    package_ids = [item["package_id"] for item in packages if item["package_code"] == "mcp-bundle-runtime"]
    assert package_ids

    preview = call_tool(client, "preview_delivery_manifest", {"target_profile_id": profile["profile_id"], "package_ids": package_ids})
    assert preview["ok"] is True
    assert preview["data"]["manifest"]["steps"]

    created = call_tool(client, "create_delivery_bundle_draft", {
        "bundle_code": "mcp-bundle-demo",
        "name": "MCP Bundle Demo",
        "version": "1.0.0",
        "target_profile_id": profile["profile_id"],
        "package_ids": package_ids,
    })
    assert created["ok"] is True
    bundle_id = created["data"]["item"]["bundle_id"]

    updated = call_tool(client, "update_delivery_bundle_composition", {"bundle_id": bundle_id, "name": "MCP Bundle Updated", "package_ids": package_ids})
    assert updated["ok"] is True
    assert updated["data"]["item"]["name"] == "MCP Bundle Updated"

    audit = call_tool(client, "audit_delivery_bundle", {"bundle_id": bundle_id})
    assert audit["ok"] is True
    assert audit["data"]["status"] in {"ok", "warning", "error"}



def test_mcp_readme_documents_application_package_type(client: TestClient):
    resource = rpc(client, "resources/read", {"uri": "opspaw://inference-env/readme"})
    assert resource.status_code == 200
    text = resource.json()["result"]["contents"][0]["text"]
    assert "application_package" in text
    assert "应用包 Agent 提示词模板" in text
    assert "尽量保持原始目录、文件名和资源形态" in text
    assert "如果原脚本存在交互输入，保留交互" in text
    assert "应用包只随交付包放入 `application_packages/` 目录" in text
    assert "不会被交付包根 install.sh / run_bundle.py 自动执行" in text
    assert "不要为应用包编写 _payload_extract 外层包装脚本" in text
    assert "`.bashrc` 环境变量写入约定" in text
    assert "# >>> OpsPaw MBAB runtime env >>>" in text
    assert "先删除旧标记块，再写入新标记块" in text
    assert "echo 'export PATH=...' >> /root/.bashrc" in text
    assert "通用 MBAB 包不要内置项目环境变量" in text
    assert "登记脚本外层必须解压到 _payload_extract/<package_code>/" not in text
    assert "将安装入口统一为归档根目录 install.sh" not in text


def test_stdio_client_readme_documents_application_package_resource_only():
    from scripts import inference_env_mcp_stdio

    text = inference_env_mcp_stdio.ENV_PACKAGE_README
    assert "应用包只随交付包放入 `application_packages/` 目录" in text
    assert "不会被交付包根 install.sh / run_bundle.py 自动执行" in text
    assert "不要为应用包编写 _payload_extract 外层包装脚本" in text
    assert "`.bashrc` 环境变量写入约定" in text
    assert "# >>> OpsPaw MBAB runtime env >>>" in text
    assert "先删除旧标记块，再写入新标记块" in text
    assert "echo 'export PATH=...' >> /root/.bashrc" in text
    assert "通用 MBAB 包不要内置项目环境变量" in text
    assert "登记脚本外层必须解压到 _payload_extract/<package_code>/" not in text
    assert "将安装入口统一为归档根目录 install.sh" not in text


def test_mcp_client_download_uses_app_local_stdio_client():
    from app.api.routes import mcp

    path = mcp._client_script_path()
    assert path.as_posix().endswith("app/mcp/inference_env_mcp_stdio.py")
    text = path.read_text(encoding="utf-8")
    assert "不要为应用包编写 _payload_extract 外层包装脚本" in text
    assert "登记脚本外层必须解压到 _payload_extract/<package_code>/" not in text


def test_mcp_accepts_application_package_type(client: TestClient, tmp_path: Path):
    profile = call_tool(client, "list_device_profiles", {"enabled": True})["data"]["items"][0]
    allowed_file = tmp_path / "packages" / "demo-application-package.tar.gz"
    allowed_file.write_text("demo application package")

    created = call_tool(client, "register_env_package", {
        "package_code": "demo-application-package",
        "name": "演示应用包",
        "package_type": "application_package",
        "version": "1.0.0",
        "storage_type": "filesystem_path",
        "file_uri": f"filesystem://{allowed_file}",
        "file_name": allowed_file.name,
        "checksum": "sha256-demo",
        "install_script": "exec bash \"${ASSET_DIR}/install.sh\"",
        "verify_script": "exec bash \"${ASSET_DIR}/verify.sh\"",
        "device_profile_ids": [profile["profile_id"]],
    })
    assert created["ok"] is True
    assert created["data"]["item"]["package_type"] == "application_package"

    listed = call_tool(client, "list_env_packages", {"profile_id": profile["profile_id"], "package_type": "application_package"})
    assert listed["ok"] is True
    assert any(item["package_code"] == "demo-application-package" for item in listed["data"]["items"])

def test_mcp_read_only_mode_hides_write_tools(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "mcp_read_only", True)
    tools = rpc(client, "tools/list")
    names = {tool["name"] for tool in tools.json()["result"]["tools"]}
    assert "list_env_packages" in names
    assert "register_env_package" not in names
    assert "create_delivery_bundle_draft" not in names


def test_mcp_delivery_bundle_lifecycle_tools_match_backend(client: TestClient, tmp_path: Path, monkeypatch):
    artifact_root = tmp_path / "artifact-root"
    monkeypatch.setattr(settings, "delivery_bundle_artifact_root", str(artifact_root))
    headers = auth_headers(client, "zhangsan", "user123")
    tools = rpc(client, "tools/list", headers=headers).json()["result"]["tools"]
    names = {tool["name"] for tool in tools}
    assert {"build_delivery_bundle_artifact", "get_delivery_bundle_build_job", "deliver_delivery_bundle", "delete_delivery_bundle", "create_delivery_bundle_version"}.issubset(names)

    profile_id = call_tool(client, "list_device_profiles", {}, headers=headers)["data"]["items"][0]["profile_id"]
    package_file = tmp_path / "packages" / "mcp-runtime.tar.gz"
    package_file.write_text("runtime bytes", encoding="utf-8")
    package = call_tool(client, "register_env_package", {
        "package_code": "mcp-runtime-lifecycle",
        "name": "MCP Runtime Lifecycle",
        "package_type": "runtime",
        "version": "1.0",
        "file_uri": f"filesystem://{package_file}",
        "file_name": "mcp-runtime.tar.gz",
        "checksum": "sha256-demo",
        "check_script": "echo check",
        "install_script": "echo install",
        "verify_script": "echo verify",
        "device_profile_ids": [profile_id],
        "storage_type": "filesystem_path",
    }, headers=headers)
    assert package["ok"] is True
    package_id = package["data"]["item"]["package_id"]

    bundle = call_tool(client, "create_delivery_bundle_draft", {
        "bundle_code": "mcp-lifecycle-bundle",
        "name": "MCP Lifecycle Bundle",
        "version": "1.0.0",
        "bundle_type": "overwrite",
        "target_profile_id": profile_id,
        "package_ids": [package_id],
    }, headers=headers)
    assert bundle["ok"] is True
    bundle_id = bundle["data"]["item"]["bundle_id"]

    built = call_tool(client, "build_delivery_bundle_artifact", {"bundle_id": bundle_id}, headers=headers)
    assert built["ok"] is True
    assert built["data"]["job"]["job_status"] == "success"
    assert built["data"]["item"]["build_status"] == "success"

    latest = call_tool(client, "get_delivery_bundle_build_job", {"bundle_id": bundle_id}, headers=headers)
    assert latest["data"]["item"]["job_status"] == "success"

    delivered = call_tool(client, "deliver_delivery_bundle", {"bundle_id": bundle_id}, headers=headers)
    assert delivered["ok"] is True
    assert delivered["data"]["item"]["lifecycle_status"] == "delivered"

    deleted = call_tool(client, "delete_delivery_bundle", {"bundle_id": bundle_id}, headers=headers)
    assert deleted["ok"] is False
    assert deleted["error"]["code"] == "DELIVERED_BUNDLE_LOCKED"

    v2 = call_tool(client, "create_delivery_bundle_version", {"bundle_id": bundle_id, "bundle_code": "mcp-lifecycle-bundle-v2", "version": "2.0.0"}, headers=headers)
    assert v2["ok"] is True
    assert v2["data"]["item"]["parent_bundle_id"] == bundle_id
    assert v2["data"]["item"]["lifecycle_status"] == "making"


def test_mcp_audit_reports_missing_payload_file(client: TestClient, tmp_path: Path, monkeypatch):
    artifact_root = tmp_path / "artifact-root"
    monkeypatch.setattr(settings, "delivery_bundle_artifact_root", str(artifact_root))
    headers = auth_headers(client, "zhangsan", "user123")
    profile_id = call_tool(client, "list_device_profiles", {}, headers=headers)["data"]["items"][0]["profile_id"]
    missing_file = tmp_path / "packages" / "missing-mcp-runtime.tar.gz"
    missing_file.parent.mkdir(parents=True, exist_ok=True)
    missing_file.write_text("runtime bytes", encoding="utf-8")

    package = call_tool(client, "register_env_package", {
        "package_code": "mcp-missing-runtime-file",
        "name": "MCP Missing Runtime File",
        "package_type": "runtime",
        "version": "1.0",
        "file_uri": f"filesystem://{missing_file}",
        "file_name": "missing-mcp-runtime.tar.gz",
        "checksum": "sha256-demo",
        "install_script": "echo install",
        "verify_script": "echo verify",
        "device_profile_ids": [profile_id],
        "storage_type": "filesystem_path",
    }, headers=headers)
    assert package["ok"] is True
    missing_file.unlink()

    bundle = call_tool(client, "create_delivery_bundle_draft", {
        "bundle_code": "mcp-missing-payload-bundle",
        "name": "MCP Missing Payload Bundle",
        "version": "1.0.0",
        "target_profile_id": profile_id,
        "package_ids": [package["data"]["item"]["package_id"]],
    }, headers=headers)
    assert bundle["ok"] is True

    audit = call_tool(client, "audit_delivery_bundle", {"bundle_id": bundle["data"]["item"]["bundle_id"]}, headers=headers)
    assert audit["ok"] is True, audit
    assert audit["data"]["status"] == "error"
    assert any(finding["code"] == "PAYLOAD_FILE_MISSING" for finding in audit["data"]["findings"])


def test_mcp_audit_rejects_recursive_wrapper_scripts(client: TestClient, tmp_path: Path, monkeypatch):
    artifact_root = tmp_path / "artifact-root"
    monkeypatch.setattr(settings, "delivery_bundle_artifact_root", str(artifact_root))
    headers = auth_headers(client, "zhangsan", "user123")
    profile_id = call_tool(client, "list_device_profiles", {}, headers=headers)["data"]["items"][0]["profile_id"]
    package_file = tmp_path / "packages" / "bad-wrapper.tar.gz"
    package_file.parent.mkdir(parents=True, exist_ok=True)
    package_file.write_text("runtime bytes", encoding="utf-8")

    package = call_tool(client, "register_env_package", {
        "package_code": "bad-recursive-wrapper",
        "name": "Bad Recursive Wrapper",
        "package_type": "runtime",
        "version": "1.0",
        "file_uri": f"filesystem://{package_file}",
        "file_name": "bad-wrapper.tar.gz",
        "checksum": "sha256-demo",
        "install_script": "bash install.sh",
        "verify_script": "bash ./verify.sh",
        "device_profile_ids": [profile_id],
        "storage_type": "filesystem_path",
    }, headers=headers)
    assert package["ok"] is True

    bundle = call_tool(client, "create_delivery_bundle_draft", {
        "bundle_code": "bad-recursive-wrapper-bundle",
        "name": "Bad Recursive Wrapper Bundle",
        "version": "1.0.0",
        "target_profile_id": profile_id,
        "package_ids": [package["data"]["item"]["package_id"]],
    }, headers=headers)
    assert bundle["ok"] is True

    audit = call_tool(client, "audit_delivery_bundle", {"bundle_id": bundle["data"]["item"]["bundle_id"]}, headers=headers)
    assert audit["ok"] is True
    assert audit["data"]["status"] == "error"
    findings = audit["data"]["findings"]
    assert any(finding["code"] == "RECURSIVE_WRAPPER_SCRIPT" and finding.get("script") == "install_script" for finding in findings)
    assert any(finding["code"] == "RECURSIVE_WRAPPER_SCRIPT" and finding.get("script") == "verify_script" for finding in findings)


def test_mcp_audit_accepts_payload_subdir_wrapper_scripts(client: TestClient, tmp_path: Path, monkeypatch):
    artifact_root = tmp_path / "artifact-root"
    monkeypatch.setattr(settings, "delivery_bundle_artifact_root", str(artifact_root))
    headers = auth_headers(client, "zhangsan", "user123")
    profile_id = call_tool(client, "list_device_profiles", {}, headers=headers)["data"]["items"][0]["profile_id"]
    package_file = tmp_path / "packages" / "good-wrapper.tar.gz"
    package_file.parent.mkdir(parents=True, exist_ok=True)
    package_file.write_text("runtime bytes", encoding="utf-8")

    install_script = '''#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXTRACT_ROOT="${SCRIPT_DIR}/_payload_extract"
ASSET_DIR="${EXTRACT_ROOT}/good-wrapper"
rm -rf "${EXTRACT_ROOT}"
mkdir -p "${ASSET_DIR}"
tar -xzf "${SCRIPT_DIR}/good-wrapper.tar.gz" -C "${ASSET_DIR}"
exec bash "${ASSET_DIR}/install.sh"
'''
    verify_script = '''#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ASSET_DIR="${SCRIPT_DIR}/_payload_extract/good-wrapper"
exec bash "${ASSET_DIR}/verify.sh"
'''
    package = call_tool(client, "register_env_package", {
        "package_code": "good-payload-wrapper",
        "name": "Good Payload Wrapper",
        "package_type": "runtime",
        "version": "1.0",
        "file_uri": f"filesystem://{package_file}",
        "file_name": "good-wrapper.tar.gz",
        "checksum": "sha256-demo",
        "install_script": install_script,
        "verify_script": verify_script,
        "device_profile_ids": [profile_id],
        "storage_type": "filesystem_path",
    }, headers=headers)
    assert package["ok"] is True

    bundle = call_tool(client, "create_delivery_bundle_draft", {
        "bundle_code": "good-payload-wrapper-bundle",
        "name": "Good Payload Wrapper Bundle",
        "version": "1.0.0",
        "target_profile_id": profile_id,
        "package_ids": [package["data"]["item"]["package_id"]],
    }, headers=headers)
    assert bundle["ok"] is True

    audit = call_tool(client, "audit_delivery_bundle", {"bundle_id": bundle["data"]["item"]["bundle_id"]}, headers=headers)
    assert audit["ok"] is True
    assert not any(finding["code"] == "RECURSIVE_WRAPPER_SCRIPT" for finding in audit["data"]["findings"])
