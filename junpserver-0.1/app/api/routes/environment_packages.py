from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, File, Form, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import delete, func, or_, select, update

from app.api.dependencies import conflict_response, current_operator, invalid_request_response, is_admin_role, missing_response, permission_denied
from app.core.config import settings
from app.core.trace import get_trace_id
from app.db.session import session_scope
from app.models import DeliveryBundle, DeliveryBundleBuildJob, DeliveryBundleItem, EnvDeviceProfile, EnvPackage, EnvPackageCompatibility, InferenceDevice, ProbeResult
from app.schemas.environment_package import (
    CreateDeliveryBundleRequest,
    CreateDeliveryBundleVersionRequest,
    CreateDeviceProfileRequest,
    CreateEnvPackageRequest,
    EditEnvPackageScriptsRequest,
    WorkspaceContentCreateRequest,
    WorkspaceContentRenameRequest,
    WorkspaceContentSaveRequest,
    CommitPackageWorkspaceRequest,
    CreateManagedDeviceRequest,
    CreateProbeResultRequest,
    CreateProfileFromDeviceRequest,
    SetPackageCompatibilitiesRequest,
    TransferAssetRequest,
    UpdateDeliveryBundleRequest,
    UpdateDeviceProfileRequest,
    UpdateEnvPackageRequest,
    UpdateManagedDeviceRequest,
)
from app.services.environment_package_service import (
    apply_update,
    build_device_profile_response,
    build_env_package_response,
    build_archive_tree,
    edit_env_package_scripts,
    list_env_package_revisions,
    build_delivery_bundle_job_response,
    build_delivery_bundle_response,
    build_delivery_manifest,
    build_delivery_bundle_artifact,
    build_managed_device_response,
    commit_package_workspace,
    create_package_workspace,
    create_workspace_content,
    delete_package_workspace,
    delete_workspace_content,
    rename_workspace_content,
    save_workspace_content,
    workspace_content_model,
    build_probe_result_response,
    build_profile_from_device,
    can_edit_package,
    create_managed_device,
    ensure_env_package_seed_data,
    extract_probe_fields,
    get_managed_device,
    list_device_profiles,
    list_env_packages,
    list_managed_devices,
    resolve_profile_id_for_filter,
    list_package_profiles,
    package_usage_count,
    replace_env_package_file,
    save_upload,
    set_package_profiles,
)
from app.services.auth_service import validate_token_user
from app.services.user_account_service import get_user

router = APIRouter(prefix="/api/v1/environment-packages", tags=["environment-packages"])



def _package_mutation_error(exc: Exception):
    message = str(exc)
    if ":" in message:
        code, detail = message.split(":", 1)
        code = code.strip()
        if code.isupper() or "_" in code:
            return invalid_request_response(code, detail.strip())
    if isinstance(exc, FileNotFoundError):
        return missing_response(message)
    return invalid_request_response("PACKAGE_MUTATION_FAILED", message)



def _get_visible_package_or_response(session, package_id: str, username: str, role: str):
    item = session.get(EnvPackage, package_id) or session.scalar(select(EnvPackage).where(EnvPackage.package_code == package_id))
    if not item:
        return None, missing_response(f"package not found: {package_id}")
    if not (can_edit_package(item, username, role) or item.visibility == "shared"):
        return None, permission_denied("package is not visible")
    return item, None


def _get_editable_package_or_response(session, package_id: str, username: str, role: str):
    item = session.get(EnvPackage, package_id)
    if not item:
        return None, missing_response(f"package not found: {package_id}")
    if not can_edit_package(item, username, role):
        return None, permission_denied("only owner or admin can edit package")
    return item, None

def _can_view_bundle(item: DeliveryBundle, username: str, role: str) -> bool:
    return is_admin_role(role) or item.owner_id == username


def _resolve_bundle_target(session, target_device_id: str | None, target_profile_id: str | None):
    if target_device_id:
        device = session.get(InferenceDevice, target_device_id) or session.scalar(select(InferenceDevice).where(InferenceDevice.device_code == target_device_id))
        if not device:
            return None, None, "", "", missing_response(f"device not found: {target_device_id}")
        resolved_device_id = device.id
    else:
        device = None
        resolved_device_id = ""

    if target_profile_id:
        profile = session.get(EnvDeviceProfile, target_profile_id) or session.scalar(select(EnvDeviceProfile).where(EnvDeviceProfile.profile_code == target_profile_id))
        if not profile:
            return None, None, "", "", missing_response(f"device profile not found: {target_profile_id}")
        resolved_profile_id = profile.id
    else:
        profile = None
        resolved_profile_id = ""

    return device, profile, resolved_device_id, resolved_profile_id, None


def _resolve_bundle_packages(session, package_ids: list[str], username: str, role: str):
    packages: list[EnvPackage] = []
    for package_id in list(dict.fromkeys(package_ids)):
        package = session.get(EnvPackage, package_id)
        if not package:
            return [], missing_response(f"package not found: {package_id}")
        if not is_admin_role(role) and package.owner_id != username and package.visibility != "shared":
            return [], permission_denied("package is not visible")
        packages.append(package)
    return packages, None


def _replace_bundle_items(session, bundle_id: str, packages: list[EnvPackage]) -> None:
    session.execute(delete(DeliveryBundleItem).where(DeliveryBundleItem.bundle_id == bundle_id))
    for index, package in enumerate(packages):
        session.add(DeliveryBundleItem(bundle_id=bundle_id, package_id=package.id, sort_order=index + 1))


def _latest_build_job(session, bundle_id: str) -> DeliveryBundleBuildJob | None:
    return session.scalar(select(DeliveryBundleBuildJob).where(DeliveryBundleBuildJob.bundle_id == bundle_id).order_by(DeliveryBundleBuildJob.created_at.desc()))


def _has_running_build_job(session, bundle_id: str) -> bool:
    return session.scalar(select(DeliveryBundleBuildJob).where(DeliveryBundleBuildJob.bundle_id == bundle_id, DeliveryBundleBuildJob.job_status.in_(["queued", "running"])).limit(1)) is not None


def _append_job_log(job: DeliveryBundleBuildJob, message: str) -> None:
    timestamp = datetime.now(timezone.utc).isoformat()
    job.log_text = (job.log_text + "\n" if job.log_text else "") + f"[{timestamp}] {message}"


def _run_build_job(job_id: str, bundle_id: str) -> None:
    with session_scope() as session:
        job = session.get(DeliveryBundleBuildJob, job_id)
        bundle = session.get(DeliveryBundle, bundle_id)
        if not job or not bundle:
            return
        job.job_status = "running"
        job.progress_percent = 1
        job.current_step = "start"
        job.current_message = "开始制作交付包"
        job.started_at = datetime.now(timezone.utc)
        bundle.build_status = "running"
        _append_job_log(job, job.current_message)

    def progress(percent: int, step: str, message: str) -> None:
        with session_scope() as progress_session:
            progress_job = progress_session.get(DeliveryBundleBuildJob, job_id)
            progress_bundle = progress_session.get(DeliveryBundle, bundle_id)
            if not progress_job:
                return
            progress_job.job_status = "running"
            progress_job.progress_percent = max(progress_job.progress_percent, percent)
            progress_job.current_step = step
            progress_job.current_message = message
            _append_job_log(progress_job, message)
            if progress_bundle:
                progress_bundle.build_status = "running"

    try:
        with session_scope() as build_session:
            bundle = build_session.get(DeliveryBundle, bundle_id)
            if not bundle:
                raise ValueError("delivery bundle not found")
            build_delivery_bundle_artifact(build_session, bundle, settings.delivery_bundle_artifact_root, progress=progress)
            build_session.execute(update(DeliveryBundle).where(DeliveryBundle.id == bundle_id).values(build_status="success", status="built"))
            build_session.flush()
            build_session.refresh(bundle)
            job = build_session.get(DeliveryBundleBuildJob, job_id)
            if job:
                job.job_status = "success"
                job.progress_percent = 100
                job.current_step = "done"
                job.current_message = "交付包制作完成"
                job.artifact_uri = bundle.artifact_uri
                job.artifact_name = bundle.artifact_name
                job.artifact_size = bundle.artifact_size
                job.artifact_checksum = bundle.artifact_checksum
                job.finished_at = datetime.now(timezone.utc)
                _append_job_log(job, job.current_message)
    except Exception as exc:
        with session_scope() as fail_session:
            job = fail_session.get(DeliveryBundleBuildJob, job_id)
            bundle = fail_session.get(DeliveryBundle, bundle_id)
            if job:
                job.job_status = "failed"
                job.current_step = "failed"
                job.current_message = str(exc)
                job.finished_at = datetime.now(timezone.utc)
                _append_job_log(job, f"制作失败：{exc}")
            if bundle:
                bundle.build_status = "failed"
                bundle.build_log = str(exc)


@router.get("/devices")
def list_devices(status: str = Query(default="", max_length=32), search: str = Query(default="", max_length=128), limit: int = Query(default=100, ge=1, le=500), offset: int = Query(default=0, ge=0)):
    with session_scope() as session:
        items, total = list_managed_devices(session, status=status, search=search, limit=limit, offset=offset)
        return {"items": [build_managed_device_response(item) for item in items], "total": total, "limit": limit, "offset": offset, "trace_id": get_trace_id()}


@router.post("/devices")
def create_device(payload: CreateManagedDeviceRequest, request: Request):
    username, role = current_operator(request)
    if not is_admin_role(role):
        return permission_denied()
    with session_scope() as session:
        ensure_env_package_seed_data(session)
        existing = get_managed_device(session, payload.device_code)
        if existing:
            return conflict_response(f"device exists: {payload.device_code}")
        item = create_managed_device(session, payload, username)
        return {"status": "ok", "item": build_managed_device_response(item), "trace_id": get_trace_id()}


@router.patch("/devices/{device_id}")
def update_device(device_id: str, payload: UpdateManagedDeviceRequest, request: Request):
    username, role = current_operator(request)
    if not is_admin_role(role):
        return permission_denied()
    with session_scope() as session:
        item = get_managed_device(session, device_id)
        if not item:
            return missing_response(f"device not found: {device_id}")
        apply_update(item, payload, list(UpdateManagedDeviceRequest.model_fields.keys()))
        item.updated_by = username
        session.flush()
        return {"status": "ok", "item": build_managed_device_response(item), "trace_id": get_trace_id()}


@router.post("/devices/{device_id}/profile")
def create_profile_from_device(device_id: str, payload: CreateProfileFromDeviceRequest, request: Request):
    username, role = current_operator(request)
    if not is_admin_role(role):
        return permission_denied()
    with session_scope() as session:
        item = get_managed_device(session, device_id)
        if not item:
            return missing_response(f"device not found: {device_id}")
        profile, created = build_profile_from_device(session, item, username=username, profile_code=payload.profile_code, name=payload.name, enabled=payload.enabled)
        return {"status": "created" if created else "updated", "item": build_device_profile_response(profile), "device": build_managed_device_response(item), "trace_id": get_trace_id()}


@router.get("/device-profiles")
def list_device_profile_options(enabled: bool | None = Query(default=None), search: str = Query(default="", max_length=128), limit: int = Query(default=100, ge=1, le=500), offset: int = Query(default=0, ge=0)):
    with session_scope() as session:
        items, total = list_device_profiles(session, enabled=enabled, search=search, limit=limit, offset=offset)
        return {"items": [build_device_profile_response(item) for item in items], "total": total, "limit": limit, "offset": offset, "trace_id": get_trace_id()}


@router.post("/device-profiles")
def create_device_profile(payload: CreateDeviceProfileRequest, request: Request):
    username, role = current_operator(request)
    if not is_admin_role(role):
        return permission_denied()
    with session_scope() as session:
        ensure_env_package_seed_data(session)
        existing = session.scalar(select(EnvDeviceProfile).where(EnvDeviceProfile.profile_code == payload.profile_code))
        if existing:
            return conflict_response(f"device profile exists: {payload.profile_code}")
        item = EnvDeviceProfile(**payload.model_dump(), created_by=username, updated_by=username)
        session.add(item)
        session.flush()
        return {"status": "ok", "item": build_device_profile_response(item), "trace_id": get_trace_id()}


@router.patch("/device-profiles/{profile_id}")
def update_device_profile(profile_id: str, payload: UpdateDeviceProfileRequest, request: Request):
    username, role = current_operator(request)
    if not is_admin_role(role):
        return permission_denied()
    with session_scope() as session:
        item = session.get(EnvDeviceProfile, profile_id) or session.scalar(select(EnvDeviceProfile).where(EnvDeviceProfile.profile_code == profile_id))
        if not item:
            return missing_response(f"device profile not found: {profile_id}")
        apply_update(item, payload, list(UpdateDeviceProfileRequest.model_fields.keys()))
        item.updated_by = username
        session.flush()
        return {"status": "ok", "item": build_device_profile_response(item), "trace_id": get_trace_id()}


@router.delete("/device-profiles/{profile_id}")
def delete_device_profile(profile_id: str, request: Request):
    _username, role = current_operator(request)
    if not is_admin_role(role):
        return permission_denied()
    with session_scope() as session:
        item = session.get(EnvDeviceProfile, profile_id) or session.scalar(select(EnvDeviceProfile).where(EnvDeviceProfile.profile_code == profile_id))
        if not item:
            return missing_response(f"device profile not found: {profile_id}")
        package_usage = int(session.scalar(select(func.count()).select_from(EnvPackageCompatibility).where(EnvPackageCompatibility.device_profile_id == item.id)) or 0)
        bundle_usage = int(session.scalar(select(func.count()).select_from(DeliveryBundle).where(DeliveryBundle.target_profile_id == item.id)) or 0)
        if package_usage or bundle_usage:
            return invalid_request_response("DEVICE_PROFILE_IN_USE", "设备适配配置已被环境包或交付包使用，不可删除")
        session.delete(item)
        return {"status": "ok", "trace_id": get_trace_id()}


@router.post("/uploads")
def upload_env_package_asset(request: Request, file: UploadFile = File(...)):
    username, _role = current_operator(request)
    item = save_upload(username, file)
    return {"status": "ok", "item": item, "trace_id": get_trace_id()}


@router.get("/packages")
def list_package_assets(request: Request, package_type: str = Query(default="", max_length=64), status: str = Query(default="", max_length=32), search: str = Query(default="", max_length=128), include_shared: bool = Query(default=False), profile_id: str = Query(default="", max_length=64), device_id: str = Query(default="", max_length=64), limit: int = Query(default=50, ge=1, le=500), offset: int = Query(default=0, ge=0)):
    username, role = current_operator(request)
    with session_scope() as session:
        items, total, scope = list_env_packages(session, username=username, role=role, package_type=package_type, status=status, search=search, include_shared=include_shared, limit=limit, offset=offset, profile_id=profile_id, device_id=device_id)
        return {"items": [build_env_package_response(item, list_package_profiles(session, item.id)) for item in items], "total": total, "limit": limit, "offset": offset, "scope": scope, "trace_id": get_trace_id()}


@router.post("/packages")
def create_env_package(payload: CreateEnvPackageRequest, request: Request):
    username, _role = current_operator(request)
    with session_scope() as session:
        ensure_env_package_seed_data(session)
        existing = session.scalar(select(EnvPackage).where(EnvPackage.package_code == payload.package_code, EnvPackage.version == payload.version, EnvPackage.owner_id == username))
        if existing:
            return conflict_response(f"package exists for owner: {payload.package_code}@{payload.version}")
        data = payload.model_dump(exclude={"device_profile_ids"})
        item = EnvPackage(**data, owner_id=username, created_by=username, updated_by=username)
        session.add(item)
        session.flush()
        ok, reason = set_package_profiles(session, item.id, payload.device_profile_ids)
        if not ok:
            return invalid_request_response("INVALID_DEVICE_PROFILE", reason)
        session.flush()
        return {"status": "ok", "item": build_env_package_response(item, list_package_profiles(session, item.id)), "trace_id": get_trace_id()}


@router.get("/packages/{package_id}")
def get_env_package(package_id: str, request: Request):
    username, role = current_operator(request)
    with session_scope() as session:
        item = session.get(EnvPackage, package_id)
        if not item:
            return missing_response(f"package not found: {package_id}")
        if not (can_edit_package(item, username, role) or item.visibility == "shared"):
            return permission_denied("package is not visible")
        return {"item": build_env_package_response(item, list_package_profiles(session, item.id)), "trace_id": get_trace_id()}




@router.post("/packages/{package_id}/workspaces")
def create_env_package_workspace(package_id: str, request: Request):
    username, role = current_operator(request)
    with session_scope() as session:
        item, error = _get_editable_package_or_response(session, package_id, username, role)
        if error:
            return error
        try:
            workspace = create_package_workspace(item, username)
        except Exception as exc:
            return _package_mutation_error(exc)
        return {"status": "ok", "item": workspace, "trace_id": get_trace_id()}


@router.get("/packages/{package_id}/workspaces/{workspace_id}/contents")
@router.get("/packages/{package_id}/workspaces/{workspace_id}/contents/{path:path}")
def get_workspace_contents(package_id: str, workspace_id: str, request: Request, path: str = "", content: bool = Query(default=True)):
    username, role = current_operator(request)
    with session_scope() as session:
        item, error = _get_visible_package_or_response(session, package_id, username, role)
        if error:
            return error
        try:
            model = workspace_content_model(item, workspace_id, path, username, role, include_content=content)
        except Exception as exc:
            return _package_mutation_error(exc)
        return {"item": model, "trace_id": get_trace_id()}


@router.post("/packages/{package_id}/workspaces/{workspace_id}/contents")
@router.post("/packages/{package_id}/workspaces/{workspace_id}/contents/{path:path}")
def create_workspace_contents(package_id: str, workspace_id: str, payload: WorkspaceContentCreateRequest, request: Request, path: str = ""):
    username, role = current_operator(request)
    with session_scope() as session:
        item, error = _get_editable_package_or_response(session, package_id, username, role)
        if error:
            return error
        try:
            model = create_workspace_content(item, workspace_id, path, payload, username, role)
        except Exception as exc:
            return _package_mutation_error(exc)
        return {"status": "ok", "item": model, "trace_id": get_trace_id()}


@router.put("/packages/{package_id}/workspaces/{workspace_id}/contents/{path:path}")
def save_workspace_contents(package_id: str, workspace_id: str, path: str, payload: WorkspaceContentSaveRequest, request: Request):
    username, role = current_operator(request)
    with session_scope() as session:
        item, error = _get_editable_package_or_response(session, package_id, username, role)
        if error:
            return error
        try:
            model = save_workspace_content(item, workspace_id, path, payload, username, role)
        except Exception as exc:
            return _package_mutation_error(exc)
        return {"status": "ok", "item": model, "trace_id": get_trace_id()}


@router.patch("/packages/{package_id}/workspaces/{workspace_id}/contents/{path:path}")
def rename_workspace_contents(package_id: str, workspace_id: str, path: str, payload: WorkspaceContentRenameRequest, request: Request):
    username, role = current_operator(request)
    with session_scope() as session:
        item, error = _get_editable_package_or_response(session, package_id, username, role)
        if error:
            return error
        try:
            model = rename_workspace_content(item, workspace_id, path, payload.path, username, role)
        except Exception as exc:
            return _package_mutation_error(exc)
        return {"status": "ok", "item": model, "trace_id": get_trace_id()}


@router.delete("/packages/{package_id}/workspaces/{workspace_id}/contents/{path:path}")
def delete_workspace_contents(package_id: str, workspace_id: str, path: str, request: Request):
    username, role = current_operator(request)
    with session_scope() as session:
        item, error = _get_editable_package_or_response(session, package_id, username, role)
        if error:
            return error
        try:
            delete_workspace_content(item, workspace_id, path, username, role)
        except Exception as exc:
            return _package_mutation_error(exc)
        return {"status": "ok", "trace_id": get_trace_id()}


@router.post("/packages/{package_id}/workspaces/{workspace_id}/commit")
def commit_env_package_workspace(package_id: str, workspace_id: str, payload: CommitPackageWorkspaceRequest, request: Request):
    username, role = current_operator(request)
    with session_scope() as session:
        item, error = _get_editable_package_or_response(session, package_id, username, role)
        if error:
            return error
        try:
            target, revision = commit_package_workspace(session, item, workspace_id, save_mode=payload.save_mode, new_version=payload.new_version, remark=payload.remark, username=username, role=role)
        except Exception as exc:
            return _package_mutation_error(exc)
        session.flush()
        return {"status": "ok", "item": build_env_package_response(target, list_package_profiles(session, target.id)), "revision": list_env_package_revisions(session, target.id)[0] if revision else None, "trace_id": get_trace_id()}


@router.delete("/packages/{package_id}/workspaces/{workspace_id}")
def delete_env_package_workspace(package_id: str, workspace_id: str, request: Request):
    username, role = current_operator(request)
    with session_scope() as session:
        item, error = _get_editable_package_or_response(session, package_id, username, role)
        if error:
            return error
        try:
            delete_package_workspace(item, workspace_id, username, role)
        except Exception as exc:
            return _package_mutation_error(exc)
        return {"status": "ok", "trace_id": get_trace_id()}


@router.get("/packages/{package_id}/archive-tree")
def get_env_package_archive_tree(package_id: str, request: Request):
    username, role = current_operator(request)
    with session_scope() as session:
        item = session.get(EnvPackage, package_id) or session.scalar(select(EnvPackage).where(EnvPackage.package_code == package_id))
        if not item:
            return missing_response(f"package not found: {package_id}")
        if not (can_edit_package(item, username, role) or item.visibility == "shared"):
            return permission_denied("package is not visible")
        try:
            tree = build_archive_tree(item)
        except Exception as exc:
            return _package_mutation_error(exc)
        return {"item": tree, "trace_id": get_trace_id()}


@router.get("/packages/{package_id}/revisions")
def get_env_package_revisions(package_id: str, request: Request):
    username, role = current_operator(request)
    with session_scope() as session:
        item = session.get(EnvPackage, package_id) or session.scalar(select(EnvPackage).where(EnvPackage.package_code == package_id))
        if not item:
            return missing_response(f"package not found: {package_id}")
        if not (can_edit_package(item, username, role) or item.visibility == "shared"):
            return permission_denied("package is not visible")
        return {"items": list_env_package_revisions(session, item.id), "trace_id": get_trace_id()}


@router.post("/packages/{package_id}/script-edit")
def edit_env_package_script_fields(package_id: str, payload: EditEnvPackageScriptsRequest, request: Request):
    username, role = current_operator(request)
    with session_scope() as session:
        item = session.get(EnvPackage, package_id)
        if not item:
            return missing_response(f"package not found: {package_id}")
        if not can_edit_package(item, username, role):
            return permission_denied("only owner or admin can edit package")
        try:
            target, revision = edit_env_package_scripts(session, item, payload, username)
        except Exception as exc:
            return _package_mutation_error(exc)
        session.flush()
        return {
            "status": "ok",
            "item": build_env_package_response(target, list_package_profiles(session, target.id)),
            "revision": list_env_package_revisions(session, target.id)[0] if revision else None,
            "usage_count": package_usage_count(session, item.id),
            "trace_id": get_trace_id(),
        }


@router.post("/packages/{package_id}/file-replace")
def replace_env_package_archive_file(
    package_id: str,
    request: Request,
    target_path: str = Form(...),
    save_mode: str = Form(default="in_place"),
    new_version: str = Form(default=""),
    remark: str = Form(default=""),
    file: UploadFile = File(...),
):
    username, role = current_operator(request)
    with session_scope() as session:
        item = session.get(EnvPackage, package_id)
        if not item:
            return missing_response(f"package not found: {package_id}")
        if not can_edit_package(item, username, role):
            return permission_denied("only owner or admin can edit package")
        try:
            target, revision = replace_env_package_file(session, item, replacement=file, target_path=target_path, save_mode=save_mode, new_version=new_version, remark=remark, username=username)
        except Exception as exc:
            return _package_mutation_error(exc)
        session.flush()
        return {
            "status": "ok",
            "item": build_env_package_response(target, list_package_profiles(session, target.id)),
            "revision": list_env_package_revisions(session, target.id)[0] if revision else None,
            "usage_count": package_usage_count(session, item.id),
            "trace_id": get_trace_id(),
        }


@router.get("/packages/{package_id}/file")
def download_env_package_file(package_id: str, request: Request, access_token: str = Query(default="")):
    with session_scope() as session:
        if access_token:
            user, error = validate_token_user(session, access_token)
            if not user:
                return JSONResponse(status_code=401, content={"code": error or "INVALID_TOKEN", "message": "invalid or expired bearer token", "trace_id": get_trace_id()})
            username, role = user.username, user.role
        else:
            username, role = current_operator(request)
        item = session.get(EnvPackage, package_id) or session.scalar(select(EnvPackage).where(EnvPackage.package_code == package_id))
        if not item:
            return missing_response(f"package not found: {package_id}")
        if not (can_edit_package(item, username, role) or item.visibility == "shared"):
            return permission_denied("package is not visible")
        if not item.file_uri:
            return invalid_request_response("PACKAGE_FILE_NOT_CONFIGURED", "environment package file is not configured")
        if not item.file_uri.startswith("filesystem://"):
            return invalid_request_response("UNSUPPORTED_PACKAGE_FILE_URI", "only filesystem package files can be downloaded")
        path = Path(item.file_uri[len("filesystem://"):]).resolve()
        if not path.exists() or not path.is_file():
            return missing_response("environment package file not found")
        media_type = "application/gzip" if path.name.endswith((".tar.gz", ".tgz", ".gz")) else "application/octet-stream"
        return FileResponse(path, media_type=media_type, filename=item.file_name or path.name)


@router.patch("/packages/{package_id}")
def update_env_package(package_id: str, payload: UpdateEnvPackageRequest, request: Request):
    username, role = current_operator(request)
    with session_scope() as session:
        item = session.get(EnvPackage, package_id)
        if not item:
            return missing_response(f"package not found: {package_id}")
        if not can_edit_package(item, username, role):
            return permission_denied("only owner or admin can edit package")
        profile_ids = payload.device_profile_ids
        fields = [field for field in UpdateEnvPackageRequest.model_fields.keys() if field != "device_profile_ids"]
        apply_update(item, payload, fields)
        item.updated_by = username
        if profile_ids is not None:
            ok, reason = set_package_profiles(session, item.id, profile_ids)
            if not ok:
                return invalid_request_response("INVALID_DEVICE_PROFILE", reason)
        session.flush()
        return {"status": "ok", "item": build_env_package_response(item, list_package_profiles(session, item.id)), "trace_id": get_trace_id()}


@router.delete("/packages/{package_id}")
def delete_env_package(package_id: str, request: Request):
    username, role = current_operator(request)
    with session_scope() as session:
        item = session.get(EnvPackage, package_id)
        if not item:
            return missing_response(f"package not found: {package_id}")
        if not can_edit_package(item, username, role):
            return permission_denied("only owner or admin can delete package")
        usage_count = int(session.scalar(select(func.count()).select_from(DeliveryBundleItem).where(DeliveryBundleItem.package_id == item.id)) or 0)
        if usage_count:
            return invalid_request_response("PACKAGE_IN_USE", "环境包资产已被交付包使用，不可删除")
        session.execute(delete(EnvPackageCompatibility).where(EnvPackageCompatibility.package_id == item.id))
        session.delete(item)
        return {"status": "ok", "trace_id": get_trace_id()}


@router.post("/packages/{package_id}/compatibilities")
def set_env_package_compatibilities(package_id: str, payload: SetPackageCompatibilitiesRequest, request: Request):
    username, role = current_operator(request)
    with session_scope() as session:
        item = session.get(EnvPackage, package_id)
        if not item:
            return missing_response(f"package not found: {package_id}")
        if not can_edit_package(item, username, role):
            return permission_denied("only owner or admin can edit package")
        ok, reason = set_package_profiles(session, item.id, payload.device_profile_ids)
        if not ok:
            return invalid_request_response("INVALID_DEVICE_PROFILE", reason)
        session.flush()
        return {"status": "ok", "item": build_env_package_response(item, list_package_profiles(session, item.id)), "trace_id": get_trace_id()}


@router.get("/delivery-bundles")
def list_delivery_bundles(request: Request, profile_id: str = Query(default="", max_length=64), device_id: str = Query(default="", max_length=64), limit: int = Query(default=100, ge=1, le=500), offset: int = Query(default=0, ge=0)):
    username, role = current_operator(request)
    with session_scope() as session:
        ensure_env_package_seed_data(session)
        stmt = select(DeliveryBundle)
        count_stmt = select(func.count()).select_from(DeliveryBundle)
        if not is_admin_role(role):
            stmt = stmt.where(DeliveryBundle.owner_id == username)
            count_stmt = count_stmt.where(DeliveryBundle.owner_id == username)
        resolved_profile_id = resolve_profile_id_for_filter(session, profile_id=profile_id, device_id=device_id if device_id and not profile_id else "")
        if device_id and resolved_profile_id:
            pred = or_(DeliveryBundle.target_device_id == device_id, DeliveryBundle.target_profile_id == resolved_profile_id)
            stmt = stmt.where(pred)
            count_stmt = count_stmt.where(pred)
        elif device_id:
            stmt = stmt.where(DeliveryBundle.target_device_id == device_id)
            count_stmt = count_stmt.where(DeliveryBundle.target_device_id == device_id)
        elif resolved_profile_id:
            stmt = stmt.where(DeliveryBundle.target_profile_id == resolved_profile_id)
            count_stmt = count_stmt.where(DeliveryBundle.target_profile_id == resolved_profile_id)
        total = int(session.scalar(count_stmt) or 0)
        items = list(session.scalars(stmt.order_by(DeliveryBundle.updated_at.desc()).offset(offset).limit(limit)))
        return {"items": [build_delivery_bundle_response(session, item) for item in items], "total": total, "limit": limit, "offset": offset, "trace_id": get_trace_id()}


@router.post("/delivery-bundles")
def create_delivery_bundle(payload: CreateDeliveryBundleRequest, request: Request):
    username, role = current_operator(request)
    with session_scope() as session:
        ensure_env_package_seed_data(session)
        existing = session.scalar(select(DeliveryBundle).where(DeliveryBundle.bundle_code == payload.bundle_code, DeliveryBundle.owner_id == username))
        if existing:
            return conflict_response(f"delivery bundle exists for owner: {payload.bundle_code}")

        device, profile, target_device_id, target_profile_id, target_error = _resolve_bundle_target(session, payload.target_device_id, payload.target_profile_id)
        if target_error:
            return target_error

        packages, package_error = _resolve_bundle_packages(session, payload.package_ids, username, role)
        if package_error:
            return package_error

        bundle = DeliveryBundle(
            bundle_code=payload.bundle_code,
            name=payload.name,
            version=payload.version,
            bundle_type=payload.bundle_type,
            target_device_id=target_device_id,
            target_profile_id=target_profile_id,
            lifecycle_status="making",
            status="draft",
            owner_id=username,
            created_by=username,
            updated_by=username,
        )
        manifest = build_delivery_manifest(bundle=bundle, packages=packages, device=device, profile=profile)
        bundle.manifest_json = json.dumps(manifest, ensure_ascii=False, indent=2)
        session.add(bundle)
        session.flush()
        _replace_bundle_items(session, bundle.id, packages)
        session.flush()
        return {"status": "ok", "item": build_delivery_bundle_response(session, bundle), "trace_id": get_trace_id()}


@router.get("/delivery-bundles/{bundle_id}")
def get_delivery_bundle(bundle_id: str, request: Request):
    username, role = current_operator(request)
    with session_scope() as session:
        item = session.get(DeliveryBundle, bundle_id) or session.scalar(select(DeliveryBundle).where(DeliveryBundle.bundle_code == bundle_id))
        if not item:
            return missing_response(f"delivery bundle not found: {bundle_id}")
        if not _can_view_bundle(item, username, role):
            return permission_denied("delivery bundle is not visible")
        return {"item": build_delivery_bundle_response(session, item), "trace_id": get_trace_id()}


@router.patch("/delivery-bundles/{bundle_id}")
def update_delivery_bundle(bundle_id: str, payload: UpdateDeliveryBundleRequest, request: Request):
    username, role = current_operator(request)
    with session_scope() as session:
        item = session.get(DeliveryBundle, bundle_id) or session.scalar(select(DeliveryBundle).where(DeliveryBundle.bundle_code == bundle_id))
        if not item:
            return missing_response(f"delivery bundle not found: {bundle_id}")
        if not _can_view_bundle(item, username, role):
            return permission_denied("delivery bundle is not visible")
        if item.lifecycle_status == "delivered":
            return invalid_request_response("DELIVERED_BUNDLE_LOCKED", "已交付交付包不可修改，请创建新版本")
        if _has_running_build_job(session, item.id):
            return invalid_request_response("BUILD_JOB_RUNNING", "交付包正在制作中，不可修改")

        target_device_id = item.target_device_id if payload.target_device_id is None else payload.target_device_id
        target_profile_id = item.target_profile_id if payload.target_profile_id is None else payload.target_profile_id
        device, profile, resolved_device_id, resolved_profile_id, target_error = _resolve_bundle_target(session, target_device_id, target_profile_id)
        if target_error:
            return target_error

        package_ids = payload.package_ids if payload.package_ids is not None else [bundle_item.package_id for bundle_item in session.scalars(select(DeliveryBundleItem).where(DeliveryBundleItem.bundle_id == item.id).order_by(DeliveryBundleItem.sort_order.asc()))]
        if not package_ids:
            return invalid_request_response("EMPTY_DELIVERY_BUNDLE", "delivery bundle requires at least one package")
        packages, package_error = _resolve_bundle_packages(session, package_ids, username, role)
        if package_error:
            return package_error

        if payload.name is not None:
            item.name = payload.name
        if payload.version is not None:
            item.version = payload.version
        if payload.bundle_type is not None:
            item.bundle_type = payload.bundle_type
        item.target_device_id = resolved_device_id
        item.target_profile_id = resolved_profile_id
        item.updated_by = username
        manifest = build_delivery_manifest(bundle=item, packages=packages, device=device, profile=profile)
        item.manifest_json = json.dumps(manifest, ensure_ascii=False, indent=2)
        _replace_bundle_items(session, item.id, packages)
        session.flush()
        return {"status": "ok", "item": build_delivery_bundle_response(session, item), "trace_id": get_trace_id()}


@router.post("/delivery-bundles/{bundle_id}/build-jobs")
@router.post("/delivery-bundles/{bundle_id}/build")
def build_delivery_bundle(bundle_id: str, request: Request):
    username, role = current_operator(request)
    job_id = ""
    resolved_bundle_id = ""
    response_job = None
    response_item = None
    with session_scope() as session:
        item = session.get(DeliveryBundle, bundle_id) or session.scalar(select(DeliveryBundle).where(DeliveryBundle.bundle_code == bundle_id))
        if not item:
            return missing_response(f"delivery bundle not found: {bundle_id}")
        if not _can_view_bundle(item, username, role):
            return permission_denied("delivery bundle is not visible")
        if item.lifecycle_status == "delivered":
            return invalid_request_response("DELIVERED_BUNDLE_LOCKED", "已交付交付包不可重新制作，请创建新版本")
        if _has_running_build_job(session, item.id):
            return invalid_request_response("BUILD_JOB_RUNNING", "已有制作任务正在运行")
        if not list(session.scalars(select(DeliveryBundleItem).where(DeliveryBundleItem.bundle_id == item.id).limit(1))):
            return invalid_request_response("EMPTY_DELIVERY_BUNDLE", "delivery bundle requires at least one package")
        job = DeliveryBundleBuildJob(bundle_id=item.id, job_status="queued", progress_percent=0, current_step="queued", current_message="已进入制作队列", created_by=username)
        _append_job_log(job, "已进入制作队列")
        session.add(job)
        item.build_status = "queued"
        session.flush()
        job_id = job.id
        resolved_bundle_id = item.id
        response_job = build_delivery_bundle_job_response(job)
        response_item = build_delivery_bundle_response(session, item)
    thread = threading.Thread(target=_run_build_job, args=(job_id, resolved_bundle_id), daemon=True)
    thread.start()
    return {"status": "queued", "job": response_job, "item": response_item, "trace_id": get_trace_id()}


@router.get("/delivery-bundles/{bundle_id}/build-jobs/latest")
def get_latest_delivery_bundle_build_job(bundle_id: str, request: Request):
    username, role = current_operator(request)
    with session_scope() as session:
        item = session.get(DeliveryBundle, bundle_id) or session.scalar(select(DeliveryBundle).where(DeliveryBundle.bundle_code == bundle_id))
        if not item:
            return missing_response(f"delivery bundle not found: {bundle_id}")
        if not _can_view_bundle(item, username, role):
            return permission_denied("delivery bundle is not visible")
        return {"item": build_delivery_bundle_job_response(_latest_build_job(session, item.id)), "trace_id": get_trace_id()}


@router.post("/delivery-bundles/{bundle_id}/deliver")
def deliver_delivery_bundle(bundle_id: str, request: Request):
    username, role = current_operator(request)
    with session_scope() as session:
        item = session.get(DeliveryBundle, bundle_id) or session.scalar(select(DeliveryBundle).where(DeliveryBundle.bundle_code == bundle_id))
        if not item:
            return missing_response(f"delivery bundle not found: {bundle_id}")
        if not _can_view_bundle(item, username, role):
            return permission_denied("delivery bundle is not visible")
        if item.lifecycle_status == "delivered":
            return {"status": "ok", "item": build_delivery_bundle_response(session, item), "trace_id": get_trace_id()}
        if item.build_status != "success" or not item.artifact_uri:
            return invalid_request_response("ARTIFACT_NOT_READY", "交付包制作成功后才能确认交付")
        if _has_running_build_job(session, item.id):
            return invalid_request_response("BUILD_JOB_RUNNING", "交付包正在制作中，不能确认交付")
        item.lifecycle_status = "delivered"
        item.status = "delivered"
        item.delivered_by = username
        item.delivered_at = datetime.now(timezone.utc)
        item.updated_by = username
        session.flush()
        return {"status": "ok", "item": build_delivery_bundle_response(session, item), "trace_id": get_trace_id()}


@router.delete("/delivery-bundles/{bundle_id}")
def delete_delivery_bundle(bundle_id: str, request: Request):
    username, role = current_operator(request)
    with session_scope() as session:
        item = session.get(DeliveryBundle, bundle_id) or session.scalar(select(DeliveryBundle).where(DeliveryBundle.bundle_code == bundle_id))
        if not item:
            return missing_response(f"delivery bundle not found: {bundle_id}")
        if not _can_view_bundle(item, username, role):
            return permission_denied("delivery bundle is not visible")
        if item.lifecycle_status == "delivered":
            return invalid_request_response("DELIVERED_BUNDLE_LOCKED", "已交付交付包不可删除")
        if _has_running_build_job(session, item.id):
            return invalid_request_response("BUILD_JOB_RUNNING", "交付包正在制作中，不可删除")
        session.execute(delete(DeliveryBundleItem).where(DeliveryBundleItem.bundle_id == item.id))
        session.execute(delete(DeliveryBundleBuildJob).where(DeliveryBundleBuildJob.bundle_id == item.id))
        session.delete(item)
        return {"status": "ok", "trace_id": get_trace_id()}


@router.post("/delivery-bundles/{bundle_id}/new-version")
def create_delivery_bundle_new_version(bundle_id: str, payload: CreateDeliveryBundleVersionRequest, request: Request):
    username, role = current_operator(request)
    with session_scope() as session:
        item = session.get(DeliveryBundle, bundle_id) or session.scalar(select(DeliveryBundle).where(DeliveryBundle.bundle_code == bundle_id))
        if not item:
            return missing_response(f"delivery bundle not found: {bundle_id}")
        if not _can_view_bundle(item, username, role):
            return permission_denied("delivery bundle is not visible")
        existing = session.scalar(select(DeliveryBundle).where(DeliveryBundle.bundle_code == payload.bundle_code, DeliveryBundle.owner_id == username))
        if existing:
            return conflict_response(f"delivery bundle exists for owner: {payload.bundle_code}")
        package_ids = [bundle_item.package_id for bundle_item in session.scalars(select(DeliveryBundleItem).where(DeliveryBundleItem.bundle_id == item.id).order_by(DeliveryBundleItem.sort_order.asc()))]
        packages, package_error = _resolve_bundle_packages(session, package_ids, username, role)
        if package_error:
            return package_error
        new_item = DeliveryBundle(
            bundle_code=payload.bundle_code,
            name=payload.name or item.name,
            version=payload.version,
            bundle_type=item.bundle_type,
            target_device_id=item.target_device_id,
            target_profile_id=item.target_profile_id,
            lifecycle_status="making",
            status="draft",
            build_status="not_built",
            parent_bundle_id=item.id,
            owner_id=username,
            created_by=username,
            updated_by=username,
        )
        device = session.get(InferenceDevice, item.target_device_id) if item.target_device_id else None
        profile = session.get(EnvDeviceProfile, item.target_profile_id) if item.target_profile_id else None
        new_item.manifest_json = json.dumps(build_delivery_manifest(bundle=new_item, packages=packages, device=device, profile=profile), ensure_ascii=False, indent=2)
        session.add(new_item)
        session.flush()
        _replace_bundle_items(session, new_item.id, packages)
        session.flush()
        return {"status": "ok", "item": build_delivery_bundle_response(session, new_item), "trace_id": get_trace_id()}


@router.get("/delivery-bundles/{bundle_id}/artifact")
def get_delivery_bundle_artifact(bundle_id: str, request: Request, access_token: str = Query(default="")):
    with session_scope() as session:
        if access_token:
            user, error = validate_token_user(session, access_token)
            if not user:
                return JSONResponse(status_code=401, content={"code": error or "INVALID_TOKEN", "message": "invalid or expired bearer token", "trace_id": get_trace_id()})
            username, role = user.username, user.role
        else:
            username, role = current_operator(request)
        item = session.get(DeliveryBundle, bundle_id) or session.scalar(select(DeliveryBundle).where(DeliveryBundle.bundle_code == bundle_id))
        if not item:
            return missing_response(f"delivery bundle not found: {bundle_id}")
        if not _can_view_bundle(item, username, role):
            return permission_denied("delivery bundle is not visible")
        if item.build_status != "success" or not item.artifact_uri:
            return invalid_request_response("ARTIFACT_NOT_READY", "delivery bundle artifact is not ready")
        if not item.artifact_uri.startswith("filesystem://"):
            return invalid_request_response("UNSUPPORTED_ARTIFACT_URI", "only filesystem artifacts can be downloaded")
        path = Path(item.artifact_uri[len("filesystem://"):]).resolve()
        if not path.exists() or not path.is_file():
            return missing_response("artifact file not found")
        return FileResponse(path, media_type="application/gzip", filename=item.artifact_name or path.name)


@router.get("/probe-results")
def list_probe_results(request: Request, limit: int = Query(default=100, ge=1, le=500), offset: int = Query(default=0, ge=0)):
    username, role = current_operator(request)
    with session_scope() as session:
        ensure_env_package_seed_data(session)
        stmt = select(ProbeResult)
        count_stmt = select(func.count()).select_from(ProbeResult)
        if not is_admin_role(role):
            stmt = stmt.where(ProbeResult.owner_id == username)
            count_stmt = count_stmt.where(ProbeResult.owner_id == username)
        total = int(session.scalar(count_stmt) or 0)
        items = list(session.scalars(stmt.order_by(ProbeResult.updated_at.desc()).offset(offset).limit(limit)))
        return {"items": [build_probe_result_response(item) for item in items], "total": total, "limit": limit, "offset": offset, "trace_id": get_trace_id()}


@router.post("/probe-results")
def create_probe_result(payload: CreateProbeResultRequest, request: Request):
    username, _role = current_operator(request)
    with session_scope() as session:
        ensure_env_package_seed_data(session)
        existing = session.scalar(select(ProbeResult).where(ProbeResult.result_code == payload.result_code, ProbeResult.owner_id == username))
        if existing:
            return conflict_response(f"probe result exists for owner: {payload.result_code}")
        if payload.device_id:
            device = session.get(InferenceDevice, payload.device_id) or session.scalar(select(InferenceDevice).where(InferenceDevice.device_code == payload.device_id))
            if not device:
                return missing_response(f"device not found: {payload.device_id}")
            device_id = device.id
        else:
            device_id = ""
        try:
            _raw, fields = extract_probe_fields(payload.raw_json)
        except (ValueError, json.JSONDecodeError) as exc:
            return invalid_request_response("INVALID_PROBE_JSON", str(exc))
        item = ProbeResult(
            result_code=payload.result_code,
            name=payload.name or payload.result_code,
            device_id=device_id,
            raw_json=payload.raw_json,
            owner_id=username,
            created_by=username,
            updated_by=username,
            **fields,
        )
        session.add(item)
        session.flush()
        return {"status": "ok", "item": build_probe_result_response(item), "trace_id": get_trace_id()}


@router.get("/admin/assets")
def list_admin_env_assets(request: Request, owner_id: str = Query(default="", max_length=64), limit: int = Query(default=100, ge=1, le=500), offset: int = Query(default=0, ge=0)):
    _username, role = current_operator(request)
    if not is_admin_role(role):
        return permission_denied()
    with session_scope() as session:
        ensure_env_package_seed_data(session)
        stmt = select(EnvPackage)
        count_stmt = select(func.count()).select_from(EnvPackage)
        if owner_id:
            stmt = stmt.where(EnvPackage.owner_id == owner_id)
            count_stmt = count_stmt.where(EnvPackage.owner_id == owner_id)
        total = int(session.scalar(count_stmt) or 0)
        items = list(session.scalars(stmt.order_by(EnvPackage.owner_id.asc(), EnvPackage.updated_at.desc()).offset(offset).limit(limit)))
        return {"items": [build_env_package_response(item, list_package_profiles(session, item.id)) for item in items], "total": total, "limit": limit, "offset": offset, "trace_id": get_trace_id()}


@router.post("/admin/assets/{package_id}/transfer")
def transfer_env_asset(package_id: str, payload: TransferAssetRequest, request: Request):
    username, role = current_operator(request)
    if not is_admin_role(role):
        return permission_denied()
    with session_scope() as session:
        item = session.get(EnvPackage, package_id)
        if not item:
            return missing_response(f"package not found: {package_id}")
        if not get_user(session, payload.target_owner_id):
            return missing_response(f"user not found: {payload.target_owner_id}")
        item.owner_id = payload.target_owner_id
        item.updated_by = username
        session.flush()
        return {"status": "ok", "item": build_env_package_response(item, list_package_profiles(session, item.id)), "trace_id": get_trace_id()}


@router.post("/admin/assets/{package_id}/share")
def share_env_asset(package_id: str, request: Request, shared: bool = Query(default=True)):
    username, role = current_operator(request)
    if not is_admin_role(role):
        return permission_denied()
    with session_scope() as session:
        item = session.get(EnvPackage, package_id)
        if not item:
            return missing_response(f"package not found: {package_id}")
        item.visibility = "shared" if shared else "private"
        item.updated_by = username
        session.flush()
        return {"status": "ok", "item": build_env_package_response(item, list_package_profiles(session, item.id)), "trace_id": get_trace_id()}
