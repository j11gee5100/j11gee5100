from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.trace import get_trace_id
from app.db.session import session_scope
from app.models import DeliveryBundle, DeliveryBundleBuildJob, DeliveryBundleItem, EnvDeviceProfile, EnvPackage, InferenceDevice, McpToolCallAudit, ProbeResult
from app.schemas.environment_package import CreateEnvPackageRequest, CreateProbeResultRequest, UpdateEnvPackageRequest
from app.services.environment_package_service import (
    build_delivery_bundle_response,
    build_delivery_bundle_job_response,
    build_delivery_bundle_artifact,
    build_delivery_manifest,
    build_device_profile_response,
    build_env_package_response,
    build_probe_result_response,
    ensure_env_package_seed_data,
    package_payload_problem,
    script_self_call_problem,
    extract_probe_fields,
    list_package_profiles,
    set_package_profiles,
)

MCP_PROTOCOL_VERSION = "2025-06-18"


class McpError(Exception):
    def __init__(self, code: str, message: str, *, retryable: bool = False, data: dict | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.data = data or {}


class ToolContext(BaseModel):
    operator_id: str = "zhangsan"
    operator_role: str = "user"
    session_id: str = ""
    client_name: str = "mcp-client"

    @property
    def is_admin(self) -> bool:
        return self.operator_role.lower() == "admin" or self.operator_id == "admin"


class ListDeviceProfilesInput(BaseModel):
    enabled: bool | None = True
    search: str = ""
    limit: int = Field(default=100, ge=1, le=500)


class ListEnvPackagesInput(BaseModel):
    profile_id: str = ""
    package_type: str = ""
    quality_status: str = ""
    include_shared: bool = True
    limit: int = Field(default=100, ge=1, le=500)


class RegisterEnvPackageInput(CreateEnvPackageRequest):
    storage_type: str = Field(default="local_upload")
    idempotency_key: str = Field(default="", max_length=128)


class UpdateEnvPackageInput(UpdateEnvPackageRequest):
    package_id: str
    storage_type: str | None = None


class ImportProbeResultInput(CreateProbeResultRequest):
    idempotency_key: str = Field(default="", max_length=128)


class PreviewDeliveryManifestInput(BaseModel):
    target_device_id: str = ""
    target_profile_id: str = ""
    package_ids: list[str] = Field(default_factory=list, min_length=1)


class CreateDeliveryBundleInput(BaseModel):
    bundle_code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    version: str = Field(default="1.0.0", max_length=128)
    bundle_type: str = Field(default="first_install", max_length=32)
    target_device_id: str = Field(default="", max_length=36)
    target_profile_id: str = Field(default="", max_length=36)
    package_ids: list[str] = Field(default_factory=list, min_length=1)
    idempotency_key: str = Field(default="", max_length=128)


class UpdateDeliveryBundleInput(BaseModel):
    bundle_id: str
    name: str | None = Field(default=None, max_length=128)
    version: str | None = Field(default=None, max_length=128)
    bundle_type: str | None = Field(default=None, max_length=32)
    target_device_id: str | None = Field(default=None, max_length=36)
    target_profile_id: str | None = Field(default=None, max_length=36)
    package_ids: list[str] | None = None


class AuditDeliveryBundleInput(BaseModel):
    bundle_id: str


class BuildDeliveryBundleArtifactInput(BaseModel):
    bundle_id: str


class CreateDeliveryBundleVersionInput(BaseModel):
    bundle_id: str
    bundle_code: str = Field(min_length=1, max_length=64)
    version: str = Field(min_length=1, max_length=128)
    name: str | None = Field(default=None, max_length=128)


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_model: type[BaseModel]
    handler: Callable[[ToolContext, BaseModel], dict]
    toolset: str
    risk_level: str
    annotations: dict[str, bool]


def allowed_toolsets() -> set[str]:
    raw = settings.mcp_toolsets or ""
    configured = {item.strip() for item in raw.split(",") if item.strip()}
    if settings.mcp_read_only:
        return {"profiles", "packages_read", "bundles_read", "audit"} & (configured or {"profiles", "packages_read", "bundles_read", "audit"})
    return configured or {"profiles", "packages_read", "bundles_read", "audit"}


def allowed_package_roots() -> list[dict]:
    roots = []
    for raw in (settings.mcp_allowed_package_roots or "").split(","):
        root = raw.strip()
        if not root:
            continue
        roots.append({"root_uri": f"filesystem://{root}", "path": root, "writable": False, "description": "Allowed package repository root"})
    return roots


def _json_hash(data: dict) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")).hexdigest()


def _is_visible_package(item: EnvPackage, ctx: ToolContext) -> bool:
    return ctx.is_admin or item.owner_id == ctx.operator_id or item.visibility == "shared"


def _can_edit_package(item: EnvPackage, ctx: ToolContext) -> bool:
    return ctx.is_admin or item.owner_id == ctx.operator_id


def _assert_allowed_file_uri(file_uri: str, storage_type: str) -> None:
    if storage_type != "filesystem_path" or not file_uri:
        return
    prefix = "filesystem://"
    if not file_uri.startswith(prefix):
        raise McpError("INVALID_FILE_URI", "filesystem_path storage requires filesystem:// URI")
    path = Path(file_uri[len(prefix):]).resolve()
    for root in allowed_package_roots():
        root_path = Path(root["path"]).resolve()
        try:
            path.relative_to(root_path)
            return
        except ValueError:
            continue
    raise McpError("FILE_OUTSIDE_ALLOWED_ROOTS", f"file_uri outside allowed roots: {file_uri}")


def _resolve_device(session: Session, value: str) -> InferenceDevice | None:
    if not value:
        return None
    return session.get(InferenceDevice, value) or session.scalar(select(InferenceDevice).where(InferenceDevice.device_code == value))


def _resolve_profile(session: Session, value: str) -> EnvDeviceProfile | None:
    if not value:
        return None
    return session.get(EnvDeviceProfile, value) or session.scalar(select(EnvDeviceProfile).where(EnvDeviceProfile.profile_code == value))


def _resolve_packages(session: Session, package_ids: list[str], ctx: ToolContext) -> list[EnvPackage]:
    packages: list[EnvPackage] = []
    for package_id in list(dict.fromkeys(package_ids)):
        item = session.get(EnvPackage, package_id)
        if not item:
            raise McpError("PACKAGE_NOT_FOUND", f"package not found: {package_id}")
        if not _is_visible_package(item, ctx):
            raise McpError("PACKAGE_NOT_VISIBLE", f"package is not visible: {package_id}")
        packages.append(item)
    return packages


def _bundle_items(session: Session, bundle_id: str) -> list[DeliveryBundleItem]:
    return list(session.scalars(select(DeliveryBundleItem).where(DeliveryBundleItem.bundle_id == bundle_id).order_by(DeliveryBundleItem.sort_order.asc())))


def _replace_bundle_items(session: Session, bundle_id: str, packages: list[EnvPackage]) -> None:
    session.execute(delete(DeliveryBundleItem).where(DeliveryBundleItem.bundle_id == bundle_id))
    for index, package in enumerate(packages):
        session.add(DeliveryBundleItem(bundle_id=bundle_id, package_id=package.id, sort_order=index + 1))


def _response(ok: bool, data: dict | None = None, error: dict | None = None) -> dict:
    return {"ok": ok, "data": data or {}, "error": error, "trace_id": get_trace_id()}


def tool_list_allowed_package_roots(ctx: ToolContext, payload: BaseModel) -> dict:
    return _response(True, {"items": allowed_package_roots()})


def tool_list_device_profiles(ctx: ToolContext, payload: BaseModel) -> dict:
    args = payload if isinstance(payload, ListDeviceProfilesInput) else ListDeviceProfilesInput()
    with session_scope() as session:
        ensure_env_package_seed_data(session)
        stmt = select(EnvDeviceProfile)
        if args.enabled is not None:
            stmt = stmt.where(EnvDeviceProfile.enabled.is_(args.enabled))
        if args.search:
            pattern = f"%{args.search.lower()}%"
            stmt = stmt.where(func.lower(EnvDeviceProfile.name).like(pattern) | func.lower(EnvDeviceProfile.profile_code).like(pattern))
        items = list(session.scalars(stmt.order_by(EnvDeviceProfile.profile_code.asc()).limit(args.limit)))
        return _response(True, {"items": [build_device_profile_response(item) for item in items]})


def tool_list_env_packages(ctx: ToolContext, payload: BaseModel) -> dict:
    args = payload if isinstance(payload, ListEnvPackagesInput) else ListEnvPackagesInput()
    with session_scope() as session:
        ensure_env_package_seed_data(session)
        stmt = select(EnvPackage)
        if not ctx.is_admin:
            if args.include_shared:
                stmt = stmt.where((EnvPackage.owner_id == ctx.operator_id) | (EnvPackage.visibility == "shared"))
            else:
                stmt = stmt.where(EnvPackage.owner_id == ctx.operator_id)
        if args.package_type:
            stmt = stmt.where(EnvPackage.package_type == args.package_type)
        items = list(session.scalars(stmt.order_by(EnvPackage.install_order.asc(), EnvPackage.updated_at.desc()).limit(args.limit)))
        responses = []
        for item in items:
            profiles = list_package_profiles(session, item.id)
            if args.profile_id and not any(profile["profile_id"] == args.profile_id or profile["profile_code"] == args.profile_id for profile in profiles):
                continue
            response = build_env_package_response(item, profiles)
            if args.quality_status and response["quality_status"] != args.quality_status:
                continue
            responses.append(response)
        return _response(True, {"items": responses})


def tool_register_env_package(ctx: ToolContext, payload: BaseModel) -> dict:
    args = payload if isinstance(payload, RegisterEnvPackageInput) else RegisterEnvPackageInput.model_validate(payload)
    _assert_allowed_file_uri(args.file_uri, args.storage_type)
    with session_scope() as session:
        ensure_env_package_seed_data(session)
        existing = session.scalar(select(EnvPackage).where(EnvPackage.package_code == args.package_code, EnvPackage.version == args.version, EnvPackage.owner_id == ctx.operator_id))
        if existing:
            return _response(True, {"item": build_env_package_response(existing, list_package_profiles(session, existing.id)), "idempotent": True})
        data = args.model_dump(exclude={"device_profile_ids", "storage_type", "idempotency_key"})
        item = EnvPackage(**data, owner_id=ctx.operator_id, created_by=ctx.operator_id, updated_by=ctx.operator_id)
        session.add(item)
        session.flush()
        ok, reason = set_package_profiles(session, item.id, args.device_profile_ids)
        if not ok:
            raise McpError("INVALID_DEVICE_PROFILE", reason)
        session.flush()
        return _response(True, {"item": build_env_package_response(item, list_package_profiles(session, item.id))})


def tool_update_env_package(ctx: ToolContext, payload: BaseModel) -> dict:
    args = payload if isinstance(payload, UpdateEnvPackageInput) else UpdateEnvPackageInput.model_validate(payload)
    if args.file_uri and args.storage_type:
        _assert_allowed_file_uri(args.file_uri, args.storage_type)
    with session_scope() as session:
        item = session.get(EnvPackage, args.package_id)
        if not item:
            raise McpError("PACKAGE_NOT_FOUND", f"package not found: {args.package_id}")
        if not _can_edit_package(item, ctx):
            raise McpError("PERMISSION_DENIED", "only owner or admin can edit package")
        fields = [field for field in UpdateEnvPackageRequest.model_fields.keys() if field != "device_profile_ids"]
        for field in fields:
            value = getattr(args, field, None)
            if value is not None:
                setattr(item, field, value)
        if args.device_profile_ids is not None:
            ok, reason = set_package_profiles(session, item.id, args.device_profile_ids)
            if not ok:
                raise McpError("INVALID_DEVICE_PROFILE", reason)
        item.updated_by = ctx.operator_id
        session.flush()
        return _response(True, {"item": build_env_package_response(item, list_package_profiles(session, item.id))})


def tool_import_probe_result(ctx: ToolContext, payload: BaseModel) -> dict:
    args = payload if isinstance(payload, ImportProbeResultInput) else ImportProbeResultInput.model_validate(payload)
    with session_scope() as session:
        ensure_env_package_seed_data(session)
        existing = session.scalar(select(ProbeResult).where(ProbeResult.result_code == args.result_code, ProbeResult.owner_id == ctx.operator_id))
        if existing:
            return _response(True, {"item": build_probe_result_response(existing), "idempotent": True})
        device_id = ""
        if args.device_id:
            device = _resolve_device(session, args.device_id)
            if not device:
                raise McpError("DEVICE_NOT_FOUND", f"device not found: {args.device_id}")
            device_id = device.id
        try:
            _raw, fields = extract_probe_fields(args.raw_json)
        except Exception as exc:
            raise McpError("INVALID_PROBE_JSON", str(exc)) from exc
        item = ProbeResult(result_code=args.result_code, name=args.name or args.result_code, device_id=device_id, raw_json=args.raw_json, owner_id=ctx.operator_id, created_by=ctx.operator_id, updated_by=ctx.operator_id, **fields)
        session.add(item)
        session.flush()
        return _response(True, {"item": build_probe_result_response(item)})


def _manifest_for_args(session: Session, ctx: ToolContext, args: PreviewDeliveryManifestInput, bundle: DeliveryBundle | None = None) -> dict:
    device = _resolve_device(session, args.target_device_id) if args.target_device_id else None
    if args.target_device_id and not device:
        raise McpError("DEVICE_NOT_FOUND", f"device not found: {args.target_device_id}")
    profile = _resolve_profile(session, args.target_profile_id) if args.target_profile_id else None
    if args.target_profile_id and not profile:
        raise McpError("DEVICE_PROFILE_NOT_FOUND", f"device profile not found: {args.target_profile_id}")
    packages = _resolve_packages(session, args.package_ids, ctx)
    temp_bundle = bundle or DeliveryBundle(bundle_code="preview", name="preview", version="", target_device_id=device.id if device else "", target_profile_id=profile.id if profile else "", status="draft", owner_id=ctx.operator_id)
    temp_bundle.target_device_id = device.id if device else ""
    temp_bundle.target_profile_id = profile.id if profile else ""
    return build_delivery_manifest(bundle=temp_bundle, packages=packages, device=device, profile=profile)


def tool_preview_delivery_manifest(ctx: ToolContext, payload: BaseModel) -> dict:
    args = payload if isinstance(payload, PreviewDeliveryManifestInput) else PreviewDeliveryManifestInput.model_validate(payload)
    with session_scope() as session:
        ensure_env_package_seed_data(session)
        return _response(True, {"manifest": _manifest_for_args(session, ctx, args)})


def tool_create_delivery_bundle_draft(ctx: ToolContext, payload: BaseModel) -> dict:
    args = payload if isinstance(payload, CreateDeliveryBundleInput) else CreateDeliveryBundleInput.model_validate(payload)
    with session_scope() as session:
        ensure_env_package_seed_data(session)
        existing = session.scalar(select(DeliveryBundle).where(DeliveryBundle.bundle_code == args.bundle_code, DeliveryBundle.owner_id == ctx.operator_id))
        if existing:
            return _response(True, {"item": build_delivery_bundle_response(session, existing), "idempotent": True})
        device = _resolve_device(session, args.target_device_id) if args.target_device_id else None
        if args.target_device_id and not device:
            raise McpError("DEVICE_NOT_FOUND", f"device not found: {args.target_device_id}")
        profile = _resolve_profile(session, args.target_profile_id) if args.target_profile_id else None
        if args.target_profile_id and not profile:
            raise McpError("DEVICE_PROFILE_NOT_FOUND", f"device profile not found: {args.target_profile_id}")
        packages = _resolve_packages(session, args.package_ids, ctx)
        item = DeliveryBundle(bundle_code=args.bundle_code, name=args.name, version=args.version, bundle_type=args.bundle_type, target_device_id=device.id if device else "", target_profile_id=profile.id if profile else "", status="draft", owner_id=ctx.operator_id, created_by=ctx.operator_id, updated_by=ctx.operator_id)
        item.manifest_json = json.dumps(build_delivery_manifest(bundle=item, packages=packages, device=device, profile=profile), ensure_ascii=False, indent=2)
        session.add(item)
        session.flush()
        _replace_bundle_items(session, item.id, packages)
        session.flush()
        return _response(True, {"item": build_delivery_bundle_response(session, item)})


def tool_update_delivery_bundle_composition(ctx: ToolContext, payload: BaseModel) -> dict:
    args = payload if isinstance(payload, UpdateDeliveryBundleInput) else UpdateDeliveryBundleInput.model_validate(payload)
    with session_scope() as session:
        item = session.get(DeliveryBundle, args.bundle_id) or session.scalar(select(DeliveryBundle).where(DeliveryBundle.bundle_code == args.bundle_id))
        if not item:
            raise McpError("BUNDLE_NOT_FOUND", f"delivery bundle not found: {args.bundle_id}")
        if not (ctx.is_admin or item.owner_id == ctx.operator_id):
            raise McpError("PERMISSION_DENIED", "delivery bundle is not visible")
        if item.lifecycle_status == "delivered":
            raise McpError("DELIVERED_BUNDLE_LOCKED", "delivered bundle cannot be modified; create a new version")
        if args.name is not None:
            item.name = args.name
        if args.version is not None:
            item.version = args.version
        if args.bundle_type is not None:
            item.bundle_type = args.bundle_type
        target_device_id = item.target_device_id if args.target_device_id is None else args.target_device_id
        target_profile_id = item.target_profile_id if args.target_profile_id is None else args.target_profile_id
        device = _resolve_device(session, target_device_id) if target_device_id else None
        if target_device_id and not device:
            raise McpError("DEVICE_NOT_FOUND", f"device not found: {target_device_id}")
        profile = _resolve_profile(session, target_profile_id) if target_profile_id else None
        if target_profile_id and not profile:
            raise McpError("DEVICE_PROFILE_NOT_FOUND", f"device profile not found: {target_profile_id}")
        package_ids = args.package_ids if args.package_ids is not None else [bundle_item.package_id for bundle_item in _bundle_items(session, item.id)]
        if not package_ids:
            raise McpError("EMPTY_DELIVERY_BUNDLE", "delivery bundle requires at least one package")
        packages = _resolve_packages(session, package_ids, ctx)
        item.target_device_id = device.id if device else ""
        item.target_profile_id = profile.id if profile else ""
        item.updated_by = ctx.operator_id
        item.manifest_json = json.dumps(build_delivery_manifest(bundle=item, packages=packages, device=device, profile=profile), ensure_ascii=False, indent=2)
        _replace_bundle_items(session, item.id, packages)
        session.flush()
        return _response(True, {"item": build_delivery_bundle_response(session, item)})


def tool_audit_delivery_bundle(ctx: ToolContext, payload: BaseModel) -> dict:
    args = payload if isinstance(payload, AuditDeliveryBundleInput) else AuditDeliveryBundleInput.model_validate(payload)
    findings = []
    with session_scope() as session:
        item = session.get(DeliveryBundle, args.bundle_id) or session.scalar(select(DeliveryBundle).where(DeliveryBundle.bundle_code == args.bundle_id))
        if not item:
            raise McpError("BUNDLE_NOT_FOUND", f"delivery bundle not found: {args.bundle_id}")
        if not (ctx.is_admin or item.owner_id == ctx.operator_id):
            raise McpError("PERMISSION_DENIED", "delivery bundle is not visible")
        profile_id = item.target_profile_id
        for bundle_item in _bundle_items(session, item.id):
            package = session.get(EnvPackage, bundle_item.package_id)
            if not package:
                findings.append({"level": "error", "code": "PACKAGE_MISSING", "package_id": bundle_item.package_id, "message": "交付包引用的安装项不存在"})
                continue
            profiles = list_package_profiles(session, package.id)
            if profile_id and not any(profile["profile_id"] == profile_id for profile in profiles):
                findings.append({"level": "warning", "code": "PROFILE_MISMATCH", "package_code": package.package_code, "message": "安装项未绑定目标适配配置"})
            if not package.install_script:
                findings.append({"level": "error", "code": "MISSING_INSTALL_SCRIPT", "package_code": package.package_code, "message": "缺少安装脚本"})
            else:
                self_call_problem = script_self_call_problem(package.install_script, "install.sh")
                if self_call_problem:
                    findings.append({"level": "error", "code": "RECURSIVE_WRAPPER_SCRIPT", "package_code": package.package_code, "script": "install_script", "message": self_call_problem})
            if not package.verify_script:
                findings.append({"level": "error", "code": "MISSING_VERIFY_SCRIPT", "package_code": package.package_code, "message": "缺少验证脚本"})
            else:
                self_call_problem = script_self_call_problem(package.verify_script, "verify.sh")
                if self_call_problem:
                    findings.append({"level": "error", "code": "RECURSIVE_WRAPPER_SCRIPT", "package_code": package.package_code, "script": "verify_script", "message": self_call_problem})
            payload_problem = package_payload_problem(package)
            if payload_problem:
                findings.append({"level": "error", "code": "PAYLOAD_FILE_MISSING", "package_code": package.package_code, "message": payload_problem})
            if package.package_type != "command_step" and not package.checksum:
                findings.append({"level": "warning", "code": "MISSING_CHECKSUM", "package_code": package.package_code, "message": "缺少 checksum"})
        status = "ok" if not findings else ("error" if any(item["level"] == "error" for item in findings) else "warning")
        return _response(True, {"status": status, "findings": findings, "build_status": item.build_status, "artifact_name": item.artifact_name, "artifact_uri": item.artifact_uri})


def _latest_build_job(session: Session, bundle_id: str) -> DeliveryBundleBuildJob | None:
    return session.scalar(select(DeliveryBundleBuildJob).where(DeliveryBundleBuildJob.bundle_id == bundle_id).order_by(DeliveryBundleBuildJob.created_at.desc()))


def _has_running_build_job(session: Session, bundle_id: str) -> bool:
    return session.scalar(select(DeliveryBundleBuildJob).where(DeliveryBundleBuildJob.bundle_id == bundle_id, DeliveryBundleBuildJob.job_status.in_(["queued", "running"])).limit(1)) is not None


def _append_job_log(job: DeliveryBundleBuildJob, message: str) -> None:
    timestamp = datetime.now(timezone.utc).isoformat()
    job.log_text = (job.log_text + "\n" if job.log_text else "") + f"[{timestamp}] {message}"


def tool_build_delivery_bundle_artifact(ctx: ToolContext, payload: BaseModel) -> dict:
    # MCP 不启动进程内线程，保持工具调用可验证：同步完成制作，但返回 latest job 结构，与后端后台任务状态模型一致。
    args = payload if isinstance(payload, BuildDeliveryBundleArtifactInput) else BuildDeliveryBundleArtifactInput.model_validate(payload)
    with session_scope() as session:
        item = session.get(DeliveryBundle, args.bundle_id) or session.scalar(select(DeliveryBundle).where(DeliveryBundle.bundle_code == args.bundle_id))
        if not item:
            raise McpError("BUNDLE_NOT_FOUND", f"delivery bundle not found: {args.bundle_id}")
        if not (ctx.is_admin or item.owner_id == ctx.operator_id):
            raise McpError("PERMISSION_DENIED", "delivery bundle is not visible")
        if item.lifecycle_status == "delivered":
            raise McpError("DELIVERED_BUNDLE_LOCKED", "delivered bundle cannot be rebuilt; create a new version")
        if _has_running_build_job(session, item.id):
            raise McpError("BUILD_JOB_RUNNING", "delivery bundle build job is already running")
        job = DeliveryBundleBuildJob(bundle_id=item.id, job_status="running", progress_percent=1, current_step="start", current_message="MCP 开始制作交付包", started_at=datetime.now(timezone.utc), created_by=ctx.operator_id)
        _append_job_log(job, "MCP 开始制作交付包")
        session.add(job)
        item.build_status = "running"
        session.flush()

        def progress(percent: int, step: str, message: str) -> None:
            job.progress_percent = max(job.progress_percent, percent)
            job.current_step = step
            job.current_message = message
            _append_job_log(job, message)

        try:
            build_delivery_bundle_artifact(session, item, settings.delivery_bundle_artifact_root, progress=progress)
        except ValueError as exc:
            job.job_status = "failed"
            job.current_step = "failed"
            job.current_message = str(exc)
            job.finished_at = datetime.now(timezone.utc)
            item.build_status = "failed"
            raise McpError("BUILD_FAILED", str(exc)) from exc
        item.build_status = "success"
        item.status = "built"
        job.job_status = "success"
        job.progress_percent = 100
        job.current_step = "done"
        job.current_message = "交付包制作完成"
        job.artifact_uri = item.artifact_uri
        job.artifact_name = item.artifact_name
        job.artifact_size = item.artifact_size
        job.artifact_checksum = item.artifact_checksum
        job.finished_at = datetime.now(timezone.utc)
        _append_job_log(job, job.current_message)
        session.flush()
        return _response(True, {"job": build_delivery_bundle_job_response(job), "item": build_delivery_bundle_response(session, item)})


def tool_get_delivery_bundle_build_job(ctx: ToolContext, payload: BaseModel) -> dict:
    args = payload if isinstance(payload, BuildDeliveryBundleArtifactInput) else BuildDeliveryBundleArtifactInput.model_validate(payload)
    with session_scope() as session:
        item = session.get(DeliveryBundle, args.bundle_id) or session.scalar(select(DeliveryBundle).where(DeliveryBundle.bundle_code == args.bundle_id))
        if not item:
            raise McpError("BUNDLE_NOT_FOUND", f"delivery bundle not found: {args.bundle_id}")
        if not (ctx.is_admin or item.owner_id == ctx.operator_id):
            raise McpError("PERMISSION_DENIED", "delivery bundle is not visible")
        return _response(True, {"item": build_delivery_bundle_job_response(_latest_build_job(session, item.id))})


def tool_deliver_delivery_bundle(ctx: ToolContext, payload: BaseModel) -> dict:
    args = payload if isinstance(payload, BuildDeliveryBundleArtifactInput) else BuildDeliveryBundleArtifactInput.model_validate(payload)
    with session_scope() as session:
        item = session.get(DeliveryBundle, args.bundle_id) or session.scalar(select(DeliveryBundle).where(DeliveryBundle.bundle_code == args.bundle_id))
        if not item:
            raise McpError("BUNDLE_NOT_FOUND", f"delivery bundle not found: {args.bundle_id}")
        if not (ctx.is_admin or item.owner_id == ctx.operator_id):
            raise McpError("PERMISSION_DENIED", "delivery bundle is not visible")
        if item.build_status != "success" or not item.artifact_uri:
            raise McpError("ARTIFACT_NOT_READY", "delivery bundle artifact is not ready")
        item.lifecycle_status = "delivered"
        item.status = "delivered"
        item.delivered_by = ctx.operator_id
        item.delivered_at = datetime.now(timezone.utc)
        item.updated_by = ctx.operator_id
        session.flush()
        return _response(True, {"item": build_delivery_bundle_response(session, item)})


def tool_delete_delivery_bundle(ctx: ToolContext, payload: BaseModel) -> dict:
    args = payload if isinstance(payload, BuildDeliveryBundleArtifactInput) else BuildDeliveryBundleArtifactInput.model_validate(payload)
    with session_scope() as session:
        item = session.get(DeliveryBundle, args.bundle_id) or session.scalar(select(DeliveryBundle).where(DeliveryBundle.bundle_code == args.bundle_id))
        if not item:
            raise McpError("BUNDLE_NOT_FOUND", f"delivery bundle not found: {args.bundle_id}")
        if not (ctx.is_admin or item.owner_id == ctx.operator_id):
            raise McpError("PERMISSION_DENIED", "delivery bundle is not visible")
        if item.lifecycle_status == "delivered":
            raise McpError("DELIVERED_BUNDLE_LOCKED", "delivered bundle cannot be deleted")
        if _has_running_build_job(session, item.id):
            raise McpError("BUILD_JOB_RUNNING", "delivery bundle build job is running")
        session.execute(delete(DeliveryBundleItem).where(DeliveryBundleItem.bundle_id == item.id))
        session.execute(delete(DeliveryBundleBuildJob).where(DeliveryBundleBuildJob.bundle_id == item.id))
        session.delete(item)
        return _response(True, {"deleted": True, "bundle_id": args.bundle_id})


def tool_create_delivery_bundle_version(ctx: ToolContext, payload: BaseModel) -> dict:
    args = payload if isinstance(payload, CreateDeliveryBundleVersionInput) else CreateDeliveryBundleVersionInput.model_validate(payload)
    with session_scope() as session:
        item = session.get(DeliveryBundle, args.bundle_id) or session.scalar(select(DeliveryBundle).where(DeliveryBundle.bundle_code == args.bundle_id))
        if not item:
            raise McpError("BUNDLE_NOT_FOUND", f"delivery bundle not found: {args.bundle_id}")
        if not (ctx.is_admin or item.owner_id == ctx.operator_id):
            raise McpError("PERMISSION_DENIED", "delivery bundle is not visible")
        if session.scalar(select(DeliveryBundle).where(DeliveryBundle.bundle_code == args.bundle_code, DeliveryBundle.owner_id == ctx.operator_id)):
            raise McpError("BUNDLE_EXISTS", f"delivery bundle exists for owner: {args.bundle_code}")
        package_ids = [bundle_item.package_id for bundle_item in _bundle_items(session, item.id)]
        packages = _resolve_packages(session, package_ids, ctx)
        new_item = DeliveryBundle(bundle_code=args.bundle_code, name=args.name or item.name, version=args.version, bundle_type=item.bundle_type, target_device_id=item.target_device_id, target_profile_id=item.target_profile_id, lifecycle_status="making", status="draft", build_status="not_built", parent_bundle_id=item.id, owner_id=ctx.operator_id, created_by=ctx.operator_id, updated_by=ctx.operator_id)
        device = _resolve_device(session, item.target_device_id) if item.target_device_id else None
        profile = _resolve_profile(session, item.target_profile_id) if item.target_profile_id else None
        new_item.manifest_json = json.dumps(build_delivery_manifest(bundle=new_item, packages=packages, device=device, profile=profile), ensure_ascii=False, indent=2)
        session.add(new_item)
        session.flush()
        _replace_bundle_items(session, new_item.id, packages)
        session.flush()
        return _response(True, {"item": build_delivery_bundle_response(session, new_item)})


def _tool_schema(model: type[BaseModel]) -> dict:
    if model is BaseModel:
        return {"type": "object", "properties": {}, "additionalProperties": False}
    return model.model_json_schema()


TOOLS: dict[str, ToolSpec] = {
    "list_allowed_package_roots": ToolSpec("list_allowed_package_roots", "列出 Agent 可登记文件路径的允许根目录", BaseModel, tool_list_allowed_package_roots, "packages_read", "low", {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}),
    "list_device_profiles": ToolSpec("list_device_profiles", "列出设备适配配置", ListDeviceProfilesInput, tool_list_device_profiles, "profiles", "low", {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}),
    "list_env_packages": ToolSpec("list_env_packages", "按适配配置和类型列出环境包资产", ListEnvPackagesInput, tool_list_env_packages, "packages_read", "low", {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}),
    "register_env_package": ToolSpec("register_env_package", "登记环境包资产", RegisterEnvPackageInput, tool_register_env_package, "packages_write", "medium", {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}),
    "update_env_package": ToolSpec("update_env_package", "更新环境包资产", UpdateEnvPackageInput, tool_update_env_package, "packages_write", "medium", {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}),
    "import_probe_result": ToolSpec("import_probe_result", "导入离线探测结果 JSON", ImportProbeResultInput, tool_import_probe_result, "probe", "medium", {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}),
    "preview_delivery_manifest": ToolSpec("preview_delivery_manifest", "预览交付包 manifest，不保存", PreviewDeliveryManifestInput, tool_preview_delivery_manifest, "bundles_read", "low", {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}),
    "create_delivery_bundle_draft": ToolSpec("create_delivery_bundle_draft", "创建交付包草稿", CreateDeliveryBundleInput, tool_create_delivery_bundle_draft, "bundles_write", "medium", {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}),
    "update_delivery_bundle_composition": ToolSpec("update_delivery_bundle_composition", "更新交付包小包编排", UpdateDeliveryBundleInput, tool_update_delivery_bundle_composition, "bundles_write", "medium", {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}),
    "audit_delivery_bundle": ToolSpec("audit_delivery_bundle", "审查交付包脚本完整性、适配一致性和产物状态", AuditDeliveryBundleInput, tool_audit_delivery_bundle, "audit", "low", {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}),
    "build_delivery_bundle_artifact": ToolSpec("build_delivery_bundle_artifact", "制作交付包完整安装包产物 tar.gz，并记录制作任务", BuildDeliveryBundleArtifactInput, tool_build_delivery_bundle_artifact, "bundles_write", "medium", {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}),
    "get_delivery_bundle_build_job": ToolSpec("get_delivery_bundle_build_job", "查询交付包最新制作任务", BuildDeliveryBundleArtifactInput, tool_get_delivery_bundle_build_job, "bundles_read", "low", {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}),
    "deliver_delivery_bundle": ToolSpec("deliver_delivery_bundle", "确认交付交付包并锁定资产", BuildDeliveryBundleArtifactInput, tool_deliver_delivery_bundle, "bundles_write", "medium", {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}),
    "delete_delivery_bundle": ToolSpec("delete_delivery_bundle", "删除制作中的交付包；已交付不可删除", BuildDeliveryBundleArtifactInput, tool_delete_delivery_bundle, "bundles_write", "high", {"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": False}),
    "create_delivery_bundle_version": ToolSpec("create_delivery_bundle_version", "基于已交付交付包创建新版本", CreateDeliveryBundleVersionInput, tool_create_delivery_bundle_version, "bundles_write", "medium", {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}),
}


def visible_tools() -> list[ToolSpec]:
    toolsets = allowed_toolsets()
    return [tool for tool in TOOLS.values() if tool.toolset in toolsets]


def mcp_tools_list() -> dict:
    return {"tools": [{"name": tool.name, "description": tool.description, "inputSchema": _tool_schema(tool.input_model), "annotations": tool.annotations} for tool in visible_tools()]}


def _audit_start(ctx: ToolContext, spec: ToolSpec, args: dict) -> McpToolCallAudit | None:
    try:
        audit = McpToolCallAudit(mcp_call_id=str(uuid.uuid4()), session_id=ctx.session_id, client_name=ctx.client_name, operator_id=ctx.operator_id, operator_role=ctx.operator_role, tool_name=spec.name, toolset=spec.toolset, risk_level=spec.risk_level, read_only=bool(spec.annotations.get("readOnlyHint")), arguments_hash=_json_hash(args), status="started", trace_id=get_trace_id())
        return audit
    except Exception:
        return None


def call_tool(name: str, arguments: dict | None, ctx: ToolContext) -> dict:
    spec = TOOLS.get(name)
    if not spec or spec.toolset not in allowed_toolsets():
        return _response(False, error={"code": "TOOL_NOT_FOUND", "message": f"tool not found or disabled: {name}", "retryable": False, "trace_id": get_trace_id()})
    args = arguments or {}
    audit = _audit_start(ctx, spec, args)
    try:
        payload = spec.input_model.model_validate(args) if spec.input_model is not BaseModel else None
        result = spec.handler(ctx, payload)
        if audit:
            with session_scope() as session:
                audit.status = "success"
                audit.finished_at = datetime.now(timezone.utc)
                audit.details_json = json.dumps({"ok": result.get("ok"), "object_id": result.get("data", {}).get("item", {}).get("package_id") or result.get("data", {}).get("item", {}).get("bundle_id") or ""}, ensure_ascii=False)
                session.add(audit)
        return result
    except ValidationError as exc:
        error = {"code": "INVALID_ARGUMENT", "message": str(exc), "retryable": False, "trace_id": get_trace_id()}
    except McpError as exc:
        error = {"code": exc.code, "message": exc.message, "retryable": exc.retryable, "trace_id": get_trace_id(), **exc.data}
    except Exception as exc:
        error = {"code": "INTERNAL_ERROR", "message": str(exc), "retryable": False, "trace_id": get_trace_id()}
    if audit:
        try:
            with session_scope() as session:
                audit.status = "error"
                audit.error_code = error["code"]
                audit.finished_at = datetime.now(timezone.utc)
                audit.details_json = json.dumps(error, ensure_ascii=False)
                session.add(audit)
        except Exception:
            pass
    return _response(False, error=error)


ENV_PACKAGE_README = """# 推理环境包制作指南（Agent/MCP）

本系统把推理环境交付物管理为“可配置、可筛选、可组合、可出包、可交付”的工程资产。Agent 新连接 MCP 后，建议先读取本资源，再调用工具。

## 1. 核心概念

- 设备适配配置（device profile）：硬件/系统/架构/推理卡等筛选条件，只能从系统已有配置选择，不能手填。
- 环境包资产（env package）：一个最小可交付安装项，可以是单包，也可以是强关联组合包。
- 交付包（delivery bundle）：多个环境包资产按顺序编排后生成的大包，交给实施人员离线安装。

## 2. 环境包资产的最小结构

当前脚本包只需要两段脚本：

1. install_script：安装脚本。
2. verify_script：安装后成功检查脚本。

不再需要 check.sh / check_script。历史字段可以为空，不参与打包执行。

每个资产还应包含：

- package_code：稳定编码，例如 atlas310b-ffmpeg-opencv-x264-combo。
- name：中文可读名称。
- package_type：driver / runtime / system_dependency / python_runtime / python_dependency / inference_server / application_package / command_step / patch / custom。
- version：资产版本。
- file_uri：资源包路径，通常是 filesystem://...。
- file_name：文件名。
- checksum_type/checksum：建议 sha256。
- install_order：默认安装顺序。
- depends_on：依赖资产编码 JSON 字符串或文本。
- device_profile_ids：适配配置 ID 列表。

## 3. 应用包（application_package）怎么做

应用包用于业务程序、模型服务、前后处理程序、脚本工程等“实施时要部署到设备上的应用形态资源”。它和编译型依赖包不同：

- 应用包只随交付包放入 `application_packages/` 目录，不进入交付包根目录 `install.sh` / `scripts/run_bundle.py` 自动安装链。
- 系统不会自动执行应用包 `install.sh` / `verify.sh`，也不会为应用包写入自动安装 `state.json` 状态。
- 应用包部署方式以交付包中的部署文档为准；如果当前资料里已有部署文档，应在 README 中引用并说明关键部署入口。
- 尽量保持原始包目录和文件形态，不要把业务目录拆散、重命名或二次改造成很多小包。
- 可以统一安装入口：归档根目录建议提供 `install.sh`。如果原始资源里有多个安装脚本，可由 Agent 整合成一个根入口 `install.sh`，按原实施顺序调用各子脚本。
- 如原脚本需要交互输入，默认保留交互，不要擅自改成静默安装；在 README 或部署文档中说明交互问题、默认值和实施人员需要输入的内容。
- 可以提供 `verify.sh`，用于人工部署后自检；但交付框架不会自动调用。
- 登记时 `package_type` 使用 `application_package`，名称应体现业务应用和版本，例如 `五舟视频分析应用包 1.9.2`。

推荐归档结构：

```text
my-application-package/
  README.md              # 说明原始来源、安装入口、交互输入、验证方式
  install.sh             # 唯一安装入口，可调用原始子脚本
  verify.sh              # 成功检查入口
  app/                   # 原始应用资源，尽量保持原形态
  models/                # 原始模型资源，如有
  scripts/               # 原始脚本资源，如有
```

应用包 Agent 提示词模板：

```text
请把当前目录/资料整理成 OpsPaw 应用包资产。要求：
1. 不要拆散原始应用包，尽量保持原始目录、文件名和资源形态。
2. 应用包只作为交付资源放入 application_packages/，不会被交付包根 install.sh / run_bundle.py 自动执行。
3. 如需统一入口，可将安装入口整理为归档根目录 install.sh；如果存在多个安装脚本，按实施文档顺序整合成一个 install.sh 去调用它们。
4. 如果原脚本存在交互输入，保留交互，不要擅自静默化；在 README.md 或部署文档中记录每个交互点、默认建议和实施人员需要输入的内容。
5. 如有明确自检方式，可编写 verify.sh 供实施人员人工执行；系统不会自动调用应用包 verify.sh。
6. 生成 tar.gz 后调用 upload_env_package_file 上传，再用 register_env_package/update_env_package 登记，package_type 必须为 application_package。
7. 不要为应用包编写 _payload_extract 外层包装脚本；应用包归档内容会被系统直接展开到交付包 application_packages/<序号>-<package_code>/。
```

## 4. 强关联包怎么做

如果几个源码包必须一起编译安装，例如 nasm + x264 + ffmpeg + opencv，应整理成一个环境包资产，而不是拆太细。推荐归档结构：

```text
my-env-package/
  README.md
  install.sh
  verify.sh
  payload/
    dependency-a.tar.gz
    dependency-b.zip
```

登记到系统时，file_uri 指向这个总归档；install_script 应先解压总归档，再执行归档内 install.sh。

## 5. 安装脚本编写规则

安装脚本必须：

- 使用 `set -Eeuo pipefail`。
- 使用 `SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)` 定位当前小包目录。
- 不假设文件在 `/root`，应从 `SCRIPT_DIR` 或解压目录读取 payload。
- 安装路径优先使用变量，例如 `THIRDPART_PATH=${THIRDPART_PATH:-/usr/local/Ascend/thirdpart/$(uname -m)}`。
- 不随意 `mv` 原始包，优先 `cp` 或直接解压。
- 对耗时编译阶段写日志。
- 对多阶段编译写阶段状态文件，失败后重新执行可跳过已完成阶段。
- 不重复污染 `~/.bashrc`；系统级环境变量优先写 `/etc/profile.d/*.sh`。
- 动态库路径优先写 `/etc/ld.so.conf.d/*.conf` 后执行 `ldconfig`。

## 6. verify_script 编写规则

## 6.1 `.bashrc` 环境变量写入约定

写入 `/root/.bashrc` 必须遵守以下约定：

1. 使用固定标记块，禁止无标记重复追加。
2. 每次写入前先删除旧标记块，再写入新标记块。
3. 标记块应放在 `.bashrc` 前部，避免被 `[ -z "$PS1" ] && return` 提前跳过。
4. 通用 MBAB 包不要内置项目环境变量；项目专用环境变量应放到独立命令步骤包中处理。

推荐写法：

```bash
BASHRC="/root/.bashrc"
TMP="$(mktemp)"

sed '/# >>> OpsPaw MBAB runtime env >>>/,/# <<< OpsPaw MBAB runtime env <<</d' "$BASHRC" > "$TMP"

{
  cat <<'EOF'
# >>> OpsPaw MBAB runtime env >>>
export PATH="/usr/local/python3.8/bin:/usr/local/Ascend/thirdpart/aarch64/bin:${PATH:-/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin}"
export LD_LIBRARY_PATH="/usr/local/python3.8/lib:/usr/local/Ascend/thirdpart/aarch64/lib:/usr/local/Ascend/thirdpart/aarch64/lib64:/usr/local/lib:${LD_LIBRARY_PATH:-}"
export PKG_CONFIG_PATH="/usr/local/lib/pkgconfig:/usr/local/Ascend/thirdpart/aarch64/lib/pkgconfig:/usr/local/Ascend/thirdpart/aarch64/lib64/pkgconfig:${PKG_CONFIG_PATH:-}"
export THIRDPART_PATH="/usr/local/Ascend/thirdpart/aarch64"
# <<< OpsPaw MBAB runtime env <<<

EOF
  cat "$TMP"
} > "$BASHRC"

rm -f "$TMP"
```

验证方式：

```bash
/bin/bash -i -l -c 'source /root/.profile; echo "$PATH"; echo "$LD_LIBRARY_PATH"; command -v python3; python3 --version'
```

禁止写法：

```bash
echo 'export PATH=...' >> /root/.bashrc
echo 'ulimit -SHn 655350' >> /root/.bashrc
```

verify_script 用于判断这个小包是否成功。它应该检查最终结果，而不是只 echo。例：

```bash
set -euo pipefail
CPU_ARCH=${CPU_ARCH:-$(uname -m)}
THIRDPART_PATH=${THIRDPART_PATH:-/usr/local/Ascend/thirdpart/${CPU_ARCH}}
ls "${THIRDPART_PATH}"/lib/libopencv_core.so* >/dev/null
ls "${THIRDPART_PATH}"/lib/libavcodec.so* >/dev/null
"${THIRDPART_PATH}/bin/ffmpeg" -version | head -1
echo verify success
```

## 7. MCP 推荐工作流

1. 调用 `mcp_login` 登录。
2. 读取本资源：`opspaw://inference-env/readme`。
3. 调用 `list_allowed_package_roots` 确认允许登记的文件根目录。
4. 调用 `list_device_profiles` 选择适配配置。
5. 读取实施手册和资源目录，识别哪些资源应合并成一个资产。
6. 在允许目录生成资产归档、install_script、verify_script。
7. Agent 必须先在本地生成环境包 tar.gz。
8. 调用 stdio MCP 客户端提供的 `upload_env_package_file` 上传本地 tar.gz 到系统存储，拿到真实 `file_uri/file_name/checksum`。
9. 调用 `register_env_package` 登记资产；已存在则 `update_env_package`。登记文件型资产时必须使用上传返回的 `file_uri/checksum`，禁止编造 `filesystem:///data/...` 路径。
10. 调用 `list_env_packages` 按 profile 检查资产可见性。
11. 调用 `create_delivery_bundle_draft` / `update_delivery_bundle_composition` 编排交付包。
12. 调用 `audit_delivery_bundle` 审计；出现 `PAYLOAD_FILE_MISSING` 必须回到本地制包/上传/更新资产。
13. 调用 `build_delivery_bundle_artifact` 制作完整交付包。
14. 调用 `get_delivery_bundle_build_job` 查看后台制作结果。

## 8. 当前重要约束

- MCP 操作必须登录；未登录只能看到登录工具和 README。
- 普通用户只管理自己的资产；admin 可以管理用户和共享资产。
- 已交付交付包不可删除；需要修改时创建新版本。
- 文件型环境包必须先由 Agent 在本地制成 tar.gz，再通过 MCP 客户端 `upload_env_package_file` 上传，最后登记；只登记 file_uri 不等于上传。
- 文件型环境包外层脚本禁止直接 `bash install.sh` / `bash ./install.sh` / `bash verify.sh` / `bash ./verify.sh`，必须解压到 `_payload_extract/<package_code>/` 后调用内层脚本；审计会用 `RECURSIVE_WRAPPER_SCRIPT` 阻断。
- 交付包大脚本负责断点续装：已 success 的小包跳过，失败小包重新执行 install.sh -> verify.sh。
"""

RESOURCES = [
    {"uri": "opspaw://inference-env/readme", "name": "推理环境包制作指南", "description": "Agent 初次连接 MCP 时应先读取的环境包制作上下文", "mimeType": "text/markdown"},
    {"uri": "opspaw://inference-env/device-profiles", "name": "设备适配配置列表", "mimeType": "application/json"},
    {"uri": "opspaw://inference-env/packages", "name": "环境包资产列表", "mimeType": "application/json"},
    {"uri": "opspaw://inference-env/delivery-bundles", "name": "交付包草稿列表", "mimeType": "application/json"},
    {"uri": "opspaw://inference-env/allowed-package-roots", "name": "允许登记的包文件根目录", "mimeType": "application/json"},
]

PROMPTS = [
    {"name": "compose_bundle_for_profile", "description": "根据设备适配配置生成交付包草稿建议", "arguments": [{"name": "profile_id", "required": True}, {"name": "goal", "required": False}]},
    {"name": "register_package_from_manual", "description": "从实施手册片段提取环境包资产登记建议", "arguments": [{"name": "manual_text", "required": True}, {"name": "profile_id", "required": False}]},
]


def resources_list() -> dict:
    return {"resources": RESOURCES}


def prompts_list() -> dict:
    return {"prompts": PROMPTS}


def read_resource(uri: str, ctx: ToolContext) -> dict:
    if uri == "opspaw://inference-env/readme":
        return {"contents": [{"uri": uri, "mimeType": "text/markdown", "text": ENV_PACKAGE_README}]}
    if uri == "opspaw://inference-env/device-profiles":
        return {"contents": [{"uri": uri, "mimeType": "application/json", "text": json.dumps(tool_list_device_profiles(ctx, ListDeviceProfilesInput())["data"], ensure_ascii=False)}]}
    if uri == "opspaw://inference-env/packages":
        return {"contents": [{"uri": uri, "mimeType": "application/json", "text": json.dumps(tool_list_env_packages(ctx, ListEnvPackagesInput())["data"], ensure_ascii=False)}]}
    if uri == "opspaw://inference-env/allowed-package-roots":
        return {"contents": [{"uri": uri, "mimeType": "application/json", "text": json.dumps({"items": allowed_package_roots()}, ensure_ascii=False)}]}
    if uri == "opspaw://inference-env/delivery-bundles":
        with session_scope() as session:
            ensure_env_package_seed_data(session)
            stmt = select(DeliveryBundle)
            if not ctx.is_admin:
                stmt = stmt.where(DeliveryBundle.owner_id == ctx.operator_id)
            items = list(session.scalars(stmt.order_by(DeliveryBundle.updated_at.desc()).limit(100)))
            data = {"items": [build_delivery_bundle_response(session, item) for item in items]}
            return {"contents": [{"uri": uri, "mimeType": "application/json", "text": json.dumps(data, ensure_ascii=False)}]}
    raise McpError("RESOURCE_NOT_FOUND", f"resource not found: {uri}")
