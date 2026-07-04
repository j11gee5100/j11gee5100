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
from app.api.routes import users as user_routes
from app.db.base import Base
from app.services import environment_package_service


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
    monkeypatch.chdir(tmp_path)
    with TestClient(api_main.app) as c:
        yield c


def test_device_profiles_are_select_options_for_package_compatibility(client: TestClient):
    profiles = client.get("/api/v1/environment-packages/device-profiles")
    assert profiles.status_code == 200
    items = profiles.json()["items"]
    assert items
    first = items[0]
    assert "profile_id" in first
    assert "label" in first
    assert first["name"]


def test_login_options_are_available_without_admin_header(client: TestClient):
    response = client.get("/api/v1/users/login-options")

    assert response.status_code == 200
    usernames = {item["username"] for item in response.json()["items"]}
    assert {"admin", "zhangsan", "lisi"}.issubset(usernames)


def test_seed_data_does_not_create_demo_environment_packages(client: TestClient):
    response = client.get("/api/v1/environment-packages/packages", headers={"x-operator-id": "admin", "x-operator-role": "admin"})

    assert response.status_code == 200
    package_codes = {item["package_code"] for item in response.json()["items"]}
    assert "nvidia-driver" not in package_codes
    assert "opencv-python" not in package_codes


def test_login_requires_password_and_token_authorizes_admin_pages(client: TestClient):
    bad = client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"})
    assert bad.status_code == 401

    login = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    assert login.status_code == 200
    body = login.json()
    assert body["user"]["username"] == "admin"
    token = body["access_token"]

    admin_users = client.get("/api/v1/users", headers={"Authorization": f"Bearer {token}"})
    assert admin_users.status_code == 200
    assert any(item["username"] == "admin" for item in admin_users.json()["items"])

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["user"]["role"] == "admin"


def test_normal_login_token_cannot_manage_users(client: TestClient):
    login = client.post("/api/v1/auth/login", json={"username": "zhangsan", "password": "user123"})
    assert login.status_code == 200
    token = login.json()["access_token"]

    denied = client.get("/api/v1/users", headers={"Authorization": f"Bearer {token}"})
    assert denied.status_code == 403


def test_normal_user_only_sees_own_packages_and_can_bind_existing_profiles(client: TestClient):
    profiles = client.get("/api/v1/environment-packages/device-profiles").json()["items"]
    profile_id = profiles[0]["profile_id"]

    create = client.post(
        "/api/v1/environment-packages/packages",
        headers={"x-operator-id": "lisi"},
        json={
            "package_code": "ffmpeg-static",
            "name": "FFmpeg Static",
            "package_type": "system_dependency",
            "version": "6.1",
            "file_uri": "s3://env/ffmpeg/6.1.tar.gz",
            "checksum": "sha256-demo",
            "install_script": "cp ffmpeg /usr/local/bin/ffmpeg",
            "verify_script": "ffmpeg -version",
            "status": "active",
            "device_profile_ids": [profile_id],
        },
    )
    assert create.status_code == 200
    item = create.json()["item"]
    assert item["owner_id"] == "lisi"
    assert item["device_profiles"][0]["profile_id"] == profile_id

    zhangsan_list = client.get("/api/v1/environment-packages/packages", headers={"x-operator-id": "zhangsan"})
    assert zhangsan_list.status_code == 200
    assert all(pkg["owner_id"] == "zhangsan" for pkg in zhangsan_list.json()["items"])

    lisi_list = client.get("/api/v1/environment-packages/packages", headers={"x-operator-id": "lisi"})
    assert lisi_list.status_code == 200
    assert any(pkg["package_code"] == "ffmpeg-static" for pkg in lisi_list.json()["items"])


def test_package_skeleton_fields_can_be_created_and_updated(client: TestClient):
    profiles = client.get("/api/v1/environment-packages/device-profiles").json()["items"]
    profile_id = profiles[0]["profile_id"]

    create = client.post(
        "/api/v1/environment-packages/packages",
        headers={"x-operator-id": "lisi"},
        json={
            "package_code": "python-runtime-310",
            "name": "Python 3.10 Runtime",
            "package_type": "python_runtime",
            "version": "3.10.14",
            "checksum": "sha256-python-demo",
            "check_script": "python3 --version",
            "install_script": "bash install-python.sh",
            "verify_script": "python3 -c 'import sys; print(sys.version)'",
            "uninstall_script": "bash uninstall-python.sh",
            "depends_on": "[]",
            "install_order": 10,
            "status": "active",
            "device_profile_ids": [profile_id],
        },
    )

    assert create.status_code == 200
    item = create.json()["item"]
    assert item["check_script"] == "python3 --version"
    assert item["depends_on"] == "[]"
    assert item["install_order"] == 10
    assert item["quality_status"] == "ok"

    update = client.patch(
        f"/api/v1/environment-packages/packages/{item['package_id']}",
        headers={"x-operator-id": "lisi"},
        json={
            "check_script": "test -x /opt/python/bin/python3",
            "depends_on": '["system-deps"]',
            "install_order": 15,
        },
    )

    assert update.status_code == 200
    updated = update.json()["item"]
    assert updated["check_script"] == "test -x /opt/python/bin/python3"
    assert updated["depends_on"] == '["system-deps"]'
    assert updated["install_order"] == 15



def test_delivery_bundle_type_models_first_install_upgrade_and_overwrite(client: TestClient):
    profile_id = client.get("/api/v1/environment-packages/device-profiles").json()["items"][0]["profile_id"]

    create_pkg = client.post(
        "/api/v1/environment-packages/packages",
        headers={"x-operator-id": "lisi"},
        json={
            "package_code": "atlas-runtime-final",
            "name": "Atlas Runtime Final",
            "package_type": "runtime",
            "version": "1.0",
            "checksum": "sha256-final",
            "check_script": "echo check",
            "install_script": "echo install",
            "verify_script": "echo verify",
            "device_profile_ids": [profile_id],
        },
    )
    assert create_pkg.status_code == 200
    package_id = create_pkg.json()["item"]["package_id"]
    assert "install_stage" not in create_pkg.json()["item"]

    bundle = client.post(
        "/api/v1/environment-packages/delivery-bundles",
        headers={"x-operator-id": "lisi"},
        json={
            "bundle_code": "atlas-a10-overwrite-final",
            "name": "A10 最终覆盖交付包",
            "version": "2026.06",
            "bundle_type": "overwrite",
            "target_profile_id": profile_id,
            "package_ids": [package_id],
        },
    )
    assert bundle.status_code == 200
    item = bundle.json()["item"]
    assert item["bundle_type"] == "overwrite"
    assert item["manifest"]["bundle_type"] == "overwrite"
    assert item["package_ids"] == [package_id]
    assert "install_stage" not in item["manifest"]["steps"][0]

    update = client.patch(
        f"/api/v1/environment-packages/delivery-bundles/{item['bundle_id']}",
        headers={"x-operator-id": "lisi"},
        json={"bundle_type": "upgrade"},
    )
    assert update.status_code == 200
    assert update.json()["item"]["bundle_type"] == "upgrade"
    assert update.json()["item"]["manifest"]["bundle_type"] == "upgrade"

def test_delivery_bundle_draft_saves_manifest_preview(client: TestClient):
    profile_id = client.get("/api/v1/environment-packages/device-profiles").json()["items"][0]["profile_id"]
    device_id = client.get("/api/v1/environment-packages/devices").json()["items"][0]["device_id"]

    package_ids = []
    for code, order in [("system-deps-bundle", 10), ("runtime-bundle", 20)]:
        create = client.post(
            "/api/v1/environment-packages/packages",
            headers={"x-operator-id": "lisi"},
            json={
                "package_code": code,
                "name": code,
                "package_type": "custom",
                "version": "1.0",
                "checksum": f"sha256-{code}",
                "check_script": "echo check",
                "install_script": "echo install",
                "verify_script": "echo verify",
                "install_order": order,
                "device_profile_ids": [profile_id],
            },
        )
        assert create.status_code == 200
        package_ids.append(create.json()["item"]["package_id"])

    bundle = client.post(
        "/api/v1/environment-packages/delivery-bundles",
        headers={"x-operator-id": "lisi"},
        json={
            "bundle_code": "bundle-demo",
            "name": "Bundle Demo",
            "version": "1.0.0",
            "target_device_id": device_id,
            "target_profile_id": profile_id,
            "package_ids": package_ids,
        },
    )

    assert bundle.status_code == 200
    item = bundle.json()["item"]
    assert item["status"] == "draft"
    assert item["package_ids"] == package_ids
    assert [step["package_code"] for step in item["manifest"]["steps"]] == ["system-deps-bundle", "runtime-bundle"]
    assert "check_script" not in item["manifest"]["steps"][0]
    assert item["manifest"]["steps"][0]["install_script"] == "echo install"

    detail = client.get(
        f"/api/v1/environment-packages/delivery-bundles/{item['bundle_id']}",
        headers={"x-operator-id": "lisi"},
    )
    assert detail.status_code == 200
    assert detail.json()["item"]["bundle_code"] == "bundle-demo"

    update = client.patch(
        f"/api/v1/environment-packages/delivery-bundles/{item['bundle_id']}",
        headers={"x-operator-id": "lisi"},
        json={
            "name": "Bundle Demo Edited",
            "version": "1.0.1",
            "package_ids": list(reversed(package_ids)),
        },
    )
    assert update.status_code == 200
    updated = update.json()["item"]
    assert updated["name"] == "Bundle Demo Edited"
    assert updated["version"] == "1.0.1"
    assert updated["package_ids"] == list(reversed(package_ids))
    assert [step["package_code"] for step in updated["manifest"]["steps"]] == ["runtime-bundle", "system-deps-bundle"]




def test_delivery_bundle_build_outputs_downloadable_artifact(client: TestClient, tmp_path: Path, monkeypatch):
    from app.core.config import settings
    import tarfile

    artifact_root = tmp_path / "artifacts-root"
    monkeypatch.setattr(settings, "delivery_bundle_artifact_root", str(artifact_root))
    profile_id = client.get("/api/v1/environment-packages/device-profiles").json()["items"][0]["profile_id"]
    package_file = tmp_path / "ffmpeg-4.3.tar.gz"
    package_file.write_text("demo package content", encoding="utf-8")

    create = client.post(
        "/api/v1/environment-packages/packages",
        headers={"x-operator-id": "lisi"},
        json={
            "package_code": "ffmpeg43-build",
            "name": "FFmpeg 4.3 Build",
            "package_type": "system_dependency",
            "version": "4.3",
            "file_uri": f"filesystem://{package_file}",
            "file_name": "ffmpeg-4.3.tar.gz",
            "checksum": "sha256-demo",
            "check_script": "echo check ffmpeg",
            "install_script": "echo install ffmpeg",
            "verify_script": "echo verify ffmpeg",
            "install_order": 10,
            "device_profile_ids": [profile_id],
        },
    )
    assert create.status_code == 200
    package_id = create.json()["item"]["package_id"]

    bundle = client.post(
        "/api/v1/environment-packages/delivery-bundles",
        headers={"x-operator-id": "lisi"},
        json={
            "bundle_code": "bundle-build-demo",
            "name": "Bundle Build Demo",
            "version": "1.0.0",
            "target_profile_id": profile_id,
            "package_ids": [package_id],
        },
    )
    assert bundle.status_code == 200
    bundle_id = bundle.json()["item"]["bundle_id"]

    built = client.post(f"/api/v1/environment-packages/delivery-bundles/{bundle_id}/build", headers={"x-operator-id": "lisi"})
    assert built.status_code == 200
    assert built.json()["status"] == "queued"

    import time
    item = None
    for _ in range(30):
        detail = client.get(f"/api/v1/environment-packages/delivery-bundles/{bundle_id}", headers={"x-operator-id": "lisi"})
        assert detail.status_code == 200
        item = detail.json()["item"]
        if item["build_status"] == "success":
            break
        time.sleep(0.1)
    assert item is not None
    assert item["status"] == "built"
    assert item["build_status"] == "success"
    assert item["artifact_name"].endswith(".tar.gz")
    assert item["artifact_size"] > 0
    assert item["artifact_checksum"].startswith("sha256:")
    assert "ffmpeg43-build" in item["build_log"]

    artifact_path = Path(item["artifact_uri"].removeprefix("filesystem://"))
    assert artifact_path.exists()
    with tarfile.open(artifact_path, "r:gz") as tar:
        names = tar.getnames()
    assert any(name.endswith("/manifest.json") for name in names)
    assert any(name.endswith("/install.sh") for name in names)
    assert any(name.endswith("/state.template.json") for name in names)
    assert not any(name.endswith("/packages/001-ffmpeg43-build/check.sh") for name in names)
    assert any(name.endswith("/packages/001-ffmpeg43-build/install.sh") for name in names)
    assert any(name.endswith("/packages/001-ffmpeg43-build/verify.sh") for name in names)
    assert any(name.endswith("/packages/001-ffmpeg43-build/ffmpeg-4.3.tar.gz") for name in names)

    download = client.get(f"/api/v1/environment-packages/delivery-bundles/{bundle_id}/artifact", headers={"x-operator-id": "lisi"})
    assert download.status_code == 200
    assert download.headers["content-type"].startswith("application/gzip")
    assert len(download.content) == item["artifact_size"]


def test_delivery_bundle_async_build_lifecycle_delete_and_new_version(client: TestClient, tmp_path: Path, monkeypatch):
    from app.core.config import settings
    import time

    artifact_root = tmp_path / "artifacts-root"
    monkeypatch.setattr(settings, "delivery_bundle_artifact_root", str(artifact_root))
    profile_id = client.get("/api/v1/environment-packages/device-profiles").json()["items"][0]["profile_id"]
    package_file = tmp_path / "runtime.tar.gz"
    package_file.write_text("demo package content", encoding="utf-8")

    package = client.post(
        "/api/v1/environment-packages/packages",
        headers={"x-operator-id": "lisi"},
        json={
            "package_code": "runtime-lifecycle",
            "name": "Runtime Lifecycle",
            "package_type": "runtime",
            "version": "1.0",
            "file_uri": f"filesystem://{package_file}",
            "file_name": "runtime.tar.gz",
            "checksum": "sha256-demo",
            "check_script": "echo check",
            "install_script": "echo install",
            "verify_script": "echo verify",
            "device_profile_ids": [profile_id],
        },
    )
    assert package.status_code == 200
    package_id = package.json()["item"]["package_id"]

    bundle = client.post(
        "/api/v1/environment-packages/delivery-bundles",
        headers={"x-operator-id": "lisi"},
        json={
            "bundle_code": "lifecycle-demo",
            "name": "Lifecycle Demo",
            "version": "1.0.0",
            "bundle_type": "overwrite",
            "target_profile_id": profile_id,
            "package_ids": [package_id],
        },
    )
    assert bundle.status_code == 200
    bundle_item = bundle.json()["item"]
    bundle_id = bundle_item["bundle_id"]
    assert bundle_item["lifecycle_status"] == "making"
    assert bundle_item["build_status"] == "not_built"

    build = client.post(f"/api/v1/environment-packages/delivery-bundles/{bundle_id}/build", headers={"x-operator-id": "lisi"})
    assert build.status_code == 200
    assert build.json()["status"] == "queued"
    assert build.json()["job"]["job_status"] in {"queued", "running"}

    latest = None
    for _ in range(30):
        latest = client.get(f"/api/v1/environment-packages/delivery-bundles/{bundle_id}/build-jobs/latest", headers={"x-operator-id": "lisi"})
        assert latest.status_code == 200
        if latest.json()["item"] and latest.json()["item"]["job_status"] == "success":
            break
        time.sleep(0.1)
    assert latest is not None
    job = latest.json()["item"]
    assert job["job_status"] == "success"
    assert job["progress_percent"] == 100
    assert "交付包制作完成" in job["log_text"]

    detail = client.get(f"/api/v1/environment-packages/delivery-bundles/{bundle_id}", headers={"x-operator-id": "lisi"})
    assert detail.status_code == 200
    assert detail.json()["item"]["build_status"] == "success"
    assert detail.json()["item"]["artifact_name"].endswith(".tar.gz")

    deliver = client.post(f"/api/v1/environment-packages/delivery-bundles/{bundle_id}/deliver", headers={"x-operator-id": "lisi"})
    assert deliver.status_code == 200
    delivered = deliver.json()["item"]
    assert delivered["lifecycle_status"] == "delivered"
    assert delivered["delivered_by"] == "lisi"

    locked_update = client.patch(
        f"/api/v1/environment-packages/delivery-bundles/{bundle_id}",
        headers={"x-operator-id": "lisi"},
        json={"name": "Should Not Change", "package_ids": [package_id]},
    )
    assert locked_update.status_code == 400
    assert locked_update.json()["code"] == "DELIVERED_BUNDLE_LOCKED"

    locked_delete = client.delete(f"/api/v1/environment-packages/delivery-bundles/{bundle_id}", headers={"x-operator-id": "lisi"})
    assert locked_delete.status_code == 400
    assert locked_delete.json()["code"] == "DELIVERED_BUNDLE_LOCKED"

    new_version = client.post(
        f"/api/v1/environment-packages/delivery-bundles/{bundle_id}/new-version",
        headers={"x-operator-id": "lisi"},
        json={"bundle_code": "lifecycle-demo-v2", "version": "2.0.0"},
    )
    assert new_version.status_code == 200
    v2 = new_version.json()["item"]
    assert v2["parent_bundle_id"] == bundle_id
    assert v2["lifecycle_status"] == "making"
    assert v2["build_status"] == "not_built"
    assert v2["artifact_name"] == ""
    assert v2["package_ids"] == [package_id]

    deleted_v2 = client.delete(f"/api/v1/environment-packages/delivery-bundles/{v2['bundle_id']}", headers={"x-operator-id": "lisi"})
    assert deleted_v2.status_code == 200
    missing_v2 = client.get(f"/api/v1/environment-packages/delivery-bundles/{v2['bundle_id']}", headers={"x-operator-id": "lisi"})
    assert missing_v2.status_code == 404

def test_probe_result_import_extracts_core_fields(client: TestClient):
    device_id = client.get("/api/v1/environment-packages/devices").json()["items"][0]["device_id"]
    create = client.post(
        "/api/v1/environment-packages/probe-results",
        headers={"x-operator-id": "lisi"},
        json={
            "result_code": "probe-a10-001",
            "name": "A10 探测结果",
            "device_id": device_id,
            "raw_json": '{"system":{"os_type":"Ubuntu","os_version":"22.04","cpu_arch":"x86_64"},"accelerator":{"vendor":"NVIDIA","model":"A10","driver_version":"535.183"}}',
        },
    )

    assert create.status_code == 200
    item = create.json()["item"]
    assert item["device_id"] == device_id
    assert item["os_type"] == "Ubuntu"
    assert item["cpu_arch"] == "x86_64"
    assert item["accelerator_vendor"] == "NVIDIA"
    assert item["accelerator_model"] == "A10"

    invalid = client.post(
        "/api/v1/environment-packages/probe-results",
        headers={"x-operator-id": "lisi"},
        json={"result_code": "bad-json", "raw_json": "not json"},
    )
    assert invalid.status_code == 400
    assert invalid.json()["code"] == "INVALID_PROBE_JSON"


def test_package_compatibility_rejects_unknown_device_profile(client: TestClient):
    response = client.post(
        "/api/v1/environment-packages/packages",
        headers={"x-operator-id": "zhangsan"},
        json={
            "package_code": "bad-profile-demo",
            "name": "Bad Profile Demo",
            "package_type": "custom",
            "version": "1.0",
            "device_profile_ids": ["missing-profile"],
        },
    )
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_DEVICE_PROFILE"


def test_admin_can_create_and_disable_device_profile(client: TestClient):
    create = client.post(
        "/api/v1/environment-packages/device-profiles",
        headers={"x-operator-id": "admin", "x-operator-role": "admin"},
        json={
            "profile_code": "a30-ubuntu2204",
            "name": "A30 Ubuntu",
            "hardware_vendor": "Inspur",
            "cpu_arch": "x86_64",
            "os_type": "Ubuntu",
            "os_version": "22.04",
            "accelerator_vendor": "NVIDIA",
            "accelerator_model": "A30",
            "driver_version": "535",
            "enabled": True,
        },
    )
    assert create.status_code == 200
    profile_id = create.json()["item"]["profile_id"]

    update = client.patch(
        f"/api/v1/environment-packages/device-profiles/{profile_id}",
        headers={"x-operator-id": "admin", "x-operator-role": "admin"},
        json={"enabled": False},
    )
    assert update.status_code == 200
    assert update.json()["item"]["enabled"] is False

    bind_disabled = client.post(
        "/api/v1/environment-packages/packages",
        headers={"x-operator-id": "zhangsan"},
        json={
            "package_code": "disabled-profile-demo",
            "name": "Disabled Profile Demo",
            "package_type": "custom",
            "version": "1.0",
            "device_profile_ids": [profile_id],
        },
    )
    assert bind_disabled.status_code == 400
    assert bind_disabled.json()["code"] == "INVALID_DEVICE_PROFILE"


def test_admin_can_manage_devices_and_generate_profile_for_package_select(client: TestClient):
    seeded = client.get("/api/v1/environment-packages/devices")
    assert seeded.status_code == 200
    assert seeded.json()["items"]

    denied = client.post(
        "/api/v1/environment-packages/devices",
        headers={"x-operator-id": "zhangsan"},
        json={"device_code": "dev-a30-denied", "name": "Denied"},
    )
    assert denied.status_code == 403

    create = client.post(
        "/api/v1/environment-packages/devices",
        headers={"x-operator-id": "admin", "x-operator-role": "admin"},
        json={
            "device_code": "dev-a30-01",
            "name": "A30 设备",
            "hostname": "a30-01",
            "ip": "10.1.0.30",
            "owner_team": "交付组",
            "location": "机房 B",
            "os_type": "Ubuntu",
            "os_version": "22.04",
            "cpu_arch": "x86_64",
            "accelerator_vendor": "NVIDIA",
            "accelerator_model": "A30",
            "accelerator_count": "1",
            "driver_version": "535",
            "status": "active",
        },
    )
    assert create.status_code == 200
    device_id = create.json()["item"]["device_id"]

    profile = client.post(
        f"/api/v1/environment-packages/devices/{device_id}/profile",
        headers={"x-operator-id": "admin", "x-operator-role": "admin"},
        json={"profile_code": "dev-a30-profile", "enabled": True},
    )
    assert profile.status_code == 200
    profile_item = profile.json()["item"]
    assert profile_item["profile_code"] == "dev-a30-profile"
    assert profile_item["accelerator_model"] == "A30"

    bind = client.post(
        "/api/v1/environment-packages/packages",
        headers={"x-operator-id": "lisi"},
        json={
            "package_code": "a30-runtime",
            "name": "A30 Runtime",
            "package_type": "runtime",
            "version": "1.0",
            "checksum": "sha256-demo",
            "install_script": "echo install",
            "verify_script": "echo verify",
            "device_profile_ids": [profile_item["profile_id"]],
        },
    )
    assert bind.status_code == 200
    assert bind.json()["item"]["device_profiles"][0]["profile_code"] == "dev-a30-profile"


def test_admin_can_create_and_update_user(client: TestClient):
    missing_password = client.post(
        "/api/v1/users",
        headers={"x-operator-id": "admin", "x-operator-role": "admin"},
        json={"username": "nopass", "display_name": "无密码用户", "role": "user", "enabled": True},
    )
    assert missing_password.status_code == 422

    create = client.post(
        "/api/v1/users",
        headers={"x-operator-id": "admin", "x-operator-role": "admin"},
        json={"username": "wangwu", "display_name": "王五", "role": "user", "password": "InitPass123!", "enabled": True},
    )
    assert create.status_code == 200
    user_id = create.json()["item"]["user_id"]

    update = client.patch(
        f"/api/v1/users/{user_id}",
        headers={"x-operator-id": "admin", "x-operator-role": "admin"},
        json={"display_name": "王五-交付", "enabled": False},
    )
    assert update.status_code == 200
    item = update.json()["item"]
    assert item["display_name"] == "王五-交付"
    assert item["enabled"] is False


def test_env_package_delete_requires_owner_and_blocks_bundle_usage(client: TestClient):
    profile_id = client.get("/api/v1/environment-packages/device-profiles").json()["items"][0]["profile_id"]

    standalone = client.post(
        "/api/v1/environment-packages/packages",
        headers={"x-operator-id": "lisi"},
        json={
            "package_code": "delete-standalone",
            "name": "Delete Standalone",
            "package_type": "custom",
            "version": "1.0",
            "checksum": "sha256-delete-standalone",
            "install_script": "echo install",
            "verify_script": "echo verify",
            "device_profile_ids": [profile_id],
        },
    )
    assert standalone.status_code == 200
    standalone_id = standalone.json()["item"]["package_id"]

    denied = client.delete(f"/api/v1/environment-packages/packages/{standalone_id}", headers={"x-operator-id": "zhangsan"})
    assert denied.status_code == 403

    deleted = client.delete(f"/api/v1/environment-packages/packages/{standalone_id}", headers={"x-operator-id": "lisi"})
    assert deleted.status_code == 200
    missing = client.get(f"/api/v1/environment-packages/packages/{standalone_id}", headers={"x-operator-id": "lisi"})
    assert missing.status_code == 404

    used = client.post(
        "/api/v1/environment-packages/packages",
        headers={"x-operator-id": "lisi"},
        json={
            "package_code": "delete-used",
            "name": "Delete Used",
            "package_type": "custom",
            "version": "1.0",
            "checksum": "sha256-delete-used",
            "install_script": "echo install",
            "verify_script": "echo verify",
            "device_profile_ids": [profile_id],
        },
    )
    assert used.status_code == 200
    used_id = used.json()["item"]["package_id"]

    bundle = client.post(
        "/api/v1/environment-packages/delivery-bundles",
        headers={"x-operator-id": "lisi"},
        json={
            "bundle_code": "delete-package-lock",
            "name": "Delete Package Lock",
            "version": "1.0",
            "target_profile_id": profile_id,
            "package_ids": [used_id],
        },
    )
    assert bundle.status_code == 200

    locked = client.delete(f"/api/v1/environment-packages/packages/{used_id}", headers={"x-operator-id": "lisi"})
    assert locked.status_code == 400
    assert locked.json()["code"] == "PACKAGE_IN_USE"


def test_upload_package_asset_returns_file_metadata_for_current_owner(client: TestClient, tmp_path: Path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "env_package_upload_root", str(tmp_path / "env-packages"))
    response = client.post(
        "/api/v1/environment-packages/uploads",
        headers={"x-operator-id": "lisi"},
        files={"file": ("../cuda toolkit.run", b"offline package bytes", "application/octet-stream")},
    )

    assert response.status_code == 200
    item = response.json()["item"]
    assert item["owner_id"] == "lisi"
    assert item["checksum_type"] == "sha256"
    assert item["checksum"] == "dc1df998caa1ed172d4771f7a64d8c59d988581f6956794b6c087812df7f2154"
    assert item["file_name"] == "cuda_toolkit.run"
    assert item["file_uri"].startswith("filesystem://")
    saved_path = Path(item["file_uri"].removeprefix("filesystem://"))
    assert saved_path == tmp_path / "env-packages" / "lisi" / "cuda_toolkit.run"
    assert saved_path.read_bytes() == b"offline package bytes"


def test_admin_can_list_users_transfer_and_share_assets(client: TestClient):
    admin_users = client.get("/api/v1/users", headers={"x-operator-id": "admin"})
    assert admin_users.status_code == 200
    assert any(user["username"] == "zhangsan" for user in admin_users.json()["items"])

    profile_id = client.get("/api/v1/environment-packages/device-profiles").json()["items"][0]["profile_id"]
    created = client.post(
        "/api/v1/environment-packages/packages",
        headers={"x-operator-id": "zhangsan"},
        json={
            "package_code": "admin-transfer-demo",
            "name": "Admin Transfer Demo",
            "package_type": "runtime",
            "version": "1.0.0",
            "checksum": "sha256-demo",
            "install_script": "echo install",
            "verify_script": "echo verify",
            "device_profile_ids": [profile_id],
        },
    )
    assert created.status_code == 200

    assets = client.get("/api/v1/environment-packages/admin/assets", headers={"x-operator-id": "admin"})
    assert assets.status_code == 200
    package = next(item for item in assets.json()["items"] if item["package_code"] == "admin-transfer-demo")

    transfer = client.post(
        f"/api/v1/environment-packages/admin/assets/{package['package_id']}/transfer",
        headers={"x-operator-id": "admin"},
        json={"target_owner_id": "lisi", "reason": "handover"},
    )
    assert transfer.status_code == 200
    assert transfer.json()["item"]["owner_id"] == "lisi"

    share = client.post(
        f"/api/v1/environment-packages/admin/assets/{package['package_id']}/share?shared=true",
        headers={"x-operator-id": "admin"},
    )
    assert share.status_code == 200
    assert share.json()["item"]["visibility"] == "shared"


def test_non_admin_cannot_manage_users_or_transfer_assets(client: TestClient):
    users = client.get("/api/v1/users", headers={"x-operator-id": "zhangsan"})
    assert users.status_code == 403

    profile_id = client.get("/api/v1/environment-packages/device-profiles").json()["items"][0]["profile_id"]
    created = client.post(
        "/api/v1/environment-packages/packages",
        headers={"x-operator-id": "zhangsan"},
        json={
            "package_code": "non-admin-transfer-demo",
            "name": "Non Admin Transfer Demo",
            "package_type": "runtime",
            "version": "1.0.0",
            "checksum": "sha256-demo",
            "install_script": "echo install",
            "verify_script": "echo verify",
            "device_profile_ids": [profile_id],
        },
    )
    assert created.status_code == 200
    package_id = created.json()["item"]["package_id"]
    transfer = client.post(
        f"/api/v1/environment-packages/admin/assets/{package_id}/transfer",
        headers={"x-operator-id": "zhangsan"},
        json={"target_owner_id": "lisi"},
    )
    assert transfer.status_code == 403


def test_delivery_bundle_build_fails_when_payload_file_missing(client: TestClient, tmp_path: Path, monkeypatch):
    from app.core.config import settings
    import time

    artifact_root = tmp_path / "artifacts-root"
    monkeypatch.setattr(settings, "delivery_bundle_artifact_root", str(artifact_root))
    profile_id = client.get("/api/v1/environment-packages/device-profiles").json()["items"][0]["profile_id"]
    missing_file = tmp_path / "missing-runtime.tar.gz"

    create = client.post(
        "/api/v1/environment-packages/packages",
        headers={"x-operator-id": "lisi"},
        json={
            "package_code": "missing-runtime-file",
            "name": "Missing Runtime File",
            "package_type": "runtime",
            "version": "1.0.0",
            "file_uri": f"filesystem://{missing_file}",
            "file_name": "missing-runtime.tar.gz",
            "checksum": "sha256-demo",
            "install_script": "echo install",
            "verify_script": "echo verify",
            "device_profile_ids": [profile_id],
        },
    )
    assert create.status_code == 200
    package_id = create.json()["item"]["package_id"]

    bundle = client.post(
        "/api/v1/environment-packages/delivery-bundles",
        headers={"x-operator-id": "lisi"},
        json={
            "bundle_code": "bundle-missing-payload",
            "name": "Bundle Missing Payload",
            "version": "1.0.0",
            "target_profile_id": profile_id,
            "package_ids": [package_id],
        },
    )
    assert bundle.status_code == 200
    bundle_id = bundle.json()["item"]["bundle_id"]

    build = client.post(f"/api/v1/environment-packages/delivery-bundles/{bundle_id}/build", headers={"x-operator-id": "lisi"})
    assert build.status_code == 200
    assert build.json()["status"] == "queued"

    item = None
    latest = None
    for _ in range(30):
        detail = client.get(f"/api/v1/environment-packages/delivery-bundles/{bundle_id}", headers={"x-operator-id": "lisi"})
        latest = client.get(f"/api/v1/environment-packages/delivery-bundles/{bundle_id}/build-jobs/latest", headers={"x-operator-id": "lisi"})
        assert detail.status_code == 200
        assert latest.status_code == 200
        item = detail.json()["item"]
        job = latest.json()["item"]
        if item["build_status"] == "failed" and job and job["job_status"] == "failed":
            break
        time.sleep(0.1)

    assert item is not None
    assert item["build_status"] == "failed"
    assert not item["artifact_uri"]
    job = latest.json()["item"]
    assert job["job_status"] == "failed"
    assert "环境包文件缺失" in job["current_message"]
    assert "missing-runtime-file" in job["current_message"]


def test_command_step_without_payload_file_can_build(client: TestClient, tmp_path: Path, monkeypatch):
    from app.core.config import settings
    import time

    artifact_root = tmp_path / "artifacts-root"
    monkeypatch.setattr(settings, "delivery_bundle_artifact_root", str(artifact_root))
    profile_id = client.get("/api/v1/environment-packages/device-profiles").json()["items"][0]["profile_id"]

    create = client.post(
        "/api/v1/environment-packages/packages",
        headers={"x-operator-id": "lisi"},
        json={
            "package_code": "command-step-no-file",
            "name": "Command Step No File",
            "package_type": "command_step",
            "version": "1.0.0",
            "file_uri": "",
            "checksum": "",
            "install_script": "echo install command",
            "verify_script": "echo verify command",
            "device_profile_ids": [profile_id],
        },
    )
    assert create.status_code == 200
    package_id = create.json()["item"]["package_id"]

    bundle = client.post(
        "/api/v1/environment-packages/delivery-bundles",
        headers={"x-operator-id": "lisi"},
        json={"bundle_code": "bundle-command-step", "name": "Bundle Command Step", "version": "1.0.0", "target_profile_id": profile_id, "package_ids": [package_id]},
    )
    assert bundle.status_code == 200
    bundle_id = bundle.json()["item"]["bundle_id"]

    build = client.post(f"/api/v1/environment-packages/delivery-bundles/{bundle_id}/build", headers={"x-operator-id": "lisi"})
    assert build.status_code == 200

    item = None
    for _ in range(30):
        detail = client.get(f"/api/v1/environment-packages/delivery-bundles/{bundle_id}", headers={"x-operator-id": "lisi"})
        item = detail.json()["item"]
        if item["build_status"] == "success":
            break
        time.sleep(0.1)

    detail = client.get(f"/api/v1/environment-packages/packages/{package_id}", headers={"x-operator-id": "lisi"})
    assert detail.status_code == 200
    assert detail.json()["item"]["quality_status"] == "ok"

    assert item is not None
    assert item["build_status"] == "success"
    assert item["artifact_size"] > 0



def test_application_package_is_carried_as_resource_and_not_managed_by_runner(client: TestClient, tmp_path: Path, monkeypatch):
    from app.core.config import settings
    import tarfile
    import subprocess

    artifact_root = tmp_path / "artifacts-root"
    monkeypatch.setattr(settings, "delivery_bundle_artifact_root", str(artifact_root))
    profile_id = client.get('/api/v1/environment-packages/device-profiles').json()['items'][0]['profile_id']
    package_file = tmp_path / 'application-package.tar.gz'
    payload_root = tmp_path / 'application-payload'
    payload_root.mkdir()
    install_script = payload_root / 'install.sh'
    verify_script = payload_root / 'verify.sh'
    install_script.write_text('#!/usr/bin/env bash\nset -e\necho app-install > should-not-be-created-by-runner.txt\n', encoding='utf-8')
    verify_script.write_text('#!/usr/bin/env bash\nset -e\necho app-verify > verify-should-not-run.txt\n', encoding='utf-8')
    install_script.chmod(0o755)
    verify_script.chmod(0o755)
    (payload_root / 'README.md').write_text('manual app payload', encoding='utf-8')
    with tarfile.open(package_file, 'w:gz') as tar:
        tar.add(payload_root, arcname='atlas310-mxhub-app')

    created = client.post(
        '/api/v1/environment-packages/packages',
        headers={'x-operator-id': 'lisi'},
        json={
            'package_code': 'atlas310-mxhub-app',
            'name': 'Atlas310 MXHub App',
            'package_type': 'application_package',
            'version': '1.0.0',
            'file_uri': f'filesystem://{package_file}',
            'file_name': package_file.name,
            'checksum': 'sha256-demo',
            'install_script': '#!/usr/bin/env bash\nset -e\necho app-install\n',
            'verify_script': '#!/usr/bin/env bash\nset -e\necho app-verify\n',
            'device_profile_ids': [profile_id],
        },
    )
    assert created.status_code == 200
    package_id = created.json()['item']['package_id']

    bundle = client.post(
        '/api/v1/environment-packages/delivery-bundles',
        headers={'x-operator-id': 'lisi'},
        json={'bundle_code': 'bundle-manual-app', 'name': 'Bundle Manual App', 'version': '1.0.0', 'target_profile_id': profile_id, 'package_ids': [package_id]},
    )
    assert bundle.status_code == 200
    bundle_id = bundle.json()['item']['bundle_id']

    build = client.post(f'/api/v1/environment-packages/delivery-bundles/{bundle_id}/build', headers={'x-operator-id': 'lisi'})
    assert build.status_code == 200

    import time
    item = None
    for _ in range(30):
        detail = client.get(f'/api/v1/environment-packages/delivery-bundles/{bundle_id}', headers={'x-operator-id': 'lisi'})
        assert detail.status_code == 200
        item = detail.json()['item']
        if item['build_status'] == 'success':
            break
        time.sleep(0.1)
    assert item is not None
    assert item['build_status'] == 'success'
    steps = item['manifest']['steps']
    assert steps == []
    resources = item['manifest']['application_resources']
    assert resources[0]['execution_mode'] == 'resource_only'
    assert resources[0]['resource_only'] is True
    assert resources[0]['path'] == 'application_packages/001-atlas310-mxhub-app'

    artifact_path = Path(item['artifact_uri'].removeprefix('filesystem://'))
    extract_root = tmp_path / 'extracted-manual-app'
    extract_root.mkdir(parents=True, exist_ok=True)
    with tarfile.open(artifact_path, 'r:gz') as tar:
        tar.extractall(extract_root)
    bundle_root = next(extract_root.iterdir())
    manifest = __import__('json').loads((bundle_root / 'manifest.json').read_text(encoding='utf-8'))
    assert manifest['steps'] == []
    assert manifest['application_resources'][0]['path'] == 'application_packages/001-atlas310-mxhub-app'
    resource_dir = bundle_root / 'application_packages' / '001-atlas310-mxhub-app'
    assert (resource_dir / 'install.sh').exists()
    assert (resource_dir / 'verify.sh').exists()
    assert (resource_dir / 'README.md').exists()
    assert not (resource_dir / '_payload_extract').exists()
    assert not (resource_dir / package_file.name).exists()
    assert not (bundle_root / 'packages' / '001-atlas310-mxhub-app').exists()

    state = __import__('json').loads((bundle_root / 'state.template.json').read_text(encoding='utf-8'))
    assert state['packages'] == {}

    proc = subprocess.run(['python3', str(bundle_root / 'scripts' / 'run_bundle.py'), str(bundle_root)], capture_output=True, text=True)
    assert proc.returncode == 0
    state_after = __import__('json').loads((bundle_root / 'state.json').read_text(encoding='utf-8'))
    assert state_after['status'] == 'success'
    assert state_after['packages'] == {}
    assert not (resource_dir / 'should-not-be-created-by-runner.txt').exists()
    assert not (resource_dir / 'verify-should-not-run.txt').exists()
    readme = (bundle_root / 'README.md').read_text(encoding='utf-8')
    assert 'application_packages/' in readme
    assert '不受根目录 `install.sh` 和 `scripts/run_bundle.py` 管理' in readme

def test_upload_env_package_uses_configured_absolute_storage_root(client: TestClient, tmp_path: Path, monkeypatch):
    from app.core.config import settings

    upload_root = tmp_path / "env-packages"
    monkeypatch.setattr(settings, "env_package_upload_root", str(upload_root))
    response = client.post(
        "/api/v1/environment-packages/uploads",
        headers={"x-operator-id": "lisi"},
        files={"file": ("demo-runtime.tar.gz", b"runtime bytes", "application/gzip")},
    )
    assert response.status_code == 200
    item = response.json()["item"]
    assert item["file_uri"].startswith("filesystem://")
    assert item["file_uri"].removeprefix("filesystem://").startswith(str(upload_root))
    assert Path(item["file_uri"].removeprefix("filesystem://")).exists()
    assert item["owner_id"] == "lisi"


def test_shared_package_is_visible_downloadable_but_not_editable_for_non_owner(client: TestClient, tmp_path: Path):
    profile_id = client.get('/api/v1/environment-packages/device-profiles').json()['items'][0]['profile_id']
    package_file = tmp_path / 'shared-readonly-runtime.tar.gz'
    package_file.write_bytes(b'shared runtime payload bytes')

    created = client.post(
        '/api/v1/environment-packages/packages',
        headers={'x-operator-id': 'lisi'},
        json={
            'package_code': 'shared-readonly-runtime',
            'name': 'Shared Readonly Runtime',
            'package_type': 'runtime',
            'version': '1.0.0',
            'file_uri': f'filesystem://{package_file}',
            'file_name': package_file.name,
            'checksum': 'sha256-demo',
            'install_script': 'echo install',
            'verify_script': 'echo verify',
            'visibility': 'private',
            'device_profile_ids': [profile_id],
        },
    )
    assert created.status_code == 200
    package_id = created.json()['item']['package_id']

    shared = client.patch(
        f'/api/v1/environment-packages/packages/{package_id}',
        headers={'x-operator-id': 'lisi'},
        json={'visibility': 'shared'},
    )
    assert shared.status_code == 200

    listed = client.get('/api/v1/environment-packages/packages?include_shared=true', headers={'x-operator-id': 'zhangsan'})
    assert listed.status_code == 200
    assert any(item['package_id'] == package_id for item in listed.json()['items'])

    detail = client.get(f'/api/v1/environment-packages/packages/{package_id}', headers={'x-operator-id': 'zhangsan'})
    assert detail.status_code == 200

    downloaded = client.get(f'/api/v1/environment-packages/packages/{package_id}/file', headers={'x-operator-id': 'zhangsan'})
    assert downloaded.status_code == 200
    assert downloaded.content == b'shared runtime payload bytes'

    update_denied = client.patch(
        f'/api/v1/environment-packages/packages/{package_id}',
        headers={'x-operator-id': 'zhangsan'},
        json={'name': 'Should Be Denied'},
    )
    assert update_denied.status_code == 403

    delete_denied = client.delete(f'/api/v1/environment-packages/packages/{package_id}', headers={'x-operator-id': 'zhangsan'})
    assert delete_denied.status_code == 403

    workspace_denied = client.post(f'/api/v1/environment-packages/packages/{package_id}/workspaces', headers={'x-operator-id': 'zhangsan'})
    assert workspace_denied.status_code == 403

    script_edit_denied = client.post(
        f'/api/v1/environment-packages/packages/{package_id}/script-edit',
        headers={'x-operator-id': 'zhangsan'},
        json={'install_script': 'echo x', 'verify_script': 'echo y', 'uninstall_script': '', 'save_mode': 'in_place'},
    )
    assert script_edit_denied.status_code == 403


def test_env_package_file_download_respects_visibility_and_owner(client: TestClient, tmp_path: Path):
    profile_id = client.get('/api/v1/environment-packages/device-profiles').json()['items'][0]['profile_id']
    package_file = tmp_path / 'download-runtime.tar.gz'
    package_file.write_bytes(b'runtime payload bytes')
    created = client.post(
        '/api/v1/environment-packages/packages',
        headers={'x-operator-id': 'lisi'},
        json={
            'package_code': 'download-runtime',
            'name': 'Download Runtime',
            'package_type': 'runtime',
            'version': '1.0.0',
            'file_uri': f'filesystem://{package_file}',
            'file_name': package_file.name,
            'checksum': 'sha256-demo',
            'install_script': 'echo install',
            'verify_script': 'echo verify',
            'visibility': 'private',
            'device_profile_ids': [profile_id],
        },
    )
    assert created.status_code == 200
    package_id = created.json()['item']['package_id']

    owner_download = client.get(f'/api/v1/environment-packages/packages/{package_id}/file', headers={'x-operator-id': 'lisi'})
    assert owner_download.status_code == 200
    assert owner_download.content == b'runtime payload bytes'
    assert 'attachment' in owner_download.headers.get('content-disposition', '')
    assert package_file.name in owner_download.headers.get('content-disposition', '')

    denied = client.get(f'/api/v1/environment-packages/packages/{package_id}/file', headers={'x-operator-id': 'zhangsan'})
    assert denied.status_code == 403

    shared = client.patch(
        f'/api/v1/environment-packages/packages/{package_id}',
        headers={'x-operator-id': 'lisi'},
        json={'visibility': 'shared'},
    )
    assert shared.status_code == 200
    shared_download = client.get(f'/api/v1/environment-packages/packages/{package_id}/file', headers={'x-operator-id': 'zhangsan'})
    assert shared_download.status_code == 200
    assert shared_download.content == b'runtime payload bytes'


def test_env_package_file_download_reports_missing_file(client: TestClient):
    profile_id = client.get('/api/v1/environment-packages/device-profiles').json()['items'][0]['profile_id']
    created = client.post(
        '/api/v1/environment-packages/packages',
        headers={'x-operator-id': 'lisi'},
        json={
            'package_code': 'download-missing-runtime',
            'name': 'Download Missing Runtime',
            'package_type': 'runtime',
            'version': '1.0.0',
            'file_uri': 'filesystem:///tmp/opspaw-not-exists-download.tar.gz',
            'file_name': 'opspaw-not-exists-download.tar.gz',
            'checksum': 'sha256-demo',
            'install_script': 'echo install',
            'verify_script': 'echo verify',
            'device_profile_ids': [profile_id],
        },
    )
    assert created.status_code == 200
    package_id = created.json()['item']['package_id']
    response = client.get(f'/api/v1/environment-packages/packages/{package_id}/file', headers={'x-operator-id': 'lisi'})
    assert response.status_code == 404
    assert response.json()['code'] == 'NOT_FOUND'


def test_packages_and_bundles_can_filter_by_device_profile(client: TestClient):
    profile = client.get('/api/v1/environment-packages/device-profiles').json()['items'][0]
    devices = client.get('/api/v1/environment-packages/devices').json()['items']
    device = next(
        item for item in devices
        if item['cpu_arch'] == profile['cpu_arch']
        and item['os_type'] == profile['os_type']
        and item['os_version'] == profile['os_version']
        and item['accelerator_vendor'] == profile['accelerator_vendor']
        and item['accelerator_model'] == profile['accelerator_model']
    )
    package = client.post(
        '/api/v1/environment-packages/packages',
        headers={'x-operator-id': 'lisi'},
        json={
            'package_code': 'device-filter-runtime',
            'name': 'Device Filter Runtime',
            'package_type': 'runtime',
            'version': '1.0.0',
            'file_uri': 'filesystem:///tmp/device-filter-runtime.tar.gz',
            'file_name': 'device-filter-runtime.tar.gz',
            'checksum': 'sha256-demo',
            'install_script': 'echo install',
            'verify_script': 'echo verify',
            'status': 'active',
            'device_profile_ids': [profile['profile_id']],
        },
    )
    assert package.status_code == 200
    package_id = package.json()['item']['package_id']

    by_profile = client.get(f"/api/v1/environment-packages/packages?profile_id={profile['profile_id']}", headers={'x-operator-id': 'lisi'})
    assert by_profile.status_code == 200
    assert package_id in {item['package_id'] for item in by_profile.json()['items']}

    by_device = client.get(f"/api/v1/environment-packages/packages?device_id={device['device_id']}", headers={'x-operator-id': 'lisi'})
    assert by_device.status_code == 200
    assert package_id in {item['package_id'] for item in by_device.json()['items']}

    bundle = client.post(
        '/api/v1/environment-packages/delivery-bundles',
        headers={'x-operator-id': 'lisi'},
        json={'bundle_code': 'device-filter-bundle', 'name': 'Device Filter Bundle', 'version': '1.0.0', 'target_device_id': device['device_id'], 'target_profile_id': profile['profile_id'], 'package_ids': [package_id]},
    )
    assert bundle.status_code == 200
    bundle_id = bundle.json()['item']['bundle_id']

    bundle_by_device = client.get(f"/api/v1/environment-packages/delivery-bundles?device_id={device['device_id']}", headers={'x-operator-id': 'lisi'})
    assert bundle_by_device.status_code == 200
    assert bundle_id in {item['bundle_id'] for item in bundle_by_device.json()['items']}


def test_device_profile_delete_rejects_profile_in_use(client: TestClient):
    profile = client.get('/api/v1/environment-packages/device-profiles').json()['items'][0]
    create = client.post(
        '/api/v1/environment-packages/packages',
        headers={'x-operator-id': 'lisi'},
        json={
            'package_code': 'profile-delete-guard',
            'name': 'Profile Delete Guard',
            'package_type': 'runtime',
            'version': '1.0.0',
            'checksum': 'sha256-demo',
            'install_script': 'echo install',
            'verify_script': 'echo verify',
            'device_profile_ids': [profile['profile_id']],
        },
    )
    assert create.status_code == 200

    delete_response = client.delete(f"/api/v1/environment-packages/device-profiles/{profile['profile_id']}", headers={'x-operator-id': 'admin', 'x-operator-role': 'admin'})
    assert delete_response.status_code == 400
    assert delete_response.json()['code'] == 'DEVICE_PROFILE_IN_USE'


def test_unused_device_profile_can_be_deleted(client: TestClient):
    create = client.post(
        '/api/v1/environment-packages/device-profiles',
        headers={'x-operator-id': 'admin', 'x-operator-role': 'admin'},
        json={'profile_code': 'unused-delete-profile', 'name': 'Unused Delete Profile', 'cpu_arch': 'x86_64', 'os_type': 'Ubuntu', 'os_version': '22.04', 'accelerator_vendor': 'NVIDIA', 'accelerator_model': 'A10'},
    )
    assert create.status_code == 200
    profile_id = create.json()['item']['profile_id']

    delete_response = client.delete(f'/api/v1/environment-packages/device-profiles/{profile_id}', headers={'x-operator-id': 'admin', 'x-operator-role': 'admin'})
    assert delete_response.status_code == 200

    profiles = client.get('/api/v1/environment-packages/device-profiles', headers={'x-operator-id': 'admin', 'x-operator-role': 'admin'}).json()['items']
    assert profile_id not in {item['profile_id'] for item in profiles}


def test_package_archive_tree_file_replace_and_script_new_version(client: TestClient, tmp_path: Path):
    import tarfile

    profile_id = client.get("/api/v1/environment-packages/device-profiles").json()["items"][0]["profile_id"]
    src_dir = tmp_path / "pkg-src"
    src_dir.mkdir()
    (src_dir / "install.sh").write_text("echo old install\n", encoding="utf-8")
    (src_dir / "verify.sh").write_text("echo verify\n", encoding="utf-8")
    (src_dir / "README.md").write_text("demo\n", encoding="utf-8")
    archive = tmp_path / "demo.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for path in src_dir.iterdir():
            tar.add(path, arcname=path.name)

    create = client.post(
        "/api/v1/environment-packages/packages",
        headers={"x-operator-id": "lisi"},
        json={
            "package_code": "editable-runtime",
            "name": "Editable Runtime",
            "package_type": "runtime",
            "version": "1.0.0",
            "file_uri": f"filesystem://{archive}",
            "file_name": archive.name,
            "checksum": "old-checksum",
            "install_script": "echo wrapper old",
            "verify_script": "echo wrapper verify",
            "device_profile_ids": [profile_id],
        },
    )
    assert create.status_code == 200
    package_id = create.json()["item"]["package_id"]

    tree = client.get(f"/api/v1/environment-packages/packages/{package_id}/archive-tree", headers={"x-operator-id": "lisi"})
    assert tree.status_code == 200
    paths = {item["path"] for item in tree.json()["item"]["items"]}
    assert {"install.sh", "verify.sh", "README.md"}.issubset(paths)

    replacement = tmp_path / "install-new.sh"
    replacement.write_text("echo new install\n", encoding="utf-8")
    with replacement.open("rb") as fh:
        replaced = client.post(
            f"/api/v1/environment-packages/packages/{package_id}/file-replace",
            headers={"x-operator-id": "lisi"},
            data={"target_path": "install.sh", "save_mode": "in_place", "remark": "replace install"},
            files={"file": ("install.sh", fh, "text/x-shellscript")},
        )
    assert replaced.status_code == 200
    updated = replaced.json()["item"]
    assert updated["package_id"] == package_id
    assert updated["checksum"] != "old-checksum"
    assert updated["file_name"].endswith(".tar.gz")

    revisions = client.get(f"/api/v1/environment-packages/packages/{package_id}/revisions", headers={"x-operator-id": "lisi"})
    assert revisions.status_code == 200
    assert revisions.json()["items"][0]["operation_type"] == "file_replace"
    assert revisions.json()["items"][0]["changed_files"] == ["install.sh"]

    script_new = client.post(
        f"/api/v1/environment-packages/packages/{package_id}/script-edit",
        headers={"x-operator-id": "lisi"},
        json={
            "install_script": "echo wrapper new",
            "verify_script": "echo wrapper verify",
            "uninstall_script": "",
            "save_mode": "new_version",
            "new_version": "1.0.1",
            "remark": "script update",
        },
    )
    assert script_new.status_code == 200
    new_item = script_new.json()["item"]
    assert new_item["package_id"] != package_id
    assert new_item["version"] == "1.0.1"
    assert new_item["install_script"] == "echo wrapper new"
    assert new_item["device_profiles"][0]["profile_id"] == profile_id


def test_file_replace_rejects_unsafe_target_path(client: TestClient, tmp_path: Path):
    import tarfile

    profile_id = client.get("/api/v1/environment-packages/device-profiles").json()["items"][0]["profile_id"]
    payload = tmp_path / "payload.txt"
    payload.write_text("ok", encoding="utf-8")
    archive = tmp_path / "unsafe-demo.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(payload, arcname="payload.txt")
    create = client.post(
        "/api/v1/environment-packages/packages",
        headers={"x-operator-id": "lisi"},
        json={"package_code": "unsafe-edit", "name": "Unsafe Edit", "package_type": "runtime", "version": "1.0", "file_uri": f"filesystem://{archive}", "file_name": archive.name, "checksum": "demo", "install_script": "echo install", "verify_script": "echo verify", "device_profile_ids": [profile_id]},
    )
    package_id = create.json()["item"]["package_id"]
    with payload.open("rb") as fh:
        response = client.post(
            f"/api/v1/environment-packages/packages/{package_id}/file-replace",
            headers={"x-operator-id": "lisi"},
            data={"target_path": "../escape.sh", "save_mode": "in_place"},
            files={"file": ("escape.sh", fh, "text/plain")},
        )
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_ARCHIVE_PATH"


def test_script_new_version_rejects_existing_package_version(client: TestClient):
    profile_id = client.get("/api/v1/environment-packages/device-profiles").json()["items"][0]["profile_id"]
    for version in ["1.0.0", "1.0.1"]:
        response = client.post(
            "/api/v1/environment-packages/packages",
            headers={"x-operator-id": "lisi"},
            json={"package_code": "duplicate-version-edit", "name": "Duplicate Version Edit", "package_type": "runtime", "version": version, "checksum": "demo", "install_script": "echo install", "verify_script": "echo verify", "device_profile_ids": [profile_id]},
        )
        assert response.status_code == 200
    first = client.get("/api/v1/environment-packages/packages", headers={"x-operator-id": "lisi"}).json()["items"]
    package_id = next(item["package_id"] for item in first if item["package_code"] == "duplicate-version-edit" and item["version"] == "1.0.0")
    response = client.post(
        f"/api/v1/environment-packages/packages/{package_id}/script-edit",
        headers={"x-operator-id": "lisi"},
        json={"install_script": "echo changed", "verify_script": "echo verify", "uninstall_script": "", "save_mode": "new_version", "new_version": "1.0.1"},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "PACKAGE_VERSION_EXISTS"


def test_command_step_workspace_loads_scripts_without_payload_file(client: TestClient):
    profile_id = client.get("/api/v1/environment-packages/device-profiles").json()["items"][0]["profile_id"]
    create = client.post(
        "/api/v1/environment-packages/packages",
        headers={"x-operator-id": "lisi"},
        json={
            "package_code": "command-step-edit",
            "name": "Command Step Edit",
            "package_type": "command_step",
            "version": "1.0.0",
            "file_uri": "",
            "checksum": "",
            "install_script": "echo old command\n",
            "verify_script": "echo verify command\n",
            "device_profile_ids": [profile_id],
        },
    )
    assert create.status_code == 200
    package_id = create.json()["item"]["package_id"]

    workspace = client.post(f"/api/v1/environment-packages/packages/{package_id}/workspaces", headers={"x-operator-id": "lisi"})
    assert workspace.status_code == 200
    body = workspace.json()["item"]
    assert body["meta"]["workspace_mode"] == "script_only"
    workspace_id = body["workspace_id"]

    root = client.get(f"/api/v1/environment-packages/packages/{package_id}/workspaces/{workspace_id}/contents", headers={"x-operator-id": "lisi"})
    assert root.status_code == 200
    assert {item["path"] for item in root.json()["item"]["content"]} >= {"install.sh", "verify.sh", "README.md"}

    install = client.get(f"/api/v1/environment-packages/packages/{package_id}/workspaces/{workspace_id}/contents/install.sh", headers={"x-operator-id": "lisi"})
    assert install.status_code == 200
    assert install.json()["item"]["content"] == "echo old command\n"

    saved = client.put(
        f"/api/v1/environment-packages/packages/{package_id}/workspaces/{workspace_id}/contents/install.sh",
        headers={"x-operator-id": "lisi"},
        json={"type": "file", "format": "text", "content": "echo new command\n"},
    )
    assert saved.status_code == 200

    committed = client.post(
        f"/api/v1/environment-packages/packages/{package_id}/workspaces/{workspace_id}/commit",
        headers={"x-operator-id": "lisi"},
        json={"save_mode": "in_place", "remark": "edit command step"},
    )
    assert committed.status_code == 200
    item = committed.json()["item"]
    assert item["install_script"] == "echo new command\n"
    assert item["verify_script"] == "echo verify command\n"
    assert item["file_uri"] == ""


def test_package_workspace_contents_crud_and_commit_new_version(client: TestClient, tmp_path: Path, monkeypatch):
    import tarfile
    from app.core.config import settings

    monkeypatch.setattr(settings, "env_package_upload_root", str(tmp_path / "uploads"))
    monkeypatch.setattr(settings, "delivery_bundle_artifact_root", str(tmp_path / "artifacts"))
    profile_id = client.get("/api/v1/environment-packages/device-profiles").json()["items"][0]["profile_id"]
    src = tmp_path / "workspace-src"
    src.mkdir()
    (src / "install.sh").write_text("echo old\n", encoding="utf-8")
    (src / "verify.sh").write_text("echo verify\n", encoding="utf-8")
    archive = tmp_path / "workspace-demo.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for path in src.iterdir():
            tar.add(path, arcname=path.name)

    create = client.post(
        "/api/v1/environment-packages/packages",
        headers={"x-operator-id": "lisi"},
        json={"package_code": "workspace-edit", "name": "Workspace Edit", "package_type": "runtime", "version": "1.0.0", "file_uri": f"filesystem://{archive}", "file_name": archive.name, "checksum": "demo", "install_script": "echo wrapper", "verify_script": "echo verify", "device_profile_ids": [profile_id]},
    )
    assert create.status_code == 200
    package_id = create.json()["item"]["package_id"]

    workspace = client.post(f"/api/v1/environment-packages/packages/{package_id}/workspaces", headers={"x-operator-id": "lisi"})
    assert workspace.status_code == 200
    workspace_id = workspace.json()["item"]["workspace_id"]

    root = client.get(f"/api/v1/environment-packages/packages/{package_id}/workspaces/{workspace_id}/contents", headers={"x-operator-id": "lisi"})
    assert root.status_code == 200
    assert {item["path"] for item in root.json()["item"]["content"]} >= {"install.sh", "verify.sh"}

    read_file = client.get(f"/api/v1/environment-packages/packages/{package_id}/workspaces/{workspace_id}/contents/install.sh", headers={"x-operator-id": "lisi"})
    assert read_file.status_code == 200
    assert read_file.json()["item"]["content"] == "echo old\n"

    save_file = client.put(
        f"/api/v1/environment-packages/packages/{package_id}/workspaces/{workspace_id}/contents/install.sh",
        headers={"x-operator-id": "lisi"},
        json={"type": "file", "format": "text", "content": "echo new\n"},
    )
    assert save_file.status_code == 200
    assert save_file.json()["item"]["content"] == "echo new\n"

    mkdir = client.post(
        f"/api/v1/environment-packages/packages/{package_id}/workspaces/{workspace_id}/contents",
        headers={"x-operator-id": "lisi"},
        json={"type": "directory", "name": "conf"},
    )
    assert mkdir.status_code == 200
    new_file = client.post(
        f"/api/v1/environment-packages/packages/{package_id}/workspaces/{workspace_id}/contents/conf",
        headers={"x-operator-id": "lisi"},
        json={"type": "file", "name": "app.conf", "content": "port=18080\n", "format": "text"},
    )
    assert new_file.status_code == 200
    renamed = client.patch(
        f"/api/v1/environment-packages/packages/{package_id}/workspaces/{workspace_id}/contents/conf/app.conf",
        headers={"x-operator-id": "lisi"},
        json={"path": "conf/runtime.conf"},
    )
    assert renamed.status_code == 200
    deleted = client.delete(f"/api/v1/environment-packages/packages/{package_id}/workspaces/{workspace_id}/contents/conf/runtime.conf", headers={"x-operator-id": "lisi"})
    assert deleted.status_code == 200

    committed = client.post(
        f"/api/v1/environment-packages/packages/{package_id}/workspaces/{workspace_id}/commit",
        headers={"x-operator-id": "lisi"},
        json={"save_mode": "new_version", "new_version": "1.0.1", "remark": "workspace commit"},
    )
    assert committed.status_code == 200
    item = committed.json()["item"]
    assert item["package_id"] != package_id
    assert item["version"] == "1.0.1"
    assert item["checksum"] != "demo"
    assert item["file_uri"].startswith("filesystem://")
    archive_path = Path(item["file_uri"].removeprefix("filesystem://"))
    assert archive_path.exists()
    with tarfile.open(archive_path, "r:gz") as tar:
        content = tar.extractfile("install.sh").read().decode("utf-8")
    assert content == "echo new\n"


def test_package_workspace_rejects_path_traversal(client: TestClient, tmp_path: Path, monkeypatch):
    import tarfile
    from app.core.config import settings

    monkeypatch.setattr(settings, "delivery_bundle_artifact_root", str(tmp_path / "artifacts"))
    profile_id = client.get("/api/v1/environment-packages/device-profiles").json()["items"][0]["profile_id"]
    payload = tmp_path / "payload.txt"
    payload.write_text("ok", encoding="utf-8")
    archive = tmp_path / "traversal.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(payload, arcname="payload.txt")
    create = client.post(
        "/api/v1/environment-packages/packages",
        headers={"x-operator-id": "lisi"},
        json={"package_code": "workspace-traversal", "name": "Workspace Traversal", "package_type": "runtime", "version": "1.0", "file_uri": f"filesystem://{archive}", "file_name": archive.name, "checksum": "demo", "install_script": "echo install", "verify_script": "echo verify", "device_profile_ids": [profile_id]},
    )
    package_id = create.json()["item"]["package_id"]
    workspace_id = client.post(f"/api/v1/environment-packages/packages/{package_id}/workspaces", headers={"x-operator-id": "lisi"}).json()["item"]["workspace_id"]
    response = client.put(
        f"/api/v1/environment-packages/packages/{package_id}/workspaces/{workspace_id}/contents/%2E%2E/escape.txt",
        headers={"x-operator-id": "lisi"},
        json={"type": "file", "format": "text", "content": "bad"},
    )
    assert response.status_code == 400
    assert response.json()["code"] in {"INVALID_ARCHIVE_PATH", "INVALID_WORKSPACE_PATH"}
