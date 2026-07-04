from __future__ import annotations

import hashlib
import json
import uuid
from threading import Lock
from pathlib import Path
from typing import Callable

from fastapi import UploadFile
from pydantic import BaseModel

from app.core.config import settings
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.models import DeliveryBundle, DeliveryBundleBuildJob, DeliveryBundleItem, EnvDeviceProfile, EnvPackage, EnvPackageCompatibility, EnvPackageRevision, InferenceDevice, ProbeResult
from app.services.user_account_service import ensure_default_users, format_dt, set_if_present

_SEED_LOCK = Lock()
_SEED_READY = False


def build_device_profile_response(item: EnvDeviceProfile) -> dict:
    label_parts = [item.name, item.cpu_arch, f"{item.os_type} {item.os_version}".strip(), f"{item.accelerator_vendor} {item.accelerator_model}".strip()]
    return {
        "profile_id": item.id,
        "profile_code": item.profile_code,
        "name": item.name,
        "label": " / ".join(part for part in label_parts if part),
        "hardware_vendor": item.hardware_vendor,
        "cpu_arch": item.cpu_arch,
        "os_type": item.os_type,
        "os_version": item.os_version,
        "accelerator_vendor": item.accelerator_vendor,
        "accelerator_model": item.accelerator_model,
        "driver_version": item.driver_version,
        "enabled": item.enabled,
        "created_by": item.created_by,
        "updated_by": item.updated_by,
        "created_at": format_dt(item.created_at),
        "updated_at": format_dt(item.updated_at),
    }


def build_managed_device_response(item: InferenceDevice) -> dict:
    return {
        "device_id": item.id,
        "device_code": item.device_code,
        "name": item.name,
        "hostname": item.hostname,
        "ip": item.ip,
        "asset_id": item.asset_id,
        "jms_asset_id": item.jms_asset_id,
        "owner_team": item.owner_team,
        "location": item.location,
        "os_type": item.os_type,
        "os_version": item.os_version,
        "cpu_arch": item.cpu_arch,
        "cpu_model": item.cpu_model,
        "memory_gb": item.memory_gb,
        "storage_summary": item.storage_summary,
        "accelerator_vendor": item.accelerator_vendor,
        "accelerator_model": item.accelerator_model,
        "accelerator_count": item.accelerator_count,
        "accelerator_memory_gb": item.accelerator_memory_gb,
        "driver_version": item.driver_version,
        "firmware_version": item.firmware_version,
        "status": item.status,
        "notes": item.notes,
        "created_by": item.created_by,
        "updated_by": item.updated_by,
        "created_at": format_dt(item.created_at),
        "updated_at": format_dt(item.updated_at),
    }


def profile_code_from_device(item: InferenceDevice) -> str:
    parts = [item.device_code, item.cpu_arch, item.os_type, item.os_version, item.accelerator_vendor, item.accelerator_model]
    raw = "-".join(part for part in parts if part).lower() or item.id
    safe = "".join(ch if ch.isalnum() else "-" for ch in raw).strip("-")
    while "--" in safe:
        safe = safe.replace("--", "-")
    return safe[:64] or item.id[:32]


def build_profile_from_device(session: Session, device: InferenceDevice, username: str, profile_code: str = "", name: str = "", enabled: bool = True) -> tuple[EnvDeviceProfile, bool]:
    code = (profile_code or profile_code_from_device(device)).strip()[:64]
    existing = session.scalar(select(EnvDeviceProfile).where(EnvDeviceProfile.profile_code == code))
    created = existing is None
    profile = existing or EnvDeviceProfile(profile_code=code, created_by=username)
    profile.name = (name or device.name or device.device_code)[:128]
    profile.hardware_vendor = profile.hardware_vendor or ""
    profile.cpu_arch = device.cpu_arch
    profile.os_type = device.os_type
    profile.os_version = device.os_version
    profile.accelerator_vendor = device.accelerator_vendor
    profile.accelerator_model = device.accelerator_model
    profile.driver_version = device.driver_version
    profile.enabled = enabled
    profile.updated_by = username
    if created:
        session.add(profile)
    session.flush()
    return profile, created


def list_package_profiles(session: Session, package_id: str) -> list[dict]:
    rows = list(session.scalars(select(EnvPackageCompatibility).where(EnvPackageCompatibility.package_id == package_id)))
    ids = [row.device_profile_id for row in rows]
    if not ids:
        return []
    profiles = list(session.scalars(select(EnvDeviceProfile).where(EnvDeviceProfile.id.in_(ids))))
    by_id = {item.id: item for item in profiles}
    return [build_device_profile_response(by_id[profile_id]) for profile_id in ids if profile_id in by_id]


def quality_status(item: EnvPackage, profiles: list[dict]) -> str:
    # 纯命令步骤不携带 payload 文件，因此不要求 checksum。
    # 仍必须具备两段脚本和适配配置，才能被交付包可靠编排。
    if item.package_type != "command_step" and not item.checksum:
        return "missing_checksum"
    # 环境包资产按“两段脚本”判定：安装脚本 + 安装后成功检查脚本。
    # check_script 字段仅为历史兼容，不再作为必填或交付包执行阶段。
    if not item.install_script or not item.verify_script:
        return "missing_script"
    if not profiles:
        return "missing_compatibility"
    return "ok"


def build_env_package_response(item: EnvPackage, profiles: list[dict] | None = None) -> dict:
    device_profiles = profiles if profiles is not None else []
    return {
        "package_id": item.id,
        "package_code": item.package_code,
        "name": item.name,
        "package_type": item.package_type,
        "version": item.version,
        "file_uri": item.file_uri,
        "file_name": item.file_name,
        "checksum_type": item.checksum_type,
        "checksum": item.checksum,
        "check_script": item.check_script,
        "install_script": item.install_script,
        "verify_script": item.verify_script,
        "uninstall_script": item.uninstall_script,
        "depends_on": item.depends_on,
        "install_order": item.install_order,
        "requires_root": item.requires_root,
        "requires_reboot": item.requires_reboot,
        "offline_supported": item.offline_supported,
        "status": item.status,
        "visibility": item.visibility,
        "owner_id": item.owner_id,
        "quality_status": quality_status(item, device_profiles),
        "device_profiles": device_profiles,
        "created_by": item.created_by,
        "updated_by": item.updated_by,
        "created_at": format_dt(item.created_at),
        "updated_at": format_dt(item.updated_at),
    }


def build_delivery_manifest(*, bundle: DeliveryBundle, packages: list[EnvPackage], device: InferenceDevice | None, profile: EnvDeviceProfile | None) -> dict:
    steps = []
    for index, package in enumerate(packages):
        step_path = f"packages/{index + 1:03d}-{_safe_name(package.package_code)}"
        manual = package_manual_instructions(package, step_path)
        steps.append({
            "step": index + 1,
            "package_id": package.id,
            "package_code": package.package_code,
            "name": package.name,
            "version": package.version,
            "package_type": package.package_type,
            "install_order": package.install_order,
            "depends_on": package.depends_on,
            "install_script": package.install_script,
            "verify_script": package.verify_script,
            **manual,
        })
    return {
        "bundle_code": bundle.bundle_code,
        "name": bundle.name,
        "version": bundle.version,
        "bundle_type": bundle.bundle_type,
        "lifecycle_status": bundle.lifecycle_status,
        "status": bundle.status,
        "target": {
            "device_id": bundle.target_device_id,
            "device_name": device.name if device else "",
            "profile_id": bundle.target_profile_id,
            "profile_name": profile.name if profile else "",
        },
        "steps": steps,
    }


def build_delivery_bundle_response(session: Session, item: DeliveryBundle) -> dict:
    bundle_items = list(session.scalars(select(DeliveryBundleItem).where(DeliveryBundleItem.bundle_id == item.id).order_by(DeliveryBundleItem.sort_order.asc())))
    packages = [session.get(EnvPackage, bundle_item.package_id) for bundle_item in bundle_items]
    packages = [package for package in packages if package is not None]
    try:
        manifest = json.loads(item.manifest_json or "{}")
    except json.JSONDecodeError:
        manifest = {}
    manifest.setdefault("bundle_type", item.bundle_type)
    manifest.setdefault("lifecycle_status", item.lifecycle_status)
    return {
        "bundle_id": item.id,
        "bundle_code": item.bundle_code,
        "name": item.name,
        "version": item.version,
        "bundle_type": item.bundle_type,
        "target_device_id": item.target_device_id,
        "target_profile_id": item.target_profile_id,
        "lifecycle_status": item.lifecycle_status,
        "delivered_by": item.delivered_by,
        "delivered_at": format_dt(item.delivered_at),
        "parent_bundle_id": item.parent_bundle_id,
        "status": item.status,
        "build_status": item.build_status,
        "artifact_uri": item.artifact_uri,
        "artifact_name": item.artifact_name,
        "artifact_size": item.artifact_size,
        "artifact_checksum": item.artifact_checksum,
        "build_log": item.build_log,
        "built_at": format_dt(item.built_at),
        "owner_id": item.owner_id,
        "package_ids": [package.id for package in packages],
        "manifest": manifest,
        "created_by": item.created_by,
        "updated_by": item.updated_by,
        "created_at": format_dt(item.created_at),
        "updated_at": format_dt(item.updated_at),
    }


def build_delivery_bundle_job_response(item: DeliveryBundleBuildJob | None) -> dict | None:
    if item is None:
        return None
    return {
        "job_id": item.id,
        "bundle_id": item.bundle_id,
        "job_status": item.job_status,
        "progress_percent": item.progress_percent,
        "current_step": item.current_step,
        "current_message": item.current_message,
        "log_text": item.log_text,
        "artifact_uri": item.artifact_uri,
        "artifact_name": item.artifact_name,
        "artifact_size": item.artifact_size,
        "artifact_checksum": item.artifact_checksum,
        "started_at": format_dt(item.started_at),
        "finished_at": format_dt(item.finished_at),
        "created_by": item.created_by,
        "created_at": format_dt(item.created_at),
        "updated_at": format_dt(item.updated_at),
    }


def _first_value(data: dict, *keys: str) -> str:
    for key in keys:
        value = data.get(key)
        if value is None:
            continue
        if isinstance(value, (str, int, float)):
            return str(value)
    return ""


def extract_probe_fields(raw_json: str) -> tuple[dict, dict]:
    data = json.loads(raw_json)
    if not isinstance(data, dict):
        raise ValueError("probe result must be a JSON object")
    system = data.get("system") if isinstance(data.get("system"), dict) else {}
    accelerator = data.get("accelerator") if isinstance(data.get("accelerator"), dict) else {}
    gpu = data.get("gpu") if isinstance(data.get("gpu"), dict) else {}
    npu = data.get("npu") if isinstance(data.get("npu"), dict) else {}
    card = accelerator or gpu or npu
    fields = {
        "os_type": _first_value(data, "os_type", "os") or _first_value(system, "os_type", "os", "name"),
        "os_version": _first_value(data, "os_version") or _first_value(system, "os_version", "version"),
        "cpu_arch": _first_value(data, "cpu_arch", "arch", "architecture") or _first_value(system, "cpu_arch", "arch", "architecture"),
        "accelerator_vendor": _first_value(data, "accelerator_vendor", "card_vendor") or _first_value(card, "vendor", "accelerator_vendor"),
        "accelerator_model": _first_value(data, "accelerator_model", "card_model") or _first_value(card, "model", "accelerator_model"),
        "driver_version": _first_value(data, "driver_version") or _first_value(card, "driver_version", "driver"),
    }
    return data, fields


def build_probe_result_response(item: ProbeResult) -> dict:
    return {
        "result_id": item.id,
        "result_code": item.result_code,
        "device_id": item.device_id,
        "name": item.name,
        "raw_json": item.raw_json,
        "os_type": item.os_type,
        "os_version": item.os_version,
        "cpu_arch": item.cpu_arch,
        "accelerator_vendor": item.accelerator_vendor,
        "accelerator_model": item.accelerator_model,
        "driver_version": item.driver_version,
        "owner_id": item.owner_id,
        "created_by": item.created_by,
        "updated_by": item.updated_by,
        "created_at": format_dt(item.created_at),
        "updated_at": format_dt(item.updated_at),
    }


def can_edit_package(item: EnvPackage, username: str, role: str) -> bool:
    return role.lower() == "admin" or item.owner_id == username


def set_package_profiles(session: Session, package_id: str, profile_ids: list[str]) -> tuple[bool, str]:
    deduped = list(dict.fromkeys(profile_ids))
    if deduped:
        found = set(session.scalars(select(EnvDeviceProfile.id).where(EnvDeviceProfile.id.in_(deduped), EnvDeviceProfile.enabled.is_(True))))
        missing = [profile_id for profile_id in deduped if profile_id not in found]
        if missing:
            return False, f"device profile not found or disabled: {missing[0]}"
    session.execute(delete(EnvPackageCompatibility).where(EnvPackageCompatibility.package_id == package_id))
    for profile_id in deduped:
        session.add(EnvPackageCompatibility(package_id=package_id, device_profile_id=profile_id))
    return True, ""


def ensure_env_package_seed_data(session: Session) -> None:
    global _SEED_READY
    if _SEED_READY:
        return
    with _SEED_LOCK:
        if _SEED_READY:
            return
        ensure_default_users(session)

        if not session.scalar(select(EnvDeviceProfile).where(EnvDeviceProfile.profile_code == "a10-ubuntu2204")):
            session.add(EnvDeviceProfile(profile_code="a10-ubuntu2204", name="A10 推理服务器", hardware_vendor="Dell", cpu_arch="x86_64", os_type="Ubuntu", os_version="22.04", accelerator_vendor="NVIDIA", accelerator_model="A10", driver_version="535.183", enabled=True, created_by="admin", updated_by="admin"))
        if not session.scalar(select(EnvDeviceProfile).where(EnvDeviceProfile.profile_code == "atlas-kylinv10")):
            session.add(EnvDeviceProfile(profile_code="atlas-kylinv10", name="Atlas 边缘设备", hardware_vendor="Huawei", cpu_arch="aarch64", os_type="Kylin", os_version="V10", accelerator_vendor="Ascend", accelerator_model="310P", driver_version="", enabled=True, created_by="admin", updated_by="admin"))
        session.flush()

        if not session.scalar(select(InferenceDevice).where(InferenceDevice.device_code == "dev-a10-01")):
            session.add(InferenceDevice(device_code="dev-a10-01", name="A10 推理服务器 01", hostname="a10-01", ip="10.0.0.11", owner_team="算法交付", location="机房 A", os_type="Ubuntu", os_version="22.04", cpu_arch="x86_64", accelerator_vendor="NVIDIA", accelerator_model="A10", accelerator_count="1", accelerator_memory_gb="24", driver_version="535.183", status="active", created_by="admin", updated_by="admin"))
        if not session.scalar(select(InferenceDevice).where(InferenceDevice.device_code == "dev-atlas-01")):
            session.add(InferenceDevice(device_code="dev-atlas-01", name="Atlas 边缘设备 01", hostname="atlas-01", ip="10.0.0.21", owner_team="边缘交付", location="实验室", os_type="Kylin", os_version="V10", cpu_arch="aarch64", accelerator_vendor="Ascend", accelerator_model="310P", accelerator_count="1", accelerator_memory_gb="8", driver_version="", status="active", created_by="admin", updated_by="admin"))

        # 不再自动创建 nvidia-driver / opencv-python 等演示环境包资产。
        # 生产环境包必须由用户或 Agent 通过 upload_env_package_file 上传真实 payload 后登记，
        # 否则会形成不可离线打包的 s3:// 占位资产并污染资产质量审计。
        session.flush()
        _SEED_READY = True

def list_device_profiles(session: Session, enabled: bool | None, search: str, limit: int, offset: int) -> tuple[list[EnvDeviceProfile], int]:
    ensure_env_package_seed_data(session)
    stmt = select(EnvDeviceProfile)
    count_stmt = select(func.count()).select_from(EnvDeviceProfile)
    if enabled is not None:
        stmt = stmt.where(EnvDeviceProfile.enabled.is_(enabled))
        count_stmt = count_stmt.where(EnvDeviceProfile.enabled.is_(enabled))
    if search:
        pattern = f"%{search.lower()}%"
        pred = or_(func.lower(EnvDeviceProfile.name).like(pattern), func.lower(EnvDeviceProfile.profile_code).like(pattern), func.lower(EnvDeviceProfile.accelerator_model).like(pattern))
        stmt = stmt.where(pred)
        count_stmt = count_stmt.where(pred)
    total = int(session.scalar(count_stmt) or 0)
    items = list(session.scalars(stmt.order_by(EnvDeviceProfile.name.asc()).offset(offset).limit(limit)))
    return items, total


def resolve_profile_id_for_filter(session: Session, profile_id: str = "", device_id: str = "") -> str:
    if profile_id:
        profile = session.get(EnvDeviceProfile, profile_id) or session.scalar(select(EnvDeviceProfile).where(EnvDeviceProfile.profile_code == profile_id))
        return profile.id if profile else "__missing_profile__"
    if not device_id:
        return ""
    device = session.get(InferenceDevice, device_id) or session.scalar(select(InferenceDevice).where(InferenceDevice.device_code == device_id))
    if not device:
        return "__missing_profile__"
    candidates = list(session.scalars(select(EnvDeviceProfile).where(EnvDeviceProfile.enabled.is_(True))))
    for profile in candidates:
        if (profile.cpu_arch or "") != (device.cpu_arch or ""):
            continue
        if (profile.os_type or "") != (device.os_type or ""):
            continue
        if (profile.os_version or "") != (device.os_version or ""):
            continue
        if (profile.accelerator_vendor or "") != (device.accelerator_vendor or ""):
            continue
        if (profile.accelerator_model or "") != (device.accelerator_model or ""):
            continue
        if profile.driver_version and device.driver_version and profile.driver_version != device.driver_version:
            continue
        return profile.id
    return "__missing_profile__"


def list_env_packages(session: Session, username: str, role: str, package_type: str, status: str, search: str, include_shared: bool, limit: int, offset: int, profile_id: str = "", device_id: str = "") -> tuple[list[EnvPackage], int, str]:
    ensure_env_package_seed_data(session)
    stmt = select(EnvPackage)
    count_stmt = select(func.count()).select_from(EnvPackage)
    if role.lower() != "admin":
        predicate = EnvPackage.owner_id == username
        if include_shared:
            predicate = or_(predicate, EnvPackage.visibility == "shared")
        stmt = stmt.where(predicate)
        count_stmt = count_stmt.where(predicate)
    resolved_profile_id = resolve_profile_id_for_filter(session, profile_id=profile_id, device_id=device_id)
    if resolved_profile_id:
        compatibility_ids = select(EnvPackageCompatibility.package_id).where(EnvPackageCompatibility.device_profile_id == resolved_profile_id)
        stmt = stmt.where(EnvPackage.id.in_(compatibility_ids))
        count_stmt = count_stmt.where(EnvPackage.id.in_(compatibility_ids))
    if package_type:
        stmt = stmt.where(EnvPackage.package_type == package_type)
        count_stmt = count_stmt.where(EnvPackage.package_type == package_type)
    if status:
        stmt = stmt.where(EnvPackage.status == status)
        count_stmt = count_stmt.where(EnvPackage.status == status)
    if search:
        pattern = f"%{search.lower()}%"
        pred = or_(func.lower(EnvPackage.name).like(pattern), func.lower(EnvPackage.package_code).like(pattern), func.lower(EnvPackage.version).like(pattern))
        stmt = stmt.where(pred)
        count_stmt = count_stmt.where(pred)
    total = int(session.scalar(count_stmt) or 0)
    items = list(session.scalars(stmt.order_by(EnvPackage.updated_at.desc(), EnvPackage.id.desc()).offset(offset).limit(limit)))
    return items, total, "all" if role.lower() == "admin" else "owned"




def list_managed_devices(session: Session, status: str, search: str, limit: int, offset: int) -> tuple[list[InferenceDevice], int]:
    ensure_env_package_seed_data(session)
    stmt = select(InferenceDevice)
    count_stmt = select(func.count()).select_from(InferenceDevice)
    if status:
        stmt = stmt.where(InferenceDevice.status == status)
        count_stmt = count_stmt.where(InferenceDevice.status == status)
    if search:
        pattern = f"%{search.lower()}%"
        pred = or_(
            func.lower(InferenceDevice.device_code).like(pattern),
            func.lower(InferenceDevice.name).like(pattern),
            func.lower(InferenceDevice.hostname).like(pattern),
            func.lower(InferenceDevice.ip).like(pattern),
            func.lower(InferenceDevice.accelerator_model).like(pattern),
        )
        stmt = stmt.where(pred)
        count_stmt = count_stmt.where(pred)
    total = int(session.scalar(count_stmt) or 0)
    items = list(session.scalars(stmt.order_by(InferenceDevice.updated_at.desc(), InferenceDevice.id.desc()).offset(offset).limit(limit)))
    return items, total


def get_managed_device(session: Session, device_id: str) -> InferenceDevice | None:
    return session.get(InferenceDevice, device_id) or session.scalar(select(InferenceDevice).where(InferenceDevice.device_code == device_id))


def create_managed_device(session: Session, payload: BaseModel, username: str) -> InferenceDevice:
    data = payload.model_dump()
    item = InferenceDevice(**data, created_by=username, updated_by=username)
    session.add(item)
    session.flush()
    return item
def safe_env_package_filename(filename: str | None) -> str:
    raw_name = Path(filename or "environment-package.bin").name
    safe_name = "".join(char if char.isalnum() or char in {".", "-", "_", "+"} else "_" for char in raw_name)
    safe_name = safe_name.strip("._")
    return safe_name or f"environment-package-{uuid.uuid4().hex}.bin"


def save_upload(username: str, file: UploadFile) -> dict:
    safe_name = safe_env_package_filename(file.filename)
    storage_dir = Path(settings.env_package_upload_root).expanduser().resolve() / username
    storage_dir.mkdir(parents=True, exist_ok=True)
    target = storage_dir / safe_name
    if target.exists():
        stem = target.stem or "environment-package"
        suffix = target.suffix
        target = storage_dir / f"{stem}-{uuid.uuid4().hex[:8]}{suffix}"

    checksum = hashlib.sha256()
    size = 0
    with target.open("wb") as output:
        while True:
            chunk = file.file.read(1024 * 1024)
            if not chunk:
                break
            checksum.update(chunk)
            size += len(chunk)
            output.write(chunk)

    return {
        "file_uri": f"filesystem://{target.as_posix()}",
        "file_name": target.name,
        "checksum_type": "sha256",
        "checksum": checksum.hexdigest(),
        "size": size,
        "owner_id": username,
    }


def apply_update(item, payload: BaseModel, fields: list[str]) -> None:
    set_if_present(item, payload, fields)


def _safe_name(value: str) -> str:
    raw = (value or "asset").strip().lower()
    safe = "".join(ch if ch.isalnum() else "-" for ch in raw).strip("-")
    while "--" in safe:
        safe = safe.replace("--", "-")
    return safe[:80] or "asset"


def _write_executable(path: Path, content: str) -> None:
    path.write_text((content or "#!/usr/bin/env bash\nset -euo pipefail\n").replace("\r\n", "\n"), encoding="utf-8")
    path.chmod(0o755)



def build_env_package_revision_response(item: EnvPackageRevision) -> dict:
    return {
        "revision_id": item.id,
        "package_id": item.package_id,
        "revision_no": item.revision_no,
        "operation_type": item.operation_type,
        "save_mode": item.save_mode,
        "old_file_uri": item.old_file_uri,
        "new_file_uri": item.new_file_uri,
        "old_checksum": item.old_checksum,
        "new_checksum": item.new_checksum,
        "changed_files": json.loads(item.changed_files or "[]"),
        "script_diff": json.loads(item.script_diff_json or "{}"),
        "remark": item.remark,
        "created_by": item.created_by,
        "created_at": format_dt(item.created_at),
    }


def _next_revision_no(session: Session, package_id: str) -> int:
    current = session.scalar(select(func.max(EnvPackageRevision.revision_no)).where(EnvPackageRevision.package_id == package_id))
    return int(current or 0) + 1


def _record_package_revision(
    session: Session,
    *,
    package_id: str,
    operation_type: str,
    save_mode: str,
    old_file_uri: str = "",
    new_file_uri: str = "",
    old_checksum: str = "",
    new_checksum: str = "",
    changed_files: list[str] | None = None,
    script_diff: dict | None = None,
    remark: str = "",
    username: str,
) -> EnvPackageRevision:
    revision = EnvPackageRevision(
        package_id=package_id,
        revision_no=_next_revision_no(session, package_id),
        operation_type=operation_type,
        save_mode=save_mode,
        old_file_uri=old_file_uri or "",
        new_file_uri=new_file_uri or "",
        old_checksum=old_checksum or "",
        new_checksum=new_checksum or "",
        changed_files=json.dumps(changed_files or [], ensure_ascii=False),
        script_diff_json=json.dumps(script_diff or {}, ensure_ascii=False),
        remark=remark or "",
        created_by=username,
    )
    session.add(revision)
    return revision


def list_env_package_revisions(session: Session, package_id: str) -> list[dict]:
    rows = list(session.scalars(select(EnvPackageRevision).where(EnvPackageRevision.package_id == package_id).order_by(EnvPackageRevision.revision_no.desc(), EnvPackageRevision.created_at.desc())))
    return [build_env_package_revision_response(item) for item in rows]


def _package_file_path(package: EnvPackage) -> Path:
    if not package.file_uri:
        raise ValueError("PACKAGE_FILE_NOT_CONFIGURED: environment package file is not configured")
    if not package.file_uri.startswith("filesystem://"):
        raise ValueError("UNSUPPORTED_PACKAGE_FILE_URI: only filesystem package files are supported")
    path = Path(package.file_uri[len("filesystem://"):]).expanduser().resolve()
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"environment package file not found: {path}")
    return path


def _archive_kind(path: Path) -> str:
    import tarfile
    import zipfile
    if tarfile.is_tarfile(path):
        return "tar"
    if zipfile.is_zipfile(path):
        return "zip"
    raise ValueError("UNSUPPORTED_ARCHIVE_TYPE: only tar/tar.gz/tgz/zip archive files are supported")


def _safe_archive_member_name(name: str) -> str:
    normalized = name.replace("\\", "/").strip()
    if not normalized or normalized.startswith("/") or normalized.startswith("../") or "/../" in normalized or normalized == "..":
        raise ValueError("INVALID_ARCHIVE_PATH: archive path is unsafe")
    return normalized


def _safe_target_path(target_path: str) -> str:
    value = _safe_archive_member_name(target_path)
    if value.endswith("/"):
        raise ValueError("INVALID_TARGET_PATH: target path must be a file")
    return value


def build_archive_tree(package: EnvPackage) -> dict:
    import tarfile
    import zipfile

    path = _package_file_path(package)
    kind = _archive_kind(path)
    items: list[dict] = []
    if kind == "tar":
        with tarfile.open(path, "r:*") as archive:
            for member in archive.getmembers():
                name = _safe_archive_member_name(member.name)
                items.append({
                    "path": name,
                    "name": Path(name).name,
                    "size": int(member.size or 0),
                    "is_dir": member.isdir(),
                    "mtime": int(member.mtime or 0),
                    "highlight": Path(name).name in {"install.sh", "verify.sh", "README.md"} or name.endswith((".service", ".conf")),
                })
    else:
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist():
                name = _safe_archive_member_name(info.filename)
                items.append({
                    "path": name,
                    "name": Path(name).name,
                    "size": int(info.file_size or 0),
                    "is_dir": info.is_dir(),
                    "mtime": 0,
                    "highlight": Path(name).name in {"install.sh", "verify.sh", "README.md"} or name.endswith((".service", ".conf")),
                })
    items.sort(key=lambda item: (not item["is_dir"], item["path"]))
    warnings = []
    file_names = {item["path"] for item in items if not item["is_dir"]}
    base_names = {Path(name).name for name in file_names}
    if "install.sh" not in base_names:
        warnings.append("归档内未发现 install.sh")
    if "verify.sh" not in base_names:
        warnings.append("归档内未发现 verify.sh")
    return {"archive_type": kind, "file_name": package.file_name or path.name, "items": items, "warnings": warnings}



def ensure_new_package_version_available(session: Session, item: EnvPackage, version: str) -> None:
    exists = session.scalar(select(EnvPackage).where(EnvPackage.package_code == item.package_code, EnvPackage.version == version, EnvPackage.owner_id == item.owner_id))
    if exists:
        raise ValueError("PACKAGE_VERSION_EXISTS: package_code/version already exists for owner")

def _copy_env_package(item: EnvPackage, *, version: str, username: str) -> EnvPackage:
    return EnvPackage(
        package_code=item.package_code,
        name=item.name,
        package_type=item.package_type,
        version=version,
        file_uri=item.file_uri,
        file_name=item.file_name,
        checksum_type=item.checksum_type,
        checksum=item.checksum,
        check_script=item.check_script,
        install_script=item.install_script,
        verify_script=item.verify_script,
        uninstall_script=item.uninstall_script,
        depends_on=item.depends_on,
        install_order=item.install_order,
        requires_root=item.requires_root,
        requires_reboot=item.requires_reboot,
        offline_supported=item.offline_supported,
        status=item.status,
        visibility=item.visibility,
        owner_id=item.owner_id,
        created_by=username,
        updated_by=username,
    )


def copy_package_profiles(session: Session, source_package_id: str, target_package_id: str) -> None:
    for row in session.scalars(select(EnvPackageCompatibility).where(EnvPackageCompatibility.package_id == source_package_id)):
        session.add(EnvPackageCompatibility(package_id=target_package_id, device_profile_id=row.device_profile_id))


def package_usage_count(session: Session, package_id: str) -> int:
    return int(session.scalar(select(func.count()).select_from(DeliveryBundleItem).where(DeliveryBundleItem.package_id == package_id)) or 0)


def _script_diff(old: dict, new: dict) -> dict:
    import difflib
    result = {}
    for key in ["install_script", "verify_script", "uninstall_script"]:
        before = (old.get(key) or "").replace("\r\n", "\n").splitlines()
        after = (new.get(key) or "").replace("\r\n", "\n").splitlines()
        if before != after:
            result[key] = "\n".join(difflib.unified_diff(before, after, fromfile=f"old/{key}", tofile=f"new/{key}", lineterm=""))
    return result


def edit_env_package_scripts(session: Session, item: EnvPackage, payload, username: str) -> tuple[EnvPackage, EnvPackageRevision]:
    save_mode = (payload.save_mode or "in_place").strip()
    if save_mode not in {"in_place", "new_version"}:
        raise ValueError("INVALID_SAVE_MODE: save_mode must be in_place or new_version")
    new_values = {
        "install_script": payload.install_script or "",
        "verify_script": payload.verify_script or "",
        "uninstall_script": payload.uninstall_script or "",
    }
    old_values = {
        "install_script": item.install_script or "",
        "verify_script": item.verify_script or "",
        "uninstall_script": item.uninstall_script or "",
    }
    diff = _script_diff(old_values, new_values)
    if save_mode == "new_version":
        if not payload.new_version:
            raise ValueError("NEW_VERSION_REQUIRED: new_version is required")
        ensure_new_package_version_available(session, item, payload.new_version)
        target = _copy_env_package(item, version=payload.new_version, username=username)
        target.install_script = new_values["install_script"]
        target.verify_script = new_values["verify_script"]
        target.uninstall_script = new_values["uninstall_script"]
        session.add(target)
        session.flush()
        copy_package_profiles(session, item.id, target.id)
    else:
        target = item
        target.install_script = new_values["install_script"]
        target.verify_script = new_values["verify_script"]
        target.uninstall_script = new_values["uninstall_script"]
        target.updated_by = username
    revision = _record_package_revision(
        session,
        package_id=target.id,
        operation_type="script_edit",
        save_mode=save_mode,
        old_file_uri=item.file_uri,
        new_file_uri=target.file_uri,
        old_checksum=item.checksum,
        new_checksum=target.checksum,
        changed_files=[key for key in diff.keys()],
        script_diff=diff,
        remark=payload.remark,
        username=username,
    )
    return target, revision


def _replace_archive_file(source: Path, replacement, target_path: str, owner: str) -> tuple[Path, str, str]:
    import shutil
    import tarfile
    import tempfile
    import zipfile

    target_member = _safe_target_path(target_path)
    kind = _archive_kind(source)
    out_dir = source.parent
    suffix = "".join(source.suffixes) or source.suffix or ".archive"
    fd, tmp_name = tempfile.mkstemp(prefix=f"{source.stem}-replace-", suffix=suffix, dir=out_dir)
    __import__("os").close(fd)
    Path(tmp_name).unlink(missing_ok=True)
    replaced = False
    if kind == "tar":
        with tarfile.open(source, "r:*") as src, tarfile.open(tmp_name, "w:gz") as dst:
            for member in src.getmembers():
                member_name = _safe_archive_member_name(member.name)
                if member_name == target_member:
                    info = tarfile.TarInfo(member_name)
                    data = replacement.file.read()
                    info.size = len(data)
                    info.mtime = int(Path(source).stat().st_mtime)
                    dst.addfile(info, fileobj=__import__('io').BytesIO(data))
                    replaced = True
                    if member.isfile():
                        continue
                if member_name == target_member:
                    continue
                extracted = src.extractfile(member) if member.isfile() else None
                dst.addfile(member, extracted)
                if extracted:
                    extracted.close()
    else:
        with zipfile.ZipFile(source) as src, zipfile.ZipFile(tmp_name, "w", compression=zipfile.ZIP_DEFLATED) as dst:
            for info in src.infolist():
                member_name = _safe_archive_member_name(info.filename)
                if member_name == target_member:
                    dst.writestr(member_name, replacement.file.read())
                    replaced = True
                else:
                    dst.writestr(info, src.read(info.filename))
    if not replaced:
        Path(tmp_name).unlink(missing_ok=True)
        raise ValueError("TARGET_FILE_NOT_FOUND: target path was not found in archive")
    final = out_dir / f"{source.stem}-edited-{uuid.uuid4().hex[:8]}{suffix}"
    shutil.move(tmp_name, final)
    return final, target_member, _sha256_file(final)


def replace_env_package_file(session: Session, item: EnvPackage, *, replacement, target_path: str, save_mode: str, new_version: str, remark: str, username: str) -> tuple[EnvPackage, EnvPackageRevision]:
    save_mode = (save_mode or "in_place").strip()
    if save_mode not in {"in_place", "new_version"}:
        raise ValueError("INVALID_SAVE_MODE: save_mode must be in_place or new_version")
    if save_mode == "new_version" and not new_version:
        raise ValueError("NEW_VERSION_REQUIRED: new_version is required")
    if save_mode == "new_version":
        ensure_new_package_version_available(session, item, new_version)
    old_path = _package_file_path(item)
    old_file_uri = item.file_uri
    old_checksum = item.checksum
    new_path, member, checksum = _replace_archive_file(old_path, replacement, target_path, item.owner_id)
    if save_mode == "new_version":
        target = _copy_env_package(item, version=new_version, username=username)
        target.file_uri = f"filesystem://{new_path.as_posix()}"
        target.file_name = new_path.name
        target.checksum_type = "sha256"
        target.checksum = checksum
        session.add(target)
        session.flush()
        copy_package_profiles(session, item.id, target.id)
    else:
        target = item
        target.file_uri = f"filesystem://{new_path.as_posix()}"
        target.file_name = new_path.name
        target.checksum_type = "sha256"
        target.checksum = checksum
        target.updated_by = username
    revision = _record_package_revision(
        session,
        package_id=target.id,
        operation_type="file_replace",
        save_mode=save_mode,
        old_file_uri=old_file_uri,
        new_file_uri=target.file_uri,
        old_checksum=old_checksum,
        new_checksum=checksum,
        changed_files=[member],
        script_diff={},
        remark=remark,
        username=username,
    )
    return target, revision

def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _package_reference(package: EnvPackage) -> dict:
    return {
        "package_id": package.id,
        "package_code": package.package_code,
        "version": package.version,
        "file_uri": package.file_uri,
        "file_name": package.file_name,
        "checksum_type": package.checksum_type,
        "checksum": package.checksum,
    }


def package_requires_payload_file(package: EnvPackage) -> bool:
    return package.package_type != "command_step"


def package_payload_problem(package: EnvPackage) -> str:
    if not package_requires_payload_file(package):
        return ""
    if not package.file_uri:
        return "未配置 file_uri"
    if not package.file_uri.startswith("filesystem://"):
        return "非本地文件 URI，无法打入离线交付包"
    source = Path(package.file_uri[len("filesystem://"):]).expanduser().resolve()
    if not source.exists() or not source.is_file():
        return f"本地文件不存在：{source}"
    return ""



def _extract_application_package_payload(package: EnvPackage, step_dir: Path) -> tuple[str, str]:
    import tarfile
    if package.package_type != "application_package":
        return _copy_package_file(package, step_dir)
    if not package.file_uri:
        return "missing", "应用包未配置 file_uri"
    if not package.file_uri.startswith("filesystem://"):
        return "referenced", f"应用包非本地文件 URI，未展开：{package.file_uri}"
    source = Path(package.file_uri[len("filesystem://"):]).expanduser().resolve()
    if not source.exists() or not source.is_file():
        return "missing", f"应用包本地文件不存在：{source}"
    if not tarfile.is_tarfile(source):
        return "missing", f"应用包必须是 tar/tar.gz 归档才能展开为交付目录：{source}"
    with tarfile.open(source, "r:*") as tar:
        def safe_members():
            for member in tar.getmembers():
                member_path = (step_dir / member.name).resolve()
                if not str(member_path).startswith(str(step_dir.resolve())):
                    raise ValueError(f"应用包归档包含非法路径：{member.name}")
                yield member
        tar.extractall(step_dir, members=safe_members())
    children = [item for item in step_dir.iterdir() if item.name not in {"install.sh", "verify.sh"}]
    dirs = [item for item in children if item.is_dir()]
    # 如果归档只有一个顶层目录，展开其内容到 step_dir，让实施人员看到的目录更干净。
    if len(dirs) == 1 and not (step_dir / "install.sh").exists() and not (step_dir / "verify.sh").exists():
        top = dirs[0]
        for child in list(top.iterdir()):
            child.rename(step_dir / child.name)
        top.rmdir()
    for script_name in ["install.sh", "verify.sh"]:
        script = step_dir / script_name
        if script.exists():
            script.chmod(script.stat().st_mode | 0o755)
    return "expanded", f"已展开应用包 {source.name} 到步骤目录"

def _copy_package_file(package: EnvPackage, target_dir: Path) -> tuple[str, str]:
    if not package.file_uri:
        return "missing", "未配置 file_uri，只写入引用清单"
    if not package.file_uri.startswith("filesystem://"):
        return "referenced", f"非本地文件 URI，未复制：{package.file_uri}"
    source = Path(package.file_uri[len("filesystem://"):]).expanduser().resolve()
    if not source.exists() or not source.is_file():
        return "missing", f"本地文件不存在：{source}"
    name = package.file_name or source.name
    dest = target_dir / name
    dest.write_bytes(source.read_bytes())
    return "copied", f"已复制 {source} -> {dest.name}"






def package_execution_mode(package: EnvPackage) -> str:
    if (package.package_type or '').strip() == 'application_package':
        return 'resource_only'
    return 'auto'


def package_manual_instructions(package: EnvPackage, step_dir_rel: str) -> dict:
    execution_mode = package_execution_mode(package)
    bundle_root_var = "${BUNDLE_ROOT}"
    manual_root = f"{bundle_root_var}/{step_dir_rel}"
    install_command = f"cd {manual_root} && bash install.sh"
    verify_command = f"cd {manual_root} && bash verify.sh"
    display_install_command = f"cd {step_dir_rel} && bash install.sh"
    display_verify_command = f"cd {step_dir_rel} && bash verify.sh"
    notes = [
        "该安装项为应用包资源，只随交付包携带，不进入交付包根 install.sh / run_bundle.py 自动安装流程。",
        "应用包部署方式以交付包内部署文档为准；系统只负责把原始应用资源放入 application_packages 目录。",
        "如果需要现场安装，请实施人员按部署文档进入该应用包目录执行对应命令。",
        "应用包目录保留原始内容和交互逻辑，不再使用 _payload_extract 包装层。",
    ] if execution_mode == "resource_only" else []
    return {
        "execution_mode": execution_mode,
        "manual_install": execution_mode == "resource_only",
        "resource_only": execution_mode == "resource_only",
        "manual_reason": "application_package is carried as deployment resource only" if execution_mode == "resource_only" else "",
        "manual_title": f"{package.name}（应用包资源）" if execution_mode == "resource_only" else "",
        "manual_package_path": step_dir_rel,
        "manual_payload_path": step_dir_rel,
        "manual_install_command": install_command,
        "manual_verify_command": verify_command,
        "display_install_command": display_install_command,
        "display_verify_command": display_verify_command,
        "manual_notes": notes,
        "manual_runner_note": "应用包不受交付包根 install.sh / run_bundle.py 管理；请按部署文档人工处理。" if execution_mode == "resource_only" else "",
    }

def script_self_call_problem(script: str, script_name: str) -> str:
    lines = []
    for raw in (script or "").replace("\r\n", "\n").split("\n"):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        lines.append(line)
    forbidden = {
        f"bash {script_name}",
        f"bash ./{script_name}",
        f"sh {script_name}",
        f"sh ./{script_name}",
        f"./{script_name}",
    }
    for line in lines:
        normalized = " ".join(line.split())
        command = normalized.split("||", 1)[0].split("&&", 1)[0].strip()
        if command in forbidden or command.startswith(tuple(item + " " for item in forbidden)):
            return f"外层 {script_name} 不能在步骤目录直接调用 {command}，会递归调用自身；文件型资产应先解压到 _payload_extract/<package_code>/ 再调用内层脚本"
    return ""


def _controller_install_script() -> str:
    return r'''#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATE_FILE="${ROOT_DIR}/state.json"
LOG_DIR="${ROOT_DIR}/logs"
mkdir -p "${LOG_DIR}"

if [ ! -f "${STATE_FILE}" ]; then
  cp "${ROOT_DIR}/state.template.json" "${STATE_FILE}"
fi

python3 "${ROOT_DIR}/scripts/run_bundle.py" "${ROOT_DIR}"
'''


def _runner_script() -> str:
    return r'''#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

root = Path(sys.argv[1]).resolve()
state_path = root / "state.json"
state_template_path = root / "state.template.json"
manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
if not state_path.exists() and state_template_path.exists():
    state_path.write_text(state_template_path.read_text(encoding="utf-8"), encoding="utf-8")
state = json.loads(state_path.read_text(encoding="utf-8"))
packages_state = state.setdefault("packages", {})
logs_dir = root / "logs"
logs_dir.mkdir(exist_ok=True)

def now():
    return datetime.now(timezone.utc).isoformat()

def save():
    state["updated_at"] = now()
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

def run_script(step_dir: Path, script_name: str, log_file: Path) -> int:
    script = step_dir / script_name
    if not script.exists():
        return 0
    with log_file.open("a", encoding="utf-8") as out:
        out.write(f"\n===== {now()} {script_name} =====\n")
        proc = subprocess.run(["bash", str(script)], cwd=str(step_dir), stdout=out, stderr=subprocess.STDOUT)
        return proc.returncode

for step in manifest.get("steps", []):
    code = step["package_code"]
    step_order = step.get("order") or step.get("step") or 0
    step_dir = root / step["path"]
    log_file = logs_dir / f"{int(step_order):03d}-{code}.log"
    pkg_state = packages_state.setdefault(code, {"status": "pending", "current_phase": "", "updated_at": ""})
    if pkg_state.get("status") == "success":
        continue
    for phase, script_name in [("install", "install.sh"), ("verify", "verify.sh")]:
        pkg_state.update({"status": "running", "current_phase": phase, "updated_at": now()})
        save()
        rc = run_script(step_dir, script_name, log_file)
        if rc != 0:
            pkg_state.update({"status": "failed", "current_phase": phase, "exit_code": rc, "updated_at": now(), "log_file": str(log_file.relative_to(root))})
            state["status"] = "failed"
            save()
            print(f"FAILED {code} phase={phase} rc={rc}; see {log_file}", file=sys.stderr)
            raise SystemExit(rc)
    pkg_state.update({"status": "success", "current_phase": "done", "exit_code": 0, "updated_at": now(), "log_file": str(log_file.relative_to(root))})
    save()

statuses = [item.get("status") for item in packages_state.values()]
if any(status == "failed" for status in statuses):
    state["status"] = "failed"
else:
    state["status"] = "success"
save()
print("delivery bundle install completed")
'''


def build_delivery_bundle_artifact(session: Session, bundle: DeliveryBundle, artifact_root: str, progress: Callable[[int, str, str], None] | None = None) -> DeliveryBundle:
    from datetime import datetime, timezone
    import shutil
    import tarfile

    bundle_items = list(session.scalars(select(DeliveryBundleItem).where(DeliveryBundleItem.bundle_id == bundle.id).order_by(DeliveryBundleItem.sort_order.asc())))
    packages = [session.get(EnvPackage, item.package_id) for item in bundle_items]
    packages = [item for item in packages if item is not None]
    if not packages:
        raise ValueError("delivery bundle requires at least one package")
    if progress:
        progress(5, "prepare", "读取交付包编排和目标适配信息")

    device = session.get(InferenceDevice, bundle.target_device_id) if bundle.target_device_id else None
    profile = session.get(EnvDeviceProfile, bundle.target_profile_id) if bundle.target_profile_id else None
    manifest = build_delivery_manifest(bundle=bundle, packages=packages, device=device, profile=profile)

    root = Path(artifact_root).expanduser().resolve()
    work_root = root / "work" / bundle.id
    out_root = root / "artifacts"
    if work_root.exists():
        shutil.rmtree(work_root)
    work_root.mkdir(parents=True, exist_ok=True)
    out_root.mkdir(parents=True, exist_ok=True)

    log_lines = [f"开始构建交付包 {bundle.bundle_code} {bundle.version}"]
    missing_payloads = [(package.package_code, problem) for package in packages if (problem := package_payload_problem(package))]
    if missing_payloads:
        details = "; ".join(f"[{code}] {problem}" for code, problem in missing_payloads)
        raise ValueError(f"交付包制作失败：环境包文件缺失或不可打包：{details}")
    references = []
    steps = []
    application_resources = []
    auto_index = 0
    for index, package in enumerate(packages, start=1):
        if progress:
            percent = min(85, 10 + int(index / max(len(packages), 1) * 70))
            progress(percent, "copy-package", f"正在处理第 {index}/{len(packages)} 个安装项 {package.package_code}")
        if package.package_type == "application_package":
            resource_dir_name = f"{len(application_resources) + 1:03d}-{_safe_name(package.package_code)}"
            resource_dir = work_root / "application_packages" / resource_dir_name
            resource_dir.mkdir(parents=True, exist_ok=True)
            copy_status, copy_message = _extract_application_package_payload(package, resource_dir)
            manual = package_manual_instructions(package, f"application_packages/{resource_dir_name}")
            resource = {
                "order": len(application_resources) + 1,
                "package_id": package.id,
                "package_code": package.package_code,
                "name": package.name,
                "version": package.version,
                "package_type": package.package_type,
                "path": f"application_packages/{resource_dir_name}",
                "deployment_doc_required": True,
                **manual,
            }
            application_resources.append(resource)
            ref = _package_reference(package)
            ref.update({"copy_status": copy_status, "path": f"application_packages/{resource_dir_name}", "resource_only": True})
        else:
            auto_index += 1
            step_dir_name = f"{auto_index:03d}-{_safe_name(package.package_code)}"
            step_dir = work_root / "packages" / step_dir_name
            step_dir.mkdir(parents=True, exist_ok=True)
            _write_executable(step_dir / "install.sh", package.install_script or "#!/usr/bin/env bash\nset -euo pipefail\necho 'missing install script' >&2\nexit 2\n")
            _write_executable(step_dir / "verify.sh", package.verify_script or "#!/usr/bin/env bash\nset -euo pipefail\necho 'missing verify script' >&2\nexit 2\n")
            copy_status, copy_message = _copy_package_file(package, step_dir)
            ref = _package_reference(package)
            ref.update({"copy_status": copy_status, "path": f"packages/{step_dir_name}", "resource_only": False})
            manual = package_manual_instructions(package, f"packages/{step_dir_name}")
            steps.append({
                "order": auto_index,
                "package_id": package.id,
                "package_code": package.package_code,
                "name": package.name,
                "version": package.version,
                "package_type": package.package_type,
                "path": f"packages/{step_dir_name}",
                "requires_root": package.requires_root,
                "requires_reboot": package.requires_reboot,
                "depends_on": package.depends_on,
                **manual,
            })
        log_lines.append(f"[{package.package_code}] {copy_message}")
        if copy_status == "missing" and package_requires_payload_file(package):
            raise ValueError(f"交付包制作失败：[{package.package_code}] {copy_message}")
        references.append(ref)

    artifact_manifest = {**manifest, "steps": steps, "application_resources": application_resources, "package_references": references}
    if progress:
        progress(88, "write-manifest", "写入 manifest、状态模板和总控脚本")
    (work_root / "manifest.json").write_text(json.dumps(artifact_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    state_template = {"status": "pending", "bundle_code": bundle.bundle_code, "version": bundle.version, "updated_at": "", "packages": {step["package_code"]: {"status": "pending", "current_phase": "", "updated_at": "", "execution_mode": step.get("execution_mode", "auto")} for step in steps}}
    (work_root / "state.template.json").write_text(json.dumps(state_template, ensure_ascii=False, indent=2), encoding="utf-8")
    readme_lines = [
        f"# {bundle.name}",
        "",
        "## 自动安装",
        "",
        "执行：`bash install.sh`。",
        "",
        "只有 `packages/` 下的环境/依赖/命令步骤会进入自动安装链：每个自动小包执行 `install.sh -> verify.sh`；失败后重新执行会从失败小包继续；已 success 的小包会跳过。",
    ]
    if application_resources:
        readme_lines.extend([
            "",
            "## 应用包资源",
            "",
            "`application_packages/` 下的应用包只随交付包携带，不受根目录 `install.sh` 和 `scripts/run_bundle.py` 管理，不会自动安装，也不会写入自动安装状态。",
            "应用包部署方式以交付包内的部署文档为准；后续系统会支持上传部署文档并随交付包输出。",
            "",
            "当前随包应用资源：",
        ])
        readme_lines.extend(f"- `{item['path']}`：{item['name']} {item['version']}" for item in application_resources)
    (work_root / "README.md").write_text("\n".join(readme_lines) + "\n", encoding="utf-8")
    (work_root / "install.sh").write_text(_controller_install_script(), encoding="utf-8")
    (work_root / "install.sh").chmod(0o755)
    scripts_dir = work_root / "scripts"
    scripts_dir.mkdir(exist_ok=True)
    (scripts_dir / "run_bundle.py").write_text(_runner_script(), encoding="utf-8")
    (scripts_dir / "run_bundle.py").chmod(0o755)

    artifact_name = f"{_safe_name(bundle.bundle_code)}-{_safe_name(bundle.version)}.tar.gz"
    artifact_path = out_root / artifact_name
    if artifact_path.exists():
        artifact_path.unlink()
    if progress:
        progress(94, "archive", f"正在生成归档 {artifact_name}")
    with tarfile.open(artifact_path, "w:gz") as tar:
        tar.add(work_root, arcname=f"{_safe_name(bundle.bundle_code)}-{_safe_name(bundle.version)}")

    bundle.manifest_json = json.dumps(artifact_manifest, ensure_ascii=False, indent=2)
    bundle.build_status = "success"
    bundle.status = "built"
    bundle.artifact_uri = f"filesystem://{artifact_path}"
    bundle.artifact_name = artifact_name
    bundle.artifact_size = artifact_path.stat().st_size
    bundle.artifact_checksum = f"sha256:{_sha256_file(artifact_path)}"
    bundle.build_log = "\n".join(log_lines)
    bundle.built_at = datetime.now(timezone.utc)
    session.flush()
    return bundle


def package_workspace_root() -> Path:
    return Path(settings.delivery_bundle_artifact_root).expanduser().resolve().parent / "package-workspaces"


def _workspace_dir(package_id: str, workspace_id: str) -> Path:
    safe_workspace = _safe_name(workspace_id)
    if not safe_workspace or safe_workspace != workspace_id:
        raise ValueError("INVALID_WORKSPACE_ID: workspace id is unsafe")
    return package_workspace_root() / package_id / workspace_id


def _workspace_meta_path(workspace: Path) -> Path:
    return workspace / ".opspaw-workspace.json"


def _workspace_files_root(workspace: Path) -> Path:
    return workspace / "files"


def _read_workspace_meta(workspace: Path) -> dict:
    meta = _workspace_meta_path(workspace)
    if not meta.exists():
        raise FileNotFoundError("workspace not found")
    return json.loads(meta.read_text(encoding="utf-8"))


def _workspace_path(workspace: Path, rel_path: str = "") -> Path:
    root = _workspace_files_root(workspace).resolve()
    rel = (rel_path or "").replace("\\", "/").strip("/")
    if rel:
        _safe_archive_member_name(rel)
    target = (root / rel).resolve()
    if target != root and not str(target).startswith(str(root) + "/"):
        raise ValueError("INVALID_WORKSPACE_PATH: workspace path is unsafe")
    return target


def _initialize_script_workspace(package: EnvPackage, workspace: Path) -> None:
    import shutil

    files_root = _workspace_files_root(workspace)
    if files_root.exists():
        shutil.rmtree(files_root)
    files_root.mkdir(parents=True, exist_ok=True)
    (files_root / "install.sh").write_text(package.install_script or "#!/usr/bin/env bash\nset -euo pipefail\n\n", encoding="utf-8")
    (files_root / "verify.sh").write_text(package.verify_script or "#!/usr/bin/env bash\nset -euo pipefail\n\n", encoding="utf-8")
    if package.check_script:
        (files_root / "precheck.sh").write_text(package.check_script, encoding="utf-8")
    (files_root / "README.md").write_text(
        "# 命令步骤资产\n\n"
        "该工作区由环境包脚本字段生成，不依赖归档文件。\n"
        "- install.sh：安装/执行命令脚本，提交后回写 install_script。\n"
        "- verify.sh：成功检查脚本，提交后回写 verify_script。\n"
        "- precheck.sh：可选前置检查脚本，提交后回写 check_script。\n",
        encoding="utf-8",
    )


def _extract_archive_to_workspace(package: EnvPackage, workspace: Path) -> None:
    import shutil
    import tarfile
    import zipfile

    source = _package_file_path(package)
    kind = _archive_kind(source)
    files_root = _workspace_files_root(workspace)
    if files_root.exists():
        shutil.rmtree(files_root)
    files_root.mkdir(parents=True, exist_ok=True)
    if kind == "tar":
        with tarfile.open(source, "r:*") as archive:
            for member in archive.getmembers():
                name = _safe_archive_member_name(member.name)
                dest = (files_root / name).resolve()
                if not str(dest).startswith(str(files_root.resolve()) + "/") and dest != files_root.resolve():
                    raise ValueError(f"INVALID_ARCHIVE_PATH: {member.name}")
            archive.extractall(files_root)
    else:
        with zipfile.ZipFile(source) as archive:
            for info in archive.infolist():
                name = _safe_archive_member_name(info.filename)
                dest = (files_root / name).resolve()
                if not str(dest).startswith(str(files_root.resolve()) + "/") and dest != files_root.resolve():
                    raise ValueError(f"INVALID_ARCHIVE_PATH: {info.filename}")
            archive.extractall(files_root)


def create_package_workspace(package: EnvPackage, username: str) -> dict:
    workspace_id = uuid.uuid4().hex
    workspace = _workspace_dir(package.id, workspace_id)
    workspace.mkdir(parents=True, exist_ok=True)
    workspace_mode = "archive"
    if package.file_uri:
        _extract_archive_to_workspace(package, workspace)
    else:
        workspace_mode = "script_only"
        _initialize_script_workspace(package, workspace)
    meta = {
        "workspace_id": workspace_id,
        "package_id": package.id,
        "package_code": package.package_code,
        "version": package.version,
        "owner_id": package.owner_id,
        "created_by": username,
        "source_file_uri": package.file_uri,
        "source_checksum": package.checksum,
        "workspace_mode": workspace_mode,
    }
    _workspace_meta_path(workspace).write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"workspace_id": workspace_id, "package_id": package.id, "root": "", "meta": meta}


def assert_workspace_access(package: EnvPackage, workspace_id: str, username: str, role: str) -> Path:
    workspace = _workspace_dir(package.id, workspace_id)
    meta = _read_workspace_meta(workspace)
    if meta.get("package_id") != package.id:
        raise ValueError("WORKSPACE_PACKAGE_MISMATCH: workspace does not belong to package")
    if not can_edit_package(package, username, role):
        raise PermissionError("only owner or admin can edit package workspace")
    return workspace


def workspace_content_model(package: EnvPackage, workspace_id: str, rel_path: str, username: str, role: str, include_content: bool = True) -> dict:
    import base64
    workspace = assert_workspace_access(package, workspace_id, username, role)
    target = _workspace_path(workspace, rel_path)
    if not target.exists():
        raise FileNotFoundError(f"workspace path not found: {rel_path}")
    root = _workspace_files_root(workspace).resolve()
    api_path = "" if target.resolve() == root else str(target.resolve().relative_to(root)).replace("\\", "/")
    if target.is_dir():
        children = []
        if include_content:
            for child in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
                if child.name == ".opspaw-workspace.json":
                    continue
                child_rel = str(child.resolve().relative_to(root)).replace("\\", "/")
                children.append({
                    "name": child.name,
                    "path": child_rel,
                    "type": "directory" if child.is_dir() else "file",
                    "writable": True,
                    "created": "",
                    "last_modified": "",
                    "mimetype": None,
                    "content": None,
                    "format": None,
                })
        return {"name": target.name or "", "path": api_path, "type": "directory", "writable": True, "content": children, "format": "json"}
    data = target.read_bytes()
    content = None
    fmt = None
    if include_content:
        try:
            content = data.decode("utf-8")
            fmt = "text"
        except UnicodeDecodeError:
            content = base64.b64encode(data).decode("ascii")
            fmt = "base64"
    return {"name": target.name, "path": api_path, "type": "file", "writable": True, "size": len(data), "content": content, "format": fmt, "mimetype": None}


def save_workspace_content(package: EnvPackage, workspace_id: str, rel_path: str, payload, username: str, role: str) -> dict:
    import base64
    workspace = assert_workspace_access(package, workspace_id, username, role)
    target = _workspace_path(workspace, rel_path)
    if payload.type == "directory":
        target.mkdir(parents=True, exist_ok=True)
        return workspace_content_model(package, workspace_id, rel_path, username, role)
    target.parent.mkdir(parents=True, exist_ok=True)
    if payload.format == "base64":
        target.write_bytes(base64.b64decode(payload.content or ""))
    else:
        target.write_text(payload.content or "", encoding="utf-8")
    return workspace_content_model(package, workspace_id, rel_path, username, role)


def create_workspace_content(package: EnvPackage, workspace_id: str, rel_path: str, payload, username: str, role: str) -> dict:
    name = payload.name or ("Untitled Folder" if payload.type == "directory" else "untitled.txt")
    _safe_archive_member_name(name)
    parent = rel_path.strip("/")
    child_path = f"{parent}/{name}" if parent else name
    return save_workspace_content(package, workspace_id, child_path, payload, username, role)


def rename_workspace_content(package: EnvPackage, workspace_id: str, rel_path: str, new_path: str, username: str, role: str) -> dict:
    workspace = assert_workspace_access(package, workspace_id, username, role)
    source = _workspace_path(workspace, rel_path)
    dest = _workspace_path(workspace, new_path)
    if not source.exists():
        raise FileNotFoundError(f"workspace path not found: {rel_path}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    source.rename(dest)
    return workspace_content_model(package, workspace_id, new_path, username, role)


def delete_workspace_content(package: EnvPackage, workspace_id: str, rel_path: str, username: str, role: str) -> None:
    import shutil
    workspace = assert_workspace_access(package, workspace_id, username, role)
    target = _workspace_path(workspace, rel_path)
    if not target.exists():
        raise FileNotFoundError(f"workspace path not found: {rel_path}")
    if target == _workspace_files_root(workspace).resolve():
        raise ValueError("INVALID_WORKSPACE_PATH: cannot delete workspace root")
    if target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink()


def _archive_workspace(workspace: Path, package: EnvPackage) -> tuple[Path, str]:
    import tarfile
    out_dir = Path(settings.env_package_upload_root).expanduser().resolve() / package.owner_id
    out_dir.mkdir(parents=True, exist_ok=True)
    artifact_name = f"{_safe_name(package.package_code)}-{_safe_name(package.version)}-workspace-{uuid.uuid4().hex[:8]}.tar.gz"
    artifact_path = out_dir / artifact_name
    files_root = _workspace_files_root(workspace)
    with tarfile.open(artifact_path, "w:gz") as tar:
        for child in sorted(files_root.iterdir(), key=lambda p: p.name.lower()):
            tar.add(child, arcname=child.name)
    return artifact_path, _sha256_file(artifact_path)


def commit_package_workspace(session: Session, item: EnvPackage, workspace_id: str, *, save_mode: str, new_version: str, remark: str, username: str, role: str) -> tuple[EnvPackage, EnvPackageRevision]:
    workspace = assert_workspace_access(item, workspace_id, username, role)
    meta = _read_workspace_meta(workspace)
    save_mode = (save_mode or "in_place").strip()
    if save_mode not in {"in_place", "new_version"}:
        raise ValueError("INVALID_SAVE_MODE: save_mode must be in_place or new_version")
    if save_mode == "new_version":
        if not new_version:
            raise ValueError("NEW_VERSION_REQUIRED: new_version is required")
        ensure_new_package_version_available(session, item, new_version)
    old_file_uri = item.file_uri
    old_checksum = item.checksum
    old_scripts = {"install_script": item.install_script or "", "verify_script": item.verify_script or "", "check_script": item.check_script or ""}

    if save_mode == "new_version":
        target = _copy_env_package(item, version=new_version, username=username)
        session.add(target)
        session.flush()
        copy_package_profiles(session, item.id, target.id)
    else:
        target = item

    if meta.get("workspace_mode") == "script_only":
        files_root = _workspace_files_root(workspace)
        install_file = files_root / "install.sh"
        verify_file = files_root / "verify.sh"
        precheck_file = files_root / "precheck.sh"
        target.install_script = install_file.read_text(encoding="utf-8") if install_file.exists() else ""
        target.verify_script = verify_file.read_text(encoding="utf-8") if verify_file.exists() else ""
        target.check_script = precheck_file.read_text(encoding="utf-8") if precheck_file.exists() else ""
        target.updated_by = username
        new_scripts = {"install_script": target.install_script or "", "verify_script": target.verify_script or "", "check_script": target.check_script or ""}
        changed = [key for key, old in old_scripts.items() if old != new_scripts.get(key, "")]
        revision = _record_package_revision(
            session,
            package_id=target.id,
            operation_type="script_workspace_commit",
            save_mode=save_mode,
            old_file_uri=old_file_uri,
            new_file_uri=target.file_uri,
            old_checksum=old_checksum,
            new_checksum=target.checksum,
            changed_files=changed or ["workspace"],
            script_diff=_script_diff(old_scripts, new_scripts),
            remark=remark,
            username=username,
        )
        return target, revision

    archive_path, checksum = _archive_workspace(workspace, item)
    target.file_uri = f"filesystem://{archive_path.as_posix()}"
    target.file_name = archive_path.name
    target.checksum_type = "sha256"
    target.checksum = checksum
    target.updated_by = username
    revision = _record_package_revision(
        session,
        package_id=target.id,
        operation_type="workspace_commit",
        save_mode=save_mode,
        old_file_uri=old_file_uri,
        new_file_uri=target.file_uri,
        old_checksum=old_checksum,
        new_checksum=checksum,
        changed_files=["workspace"],
        script_diff={},
        remark=remark,
        username=username,
    )
    return target, revision


def delete_package_workspace(package: EnvPackage, workspace_id: str, username: str, role: str) -> None:
    import shutil
    workspace = assert_workspace_access(package, workspace_id, username, role)
    shutil.rmtree(workspace, ignore_errors=True)
