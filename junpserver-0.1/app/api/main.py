from __future__ import annotations

import json
import logging
import time
import uuid
import csv
import io
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Query, Request
from pydantic import BaseModel, Field
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy import func, or_, select

from app.core.callback_security import evaluate_callback_url_policy
from app.core.config import settings
from app.core.failure import format_failure_reason, infer_failure_code, strip_failure_prefix
from app.core.logging import configure_logging
from app.core.trace import clear_trace_id, get_trace_id, set_trace_id
from app.db.init_db import init_db
from app.db.session import session_scope
from app.models import (
    ApprovalActionAudit,
    ApprovalRequest,
    AssetProjection,
    AuditLink,
    CallbackDelivery,
    CallbackHook,
    CallbackReplayAudit,
    CommandBlacklistRule,
    CommandTemplate,
    EnvironmentHandover,
    EnvironmentImplementation,
    EnvironmentSpec,
    EnvDeviceProfile,
    EnvPackage,
    EnvPackageCompatibility,
    Execution,
    FailureSummaryBucket,
    GovernanceAudit,
    InferenceDevice,
    MetricsPreaggregationRun,
    ModelDeploymentRequirement,
    SyncSnapshot,
    Task,
    TaskRetryAuditCountBucket,
    TaskRetryAudit,
    TaskRetryAuditItem,
    TaskRetrySummaryBucket,
    UserAccount,
)
from app.services.approval_service import (
    APPROVAL_STATUS_EXPIRED,
    APPROVAL_STATUS_PENDING,
    approve_task_approval,
    create_or_get_task_approval,
    escalate_task_approval,
    get_approval_by_task_id,
    is_approval_required,
    reject_task_approval,
)
from app.services.callback_service import run_callback_tick
from app.services.governance_service import (
    create_blacklist_rule,
    create_command_template,
    evaluate_command_policy,
    get_template_by_template_id,
    merge_risk_level,
    normalize_risk_level,
    record_governance_audit,
    update_blacklist_rule,
    update_command_template,
)
from app.services.jumpserver.client import JumpServerClient, JumpServerClientError
from app.services.metrics_aggregation_service import run_metrics_preaggregation
from app.services.orchestrator_service import run_orchestrator_tick
from app.services.remediation_service import (
    get_contextual_remediation_template,
    list_remediation_templates,
)
from app.services.sync_service import refresh_asset_once, run_sync_once
from app.services.task_retry_service import RETRYABLE_FAILURE_CODES, run_task_refresh_retry_batch
from app.api.routes.auth import router as auth_router
from app.api.routes.environment_packages import router as environment_packages_router
from app.api.routes.users import router as users_router
from app.api.routes.mcp import router as mcp_router


configure_logging(settings.app_log_level)
logger = logging.getLogger("opspaw.api")

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(mcp_router)
app.include_router(environment_packages_router)


class CreateTaskRequest(BaseModel):
    command: str = Field(default="", max_length=2048)
    command_template_id: str = Field(default="", max_length=64)
    target_asset_id: str = Field(min_length=1, max_length=64)
    run_as_system_user_id: str = Field(min_length=1, max_length=64)
    reason: str = Field(default="", max_length=1024)
    risk_level: str = Field(default="readonly", max_length=32)
    source: str = Field(default="api", max_length=32)
    idempotency_key: str = Field(default="")
    callback_url: str = Field(default="", max_length=1024)
    callback_secret: str = Field(default="", max_length=255)


class CancelTaskRequest(BaseModel):
    reason: str = Field(default="canceled by user", max_length=1024)


class ApprovalDecisionRequest(BaseModel):
    reason: str = Field(default="", max_length=1024)


class GovernancePolicyEvaluateRequest(BaseModel):
    command: str = Field(default="", max_length=2048)
    command_template_id: str = Field(default="", max_length=64)
    requested_risk_level: str = Field(default="readonly", max_length=32)


class CreateCommandTemplateRequest(BaseModel):
    template_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    description: str = Field(default="", max_length=1024)
    command: str = Field(min_length=1, max_length=2048)
    risk_level: str = Field(default="readonly", max_length=32)
    enabled: bool = True


class UpdateCommandTemplateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    description: str | None = Field(default=None, max_length=1024)
    command: str | None = Field(default=None, max_length=2048)
    risk_level: str | None = Field(default=None, max_length=32)
    enabled: bool | None = None


class CreateBlacklistRuleRequest(BaseModel):
    pattern: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=1024)
    hard_block: bool = True
    enabled: bool = True


class UpdateBlacklistRuleRequest(BaseModel):
    pattern: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=1024)
    hard_block: bool | None = None
    enabled: bool | None = None


class ReplayCallbackDeliveryRequest(BaseModel):
    reset_attempts: bool = Field(default=False)


class ReplayCallbackDeliveriesRequest(BaseModel):
    delivery_ids: list[str] = Field(default_factory=list)
    status: str = Field(default="dead", max_length=16)
    task_id: str = Field(default="", max_length=64)
    error_contains: str = Field(default="", max_length=128)
    limit: int = Field(default=100, ge=1, le=500)
    reset_attempts: bool = Field(default=False)
    dry_run: bool = Field(default=False)


class BatchRefreshRetryTasksRequest(BaseModel):
    task_ids: list[str] = Field(default_factory=list)
    hours: int = Field(default=24, ge=1, le=24 * 30)
    source: str = Field(default="", max_length=32)
    failure_codes: list[str] = Field(default_factory=list)
    limit: int = Field(default=100, ge=1, le=500)
    window_size: int = Field(default=0, ge=0, le=100)
    max_windows: int = Field(default=0, ge=0, le=20)
    same_asset_max_retries: int = Field(default=0, ge=0, le=100)
    task_cooldown_minutes: int = Field(default=0, ge=0, le=24 * 60)
    dry_run: bool = Field(default=False)


class CreateInferenceDeviceRequest(BaseModel):
    device_code: str = Field(min_length=1, max_length=64)
    name: str = Field(default="", max_length=128)
    hostname: str = Field(default="", max_length=255)
    ip: str = Field(default="", max_length=255)
    asset_id: str = Field(default="", max_length=36)
    jms_asset_id: str = Field(default="", max_length=64)
    owner_team: str = Field(default="", max_length=128)
    location: str = Field(default="", max_length=255)
    os_type: str = Field(default="", max_length=64)
    os_version: str = Field(default="", max_length=128)
    cpu_arch: str = Field(default="", max_length=64)
    cpu_model: str = Field(default="", max_length=255)
    memory_gb: str = Field(default="", max_length=32)
    storage_summary: str = Field(default="", max_length=512)
    accelerator_vendor: str = Field(default="", max_length=64)
    accelerator_model: str = Field(default="", max_length=128)
    accelerator_count: str = Field(default="", max_length=32)
    accelerator_memory_gb: str = Field(default="", max_length=32)
    driver_version: str = Field(default="", max_length=128)
    firmware_version: str = Field(default="", max_length=128)
    status: str = Field(default="active", max_length=32)
    notes: str = Field(default="", max_length=2048)


class UpdateInferenceDeviceRequest(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    hostname: str | None = Field(default=None, max_length=255)
    ip: str | None = Field(default=None, max_length=255)
    asset_id: str | None = Field(default=None, max_length=36)
    jms_asset_id: str | None = Field(default=None, max_length=64)
    owner_team: str | None = Field(default=None, max_length=128)
    location: str | None = Field(default=None, max_length=255)
    os_type: str | None = Field(default=None, max_length=64)
    os_version: str | None = Field(default=None, max_length=128)
    cpu_arch: str | None = Field(default=None, max_length=64)
    cpu_model: str | None = Field(default=None, max_length=255)
    memory_gb: str | None = Field(default=None, max_length=32)
    storage_summary: str | None = Field(default=None, max_length=512)
    accelerator_vendor: str | None = Field(default=None, max_length=64)
    accelerator_model: str | None = Field(default=None, max_length=128)
    accelerator_count: str | None = Field(default=None, max_length=32)
    accelerator_memory_gb: str | None = Field(default=None, max_length=32)
    driver_version: str | None = Field(default=None, max_length=128)
    firmware_version: str | None = Field(default=None, max_length=128)
    status: str | None = Field(default=None, max_length=32)
    notes: str | None = Field(default=None, max_length=2048)


class CreateEnvironmentSpecRequest(BaseModel):
    spec_id: str = Field(default="", max_length=64)
    name: str = Field(min_length=1, max_length=128)
    version: str = Field(default="", max_length=64)
    description: str = Field(default="", max_length=2048)
    os_type: str = Field(default="", max_length=64)
    os_version: str = Field(default="", max_length=128)
    accelerator_vendor: str = Field(default="", max_length=64)
    accelerator_model: str = Field(default="", max_length=128)
    required_accelerator_type: str = Field(default="", max_length=64)
    min_vram_gb: int | None = None
    min_ram_gb: int | None = None
    required_cuda_version: str = Field(default="", max_length=128)
    required_capabilities: list[str] = Field(default_factory=list)
    notes: str = Field(default="", max_length=2048)
    min_accelerator_count: str = Field(default="", max_length=32)
    min_accelerator_memory_gb: str = Field(default="", max_length=32)
    driver_version: str = Field(default="", max_length=128)
    runtime_name: str = Field(default="", max_length=128)
    runtime: str = Field(default="", max_length=128)
    accelerator_type: str = Field(default="", max_length=64)
    runtime_version: str = Field(default="", max_length=128)
    python_version: str = Field(default="", max_length=64)
    framework: str = Field(default="", max_length=128)
    framework_version: str = Field(default="", max_length=128)
    inference_server: str = Field(default="", max_length=128)
    container_image: str = Field(default="", max_length=512)
    dependency_manifest: str = Field(default="", max_length=4096)
    ports: str = Field(default="", max_length=512)
    startup_command: str = Field(default="", max_length=2048)
    health_check: str = Field(default="", max_length=2048)
    enabled: bool = True


class UpdateEnvironmentSpecRequest(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    version: str | None = Field(default=None, max_length=64)
    description: str | None = Field(default=None, max_length=2048)
    os_type: str | None = Field(default=None, max_length=64)
    os_version: str | None = Field(default=None, max_length=128)
    accelerator_vendor: str | None = Field(default=None, max_length=64)
    accelerator_model: str | None = Field(default=None, max_length=128)
    min_accelerator_count: str | None = Field(default=None, max_length=32)
    min_accelerator_memory_gb: str | None = Field(default=None, max_length=32)
    driver_version: str | None = Field(default=None, max_length=128)
    runtime_name: str | None = Field(default=None, max_length=128)
    runtime_version: str | None = Field(default=None, max_length=128)
    python_version: str | None = Field(default=None, max_length=64)
    framework: str | None = Field(default=None, max_length=128)
    framework_version: str | None = Field(default=None, max_length=128)
    inference_server: str | None = Field(default=None, max_length=128)
    container_image: str | None = Field(default=None, max_length=512)
    dependency_manifest: str | None = Field(default=None, max_length=4096)
    ports: str | None = Field(default=None, max_length=512)
    startup_command: str | None = Field(default=None, max_length=2048)
    health_check: str | None = Field(default=None, max_length=2048)
    enabled: bool | None = None


class CreateModelDeploymentRequirementRequest(BaseModel):
    requirement_id: str = Field(default="", max_length=64)
    model_id: str = Field(default="", max_length=128)
    model_name: str = Field(default="", max_length=255)
    model_version: str = Field(default="", max_length=128)
    model_platform_url: str = Field(default="", max_length=1024)
    model_artifact_uri: str = Field(default="", max_length=1024)
    environment_spec_id: str = Field(default="", max_length=64)
    accelerator_vendor: str = Field(default="", max_length=64)
    accelerator_model: str = Field(default="", max_length=128)
    min_accelerator_count: str = Field(default="", max_length=32)
    min_accelerator_memory_gb: str = Field(default="", max_length=32)
    performance_baseline: str = Field(default="", max_length=2048)
    deployment_notes: str = Field(default="", max_length=2048)
    source: str = Field(default="manual", max_length=64)
    status: str = Field(default="active", max_length=32)
    # Backward-compatible legacy inference-environment fields. They are mapped
    # into the current normalized model fields in create_model_deployment_requirement.
    required_accelerator_type: str = Field(default="", max_length=64)
    min_vram_gb: int | None = None
    min_ram_gb: int | None = None
    required_cuda_version: str = Field(default="", max_length=128)
    required_capabilities: list[str] = Field(default_factory=list)
    notes: str = Field(default="", max_length=2048)


class UpdateModelDeploymentRequirementRequest(BaseModel):
    model_id: str | None = Field(default=None, max_length=128)
    model_name: str | None = Field(default=None, max_length=255)
    model_version: str | None = Field(default=None, max_length=128)
    model_platform_url: str | None = Field(default=None, max_length=1024)
    model_artifact_uri: str | None = Field(default=None, max_length=1024)
    environment_spec_id: str | None = Field(default=None, max_length=64)
    accelerator_vendor: str | None = Field(default=None, max_length=64)
    accelerator_model: str | None = Field(default=None, max_length=128)
    min_accelerator_count: str | None = Field(default=None, max_length=32)
    min_accelerator_memory_gb: str | None = Field(default=None, max_length=32)
    performance_baseline: str | None = Field(default=None, max_length=2048)
    deployment_notes: str | None = Field(default=None, max_length=2048)
    source: str | None = Field(default=None, max_length=64)
    status: str | None = Field(default=None, max_length=32)


class CreateEnvironmentImplementationRequest(BaseModel):
    implementation_name: str = Field(default="", max_length=128)
    spec_id: str = Field(default="", max_length=64)
    device_ids: list[str] = Field(default_factory=list)
    engine: str = Field(default="", max_length=128)
    engine_version: str = Field(default="", max_length=128)
    endpoint: str = Field(default="", max_length=1024)
    status: str = Field(default="", max_length=32)
    device_id: str = Field(default="", max_length=36)
    environment_spec_id: str = Field(default="", max_length=64)
    requirement_id: str = Field(default="", max_length=64)
    implementation_status: str = Field(default="planned", max_length=32)
    implemented_by: str = Field(default="", max_length=64)
    implemented_at: datetime | None = None
    install_method: str = Field(default="manual", max_length=128)
    actual_os_version: str = Field(default="", max_length=128)
    actual_driver_version: str = Field(default="", max_length=128)
    actual_runtime_version: str = Field(default="", max_length=128)
    actual_framework_version: str = Field(default="", max_length=128)
    actual_inference_server: str = Field(default="", max_length=128)
    actual_container_image: str = Field(default="", max_length=512)
    config_summary: str = Field(default="", max_length=2048)
    artifact_uri: str = Field(default="", max_length=1024)
    log_uri: str = Field(default="", max_length=1024)
    diff_summary: str = Field(default="", max_length=2048)
    issue_summary: str = Field(default="", max_length=2048)


class UpdateEnvironmentImplementationRequest(BaseModel):
    device_id: str | None = Field(default=None, max_length=36)
    environment_spec_id: str | None = Field(default=None, max_length=64)
    requirement_id: str | None = Field(default=None, max_length=64)
    implementation_status: str | None = Field(default=None, max_length=32)
    implemented_by: str | None = Field(default=None, max_length=64)
    implemented_at: datetime | None = None
    install_method: str | None = Field(default=None, max_length=128)
    actual_os_version: str | None = Field(default=None, max_length=128)
    actual_driver_version: str | None = Field(default=None, max_length=128)
    actual_runtime_version: str | None = Field(default=None, max_length=128)
    actual_framework_version: str | None = Field(default=None, max_length=128)
    actual_inference_server: str | None = Field(default=None, max_length=128)
    actual_container_image: str | None = Field(default=None, max_length=512)
    config_summary: str | None = Field(default=None, max_length=2048)
    artifact_uri: str | None = Field(default=None, max_length=1024)
    log_uri: str | None = Field(default=None, max_length=1024)
    diff_summary: str | None = Field(default=None, max_length=2048)
    issue_summary: str | None = Field(default=None, max_length=2048)


class CreateEnvironmentHandoverRequest(BaseModel):
    target_owner: str = Field(default="", max_length=128)
    reason: str = Field(default="", max_length=2048)
    artifacts: list[dict] = Field(default_factory=list)
    handover_no: str = Field(default="", max_length=64)
    title: str = Field(default="", max_length=255)
    device_id: str = Field(default="", max_length=36)
    implementation_id: str = Field(default="", max_length=36)
    requirement_id: str = Field(default="", max_length=64)
    environment_spec_id: str = Field(default="", max_length=64)
    status: str = Field(default="draft", max_length=32)
    test_result: str = Field(default="pending", max_length=32)
    test_report_url: str = Field(default="", max_length=1024)
    model_platform_url: str = Field(default="", max_length=1024)
    package_manifest: str = Field(default="", max_length=4096)
    validation_summary: str = Field(default="", max_length=2048)
    recipient: str = Field(default="", max_length=128)
    accepted_by: str = Field(default="", max_length=64)
    accepted_at: datetime | None = None
    rejection_reason: str = Field(default="", max_length=2048)


class UpdateEnvironmentHandoverRequest(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    device_id: str | None = Field(default=None, max_length=36)
    implementation_id: str | None = Field(default=None, max_length=36)
    requirement_id: str | None = Field(default=None, max_length=64)
    environment_spec_id: str | None = Field(default=None, max_length=64)
    status: str | None = Field(default=None, max_length=32)
    test_result: str | None = Field(default=None, max_length=32)
    test_report_url: str | None = Field(default=None, max_length=1024)
    model_platform_url: str | None = Field(default=None, max_length=1024)
    package_manifest: str | None = Field(default=None, max_length=4096)
    validation_summary: str | None = Field(default=None, max_length=2048)
    recipient: str | None = Field(default=None, max_length=128)
    accepted_by: str | None = Field(default=None, max_length=64)
    accepted_at: datetime | None = None
    rejection_reason: str | None = Field(default=None, max_length=2048)


class HandoverStatusActionRequest(BaseModel):
    reason: str = Field(default="", max_length=2048)
    operator_id: str = Field(default="", max_length=64)



TASK_REFRESH_RETRYABLE_CODES = set(RETRYABLE_FAILURE_CODES)


def _extract_operator_id(request: Request) -> str:
    operator = (request.headers.get("x-operator-id") or "").strip()
    if operator:
        return operator[:64]
    return "unknown"


def _extract_source_ip(request: Request) -> str:
    if request.client and request.client.host:
        return str(request.client.host)[:64]
    forwarded_for = (request.headers.get("x-forwarded-for") or "").strip()
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()[:64]
    return "unknown"


def _compact_json(payload: object, max_len: int) -> str:
    raw = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    if len(raw) <= max_len:
        return raw
    return raw[: max_len - 3] + "..."


def _build_callback_replay_audit_response(item: CallbackReplayAudit) -> dict:
    return {
        "audit_id": item.id,
        "endpoint": item.endpoint,
        "operator_id": item.operator_id,
        "source_ip": item.source_ip,
        "trace_id": item.trace_id,
        "dry_run": item.dry_run,
        "matched": item.matched,
        "replayed": item.replayed,
        "skipped_non_replayable": item.skipped_non_replayable,
        "blocked_by_guardrail": item.blocked_by_guardrail,
        "guardrail_reason": item.guardrail_reason,
        "created_at": _format_dt(item.created_at),
    }


def _insert_callback_replay_audit(
    *,
    session,
    endpoint: str,
    operator_id: str,
    source_ip: str,
    dry_run: bool,
    matched: int,
    replayed: int,
    skipped_non_replayable: int,
    blocked_by_guardrail: bool,
    guardrail_reason: str,
    filters: dict,
    delivery_ids: list[str],
) -> CallbackReplayAudit:
    item = CallbackReplayAudit(
        endpoint=endpoint[:128],
        operator_id=operator_id[:64],
        source_ip=source_ip[:64],
        trace_id=(get_trace_id() or "")[:64],
        dry_run=dry_run,
        matched=matched,
        replayed=replayed,
        skipped_non_replayable=skipped_non_replayable,
        blocked_by_guardrail=blocked_by_guardrail,
        guardrail_reason=guardrail_reason[:255],
        filters_json=_compact_json(filters, max_len=4096),
        delivery_ids_json=_compact_json(delivery_ids[:120], max_len=8192),
    )
    session.add(item)
    session.flush()
    return item


def _format_dt(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _to_utc_hour_bucket(value: datetime | None) -> str:
    if value is None:
        return datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0).isoformat()
    if value.tzinfo is None:
        normalized = value.replace(tzinfo=timezone.utc)
    else:
        normalized = value.astimezone(timezone.utc)
    return normalized.replace(minute=0, second=0, microsecond=0).isoformat()


def _to_bucket_utc(value: datetime | None, granularity: str) -> str:
    if granularity == "day":
        if value is None:
            now = datetime.now(timezone.utc)
            return now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        if value.tzinfo is None:
            normalized = value.replace(tzinfo=timezone.utc)
        else:
            normalized = value.astimezone(timezone.utc)
        return normalized.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    return _to_utc_hour_bucket(value)


def _to_buckets(data: dict[str, int], key_name: str) -> list[dict]:
    rows = sorted(data.items(), key=lambda item: (-item[1], item[0]))
    return [{key_name: key, "count": count} for key, count in rows]


def _normalize_failed_reason(reason: str) -> tuple[str | None, str]:
    code = infer_failure_code(reason)
    if code:
        return code, strip_failure_prefix(reason)
    return None, reason


def _is_http_url(value: str) -> bool:
    trimmed = value.strip().lower()
    return trimmed.startswith("http://") or trimmed.startswith("https://")


def _parse_json_safe(raw: str, fallback):
    try:
        return json.loads(raw or "")
    except Exception:
        return fallback


def _build_task_retry_audit_response(item: TaskRetryAudit) -> dict:
    summary = _parse_json_safe(item.summary_json, {})
    return {
        "audit_id": item.id,
        "endpoint": item.endpoint,
        "operator_id": item.operator_id,
        "source_ip": item.source_ip,
        "trace_id": item.trace_id,
        "dry_run": item.dry_run,
        "effective_hours": item.effective_hours,
        "source_filter": item.source_filter or None,
        "failure_codes": [code for code in (item.failure_codes_csv or "").split(",") if code],
        "window_size": item.window_size,
        "max_windows": item.max_windows,
        "same_asset_max_retries": item.same_asset_max_retries,
        "requested": item.requested,
        "missing_tasks": item.missing_tasks,
        "matched_by_failure": item.matched_by_failure,
        "queued": item.queued,
        "skipped_non_retryable": item.skipped_non_retryable,
        "skipped_in_progress": item.skipped_in_progress,
        "skipped_asset_not_found": item.skipped_asset_not_found,
        "skipped_rate_limited": item.skipped_rate_limited,
        "skipped_asset_guardrail": item.skipped_asset_guardrail,
        "skipped_task_cooldown": int(summary.get("skipped_task_cooldown", 0) or 0),
        "filters": _parse_json_safe(item.filters_json, {}),
        "summary": summary,
        "created_at": _format_dt(item.created_at),
    }


def _build_task_retry_audit_item_response(item: TaskRetryAuditItem) -> dict:
    return {
        "item_id": item.id,
        "audit_id": item.audit_id,
        "task_id": item.task_id,
        "target_asset_id": item.target_asset_id,
        "source": item.source,
        "action": item.action,
        "failure_code": item.failure_code or None,
        "final_status": item.final_status or None,
        "final_failure_code": item.final_failure_code or None,
        "message": item.message,
        "created_at": _format_dt(item.created_at),
    }


def _build_approval_action_response(item: ApprovalActionAudit) -> dict:
    return {
        "action_id": item.id,
        "approval_id": item.approval_id,
        "task_id": item.task_id,
        "action": item.action,
        "operator_id": item.operator_id,
        "source_ip": item.source_ip,
        "reason": item.reason,
        "created_at": _format_dt(item.created_at),
    }


def _build_approval_response(item: ApprovalRequest, task: Task | None = None) -> dict:
    return {
        "approval_id": item.id,
        "task_id": item.task_id,
        "status": item.status,
        "requested_by": item.requested_by,
        "source_ip": item.source_ip,
        "decided_by": item.decided_by or None,
        "decision_reason": item.decision_reason or None,
        "current_level": item.current_level,
        "max_level": item.max_level,
        "escalation_count": item.escalation_count,
        "requested_at": _format_dt(item.requested_at),
        "decided_at": _format_dt(item.decided_at),
        "next_escalate_at": _format_dt(item.next_escalate_at),
        "expires_at": _format_dt(item.expires_at),
        "created_at": _format_dt(item.created_at),
        "updated_at": _format_dt(item.updated_at),
        "task_status": task.status if task else None,
        "task_source": task.source if task else None,
        "task_risk_level": task.risk_level if task else None,
    }


def _build_command_template_response(item: CommandTemplate) -> dict:
    return {
        "template_uuid": item.id,
        "template_id": item.template_id,
        "name": item.name,
        "description": item.description,
        "command": item.command,
        "risk_level": item.risk_level,
        "enabled": bool(item.enabled),
        "created_by": item.created_by,
        "updated_by": item.updated_by,
        "created_at": _format_dt(item.created_at),
        "updated_at": _format_dt(item.updated_at),
    }


def _build_blacklist_rule_response(item: CommandBlacklistRule) -> dict:
    return {
        "rule_id": item.id,
        "pattern": item.pattern,
        "description": item.description,
        "hard_block": bool(item.hard_block),
        "enabled": bool(item.enabled),
        "created_by": item.created_by,
        "updated_by": item.updated_by,
        "created_at": _format_dt(item.created_at),
        "updated_at": _format_dt(item.updated_at),
    }


def _build_governance_audit_response(item: GovernanceAudit) -> dict:
    return {
        "audit_id": item.id,
        "entity_type": item.entity_type,
        "entity_id": item.entity_id,
        "action": item.action,
        "operator_id": item.operator_id,
        "source_ip": item.source_ip,
        "detail": _parse_json_safe(item.detail_json, {}),
        "created_at": _format_dt(item.created_at),
    }


def _render_task_retry_audit_csv(*, audit: dict, items: list[dict]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "audit_id",
            "operator_id",
            "source_ip",
            "created_at",
            "task_id",
            "target_asset_id",
            "source",
            "action",
            "failure_code",
            "final_status",
            "final_failure_code",
            "message",
        ]
    )
    for item in items:
        writer.writerow(
            [
                audit.get("audit_id", ""),
                audit.get("operator_id", ""),
                audit.get("source_ip", ""),
                audit.get("created_at", ""),
                item.get("task_id", ""),
                item.get("target_asset_id", ""),
                item.get("source", ""),
                item.get("action", ""),
                item.get("failure_code", ""),
                item.get("final_status", ""),
                item.get("final_failure_code", ""),
                item.get("message", ""),
            ]
        )
    return buffer.getvalue()


def _build_execution_response(
    execution: Execution,
    task: Task | None,
    audit_relation_ids: list[str],
) -> dict:
    result_summary = execution.result_summary or ""
    failure_code = infer_failure_code(result_summary)
    error_message = strip_failure_prefix(result_summary) if failure_code else None

    if not failure_code and task and task.status == "failed":
        task_failure_code = infer_failure_code(task.reason)
        if task_failure_code:
            failure_code = task_failure_code
            error_message = strip_failure_prefix(task.reason)

    return {
        "execution_id": execution.id,
        "task_id": execution.task_id,
        "jms_execution_id": execution.jms_execution_id,
        "status": execution.status,
        "result_summary": result_summary,
        "failure_code": failure_code,
        "error_message": error_message,
        "trace_id": task.trace_id if task else get_trace_id(),
        "started_at": _format_dt(execution.started_at),
        "finished_at": _format_dt(execution.finished_at),
        "created_at": _format_dt(execution.created_at),
        "updated_at": _format_dt(execution.updated_at),
        "audit_relation_ids": audit_relation_ids,
    }


def _build_callback_hook_response(hook: CallbackHook) -> dict:
    return {
        "hook_id": hook.id,
        "task_id": hook.task_id,
        "callback_url": hook.callback_url,
        "status": hook.status,
        "created_at": _format_dt(hook.created_at),
        "updated_at": _format_dt(hook.updated_at),
    }


def _build_callback_delivery_response(delivery: CallbackDelivery) -> dict:
    return {
        "delivery_id": delivery.id,
        "task_id": delivery.task_id,
        "hook_id": delivery.hook_id,
        "event_type": delivery.event_type,
        "status": delivery.status,
        "attempts": delivery.attempts,
        "max_attempts": delivery.max_attempts,
        "next_retry_at": _format_dt(delivery.next_retry_at),
        "last_http_status": delivery.last_http_status,
        "last_error": delivery.last_error,
        "created_at": _format_dt(delivery.created_at),
        "updated_at": _format_dt(delivery.updated_at),
    }


def _build_sync_snapshot_response(snapshot: SyncSnapshot) -> dict:
    return {
        "snapshot_id": snapshot.id,
        "source": snapshot.source,
        "snapshot_type": snapshot.snapshot_type,
        "offset": snapshot.offset,
        "next_offset": snapshot.next_offset,
        "page_size": snapshot.page_size,
        "fetched_assets": snapshot.fetched_assets,
        "fetched_system_users": snapshot.fetched_system_users,
        "fetched_relations": snapshot.fetched_relations,
        "upstream_total_assets": snapshot.upstream_total_assets,
        "local_total_assets": snapshot.local_total_assets,
        "local_total_system_users": snapshot.local_total_system_users,
        "local_total_relations": snapshot.local_total_relations,
        "consistency_status": snapshot.consistency_status,
        "consistency_delta_assets": snapshot.consistency_delta_assets,
        "checksum": snapshot.checksum,
        "detail": snapshot.detail,
        "created_at": _format_dt(snapshot.created_at),
    }


def _build_asset_projection_response(asset: AssetProjection) -> dict:
    return {
        "asset_id": asset.id,
        "jms_asset_id": asset.jms_asset_id,
        "hostname": asset.hostname,
        "ip": asset.ip,
        "status": asset.status,
        "freshness_status": asset.freshness_status,
        "sync_at": _format_dt(asset.sync_at),
        "created_at": _format_dt(asset.created_at),
        "updated_at": _format_dt(asset.updated_at),
    }



def _set_if_present(item, payload: BaseModel, fields: list[str]) -> None:
    data = payload.model_dump(exclude_unset=True)
    for field in fields:
        if field in data and data[field] is not None:
            setattr(item, field, data[field])


def _missing_response(message: str) -> JSONResponse:
    return JSONResponse(status_code=404, content={"code": "NOT_FOUND", "message": message, "trace_id": get_trace_id()})


def _conflict_response(message: str) -> JSONResponse:
    return JSONResponse(status_code=409, content={"code": "ALREADY_EXISTS", "message": message, "trace_id": get_trace_id()})


def _build_inference_device_response(item: InferenceDevice) -> dict:
    return {
        "device_id": item.id,
        "device_code": item.device_code,
        "name": item.name,
        "hostname": item.hostname,
        "ip": item.ip,
        "asset_id": item.asset_id or None,
        "jms_asset_id": item.jms_asset_id or None,
        "owner_team": item.owner_team or None,
        "location": item.location or None,
        "os_type": item.os_type or None,
        "os_version": item.os_version or None,
        "cpu_arch": item.cpu_arch or None,
        "cpu_model": item.cpu_model or None,
        "memory_gb": item.memory_gb or None,
        "storage_summary": item.storage_summary or None,
        "accelerator_vendor": item.accelerator_vendor or None,
        "accelerator_model": item.accelerator_model or None,
        "accelerator_count": item.accelerator_count or None,
        "accelerator_memory_gb": item.accelerator_memory_gb or None,
        "driver_version": item.driver_version or None,
        "firmware_version": item.firmware_version or None,
        "status": item.status,
        "notes": item.notes or None,
        "created_by": item.created_by,
        "updated_by": item.updated_by,
        "created_at": _format_dt(item.created_at),
        "updated_at": _format_dt(item.updated_at),
    }


def _build_environment_spec_response(item: EnvironmentSpec) -> dict:
    return {
        "spec_uuid": item.id,
        "spec_id": item.spec_id,
        "name": item.name,
        "version": item.version,
        "description": item.description,
        "os_type": item.os_type,
        "os_version": item.os_version,
        "accelerator_vendor": item.accelerator_vendor,
        "accelerator_model": item.accelerator_model,
        "accelerator_type": item.accelerator_vendor,
        "min_accelerator_count": item.min_accelerator_count,
        "min_accelerator_memory_gb": item.min_accelerator_memory_gb,
        "driver_version": item.driver_version,
        "runtime_name": item.runtime_name,
        "runtime": item.runtime_name,
        "runtime_version": item.runtime_version,
        "python_version": item.python_version,
        "framework": item.framework,
        "framework_version": item.framework_version,
        "inference_server": item.inference_server,
        "container_image": item.container_image,
        "dependency_manifest": item.dependency_manifest,
        "ports": item.ports,
        "startup_command": item.startup_command,
        "health_check": item.health_check,
        "enabled": bool(item.enabled),
        "created_by": item.created_by,
        "updated_by": item.updated_by,
        "created_at": _format_dt(item.created_at),
        "updated_at": _format_dt(item.updated_at),
    }


def _build_model_requirement_response(item: ModelDeploymentRequirement) -> dict:
    return {
        "requirement_uuid": item.id,
        "requirement_id": item.requirement_id,
        "model_id": item.model_id,
        "model_name": item.model_name,
        "model_version": item.model_version,
        "model_platform_url": item.model_platform_url,
        "model_artifact_uri": item.model_artifact_uri,
        "environment_spec_id": item.environment_spec_id,
        "accelerator_vendor": item.accelerator_vendor,
        "accelerator_model": item.accelerator_model,
        "required_accelerator_type": item.accelerator_vendor,
        "min_accelerator_count": item.min_accelerator_count,
        "min_accelerator_memory_gb": item.min_accelerator_memory_gb,
        "min_vram_gb": int(item.min_accelerator_memory_gb) if item.min_accelerator_memory_gb.isdigit() else None,
        "performance_baseline": item.performance_baseline,
        "deployment_notes": item.deployment_notes,
        "source": item.source,
        "status": item.status,
        "created_by": item.created_by,
        "updated_by": item.updated_by,
        "created_at": _format_dt(item.created_at),
        "updated_at": _format_dt(item.updated_at),
    }


def _build_environment_implementation_response(item: EnvironmentImplementation) -> dict:
    device_ids = [item.device_id] if item.device_id else []
    return {
        "implementation_id": item.id,
        "implementation_name": item.config_summary,
        "device_id": item.device_id,
        "device_ids": device_ids,
        "environment_spec_id": item.environment_spec_id,
        "spec_id": item.environment_spec_id,
        "requirement_id": item.requirement_id,
        "implementation_status": item.implementation_status,
        "status": item.implementation_status,
        "implemented_by": item.implemented_by,
        "implemented_at": _format_dt(item.implemented_at),
        "install_method": item.install_method,
        "actual_os_version": item.actual_os_version,
        "actual_driver_version": item.actual_driver_version,
        "actual_runtime_version": item.actual_runtime_version,
        "actual_framework_version": item.actual_framework_version,
        "actual_inference_server": item.actual_inference_server,
        "engine": item.actual_inference_server,
        "engine_version": item.actual_framework_version or item.actual_runtime_version,
        "endpoint": item.artifact_uri,
        "actual_container_image": item.actual_container_image,
        "config_summary": item.config_summary,
        "artifact_uri": item.artifact_uri,
        "log_uri": item.log_uri,
        "diff_summary": item.diff_summary,
        "issue_summary": item.issue_summary,
        "created_by": item.created_by,
        "updated_by": item.updated_by,
        "created_at": _format_dt(item.created_at),
        "updated_at": _format_dt(item.updated_at),
    }


def _build_environment_handover_response(item: EnvironmentHandover) -> dict:
    return {
        "handover_id": item.id,
        "handover_no": item.handover_no,
        "title": item.title,
        "device_id": item.device_id,
        "implementation_id": item.implementation_id,
        "requirement_id": item.requirement_id,
        "environment_spec_id": item.environment_spec_id,
        "status": item.status,
        "test_result": item.test_result,
        "test_report_url": item.test_report_url,
        "model_platform_url": item.model_platform_url,
        "package_manifest": item.package_manifest,
        "validation_summary": item.validation_summary,
        "recipient": item.recipient,
        "target_owner": item.recipient,
        "accepted_by": item.accepted_by or None,
        "accepted_at": _format_dt(item.accepted_at),
        "rejection_reason": item.rejection_reason or None,
        "created_by": item.created_by,
        "updated_by": item.updated_by,
        "created_at": _format_dt(item.created_at),
        "updated_at": _format_dt(item.updated_at),
    }
@app.on_event("startup")
def startup_event():
    last_error: Exception | None = None
    for attempt in range(1, 11):
        try:
            init_db()
            logger.info("database schema initialized on startup")
            return
        except Exception as exc:  # pragma: no cover - startup guard
            last_error = exc
            logger.warning("database init failed attempt=%s error=%s", attempt, exc)
            time.sleep(2)
    if last_error:
        raise last_error


@app.middleware("http")
async def trace_middleware(request: Request, call_next):
    incoming_trace_id = request.headers.get("x-trace-id")
    trace_id = incoming_trace_id or str(uuid.uuid4())
    set_trace_id(trace_id)

    response = await call_next(request)
    response.headers["x-trace-id"] = trace_id

    clear_trace_id()
    return response


@app.get("/healthz")
def healthz():
    logger.info("health check requested")
    return {
        "status": "ok",
        "service": settings.app_name,
        "env": settings.app_env,
        "version": settings.app_version,
        "trace_id": get_trace_id(),
    }


@app.get("/readyz")
def readyz():
    # MVP bootstrap: readiness means API process is alive and config loaded.
    return {
        "status": "ready",
        "service": settings.app_name,
        "trace_id": get_trace_id(),
    }


@app.get("/api/v1/system/info")
def system_info():
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "env": settings.app_env,
        "trace_id": get_trace_id(),
    }


@app.get("/api/v1/assets")
def list_assets(
    status: str = Query(default="", max_length=32),
    freshness_status: str = Query(default="", max_length=16),
    search: str = Query(default="", max_length=255),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    with session_scope() as session:
        stmt = select(AssetProjection)
        count_stmt = select(func.count()).select_from(AssetProjection)
        if status:
            stmt = stmt.where(AssetProjection.status == status)
            count_stmt = count_stmt.where(AssetProjection.status == status)
        if freshness_status:
            stmt = stmt.where(AssetProjection.freshness_status == freshness_status)
            count_stmt = count_stmt.where(AssetProjection.freshness_status == freshness_status)
        if search:
            pattern = f"%{search.lower()}%"
            predicate = or_(
                func.lower(AssetProjection.hostname).like(pattern),
                func.lower(AssetProjection.ip).like(pattern),
                func.lower(AssetProjection.jms_asset_id).like(pattern),
            )
            stmt = stmt.where(predicate)
            count_stmt = count_stmt.where(predicate)

        total = int(session.scalar(count_stmt) or 0)
        items = list(
            session.scalars(
                stmt.order_by(AssetProjection.updated_at.desc(), AssetProjection.id.desc())
                .offset(offset)
                .limit(limit)
            )
        )
        return {
            "items": [_build_asset_projection_response(item) for item in items],
            "total": total,
            "limit": limit,
            "offset": offset,
            "status_filter": status or None,
            "freshness_status_filter": freshness_status or None,
            "search_filter": search or None,
            "trace_id": get_trace_id(),
        }
@app.get("/api/v1/inference-environments/devices")
def list_inference_devices(
    status: str = Query(default="", max_length=32),
    accelerator_vendor: str = Query(default="", max_length=64),
    search: str = Query(default="", max_length=255),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    with session_scope() as session:
        stmt = select(InferenceDevice)
        count_stmt = select(func.count()).select_from(InferenceDevice)
        if status:
            stmt = stmt.where(InferenceDevice.status == status)
            count_stmt = count_stmt.where(InferenceDevice.status == status)
        if accelerator_vendor:
            stmt = stmt.where(InferenceDevice.accelerator_vendor == accelerator_vendor)
            count_stmt = count_stmt.where(InferenceDevice.accelerator_vendor == accelerator_vendor)
        if search:
            pattern = f"%{search.lower()}%"
            predicate = or_(
                func.lower(InferenceDevice.device_code).like(pattern),
                func.lower(InferenceDevice.name).like(pattern),
                func.lower(InferenceDevice.hostname).like(pattern),
                func.lower(InferenceDevice.ip).like(pattern),
                func.lower(InferenceDevice.accelerator_model).like(pattern),
            )
            stmt = stmt.where(predicate)
            count_stmt = count_stmt.where(predicate)
        total = int(session.scalar(count_stmt) or 0)
        items = list(session.scalars(stmt.order_by(InferenceDevice.updated_at.desc(), InferenceDevice.id.desc()).offset(offset).limit(limit)))
        return {"items": [_build_inference_device_response(item) for item in items], "total": total, "limit": limit, "offset": offset, "trace_id": get_trace_id()}


@app.post("/api/v1/inference-environments/devices")
def create_inference_device(payload: CreateInferenceDeviceRequest, request: Request):
    operator_id = _extract_operator_id(request)
    source_ip = _extract_source_ip(request)
    with session_scope() as session:
        existing = session.scalar(select(InferenceDevice).where(InferenceDevice.device_code == payload.device_code))
        if existing:
            return _conflict_response(f"device exists: {payload.device_code}")
        item = InferenceDevice(**payload.model_dump(), created_by=operator_id, updated_by=operator_id)
        session.add(item)
        session.flush()
        record_governance_audit(session=session, entity_type="inference_device", entity_id=item.device_code, action="create", operator_id=operator_id, source_ip=source_ip, detail={"status": item.status})
        return {"status": "ok", "item": _build_inference_device_response(item), **_build_inference_device_response(item), "trace_id": get_trace_id()}


@app.patch("/api/v1/inference-environments/devices/{device_id}")
def update_inference_device(device_id: str, payload: UpdateInferenceDeviceRequest, request: Request):
    operator_id = _extract_operator_id(request)
    with session_scope() as session:
        item = session.get(InferenceDevice, device_id)
        if not item:
            return _missing_response(f"device not found: {device_id}")
        _set_if_present(item, payload, list(UpdateInferenceDeviceRequest.model_fields.keys()))
        item.updated_by = operator_id
        session.flush()
        return {"status": "ok", "item": _build_inference_device_response(item), **_build_inference_device_response(item), "trace_id": get_trace_id()}


@app.get("/api/v1/inference-environments/specs")
def list_environment_specs(enabled: bool | None = Query(default=None), search: str = Query(default="", max_length=255), limit: int = Query(default=50, ge=1, le=500), offset: int = Query(default=0, ge=0)):
    with session_scope() as session:
        stmt = select(EnvironmentSpec)
        count_stmt = select(func.count()).select_from(EnvironmentSpec)
        if enabled is not None:
            stmt = stmt.where(EnvironmentSpec.enabled.is_(enabled))
            count_stmt = count_stmt.where(EnvironmentSpec.enabled.is_(enabled))
        if search:
            pattern = f"%{search.lower()}%"
            predicate = or_(func.lower(EnvironmentSpec.spec_id).like(pattern), func.lower(EnvironmentSpec.name).like(pattern), func.lower(EnvironmentSpec.framework).like(pattern))
            stmt = stmt.where(predicate)
            count_stmt = count_stmt.where(predicate)
        total = int(session.scalar(count_stmt) or 0)
        items = list(session.scalars(stmt.order_by(EnvironmentSpec.updated_at.desc(), EnvironmentSpec.id.desc()).offset(offset).limit(limit)))
        return {"items": [_build_environment_spec_response(item) for item in items], "total": total, "limit": limit, "offset": offset, "trace_id": get_trace_id()}


@app.post("/api/v1/inference-environments/specs")
def create_environment_spec(payload: CreateEnvironmentSpecRequest, request: Request):
    operator_id = _extract_operator_id(request)
    source_ip = _extract_source_ip(request)
    spec_id = payload.spec_id or f"spec-{uuid.uuid4().hex[:12]}"
    with session_scope() as session:
        existing = session.scalar(select(EnvironmentSpec).where(EnvironmentSpec.spec_id == spec_id))
        if existing:
            return _conflict_response(f"environment spec exists: {spec_id}")
        data = payload.model_dump(exclude={"spec_id", "runtime", "accelerator_type", "required_accelerator_type", "min_vram_gb", "min_ram_gb", "required_cuda_version", "required_capabilities", "notes"})
        if not data.get("runtime_name"):
            data["runtime_name"] = payload.runtime
        if not data.get("accelerator_vendor"):
            data["accelerator_vendor"] = payload.accelerator_type or payload.required_accelerator_type
        if not data.get("min_accelerator_memory_gb") and payload.min_vram_gb is not None:
            data["min_accelerator_memory_gb"] = str(payload.min_vram_gb)
        if not data.get("runtime_version") and payload.required_cuda_version:
            data["runtime_version"] = payload.required_cuda_version
        if not data.get("description"):
            description_parts = [payload.notes] if payload.notes else []
            if payload.required_capabilities:
                description_parts.append("capabilities: " + ",".join(payload.required_capabilities))
            data["description"] = " ".join(description_parts)
        item = EnvironmentSpec(spec_id=spec_id, **data, created_by=operator_id, updated_by=operator_id)
        session.add(item)
        session.flush()
        record_governance_audit(session=session, entity_type="environment_spec", entity_id=item.spec_id, action="create", operator_id=operator_id, source_ip=source_ip, detail={"name": item.name, "enabled": item.enabled})
        return {"status": "ok", "item": _build_environment_spec_response(item), **_build_environment_spec_response(item), "trace_id": get_trace_id()}


@app.patch("/api/v1/inference-environments/specs/{spec_id}")
def update_environment_spec(spec_id: str, payload: UpdateEnvironmentSpecRequest, request: Request):
    operator_id = _extract_operator_id(request)
    with session_scope() as session:
        item = session.scalar(select(EnvironmentSpec).where(EnvironmentSpec.spec_id == spec_id))
        if not item:
            return _missing_response(f"environment spec not found: {spec_id}")
        _set_if_present(item, payload, list(UpdateEnvironmentSpecRequest.model_fields.keys()))
        item.updated_by = operator_id
        session.flush()
        return {"status": "ok", "item": _build_environment_spec_response(item), **_build_environment_spec_response(item), "trace_id": get_trace_id()}


@app.get("/api/v1/inference-environments/deployment-requirements")
def list_model_deployment_requirements(status: str = Query(default="", max_length=32), model_id: str = Query(default="", max_length=128), limit: int = Query(default=50, ge=1, le=500), offset: int = Query(default=0, ge=0)):
    with session_scope() as session:
        stmt = select(ModelDeploymentRequirement)
        count_stmt = select(func.count()).select_from(ModelDeploymentRequirement)
        if status:
            stmt = stmt.where(ModelDeploymentRequirement.status == status)
            count_stmt = count_stmt.where(ModelDeploymentRequirement.status == status)
        if model_id:
            stmt = stmt.where(ModelDeploymentRequirement.model_id == model_id)
            count_stmt = count_stmt.where(ModelDeploymentRequirement.model_id == model_id)
        total = int(session.scalar(count_stmt) or 0)
        items = list(session.scalars(stmt.order_by(ModelDeploymentRequirement.updated_at.desc(), ModelDeploymentRequirement.id.desc()).offset(offset).limit(limit)))
        return {"items": [_build_model_requirement_response(item) for item in items], "total": total, "limit": limit, "offset": offset, "trace_id": get_trace_id()}


@app.post("/api/v1/inference-environments/deployment-requirements")
def create_model_deployment_requirement(payload: CreateModelDeploymentRequirementRequest, request: Request):
    operator_id = _extract_operator_id(request)
    source_ip = _extract_source_ip(request)
    requirement_id = payload.requirement_id or f"req-{uuid.uuid4().hex[:12]}"
    with session_scope() as session:
        existing = session.scalar(select(ModelDeploymentRequirement).where(ModelDeploymentRequirement.requirement_id == requirement_id))
        if existing:
            return _conflict_response(f"model deployment requirement exists: {requirement_id}")
        data = payload.model_dump(exclude={"requirement_id", "required_accelerator_type", "min_vram_gb", "min_ram_gb", "required_cuda_version", "required_capabilities", "notes"})
        if not data.get("model_name"):
            data["model_name"] = data.get("model_id", "")
        if not data.get("accelerator_vendor"):
            data["accelerator_vendor"] = payload.required_accelerator_type
        if not data.get("min_accelerator_memory_gb") and payload.min_vram_gb is not None:
            data["min_accelerator_memory_gb"] = str(payload.min_vram_gb)
        if not data.get("performance_baseline") and payload.required_cuda_version:
            data["performance_baseline"] = f"cuda={payload.required_cuda_version}"
        if not data.get("deployment_notes"):
            notes = payload.notes or ""
            extra_parts = []
            if payload.min_ram_gb is not None:
                extra_parts.append(f"min_ram_gb={payload.min_ram_gb}")
            if payload.required_capabilities:
                extra_parts.append("capabilities=" + ",".join(payload.required_capabilities))
            if extra_parts:
                notes = (notes + " " + " ".join(extra_parts)).strip()
            data["deployment_notes"] = notes
        item = ModelDeploymentRequirement(requirement_id=requirement_id, **data, created_by=operator_id, updated_by=operator_id)
        session.add(item)
        session.flush()
        record_governance_audit(session=session, entity_type="model_requirement", entity_id=item.requirement_id, action="create", operator_id=operator_id, source_ip=source_ip, detail={"model_id": item.model_id, "model_version": item.model_version})
        return {"status": "ok", "item": _build_model_requirement_response(item), **_build_model_requirement_response(item), "trace_id": get_trace_id()}


@app.patch("/api/v1/inference-environments/deployment-requirements/{requirement_id}")
def update_model_deployment_requirement(requirement_id: str, payload: UpdateModelDeploymentRequirementRequest, request: Request):
    operator_id = _extract_operator_id(request)
    with session_scope() as session:
        item = session.scalar(select(ModelDeploymentRequirement).where(ModelDeploymentRequirement.requirement_id == requirement_id))
        if not item:
            return _missing_response(f"model deployment requirement not found: {requirement_id}")
        _set_if_present(item, payload, list(UpdateModelDeploymentRequirementRequest.model_fields.keys()))
        item.updated_by = operator_id
        session.flush()
        return {"status": "ok", "item": _build_model_requirement_response(item), **_build_model_requirement_response(item), "trace_id": get_trace_id()}


@app.get("/api/v1/inference-environments/implementations")
def list_environment_implementations(device_id: str = Query(default="", max_length=36), requirement_id: str = Query(default="", max_length=64), limit: int = Query(default=50, ge=1, le=500), offset: int = Query(default=0, ge=0)):
    with session_scope() as session:
        stmt = select(EnvironmentImplementation)
        count_stmt = select(func.count()).select_from(EnvironmentImplementation)
        if device_id:
            stmt = stmt.where(EnvironmentImplementation.device_id == device_id)
            count_stmt = count_stmt.where(EnvironmentImplementation.device_id == device_id)
        if requirement_id:
            stmt = stmt.where(EnvironmentImplementation.requirement_id == requirement_id)
            count_stmt = count_stmt.where(EnvironmentImplementation.requirement_id == requirement_id)
        total = int(session.scalar(count_stmt) or 0)
        items = list(session.scalars(stmt.order_by(EnvironmentImplementation.updated_at.desc(), EnvironmentImplementation.id.desc()).offset(offset).limit(limit)))
        return {"items": [_build_environment_implementation_response(item) for item in items], "total": total, "limit": limit, "offset": offset, "trace_id": get_trace_id()}


@app.post("/api/v1/inference-environments/implementations")
def create_environment_implementation(payload: CreateEnvironmentImplementationRequest, request: Request):
    operator_id = _extract_operator_id(request)
    data = payload.model_dump()
    device_id = data.get("device_id") or (data.get("device_ids") or [""])[0]
    environment_spec_id = data.get("environment_spec_id") or data.get("spec_id") or ""
    implementation_status = data.get("implementation_status") or data.get("status") or "planned"
    actual_inference_server = data.get("actual_inference_server") or data.get("engine") or ""
    actual_framework_version = data.get("actual_framework_version") or data.get("engine_version") or ""
    artifact_uri = data.get("artifact_uri") or data.get("endpoint") or ""
    config_summary = data.get("config_summary") or data.get("implementation_name") or ""
    with session_scope() as session:
        item = EnvironmentImplementation(
            device_id=device_id,
            environment_spec_id=environment_spec_id,
            requirement_id=data.get("requirement_id") or "",
            implementation_status=implementation_status,
            implemented_by=data.get("implemented_by") or operator_id,
            implemented_at=data.get("implemented_at"),
            install_method=data.get("install_method") or "manual",
            actual_os_version=data.get("actual_os_version") or "",
            actual_driver_version=data.get("actual_driver_version") or "",
            actual_runtime_version=data.get("actual_runtime_version") or "",
            actual_framework_version=actual_framework_version,
            actual_inference_server=actual_inference_server,
            actual_container_image=data.get("actual_container_image") or "",
            config_summary=config_summary,
            artifact_uri=artifact_uri,
            log_uri=data.get("log_uri") or "",
            diff_summary=data.get("diff_summary") or "",
            issue_summary=data.get("issue_summary") or "",
            created_by=operator_id,
            updated_by=operator_id,
        )
        session.add(item)
        session.flush()
        return {"status": "ok", "item": _build_environment_implementation_response(item), **_build_environment_implementation_response(item), "trace_id": get_trace_id()}


@app.patch("/api/v1/inference-environments/implementations/{implementation_id}")
def update_environment_implementation(implementation_id: str, payload: UpdateEnvironmentImplementationRequest, request: Request):
    operator_id = _extract_operator_id(request)
    with session_scope() as session:
        item = session.get(EnvironmentImplementation, implementation_id)
        if not item:
            return _missing_response(f"environment implementation not found: {implementation_id}")
        _set_if_present(item, payload, list(UpdateEnvironmentImplementationRequest.model_fields.keys()))
        item.updated_by = operator_id
        session.flush()
        return {"status": "ok", "item": _build_environment_implementation_response(item), **_build_environment_implementation_response(item), "trace_id": get_trace_id()}


@app.get("/api/v1/inference-environments/handovers")
def list_environment_handovers(status: str = Query(default="", max_length=32), recipient: str = Query(default="", max_length=128), limit: int = Query(default=50, ge=1, le=500), offset: int = Query(default=0, ge=0)):
    with session_scope() as session:
        stmt = select(EnvironmentHandover)
        count_stmt = select(func.count()).select_from(EnvironmentHandover)
        if status:
            stmt = stmt.where(EnvironmentHandover.status == status)
            count_stmt = count_stmt.where(EnvironmentHandover.status == status)
        if recipient:
            stmt = stmt.where(EnvironmentHandover.recipient == recipient)
            count_stmt = count_stmt.where(EnvironmentHandover.recipient == recipient)
        total = int(session.scalar(count_stmt) or 0)
        items = list(session.scalars(stmt.order_by(EnvironmentHandover.updated_at.desc(), EnvironmentHandover.id.desc()).offset(offset).limit(limit)))
        return {"items": [_build_environment_handover_response(item) for item in items], "total": total, "limit": limit, "offset": offset, "trace_id": get_trace_id()}


@app.post("/api/v1/inference-environments/handovers")
def create_environment_handover(payload: CreateEnvironmentHandoverRequest, request: Request):
    operator_id = _extract_operator_id(request)
    source_ip = _extract_source_ip(request)
    data = payload.model_dump()
    handover_no = data.get("handover_no") or f"H-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:8]}"
    title = data.get("title") or data.get("reason") or f"Environment handover {handover_no}"
    recipient = data.get("recipient") or data.get("target_owner") or ""
    package_manifest = data.get("package_manifest") or (json.dumps(data.get("artifacts", []), ensure_ascii=False) if data.get("artifacts") else "")
    with session_scope() as session:
        existing = session.scalar(select(EnvironmentHandover).where(EnvironmentHandover.handover_no == handover_no))
        if existing:
            return _conflict_response(f"handover exists: {handover_no}")
        item = EnvironmentHandover(
            handover_no=handover_no,
            title=title,
            device_id=data.get("device_id") or "",
            implementation_id=data.get("implementation_id") or "",
            requirement_id=data.get("requirement_id") or "",
            environment_spec_id=data.get("environment_spec_id") or "",
            status=data.get("status") if "status" in payload.model_fields_set else "pending",
            test_result=data.get("test_result") or "pending",
            test_report_url=data.get("test_report_url") or "",
            model_platform_url=data.get("model_platform_url") or "",
            package_manifest=package_manifest,
            validation_summary=data.get("validation_summary") or data.get("reason") or "",
            recipient=recipient,
            accepted_by=data.get("accepted_by") or "",
            accepted_at=data.get("accepted_at"),
            rejection_reason=data.get("rejection_reason") or "",
            created_by=operator_id,
            updated_by=operator_id,
        )
        session.add(item)
        session.flush()
        record_governance_audit(session=session, entity_type="environment_handover", entity_id=item.handover_no, action="create", operator_id=operator_id, source_ip=source_ip, detail={"status": item.status, "recipient": item.recipient})
        return {"status": "ok", "item": _build_environment_handover_response(item), **_build_environment_handover_response(item), "trace_id": get_trace_id()}


@app.patch("/api/v1/inference-environments/handovers/{handover_id}")
def update_environment_handover(handover_id: str, payload: UpdateEnvironmentHandoverRequest, request: Request):
    operator_id = _extract_operator_id(request)
    with session_scope() as session:
        item = session.get(EnvironmentHandover, handover_id)
        if not item:
            item = session.scalar(select(EnvironmentHandover).where(EnvironmentHandover.handover_no == handover_id))
        if not item:
            return _missing_response(f"environment handover not found: {handover_id}")
        _set_if_present(item, payload, list(UpdateEnvironmentHandoverRequest.model_fields.keys()))
        item.updated_by = operator_id
        session.flush()
        return {"status": "ok", "item": _build_environment_handover_response(item), **_build_environment_handover_response(item), "trace_id": get_trace_id()}


@app.post("/api/v1/inference-environments/handovers/{handover_id}/accept")
def accept_environment_handover(handover_id: str, payload: HandoverStatusActionRequest, request: Request):
    operator_id = payload.operator_id or _extract_operator_id(request)
    with session_scope() as session:
        item = session.get(EnvironmentHandover, handover_id) or session.scalar(select(EnvironmentHandover).where(EnvironmentHandover.handover_no == handover_id))
        if not item:
            return _missing_response(f"environment handover not found: {handover_id}")
        item.status = "accepted"
        item.accepted_by = operator_id
        item.accepted_at = datetime.now(timezone.utc)
        item.updated_by = operator_id
        if payload.reason:
            item.validation_summary = payload.reason
        session.flush()
        return {"status": "ok", "item": _build_environment_handover_response(item), **_build_environment_handover_response(item), "trace_id": get_trace_id()}


@app.post("/api/v1/inference-environments/handovers/{handover_id}/reject")
def reject_environment_handover(handover_id: str, payload: HandoverStatusActionRequest, request: Request):
    operator_id = payload.operator_id or _extract_operator_id(request)
    with session_scope() as session:
        item = session.get(EnvironmentHandover, handover_id) or session.scalar(select(EnvironmentHandover).where(EnvironmentHandover.handover_no == handover_id))
        if not item:
            return _missing_response(f"environment handover not found: {handover_id}")
        item.status = "rejected"
        item.rejection_reason = payload.reason
        item.updated_by = operator_id
        session.flush()
        return {"status": "ok", "item": _build_environment_handover_response(item), **_build_environment_handover_response(item), "trace_id": get_trace_id()}


@app.get("/api/v1/inference-environments/compatibility")
def check_inference_environment_compatibility(device_id: str = Query(min_length=1, max_length=36), requirement_id: str = Query(default="", max_length=64), spec_id: str = Query(default="", max_length=64)):
    with session_scope() as session:
        device = session.get(InferenceDevice, device_id)
        if not device:
            return _missing_response(f"device not found: {device_id}")
        requirement = session.scalar(select(ModelDeploymentRequirement).where(ModelDeploymentRequirement.requirement_id == requirement_id)) if requirement_id else None
        spec = session.scalar(select(EnvironmentSpec).where(EnvironmentSpec.spec_id == (spec_id or (requirement.environment_spec_id if requirement else "")))) if (spec_id or requirement) else None
        checks = []
        def add_check(name: str, expected: str, actual: str):
            ok = not expected or expected.lower() == (actual or "").lower()
            checks.append({"name": name, "expected": expected or None, "actual": actual or None, "passed": ok})
        if requirement:
            add_check("accelerator_vendor", requirement.accelerator_vendor, device.accelerator_vendor)
            add_check("accelerator_model", requirement.accelerator_model, device.accelerator_model)
        if spec:
            add_check("os_type", spec.os_type, device.os_type)
            add_check("driver_version", spec.driver_version, device.driver_version)
            add_check("spec_accelerator_vendor", spec.accelerator_vendor, device.accelerator_vendor)
            add_check("spec_accelerator_model", spec.accelerator_model, device.accelerator_model)
        compatible = all(check["passed"] for check in checks) if checks else True
        return {"compatible": compatible, "device": _build_inference_device_response(device), "requirement": _build_model_requirement_response(requirement) if requirement else None, "spec": _build_environment_spec_response(spec) if spec else None, "checks": checks, "trace_id": get_trace_id()}



@app.post("/api/v1/tasks")
def create_task(payload: CreateTaskRequest, request: Request):
    trace_id = get_trace_id() or ""
    idempotency_key = payload.idempotency_key or str(uuid.uuid4())
    template_id = (payload.command_template_id or "").strip()
    inline_command = (payload.command or "").strip()
    if not template_id and not inline_command:
        return JSONResponse(
            status_code=400,
            content={
                "code": "INVALID_ARGUMENT",
                "message": "either command or command_template_id is required",
                "trace_id": trace_id or get_trace_id(),
            },
        )

    callback_url = (payload.callback_url or "").strip()
    callback_secret = (payload.callback_secret or "").strip()
    operator_id = _extract_operator_id(request)
    source_ip = _extract_source_ip(request)
    if callback_url:
        if not _is_http_url(callback_url):
            return JSONResponse(
                status_code=400,
                content={
                    "code": "INVALID_ARGUMENT",
                    "message": "callback_url must start with http:// or https://",
                    "trace_id": trace_id or get_trace_id(),
                },
            )
        policy = evaluate_callback_url_policy(callback_url, resolve_dns=False)
        if not policy.allowed:
            return JSONResponse(
                status_code=400,
                content={
                    "code": "CALLBACK_URL_BLOCKED",
                    "message": policy.reason,
                    "trace_id": trace_id or get_trace_id(),
                },
            )

    with session_scope() as session:
        existing = session.scalar(select(Task).where(Task.idempotency_key == idempotency_key))
        if existing:
            existing_hook = session.scalar(select(CallbackHook).where(CallbackHook.task_id == existing.id))
            existing_approval = get_approval_by_task_id(session, existing.id)
            return {
                "task_id": existing.id,
                "status": existing.status,
                "idempotency_key": existing.idempotency_key,
                "trace_id": trace_id,
                "deduplicated": True,
                "callback_registered": bool(existing_hook),
                "approval_required": is_approval_required(existing.risk_level),
                "approval_id": existing_approval.id if existing_approval else None,
                "approval_status": existing_approval.status if existing_approval else None,
                "risk_level_final": existing.risk_level,
                "command_template_id": existing.command_template_id or None,
            }

        template: CommandTemplate | None = None
        effective_command = inline_command
        if template_id:
            template = get_template_by_template_id(session, template_id)
            if not template:
                return JSONResponse(
                    status_code=404,
                    content={
                        "code": "TEMPLATE_NOT_FOUND",
                        "message": f"command template not found: {template_id}",
                        "trace_id": trace_id or get_trace_id(),
                    },
                )
            if not template.enabled:
                return JSONResponse(
                    status_code=409,
                    content={
                        "code": "TEMPLATE_DISABLED",
                        "message": f"command template disabled: {template_id}",
                        "trace_id": trace_id or get_trace_id(),
                    },
                )
            effective_command = (template.command or "").strip()
        policy_eval = evaluate_command_policy(
            session=session,
            command=effective_command,
            builtin_blacklist_raw=settings.policy_builtin_blacklist,
            requested_risk_level=payload.risk_level,
            template_risk_level=template.risk_level if template else None,
        )
        if not policy_eval["allowed"]:
            return JSONResponse(
                status_code=400,
                content={
                    "code": "POLICY_BLOCKED",
                    "message": policy_eval["block_reason"],
                    "matched_rules": policy_eval["matched"],
                    "trace_id": trace_id or get_trace_id(),
                },
            )

        final_risk_level = merge_risk_level(
            payload.risk_level,
            template.risk_level if template else None,
            policy_eval["inferred_risk_level"],
        )
        approval_required = is_approval_required(final_risk_level)
        task = Task(
            trace_id=trace_id,
            source=payload.source,
            status="approval_pending" if approval_required else "pending",
            risk_level=final_risk_level,
            idempotency_key=idempotency_key,
            command_template_id=template.template_id if template else "",
            command=effective_command,
            target_asset_id=payload.target_asset_id,
            run_as_system_user_id=payload.run_as_system_user_id,
            reason=payload.reason,
        )
        session.add(task)
        session.flush()
        task_id = task.id
        approval_id = None
        approval_status = None
        if approval_required:
            approval, _ = create_or_get_task_approval(
                session=session,
                task=task,
                requested_by=operator_id,
                source_ip=source_ip,
                timeout_hours=max(1, settings.approval_timeout_hours),
                escalation_enabled=settings.approval_escalation_enabled,
                escalation_after_minutes=max(1, settings.approval_escalation_after_minutes),
                max_levels=max(1, settings.approval_max_levels),
            )
            approval_id = approval.id
            approval_status = approval.status
        callback_registered = False
        if callback_url:
            session.add(
                CallbackHook(
                    task_id=task_id,
                    callback_url=callback_url,
                    callback_secret=callback_secret,
                    status="active",
                )
            )
            callback_registered = True

    return {
        "task_id": task_id,
        "status": "approval_pending" if approval_required else "pending",
        "idempotency_key": idempotency_key,
        "trace_id": trace_id,
        "deduplicated": False,
        "callback_registered": callback_registered,
        "approval_required": approval_required,
        "approval_id": approval_id,
        "approval_status": approval_status,
        "risk_level_final": final_risk_level,
        "risk_level_inferred": normalize_risk_level(policy_eval["inferred_risk_level"]),
        "command_template_id": template.template_id if template else None,
    }


@app.get("/api/v1/tasks/{task_id}")
def get_task(task_id: str):
    with session_scope() as session:
        task = session.get(Task, task_id)
        if not task:
            return JSONResponse(
                status_code=404,
                content={
                    "code": "NOT_FOUND",
                    "message": "task not found",
                    "trace_id": get_trace_id(),
                },
            )
        failure_code = infer_failure_code(task.reason)
        reason = strip_failure_prefix(task.reason) if failure_code else task.reason
        approval = get_approval_by_task_id(session, task.id)

        return {
            "task_id": task.id,
            "status": task.status,
            "failure_code": failure_code,
            "risk_level": task.risk_level,
            "source": task.source,
            "reason": reason,
            "command_template_id": task.command_template_id or None,
            "target_asset_id": task.target_asset_id,
            "run_as_system_user_id": task.run_as_system_user_id,
            "approval_required": is_approval_required(task.risk_level),
            "approval_id": approval.id if approval else None,
            "approval_status": approval.status if approval else None,
            "approval_expires_at": _format_dt(approval.expires_at) if approval else None,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "updated_at": task.updated_at.isoformat() if task.updated_at else None,
            "trace_id": task.trace_id or get_trace_id(),
        }


@app.post("/api/v1/tasks/{task_id}/cancel")
def cancel_task(task_id: str, payload: CancelTaskRequest | None = None):
    cancel_reason = (payload.reason if payload else "canceled by user").strip() or "canceled by user"
    with session_scope() as session:
        task = session.get(Task, task_id)
        if not task:
            return JSONResponse(
                status_code=404,
                content={
                    "code": "NOT_FOUND",
                    "message": "task not found",
                    "trace_id": get_trace_id(),
                },
            )

        if task.status == "canceled":
            return {
                "task_id": task.id,
                "status": task.status,
                "already_canceled": True,
                "reason": strip_failure_prefix(task.reason),
                "trace_id": task.trace_id or get_trace_id(),
            }

        if task.status not in ("pending", "planning", "approval_pending"):
            return JSONResponse(
                status_code=409,
                content={
                    "code": "TASK_NOT_CANCELABLE",
                    "message": f"task status={task.status} cannot be canceled",
                    "task_id": task.id,
                    "status": task.status,
                    "trace_id": task.trace_id or get_trace_id(),
                },
            )

        task.status = "canceled"
        task.reason = format_failure_reason("CANCELED", cancel_reason)[:1024]
        approval = get_approval_by_task_id(session, task.id)
        if approval and approval.status == APPROVAL_STATUS_PENDING:
            approval.status = APPROVAL_STATUS_EXPIRED
            approval.decided_by = "system"
            approval.decision_reason = "task canceled"
            approval.decided_at = datetime.now(timezone.utc)
            session.add(
                ApprovalActionAudit(
                    approval_id=approval.id,
                    task_id=task.id,
                    action="canceled",
                    operator_id="system",
                    source_ip="127.0.0.1",
                    reason="task canceled",
                )
            )
        session.flush()

        return {
            "task_id": task.id,
            "status": task.status,
            "already_canceled": False,
            "reason": cancel_reason,
            "trace_id": task.trace_id or get_trace_id(),
        }


@app.get("/api/v1/tasks/{task_id}/approval")
def get_task_approval(task_id: str):
    with session_scope() as session:
        task = session.get(Task, task_id)
        if not task:
            return JSONResponse(
                status_code=404,
                content={"code": "NOT_FOUND", "message": "task not found", "trace_id": get_trace_id()},
            )
        approval = get_approval_by_task_id(session, task_id)
        if not approval:
            return JSONResponse(
                status_code=404,
                content={"code": "NOT_FOUND", "message": "approval not found", "trace_id": get_trace_id()},
            )
        actions = list(
            session.scalars(
                select(ApprovalActionAudit)
                .where(ApprovalActionAudit.approval_id == approval.id)
                .order_by(ApprovalActionAudit.created_at.asc())
            )
        )
        return {
            "approval": _build_approval_response(approval, task=task),
            "actions": [_build_approval_action_response(item) for item in actions],
            "trace_id": task.trace_id or get_trace_id(),
        }


@app.get("/api/v1/approvals")
def list_approvals(
    status: str | None = Query(default=None, min_length=1, max_length=16),
    source: str | None = Query(default=None, min_length=1, max_length=32),
    risk_level: str | None = Query(default=None, min_length=1, max_length=32),
    current_level: int | None = Query(default=None, ge=1, le=10),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    with session_scope() as session:
        stmt = select(ApprovalRequest).join(Task, Task.id == ApprovalRequest.task_id)
        count_stmt = select(func.count()).select_from(ApprovalRequest).join(Task, Task.id == ApprovalRequest.task_id)
        if status:
            stmt = stmt.where(ApprovalRequest.status == status)
            count_stmt = count_stmt.where(ApprovalRequest.status == status)
        if source:
            stmt = stmt.where(Task.source == source)
            count_stmt = count_stmt.where(Task.source == source)
        if risk_level:
            stmt = stmt.where(Task.risk_level == risk_level)
            count_stmt = count_stmt.where(Task.risk_level == risk_level)
        if current_level is not None:
            stmt = stmt.where(ApprovalRequest.current_level == current_level)
            count_stmt = count_stmt.where(ApprovalRequest.current_level == current_level)

        approvals = list(
            session.scalars(
                stmt.order_by(ApprovalRequest.created_at.desc(), ApprovalRequest.id.desc())
                .offset(offset)
                .limit(limit)
            )
        )
        total = int(session.scalar(count_stmt) or 0)
        task_map: dict[str, Task] = {}
        if approvals:
            task_ids = [item.task_id for item in approvals]
            task_map = {item.id: item for item in session.scalars(select(Task).where(Task.id.in_(task_ids)))}

        return {
            "items": [_build_approval_response(item, task=task_map.get(item.task_id)) for item in approvals],
            "total": total,
            "limit": limit,
            "offset": offset,
            "status_filter": status,
            "source_filter": source,
            "risk_level_filter": risk_level,
            "current_level_filter": current_level,
            "trace_id": get_trace_id(),
        }


@app.get("/api/v1/approvals/pending")
def list_pending_approvals(
    current_level: int | None = Query(default=None, ge=1, le=10),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    return list_approvals(
        status=APPROVAL_STATUS_PENDING,
        source=None,
        risk_level=None,
        current_level=current_level,
        limit=limit,
        offset=offset,
    )


@app.get("/api/v1/approvals/{approval_id}")
def get_approval(
    approval_id: str,
    action_limit: int = Query(default=200, ge=1, le=1000),
    action_offset: int = Query(default=0, ge=0),
):
    with session_scope() as session:
        approval = session.get(ApprovalRequest, approval_id)
        if not approval:
            return JSONResponse(
                status_code=404,
                content={"code": "NOT_FOUND", "message": "approval not found", "trace_id": get_trace_id()},
            )
        task = session.get(Task, approval.task_id)
        actions = list(
            session.scalars(
                select(ApprovalActionAudit)
                .where(ApprovalActionAudit.approval_id == approval_id)
                .order_by(ApprovalActionAudit.created_at.asc(), ApprovalActionAudit.id.asc())
                .offset(action_offset)
                .limit(action_limit)
            )
        )
        total_actions = int(
            session.scalar(
                select(func.count())
                .select_from(ApprovalActionAudit)
                .where(ApprovalActionAudit.approval_id == approval_id)
            )
            or 0
        )
        return {
            "approval": _build_approval_response(approval, task=task),
            "actions": [_build_approval_action_response(item) for item in actions],
            "total_actions": total_actions,
            "action_limit": action_limit,
            "action_offset": action_offset,
            "trace_id": get_trace_id(),
        }


@app.post("/api/v1/approvals/{approval_id}/approve")
def approve_approval(approval_id: str, request: Request, payload: ApprovalDecisionRequest | None = None):
    operator_id = _extract_operator_id(request)
    source_ip = _extract_source_ip(request)
    reason = (payload.reason if payload else "approved").strip() or "approved"
    with session_scope() as session:
        approval = session.get(ApprovalRequest, approval_id)
        if not approval:
            return JSONResponse(
                status_code=404,
                content={"code": "NOT_FOUND", "message": "approval not found", "trace_id": get_trace_id()},
            )
        ok, message = approve_task_approval(
            session=session,
            approval=approval,
            operator_id=operator_id,
            source_ip=source_ip,
            reason=reason,
        )
        if not ok:
            return JSONResponse(
                status_code=409,
                content={"code": "APPROVAL_STATE_CONFLICT", "message": message, "trace_id": get_trace_id()},
            )
        task = session.get(Task, approval.task_id)
        return {
            "status": "ok",
            "approval": _build_approval_response(approval, task=task),
            "trace_id": get_trace_id(),
        }


@app.post("/api/v1/approvals/{approval_id}/reject")
def reject_approval(approval_id: str, request: Request, payload: ApprovalDecisionRequest | None = None):
    operator_id = _extract_operator_id(request)
    source_ip = _extract_source_ip(request)
    reason = (payload.reason if payload else "approval rejected").strip() or "approval rejected"
    with session_scope() as session:
        approval = session.get(ApprovalRequest, approval_id)
        if not approval:
            return JSONResponse(
                status_code=404,
                content={"code": "NOT_FOUND", "message": "approval not found", "trace_id": get_trace_id()},
            )
        ok, message = reject_task_approval(
            session=session,
            approval=approval,
            operator_id=operator_id,
            source_ip=source_ip,
            reason=reason,
        )
        if not ok:
            return JSONResponse(
                status_code=409,
                content={"code": "APPROVAL_STATE_CONFLICT", "message": message, "trace_id": get_trace_id()},
            )
        task = session.get(Task, approval.task_id)
        return {
            "status": "ok",
            "approval": _build_approval_response(approval, task=task),
            "trace_id": get_trace_id(),
        }


@app.post("/api/v1/approvals/{approval_id}/escalate")
def escalate_approval(approval_id: str, request: Request, payload: ApprovalDecisionRequest | None = None):
    operator_id = _extract_operator_id(request)
    source_ip = _extract_source_ip(request)
    reason = (payload.reason if payload else "").strip() or "manual escalation"
    with session_scope() as session:
        approval = session.get(ApprovalRequest, approval_id)
        if not approval:
            return JSONResponse(
                status_code=404,
                content={"code": "NOT_FOUND", "message": "approval not found", "trace_id": get_trace_id()},
            )
        ok, message = escalate_task_approval(
            session=session,
            approval=approval,
            operator_id=operator_id,
            source_ip=source_ip,
            reason=reason,
            escalation_after_minutes=max(1, settings.approval_escalation_after_minutes),
        )
        if not ok:
            return JSONResponse(
                status_code=409,
                content={"code": "APPROVAL_STATE_CONFLICT", "message": message, "trace_id": get_trace_id()},
            )
        task = session.get(Task, approval.task_id)
        return {
            "status": "ok",
            "approval": _build_approval_response(approval, task=task),
            "trace_id": get_trace_id(),
        }


@app.get("/api/v1/templates/commands")
def list_command_templates(
    enabled: bool | None = Query(default=None),
    risk_level: str | None = Query(default=None, min_length=1, max_length=32),
    search: str | None = Query(default=None, min_length=1, max_length=64),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    with session_scope() as session:
        stmt = select(CommandTemplate)
        count_stmt = select(func.count()).select_from(CommandTemplate)
        if enabled is not None:
            stmt = stmt.where(CommandTemplate.enabled.is_(enabled))
            count_stmt = count_stmt.where(CommandTemplate.enabled.is_(enabled))
        if risk_level:
            normalized_risk = normalize_risk_level(risk_level)
            stmt = stmt.where(CommandTemplate.risk_level == normalized_risk)
            count_stmt = count_stmt.where(CommandTemplate.risk_level == normalized_risk)
        if search:
            pattern = f"%{search.strip()}%"
            stmt = stmt.where(or_(CommandTemplate.template_id.like(pattern), CommandTemplate.name.like(pattern)))
            count_stmt = count_stmt.where(or_(CommandTemplate.template_id.like(pattern), CommandTemplate.name.like(pattern)))
        items = list(
            session.scalars(
                stmt.order_by(CommandTemplate.created_at.desc(), CommandTemplate.id.desc()).offset(offset).limit(limit)
            )
        )
        total = int(session.scalar(count_stmt) or 0)
        return {
            "items": [_build_command_template_response(item) for item in items],
            "total": total,
            "limit": limit,
            "offset": offset,
            "trace_id": get_trace_id(),
        }


@app.post("/api/v1/templates/commands")
def create_template(payload: CreateCommandTemplateRequest, request: Request):
    operator_id = _extract_operator_id(request)
    source_ip = _extract_source_ip(request)
    with session_scope() as session:
        existing = get_template_by_template_id(session, payload.template_id)
        if existing:
            return JSONResponse(
                status_code=409,
                content={
                    "code": "TEMPLATE_ALREADY_EXISTS",
                    "message": f"template exists: {payload.template_id}",
                    "trace_id": get_trace_id(),
                },
            )
        item = create_command_template(
            session=session,
            template_id=payload.template_id,
            name=payload.name,
            description=payload.description,
            command=payload.command,
            risk_level=payload.risk_level,
            enabled=payload.enabled,
            operator_id=operator_id,
        )
        record_governance_audit(
            session=session,
            entity_type="template",
            entity_id=item.template_id,
            action="create",
            operator_id=operator_id,
            source_ip=source_ip,
            detail={
                "name": item.name,
                "risk_level": item.risk_level,
                "enabled": item.enabled,
            },
        )
        return {
            "status": "ok",
            "item": _build_command_template_response(item),
            "trace_id": get_trace_id(),
        }


@app.patch("/api/v1/templates/commands/{template_id}")
def update_template(template_id: str, payload: UpdateCommandTemplateRequest, request: Request):
    operator_id = _extract_operator_id(request)
    source_ip = _extract_source_ip(request)
    with session_scope() as session:
        item = get_template_by_template_id(session, template_id)
        if not item:
            return JSONResponse(
                status_code=404,
                content={
                    "code": "NOT_FOUND",
                    "message": f"template not found: {template_id}",
                    "trace_id": get_trace_id(),
                },
            )
        update_command_template(
            template=item,
            name=payload.name,
            description=payload.description,
            command=payload.command,
            risk_level=payload.risk_level,
            enabled=payload.enabled,
            operator_id=operator_id,
        )
        session.flush()
        record_governance_audit(
            session=session,
            entity_type="template",
            entity_id=item.template_id,
            action="update",
            operator_id=operator_id,
            source_ip=source_ip,
            detail={
                "name": item.name,
                "risk_level": item.risk_level,
                "enabled": item.enabled,
            },
        )
        return {
            "status": "ok",
            "item": _build_command_template_response(item),
            "trace_id": get_trace_id(),
        }


@app.get("/api/v1/policies/command-blacklist")
def list_command_blacklist_rules(
    enabled: bool | None = Query(default=None),
    hard_block: bool | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    with session_scope() as session:
        stmt = select(CommandBlacklistRule)
        count_stmt = select(func.count()).select_from(CommandBlacklistRule)
        if enabled is not None:
            stmt = stmt.where(CommandBlacklistRule.enabled.is_(enabled))
            count_stmt = count_stmt.where(CommandBlacklistRule.enabled.is_(enabled))
        if hard_block is not None:
            stmt = stmt.where(CommandBlacklistRule.hard_block.is_(hard_block))
            count_stmt = count_stmt.where(CommandBlacklistRule.hard_block.is_(hard_block))
        items = list(
            session.scalars(
                stmt.order_by(CommandBlacklistRule.created_at.desc(), CommandBlacklistRule.id.desc())
                .offset(offset)
                .limit(limit)
            )
        )
        total = int(session.scalar(count_stmt) or 0)
        return {
            "builtin_patterns": [p for p in (settings.policy_builtin_blacklist or "").split(",") if p.strip()],
            "items": [_build_blacklist_rule_response(item) for item in items],
            "total": total,
            "limit": limit,
            "offset": offset,
            "trace_id": get_trace_id(),
        }


@app.post("/api/v1/policies/command-blacklist")
def create_command_blacklist(payload: CreateBlacklistRuleRequest, request: Request):
    operator_id = _extract_operator_id(request)
    source_ip = _extract_source_ip(request)
    with session_scope() as session:
        item = create_blacklist_rule(
            session=session,
            pattern=payload.pattern,
            description=payload.description,
            hard_block=payload.hard_block,
            enabled=payload.enabled,
            operator_id=operator_id,
        )
        record_governance_audit(
            session=session,
            entity_type="blacklist_rule",
            entity_id=item.id,
            action="create",
            operator_id=operator_id,
            source_ip=source_ip,
            detail={
                "pattern": item.pattern,
                "hard_block": item.hard_block,
                "enabled": item.enabled,
            },
        )
        return {
            "status": "ok",
            "item": _build_blacklist_rule_response(item),
            "trace_id": get_trace_id(),
        }


@app.patch("/api/v1/policies/command-blacklist/{rule_id}")
def update_command_blacklist(rule_id: str, payload: UpdateBlacklistRuleRequest, request: Request):
    operator_id = _extract_operator_id(request)
    source_ip = _extract_source_ip(request)
    with session_scope() as session:
        item = session.get(CommandBlacklistRule, rule_id)
        if not item:
            return JSONResponse(
                status_code=404,
                content={"code": "NOT_FOUND", "message": "rule not found", "trace_id": get_trace_id()},
            )
        update_blacklist_rule(
            rule=item,
            pattern=payload.pattern,
            description=payload.description,
            hard_block=payload.hard_block,
            enabled=payload.enabled,
            operator_id=operator_id,
        )
        session.flush()
        record_governance_audit(
            session=session,
            entity_type="blacklist_rule",
            entity_id=item.id,
            action="update",
            operator_id=operator_id,
            source_ip=source_ip,
            detail={
                "pattern": item.pattern,
                "hard_block": item.hard_block,
                "enabled": item.enabled,
            },
        )
        return {
            "status": "ok",
            "item": _build_blacklist_rule_response(item),
            "trace_id": get_trace_id(),
        }


@app.post("/api/v1/policies/evaluate")
def evaluate_governance_policy(payload: GovernancePolicyEvaluateRequest):
    template_id = (payload.command_template_id or "").strip()
    inline_command = (payload.command or "").strip()
    with session_scope() as session:
        template: CommandTemplate | None = None
        effective_command = inline_command
        if template_id:
            template = get_template_by_template_id(session, template_id)
            if not template:
                return JSONResponse(
                    status_code=404,
                    content={
                        "code": "TEMPLATE_NOT_FOUND",
                        "message": f"command template not found: {template_id}",
                        "trace_id": get_trace_id(),
                    },
                )
            effective_command = template.command
        if not effective_command:
            return JSONResponse(
                status_code=400,
                content={
                    "code": "INVALID_ARGUMENT",
                    "message": "either command or command_template_id is required",
                    "trace_id": get_trace_id(),
                },
            )
        result = evaluate_command_policy(
            session=session,
            command=effective_command,
            builtin_blacklist_raw=settings.policy_builtin_blacklist,
            requested_risk_level=payload.requested_risk_level,
            template_risk_level=template.risk_level if template else None,
        )
        return {
            "allowed": result["allowed"],
            "block_reason": result["block_reason"] or None,
            "matched_rules": result["matched"],
            "requested_risk_level": normalize_risk_level(payload.requested_risk_level),
            "template_risk_level": template.risk_level if template else None,
            "inferred_risk_level": result["inferred_risk_level"],
            "final_risk_level": result["final_risk_level"],
            "approval_required": result["approval_required"],
            "trace_id": get_trace_id(),
        }


@app.get("/api/v1/governance/audits")
def list_governance_audits(
    entity_type: str | None = Query(default=None, min_length=1, max_length=32),
    entity_id: str | None = Query(default=None, min_length=1, max_length=64),
    action: str | None = Query(default=None, min_length=1, max_length=32),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    with session_scope() as session:
        stmt = select(GovernanceAudit)
        count_stmt = select(func.count()).select_from(GovernanceAudit)
        if entity_type:
            stmt = stmt.where(GovernanceAudit.entity_type == entity_type)
            count_stmt = count_stmt.where(GovernanceAudit.entity_type == entity_type)
        if entity_id:
            stmt = stmt.where(GovernanceAudit.entity_id == entity_id)
            count_stmt = count_stmt.where(GovernanceAudit.entity_id == entity_id)
        if action:
            stmt = stmt.where(GovernanceAudit.action == action)
            count_stmt = count_stmt.where(GovernanceAudit.action == action)
        items = list(
            session.scalars(
                stmt.order_by(GovernanceAudit.created_at.desc(), GovernanceAudit.id.desc()).offset(offset).limit(limit)
            )
        )
        total = int(session.scalar(count_stmt) or 0)
        return {
            "items": [_build_governance_audit_response(item) for item in items],
            "total": total,
            "limit": limit,
            "offset": offset,
            "trace_id": get_trace_id(),
        }


@app.get("/api/v1/tasks/{task_id}/executions")
def list_task_executions(task_id: str, limit: int = Query(default=20, ge=1, le=200)):
    with session_scope() as session:
        task = session.get(Task, task_id)
        if not task:
            return JSONResponse(
                status_code=404,
                content={
                    "code": "NOT_FOUND",
                    "message": "task not found",
                    "trace_id": get_trace_id(),
                },
            )

        stmt = (
            select(Execution)
            .where(Execution.task_id == task_id)
            .order_by(Execution.created_at.desc())
            .limit(limit)
        )
        executions = list(session.scalars(stmt))
        execution_ids = [item.id for item in executions]

        audit_map: dict[str, list[str]] = {}
        if execution_ids:
            audit_stmt = select(AuditLink).where(AuditLink.execution_id.in_(execution_ids))
            for item in session.scalars(audit_stmt):
                audit_map.setdefault(item.execution_id, []).append(item.jms_audit_relation_id)

        return {
            "task_id": task_id,
            "items": [
                _build_execution_response(
                    execution=item,
                    task=task,
                    audit_relation_ids=audit_map.get(item.id, []),
                )
                for item in executions
            ],
            "trace_id": task.trace_id or get_trace_id(),
        }


@app.get("/api/v1/tasks/{task_id}/callbacks")
def list_task_callbacks(task_id: str, limit: int = Query(default=20, ge=1, le=200)):
    with session_scope() as session:
        task = session.get(Task, task_id)
        if not task:
            return JSONResponse(
                status_code=404,
                content={
                    "code": "NOT_FOUND",
                    "message": "task not found",
                    "trace_id": get_trace_id(),
                },
            )

        hook = session.scalar(select(CallbackHook).where(CallbackHook.task_id == task_id))
        deliveries = list(
            session.scalars(
                select(CallbackDelivery)
                .where(CallbackDelivery.task_id == task_id)
                .order_by(CallbackDelivery.created_at.desc())
                .limit(limit)
            )
        )
        return {
            "task_id": task_id,
            "hook": _build_callback_hook_response(hook) if hook else None,
            "deliveries": [_build_callback_delivery_response(item) for item in deliveries],
            "trace_id": task.trace_id or get_trace_id(),
        }


@app.get("/api/v1/executions/{execution_id}")
def get_execution(execution_id: str):
    with session_scope() as session:
        execution = session.get(Execution, execution_id)
        if not execution:
            execution = session.scalar(
                select(Execution).where(Execution.jms_execution_id == execution_id)
            )
        if not execution:
            return JSONResponse(
                status_code=404,
                content={
                    "code": "NOT_FOUND",
                    "message": "execution not found",
                    "trace_id": get_trace_id(),
                },
            )

        task = session.get(Task, execution.task_id)
        audit_stmt = select(AuditLink).where(AuditLink.execution_id == execution.id)
        audit_relation_ids = [item.jms_audit_relation_id for item in session.scalars(audit_stmt)]
        return _build_execution_response(
            execution=execution,
            task=task,
            audit_relation_ids=audit_relation_ids,
        )


@app.get("/api/v1/executions")
def list_executions(
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    status: str | None = Query(default=None, min_length=1, max_length=32),
    source: str | None = Query(default=None, min_length=1, max_length=32),
    risk_level: str | None = Query(default=None, min_length=1, max_length=32),
    task_id: str | None = Query(default=None, min_length=1, max_length=64),
    hours: int | None = Query(default=None, ge=1, le=24 * 30),
):
    since = None
    if hours is not None:
        since = datetime.now(timezone.utc) - timedelta(hours=hours)

    with session_scope() as session:
        stmt = select(Execution).join(Task, Task.id == Execution.task_id)
        count_stmt = select(func.count()).select_from(Execution).join(Task, Task.id == Execution.task_id)

        if status:
            stmt = stmt.where(Execution.status == status)
            count_stmt = count_stmt.where(Execution.status == status)
        if source:
            stmt = stmt.where(Task.source == source)
            count_stmt = count_stmt.where(Task.source == source)
        if risk_level:
            stmt = stmt.where(Task.risk_level == risk_level)
            count_stmt = count_stmt.where(Task.risk_level == risk_level)
        if task_id:
            stmt = stmt.where(Execution.task_id == task_id)
            count_stmt = count_stmt.where(Execution.task_id == task_id)
        if since is not None:
            stmt = stmt.where(Execution.updated_at >= since)
            count_stmt = count_stmt.where(Execution.updated_at >= since)

        stmt = stmt.order_by(Execution.created_at.desc()).offset(offset).limit(limit)
        executions = list(session.scalars(stmt))
        total = int(session.scalar(count_stmt) or 0)

        execution_ids = [item.id for item in executions]
        task_ids = [item.task_id for item in executions]

        audit_map: dict[str, list[str]] = {}
        if execution_ids:
            audit_stmt = select(AuditLink).where(AuditLink.execution_id.in_(execution_ids))
            for item in session.scalars(audit_stmt):
                audit_map.setdefault(item.execution_id, []).append(item.jms_audit_relation_id)

        task_map: dict[str, Task] = {}
        if task_ids:
            task_stmt = select(Task).where(Task.id.in_(task_ids))
            task_map = {item.id: item for item in session.scalars(task_stmt)}

        return {
            "items": [
                _build_execution_response(
                    execution=item,
                    task=task_map.get(item.task_id),
                    audit_relation_ids=audit_map.get(item.id, []),
                )
                for item in executions
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
            "status_filter": status,
            "source_filter": source,
            "risk_level_filter": risk_level,
            "task_id_filter": task_id,
            "hours_filter": hours,
            "trace_id": get_trace_id(),
        }


@app.get("/api/v1/metrics/failures/summary")
def failure_summary(
    hours: int = Query(default=24, ge=1, le=24 * 30),
    source: str | None = Query(default=None, min_length=1, max_length=32),
    prefer_preaggregated: bool = Query(default=True),
):
    now_utc = datetime.now(timezone.utc)
    since = now_utc - timedelta(hours=hours)
    if prefer_preaggregated:
        granularity = "hour"
        bucket_since = since
        if hours > max(1, settings.metrics_preaggregation_hourly_lookback_hours):
            granularity = "day"
            bucket_since = now_utc - timedelta(days=max(1, (hours + 23) // 24))

        with session_scope() as session:
            stmt = select(FailureSummaryBucket).where(
                FailureSummaryBucket.granularity == granularity,
                FailureSummaryBucket.bucket_start >= bucket_since,
            )
            if source:
                stmt = stmt.where(FailureSummaryBucket.source == source)
            preagg_rows = list(session.scalars(stmt))

        if preagg_rows:
            by_code: dict[str, int] = {}
            by_source: dict[str, int] = {}
            by_risk_level: dict[str, int] = {}
            unknown_reasons: dict[str, int] = {}
            total_failed = 0
            for row in preagg_rows:
                count = int(row.count or 0)
                total_failed += count
                by_code[row.failure_code] = by_code.get(row.failure_code, 0) + count
                by_source[row.source] = by_source.get(row.source, 0) + count
                by_risk_level[row.risk_level] = by_risk_level.get(row.risk_level, 0) + count
                if row.failure_code == "UNKNOWN" and row.unknown_reason:
                    unknown_reasons[row.unknown_reason] = unknown_reasons.get(row.unknown_reason, 0) + count

            return {
                "window_hours": hours,
                "to": now_utc.isoformat(),
                "since": since.isoformat(),
                "source_filter": source,
                "total_failed": total_failed,
                "by_failure_code": _to_buckets(by_code, "failure_code"),
                "by_source": _to_buckets(by_source, "source"),
                "by_risk_level": _to_buckets(by_risk_level, "risk_level"),
                "unknown_reason_samples": _to_buckets(unknown_reasons, "reason")[:5],
                "data_mode": f"preaggregated_{granularity}",
                "trace_id": get_trace_id(),
            }

    with session_scope() as session:
        stmt = select(Task).where(Task.status == "failed", Task.updated_at >= since)
        if source:
            stmt = stmt.where(Task.source == source)
        failed_tasks = list(session.scalars(stmt))

    by_code: dict[str, int] = {}
    by_source: dict[str, int] = {}
    by_risk_level: dict[str, int] = {}
    unknown_reasons: dict[str, int] = {}
    for task in failed_tasks:
        code, message = _normalize_failed_reason(task.reason)
        normalized_code = code or "UNKNOWN"
        by_code[normalized_code] = by_code.get(normalized_code, 0) + 1
        by_source[task.source] = by_source.get(task.source, 0) + 1
        by_risk_level[task.risk_level] = by_risk_level.get(task.risk_level, 0) + 1
        if normalized_code == "UNKNOWN":
            unknown_key = message or "unknown failure"
            unknown_reasons[unknown_key] = unknown_reasons.get(unknown_key, 0) + 1

    return {
        "window_hours": hours,
        "to": now_utc.isoformat(),
        "since": since.isoformat(),
        "source_filter": source,
        "total_failed": len(failed_tasks),
        "by_failure_code": _to_buckets(by_code, "failure_code"),
        "by_source": _to_buckets(by_source, "source"),
        "by_risk_level": _to_buckets(by_risk_level, "risk_level"),
        "unknown_reason_samples": _to_buckets(unknown_reasons, "reason")[:5],
        "data_mode": "raw",
        "trace_id": get_trace_id(),
    }


@app.get("/api/v1/metrics/task-retry/summary")
def task_retry_summary(
    hours: int = Query(default=24, ge=1, le=24 * 30),
    source: str | None = Query(default=None, min_length=1, max_length=32),
    operator_id: str | None = Query(default=None, min_length=1, max_length=64),
    include_dry_run: bool = Query(default=True),
    prefer_preaggregated: bool = Query(default=True),
):
    now_utc = datetime.now(timezone.utc)
    since = now_utc - timedelta(hours=hours)
    if prefer_preaggregated:
        granularity = "hour"
        bucket_since = since
        if hours > max(1, settings.metrics_preaggregation_hourly_lookback_hours):
            granularity = "day"
            bucket_since = now_utc - timedelta(days=max(1, (hours + 23) // 24))

        with session_scope() as session:
            item_stmt = select(TaskRetrySummaryBucket).where(
                TaskRetrySummaryBucket.granularity == granularity,
                TaskRetrySummaryBucket.bucket_start >= bucket_since,
            )
            if source:
                item_stmt = item_stmt.where(TaskRetrySummaryBucket.source == source)
            if operator_id:
                item_stmt = item_stmt.where(TaskRetrySummaryBucket.operator_id == operator_id)
            if not include_dry_run:
                item_stmt = item_stmt.where(TaskRetrySummaryBucket.dry_run == False)  # noqa: E712
            preagg_items = list(session.scalars(item_stmt))

            selector = source if source else "*"
            audit_stmt = select(TaskRetryAuditCountBucket).where(
                TaskRetryAuditCountBucket.granularity == granularity,
                TaskRetryAuditCountBucket.bucket_start >= bucket_since,
                TaskRetryAuditCountBucket.source_selector == selector,
            )
            if operator_id:
                audit_stmt = audit_stmt.where(TaskRetryAuditCountBucket.operator_id == operator_id)
            if not include_dry_run:
                audit_stmt = audit_stmt.where(TaskRetryAuditCountBucket.dry_run == False)  # noqa: E712
            preagg_audits = list(session.scalars(audit_stmt))

        if preagg_items:
            by_action: dict[str, int] = {}
            by_failure_code: dict[str, int] = {}
            by_source: dict[str, int] = {}
            hour_item_totals: dict[str, int] = {}
            hour_action_counts: dict[str, dict[str, int]] = {}

            for item in preagg_items:
                count = int(item.count or 0)
                by_action[item.action] = by_action.get(item.action, 0) + count
                by_failure_code[item.failure_code] = by_failure_code.get(item.failure_code, 0) + count
                by_source[item.source] = by_source.get(item.source, 0) + count
                hour_key = _to_bucket_utc(item.bucket_start, granularity)
                hour_item_totals[hour_key] = hour_item_totals.get(hour_key, 0) + count
                action_bucket = hour_action_counts.setdefault(hour_key, {})
                action_bucket[item.action] = action_bucket.get(item.action, 0) + count

            audit_by_hour: dict[str, int] = {}
            audit_total = 0
            for item in preagg_audits:
                count = int(item.count or 0)
                audit_total += count
                hour_key = _to_bucket_utc(item.bucket_start, granularity)
                audit_by_hour[hour_key] = audit_by_hour.get(hour_key, 0) + count

            by_hour = []
            for hour_key in sorted(hour_item_totals.keys()):
                action_rows = _to_buckets(hour_action_counts.get(hour_key, {}), "action")
                by_hour.append({"hour": hour_key, "total": hour_item_totals[hour_key], "by_action": action_rows})

            return {
                "window_hours": hours,
                "to": now_utc.isoformat(),
                "since": since.isoformat(),
                "source_filter": source,
                "operator_id_filter": operator_id,
                "include_dry_run": include_dry_run,
                "audit_total": audit_total,
                "item_total": sum(int(item.count or 0) for item in preagg_items),
                "audit_by_hour": [
                    {"hour": key, "count": audit_by_hour[key]} for key in sorted(audit_by_hour.keys())
                ],
                "by_hour": by_hour,
                "by_action": _to_buckets(by_action, "action"),
                "by_failure_code": _to_buckets(by_failure_code, "failure_code"),
                "by_source": _to_buckets(by_source, "source"),
                "data_mode": f"preaggregated_{granularity}",
                "trace_id": get_trace_id(),
            }

    with session_scope() as session:
        audits_stmt = select(TaskRetryAudit).where(TaskRetryAudit.created_at >= since)
        if operator_id:
            audits_stmt = audits_stmt.where(TaskRetryAudit.operator_id == operator_id)
        if not include_dry_run:
            audits_stmt = audits_stmt.where(TaskRetryAudit.dry_run == False)  # noqa: E712
        audits = list(session.scalars(audits_stmt.order_by(TaskRetryAudit.created_at.desc())))

        audit_ids = [audit.id for audit in audits]
        items: list[TaskRetryAuditItem] = []
        if audit_ids:
            items_stmt = select(TaskRetryAuditItem).where(TaskRetryAuditItem.audit_id.in_(audit_ids))
            if source:
                items_stmt = items_stmt.where(TaskRetryAuditItem.source == source)
            items = list(session.scalars(items_stmt))

    selected_audit_ids = {item.audit_id for item in items} if source else set(audit_ids)
    selected_audits = [audit for audit in audits if audit.id in selected_audit_ids]

    by_action: dict[str, int] = {}
    by_failure_code: dict[str, int] = {}
    by_source: dict[str, int] = {}
    hour_item_totals: dict[str, int] = {}
    hour_action_counts: dict[str, dict[str, int]] = {}
    for item in items:
        action_key = item.action or "unknown"
        by_action[action_key] = by_action.get(action_key, 0) + 1

        failure_key = item.failure_code or "UNKNOWN"
        by_failure_code[failure_key] = by_failure_code.get(failure_key, 0) + 1

        source_key = item.source or "unknown"
        by_source[source_key] = by_source.get(source_key, 0) + 1

        hour_key = _to_utc_hour_bucket(item.created_at)
        hour_item_totals[hour_key] = hour_item_totals.get(hour_key, 0) + 1
        action_bucket = hour_action_counts.setdefault(hour_key, {})
        action_bucket[action_key] = action_bucket.get(action_key, 0) + 1

    audit_by_hour: dict[str, int] = {}
    for audit in selected_audits:
        hour_key = _to_utc_hour_bucket(audit.created_at)
        audit_by_hour[hour_key] = audit_by_hour.get(hour_key, 0) + 1

    by_hour = []
    for hour_key in sorted(hour_item_totals.keys()):
        action_rows = _to_buckets(hour_action_counts.get(hour_key, {}), "action")
        by_hour.append({"hour": hour_key, "total": hour_item_totals[hour_key], "by_action": action_rows})

    return {
        "window_hours": hours,
        "to": now_utc.isoformat(),
        "since": since.isoformat(),
        "source_filter": source,
        "operator_id_filter": operator_id,
        "include_dry_run": include_dry_run,
        "audit_total": len(selected_audits),
        "item_total": len(items),
        "audit_by_hour": [
            {"hour": key, "count": audit_by_hour[key]} for key in sorted(audit_by_hour.keys())
        ],
        "by_hour": by_hour,
        "by_action": _to_buckets(by_action, "action"),
        "by_failure_code": _to_buckets(by_failure_code, "failure_code"),
        "by_source": _to_buckets(by_source, "source"),
        "data_mode": "raw",
        "trace_id": get_trace_id(),
    }


@app.get("/api/v1/metrics/failures/remediation-template")
def failure_remediation_template(
    failure_code: str | None = Query(default=None, min_length=1, max_length=64),
    source: str | None = Query(default=None, min_length=1, max_length=32),
    risk_level: str | None = Query(default=None, min_length=1, max_length=32),
):
    requested_code, matched, template = get_contextual_remediation_template(
        failure_code=failure_code,
        source=source,
        risk_level=risk_level,
        resolved_from="failure_code",
    )
    return {
        "requested_failure_code": requested_code,
        "matched": matched,
        "source_filter": source,
        "risk_level_filter": risk_level,
        "template": template,
        "trace_id": get_trace_id(),
    }


@app.get("/api/v1/metrics/failures/remediation")
def failure_remediation(
    task_id: str | None = Query(default=None, min_length=1, max_length=64),
    execution_id: str | None = Query(default=None, min_length=1, max_length=64),
    failure_code: str | None = Query(default=None, min_length=1, max_length=64),
):
    if not task_id and not execution_id and not failure_code:
        return JSONResponse(
            status_code=400,
            content={
                "code": "INVALID_ARGUMENT",
                "message": "one of task_id/execution_id/failure_code is required",
                "trace_id": get_trace_id(),
            },
        )

    resolved_from = "failure_code"
    task: Task | None = None
    execution: Execution | None = None
    raw_reason = ""

    with session_scope() as session:
        if execution_id:
            execution = session.get(Execution, execution_id)
            if not execution:
                execution = session.scalar(select(Execution).where(Execution.jms_execution_id == execution_id))
            if not execution:
                return JSONResponse(
                    status_code=404,
                    content={
                        "code": "NOT_FOUND",
                        "message": "execution not found",
                        "trace_id": get_trace_id(),
                    },
                )
            task = session.get(Task, execution.task_id)
            raw_reason = execution.result_summary or (task.reason if task else "")
            resolved_from = "execution"
        elif task_id:
            task = session.get(Task, task_id)
            if not task:
                return JSONResponse(
                    status_code=404,
                    content={
                        "code": "NOT_FOUND",
                        "message": "task not found",
                        "trace_id": get_trace_id(),
                    },
                )
            raw_reason = task.reason
            resolved_from = "task"
        else:
            raw_reason = failure_code or ""

    inferred = infer_failure_code(raw_reason)
    code_input = failure_code or inferred
    requested_code, matched, template = get_contextual_remediation_template(
        failure_code=code_input,
        source=task.source if task else None,
        risk_level=task.risk_level if task else None,
        resolved_from=resolved_from,
    )

    return {
        "resolved_from": resolved_from,
        "requested_failure_code": requested_code,
        "inferred_failure_code": inferred,
        "matched": matched,
        "failure_code_override": bool(failure_code and resolved_from in {"task", "execution"}),
        "context": {
            "task_id": task.id if task else None,
            "execution_id": execution.id if execution else None,
            "jms_execution_id": execution.jms_execution_id if execution else None,
            "task_status": task.status if task else None,
            "execution_status": execution.status if execution else None,
            "source": task.source if task else None,
            "risk_level": task.risk_level if task else None,
            "error_message": strip_failure_prefix(raw_reason) if raw_reason else None,
        },
        "template": template,
        "trace_id": get_trace_id(),
    }


@app.get("/api/v1/metrics/failures/remediation-templates")
def failure_remediation_templates():
    items = list_remediation_templates()
    return {
        "items": items,
        "total": len(items),
        "trace_id": get_trace_id(),
    }


@app.get("/api/v1/metrics/preaggregation/status")
def metrics_preaggregation_status(
    granularity: str = Query(default="hour", pattern="^(hour|day)$"),
):
    return _build_preaggregation_status(granularity=granularity)


def _build_preaggregation_status(*, granularity: str) -> dict:
    now_utc = datetime.now(timezone.utc)
    with session_scope() as session:
        latest_run = session.scalar(
            select(MetricsPreaggregationRun).order_by(MetricsPreaggregationRun.run_at.desc()).limit(1)
        )
        failure_latest = session.scalar(
            select(FailureSummaryBucket.bucket_start)
            .where(FailureSummaryBucket.granularity == granularity)
            .order_by(FailureSummaryBucket.bucket_start.desc())
            .limit(1)
        )
        retry_item_latest = session.scalar(
            select(TaskRetrySummaryBucket.bucket_start)
            .where(TaskRetrySummaryBucket.granularity == granularity)
            .order_by(TaskRetrySummaryBucket.bucket_start.desc())
            .limit(1)
        )
        retry_audit_latest = session.scalar(
            select(TaskRetryAuditCountBucket.bucket_start)
            .where(TaskRetryAuditCountBucket.granularity == granularity)
            .order_by(TaskRetryAuditCountBucket.bucket_start.desc())
            .limit(1)
        )

    max_lag_minutes = max(1, settings.metrics_preaggregation_max_lag_minutes)
    if granularity == "day":
        max_lag_minutes = 24 * 60 + max_lag_minutes

    run_lag_minutes = None
    if latest_run and latest_run.run_at:
        run_ts = latest_run.run_at if latest_run.run_at.tzinfo else latest_run.run_at.replace(tzinfo=timezone.utc)
        run_lag_minutes = max(0.0, (now_utc - run_ts.astimezone(timezone.utc)).total_seconds() / 60.0)

    bucket_lag_minutes = None
    latest_items = [item for item in [failure_latest, retry_item_latest, retry_audit_latest] if item is not None]
    if latest_items:
        lags = []
        for item in latest_items:
            normalized = item if item.tzinfo else item.replace(tzinfo=timezone.utc)
            lags.append(max(0.0, (now_utc - normalized.astimezone(timezone.utc)).total_seconds() / 60.0))
        if lags:
            bucket_lag_minutes = max(lags)

    healthy = bool(run_lag_minutes is not None and run_lag_minutes <= max_lag_minutes)
    if run_lag_minutes is None:
        healthy = bool(
            failure_latest is not None
            and retry_item_latest is not None
            and retry_audit_latest is not None
            and bucket_lag_minutes is not None
            and bucket_lag_minutes <= max_lag_minutes
        )

    return {
        "granularity": granularity,
        "healthy": healthy,
        "max_allowed_lag_minutes": max_lag_minutes,
        "run_lag_minutes": run_lag_minutes,
        "bucket_lag_minutes": bucket_lag_minutes,
        "latest": {
            "run_at": _format_dt(latest_run.run_at if latest_run else None),
            "failure_summary_bucket": _format_dt(failure_latest),
            "task_retry_item_bucket": _format_dt(retry_item_latest),
            "task_retry_audit_bucket": _format_dt(retry_audit_latest),
        },
        "trace_id": get_trace_id(),
    }


@app.get("/api/v1/metrics/preaggregation/alerts")
def metrics_preaggregation_alerts(
    granularity: str = Query(default="hour", pattern="^(hour|day)$"),
):
    status_payload = _build_preaggregation_status(granularity=granularity)
    run_lag_minutes = status_payload.get("run_lag_minutes")
    max_allowed = float(status_payload.get("max_allowed_lag_minutes") or 0.0)

    if not status_payload.get("healthy", False):
        level = "critical"
        summary = "预聚合作业已超出可接受延迟，建议立即检查 scheduler 运行与日志。"
        actions = [
            "检查 opspaw-scheduler.service 是否 active。",
            "查看 scheduler 日志中 preaggregation 执行记录与异常堆栈。",
            "必要时临时开启 debug 手工触发 /admin/metrics/preaggregation/run。",
        ]
    else:
        warn_threshold = max_allowed * 0.8 if max_allowed > 0 else 0
        if run_lag_minutes is not None and run_lag_minutes >= warn_threshold:
            level = "warn"
            summary = "预聚合作业接近延迟阈值，建议关注调度负载与任务执行耗时。"
            actions = [
                "观察下一轮 preaggregation run_lag 是否继续上升。",
                "评估是否需调大调度间隔或缩短 lookback 窗口。",
            ]
        else:
            level = "ok"
            summary = "预聚合作业运行正常。"
            actions = [
                "保持现有调度参数，持续监控 run_lag 变化。",
            ]

    return {
        "granularity": granularity,
        "level": level,
        "summary": summary,
        "suggested_actions": actions,
        "status": status_payload,
        "trace_id": get_trace_id(),
    }


@app.get("/api/v1/dashboard/overview")
def dashboard_overview(
    hours: int = Query(default=24, ge=1, le=24 * 30),
    source: str | None = Query(default=None, min_length=1, max_length=32),
    top_n: int = Query(default=5, ge=1, le=20),
):
    summary_payload = failure_summary(
        hours=hours,
        source=source,
        prefer_preaggregated=True,
    )
    if isinstance(summary_payload, JSONResponse):
        return summary_payload

    alerts_payload = metrics_preaggregation_alerts(granularity="hour")
    if isinstance(alerts_payload, JSONResponse):
        return alerts_payload

    top_failures = list(summary_payload.get("by_failure_code", []))[:top_n]
    remediation_cards: list[dict] = []
    for item in top_failures:
        failure_code = str(item.get("failure_code") or "").strip().upper()
        requested_code, matched, template = get_contextual_remediation_template(
            failure_code=failure_code,
            source=source,
            risk_level=None,
            resolved_from="dashboard",
        )
        remediation_cards.append(
            {
                "failure_code": requested_code,
                "count": int(item.get("count") or 0),
                "matched": matched,
                "title": template.get("title"),
                "severity": template.get("severity"),
                "summary": template.get("summary"),
                "recommended_actions": template.get("recommended_actions", []),
            }
        )

    return {
        "window_hours": hours,
        "source_filter": source,
        "data_mode": summary_payload.get("data_mode"),
        "alerts": alerts_payload,
        "failure_summary": {
            "total_failed": summary_payload.get("total_failed", 0),
            "by_failure_code": summary_payload.get("by_failure_code", []),
            "by_source": summary_payload.get("by_source", []),
            "by_risk_level": summary_payload.get("by_risk_level", []),
            "unknown_reason_samples": summary_payload.get("unknown_reason_samples", []),
        },
        "remediation_cards": remediation_cards,
        "trace_id": get_trace_id(),
    }


@app.get("/api/v1/dashboard/failures/{failure_code}/detail")
def dashboard_failure_detail(
    failure_code: str,
    hours: int = Query(default=24, ge=1, le=24 * 30),
    source: str | None = Query(default=None, min_length=1, max_length=32),
    limit: int = Query(default=20, ge=1, le=100),
):
    now_utc = datetime.now(timezone.utc)
    since = now_utc - timedelta(hours=hours)
    normalized = (failure_code or "").strip().upper()
    requested_code, matched, template = get_contextual_remediation_template(
        failure_code=normalized,
        source=source,
        risk_level=None,
        resolved_from="dashboard",
    )
    with session_scope() as session:
        stmt = select(Task).where(Task.status == "failed", Task.updated_at >= since)
        if source:
            stmt = stmt.where(Task.source == source)
        candidates = list(
            session.scalars(stmt.order_by(Task.updated_at.desc(), Task.id.desc()).limit(max(limit * 5, 100)))
        )
        items: list[dict] = []
        for task in candidates:
            task_failure = infer_failure_code(task.reason)
            if task_failure != requested_code:
                continue
            items.append(
                {
                    "task_id": task.id,
                    "source": task.source,
                    "risk_level": task.risk_level,
                    "target_asset_id": task.target_asset_id,
                    "error_message": strip_failure_prefix(task.reason),
                    "updated_at": _format_dt(task.updated_at),
                }
            )
            if len(items) >= limit:
                break

    return {
        "failure_code": requested_code,
        "matched": matched,
        "window_hours": hours,
        "source_filter": source,
        "template": template,
        "recent_failed_tasks": items,
        "trace_id": get_trace_id(),
    }


@app.get("/api/v1/audits/summary")
def audits_summary(
    hours: int = Query(default=24, ge=1, le=24 * 30),
    source: str | None = Query(default=None, min_length=1, max_length=32),
    asset_id: str | None = Query(default=None, min_length=1, max_length=64),
    top_assets: int = Query(default=10, ge=1, le=100),
):
    now_utc = datetime.now(timezone.utc)
    since = now_utc - timedelta(hours=hours)

    with session_scope() as session:
        task_stmt = select(Task).where(Task.created_at >= since)
        if source:
            task_stmt = task_stmt.where(Task.source == source)
        if asset_id:
            task_stmt = task_stmt.where(Task.target_asset_id == asset_id)
        tasks = list(session.scalars(task_stmt))

        task_ids = [task.id for task in tasks]

        executions: list[Execution] = []
        audit_links: list[AuditLink] = []
        if task_ids:
            executions = list(
                session.scalars(
                    select(Execution).where(
                        Execution.created_at >= since,
                        Execution.task_id.in_(task_ids),
                    )
                )
            )
            execution_ids = [item.id for item in executions]
            if execution_ids:
                audit_links = list(
                    session.scalars(
                        select(AuditLink).where(
                            AuditLink.created_at >= since,
                            AuditLink.execution_id.in_(execution_ids),
                        )
                    )
                )

    by_source: dict[str, int] = {}
    by_asset: dict[str, int] = {}
    by_task_status: dict[str, int] = {}
    by_execution_status: dict[str, int] = {}
    by_failure_code: dict[str, int] = {}
    task_hourly: dict[str, int] = {}
    execution_hourly: dict[str, int] = {}
    audit_hourly: dict[str, int] = {}

    for task in tasks:
        source_key = task.source or "unknown"
        asset_key = task.target_asset_id or "unknown"
        status_key = task.status or "unknown"
        by_source[source_key] = by_source.get(source_key, 0) + 1
        by_asset[asset_key] = by_asset.get(asset_key, 0) + 1
        by_task_status[status_key] = by_task_status.get(status_key, 0) + 1
        if task.status == "failed":
            code = infer_failure_code(task.reason) or "UNKNOWN"
            by_failure_code[code] = by_failure_code.get(code, 0) + 1
        task_hour = _to_utc_hour_bucket(task.created_at)
        task_hourly[task_hour] = task_hourly.get(task_hour, 0) + 1

    for execution in executions:
        status_key = execution.status or "unknown"
        by_execution_status[status_key] = by_execution_status.get(status_key, 0) + 1
        exec_hour = _to_utc_hour_bucket(execution.created_at)
        execution_hourly[exec_hour] = execution_hourly.get(exec_hour, 0) + 1

    for item in audit_links:
        audit_hour = _to_utc_hour_bucket(item.created_at)
        audit_hourly[audit_hour] = audit_hourly.get(audit_hour, 0) + 1

    hourly_keys = sorted(set(task_hourly.keys()) | set(execution_hourly.keys()) | set(audit_hourly.keys()))
    by_hour = []
    for key in hourly_keys:
        by_hour.append(
            {
                "hour": key,
                "task_count": task_hourly.get(key, 0),
                "execution_count": execution_hourly.get(key, 0),
                "audit_link_count": audit_hourly.get(key, 0),
            }
        )

    return {
        "window_hours": hours,
        "to": now_utc.isoformat(),
        "since": since.isoformat(),
        "source_filter": source,
        "asset_id_filter": asset_id,
        "task_total": len(tasks),
        "execution_total": len(executions),
        "audit_link_total": len(audit_links),
        "failed_task_total": int(by_task_status.get("failed", 0)),
        "by_source": _to_buckets(by_source, "source"),
        "by_asset": _to_buckets(by_asset, "asset_id")[:top_assets],
        "by_task_status": _to_buckets(by_task_status, "status"),
        "by_execution_status": _to_buckets(by_execution_status, "status"),
        "by_failure_code": _to_buckets(by_failure_code, "failure_code"),
        "by_hour": by_hour,
        "trace_id": get_trace_id(),
    }


@app.get("/api/v1/integrations/jumpserver/check")
def jumpserver_check():
    client = JumpServerClient()
    try:
        api_mode = client.get_api_mode()
        assets = client.list_assets(limit=1, offset=0)
        return {
            "status": "ok",
            "reachable": True,
            "api_mode": api_mode,
            "sample_asset_count": len(assets),
            "base_url": settings.jumpserver_base_url,
            "trace_id": get_trace_id(),
        }
    except JumpServerClientError as exc:
        return JSONResponse(
            status_code=502,
            content={
                "status": "error",
                "reachable": False,
                "base_url": settings.jumpserver_base_url,
                "message": str(exc),
                "trace_id": get_trace_id(),
            },
        )


@app.get("/api/v1/integrations/jumpserver/capabilities")
def jumpserver_capabilities():
    client = JumpServerClient()
    try:
        api_mode = client.get_api_mode()
        health = client.get_health()
        public_settings = client.get_public_settings()
        command_execution_enabled = bool(public_settings.get("SECURITY_COMMAND_EXECUTION", False))

        raw_blacklist = public_settings.get("SECURITY_COMMAND_BLACKLIST")
        command_blacklist = raw_blacklist if isinstance(raw_blacklist, list) else []

        execution_query_accessible = True
        execution_query_error = None
        try:
            client.list_command_executions(limit=1, offset=0)
        except JumpServerClientError as exc:
            execution_query_accessible = False
            execution_query_error = str(exc)

        return {
            "status": "ok",
            "reachable": True,
            "api_mode": api_mode,
            "base_url": settings.jumpserver_base_url,
            "health": health,
            "command_execution_enabled": command_execution_enabled,
            "command_blacklist_count": len(command_blacklist),
            "command_blacklist_preview": command_blacklist[:10],
            "execution_query_accessible": execution_query_accessible,
            "execution_query_error": execution_query_error,
            "trace_id": get_trace_id(),
        }
    except JumpServerClientError as exc:
        return JSONResponse(
            status_code=502,
            content={
                "status": "error",
                "reachable": False,
                "base_url": settings.jumpserver_base_url,
                "message": str(exc),
                "trace_id": get_trace_id(),
            },
        )


@app.get("/api/v1/integrations/jumpserver/permission-check")
def jumpserver_permission_check():
    client = JumpServerClient()

    try:
        api_mode = client.get_api_mode()
    except JumpServerClientError as exc:
        return JSONResponse(
            status_code=502,
            content={
                "status": "error",
                "reachable": False,
                "base_url": settings.jumpserver_base_url,
                "message": str(exc),
                "trace_id": get_trace_id(),
            },
        )

    checks: list[dict] = []
    sample_asset_id: str | None = None

    def _append_check(
        *,
        name: str,
        required: bool,
        ok: bool,
        detail: str | None = None,
        error: str | None = None,
        skipped: bool = False,
    ) -> None:
        checks.append(
            {
                "name": name,
                "required": required,
                "ok": ok,
                "skipped": skipped,
                "detail": detail,
                "error": error,
            }
        )

    try:
        assets = client.list_assets(limit=1, offset=0)
        if assets:
            sample_asset_id = assets[0].id
        _append_check(
            name="list_assets",
            required=True,
            ok=True,
            detail=f"assets_visible={len(assets)}",
        )
    except JumpServerClientError as exc:
        _append_check(
            name="list_assets",
            required=True,
            ok=False,
            error=str(exc),
        )

    if sample_asset_id:
        try:
            users = client.list_asset_system_users(sample_asset_id)
            _append_check(
                name="list_asset_system_users",
                required=True,
                ok=True,
                detail=f"sample_asset_id={sample_asset_id}, users={len(users)}",
            )
        except JumpServerClientError as exc:
            _append_check(
                name="list_asset_system_users",
                required=True,
                ok=False,
                error=str(exc),
            )
    else:
        _append_check(
            name="list_asset_system_users",
            required=True,
            ok=False,
            skipped=True,
            detail="no visible assets from list_assets",
        )

    try:
        execution_payload = client.list_command_executions(limit=1, offset=0)
        total = execution_payload.get("count") if isinstance(execution_payload, dict) else None
        _append_check(
            name="list_command_executions",
            required=True,
            ok=True,
            detail=f"count={total}",
        )
    except JumpServerClientError as exc:
        _append_check(
            name="list_command_executions",
            required=True,
            ok=False,
            error=str(exc),
        )

    try:
        public_settings = client.get_public_settings()
        command_execution_enabled = bool(public_settings.get("SECURITY_COMMAND_EXECUTION", False))
        _append_check(
            name="read_public_settings",
            required=False,
            ok=True,
            detail=f"SECURITY_COMMAND_EXECUTION={command_execution_enabled}",
        )
    except JumpServerClientError as exc:
        _append_check(
            name="read_public_settings",
            required=False,
            ok=False,
            error=str(exc),
        )

    required_checks = [item for item in checks if item["required"]]
    overall_required_ok = all(item["ok"] and not item["skipped"] for item in required_checks)

    recommendation = "permission set is ready for OpsPaw sync and execution"
    if not overall_required_ok:
        recommendation = (
            "grant missing JumpServer API permissions for list_assets, "
            "asset system user mapping, and execution listing"
        )

    return {
        "status": "ok" if overall_required_ok else "degraded",
        "reachable": True,
        "api_mode": api_mode,
        "base_url": settings.jumpserver_base_url,
        "overall_required_ok": overall_required_ok,
        "required_checks": len(required_checks),
        "required_checks_ok": len([item for item in required_checks if item["ok"] and not item["skipped"]]),
        "checks": checks,
        "recommendation": recommendation,
        "trace_id": get_trace_id(),
    }


@app.get("/api/v1/sync/snapshots/latest")
def get_latest_sync_snapshot(source: str = Query(default="jumpserver", min_length=1, max_length=64)):
    with session_scope() as session:
        snapshot = session.scalar(
            select(SyncSnapshot)
            .where(SyncSnapshot.source == source)
            .order_by(SyncSnapshot.created_at.desc(), SyncSnapshot.id.desc())
            .limit(1)
        )
        if not snapshot:
            return JSONResponse(
                status_code=404,
                content={
                    "code": "NOT_FOUND",
                    "message": "sync snapshot not found",
                    "trace_id": get_trace_id(),
                },
            )

        return {
            "item": _build_sync_snapshot_response(snapshot),
            "trace_id": get_trace_id(),
        }


@app.get("/api/v1/sync/snapshots")
def list_sync_snapshots(
    source: str = Query(default="jumpserver", min_length=1, max_length=64),
    limit: int = Query(default=20, ge=1, le=200),
):
    with session_scope() as session:
        stmt = (
            select(SyncSnapshot)
            .where(SyncSnapshot.source == source)
            .order_by(SyncSnapshot.created_at.desc(), SyncSnapshot.id.desc())
            .limit(limit)
        )
        items = list(session.scalars(stmt))
        return {
            "source": source,
            "items": [_build_sync_snapshot_response(item) for item in items],
            "trace_id": get_trace_id(),
        }


@app.post("/api/v1/admin/sync/once")
def admin_sync_once():
    if not settings.app_allow_admin_debug_endpoints:
        return JSONResponse(
            status_code=403,
            content={"code": "FORBIDDEN", "message": "admin debug endpoints are disabled", "trace_id": get_trace_id()},
        )

    client = JumpServerClient()
    try:
        with session_scope() as session:
            result = run_sync_once(
                session=session,
                client=client,
                page_size=settings.jumpserver_sync_page_size,
            )
        return {
            "status": "ok",
            "result": result,
            "trace_id": get_trace_id(),
        }
    except JumpServerClientError as exc:
        return JSONResponse(
            status_code=502,
            content={
                "status": "error",
                "message": str(exc),
                "trace_id": get_trace_id(),
            },
        )


@app.post("/api/v1/admin/metrics/preaggregation/run")
def admin_run_metrics_preaggregation():
    if not settings.app_allow_admin_debug_endpoints:
        return JSONResponse(
            status_code=403,
            content={"code": "FORBIDDEN", "message": "admin debug endpoints are disabled", "trace_id": get_trace_id()},
        )

    with session_scope() as session:
        result = run_metrics_preaggregation(
            session=session,
            hourly_lookback_hours=max(1, settings.metrics_preaggregation_hourly_lookback_hours),
            daily_lookback_days=max(1, settings.metrics_preaggregation_daily_lookback_days),
        )
    return {
        "status": "ok",
        "result": result,
        "trace_id": get_trace_id(),
    }


@app.post("/api/v1/admin/sync/assets/{jms_asset_id}/refresh")
def admin_refresh_single_asset(jms_asset_id: str):
    if not settings.app_allow_admin_debug_endpoints:
        return JSONResponse(
            status_code=403,
            content={"code": "FORBIDDEN", "message": "admin debug endpoints are disabled", "trace_id": get_trace_id()},
        )

    client = JumpServerClient()
    try:
        with session_scope() as session:
            result = refresh_asset_once(
                session=session,
                client=client,
                jms_asset_id=jms_asset_id,
            )
        if not result.get("found"):
            return JSONResponse(
                status_code=404,
                content={
                    "code": "ASSET_NOT_FOUND",
                    "message": f"asset not found on jumpserver: {jms_asset_id}",
                    "trace_id": get_trace_id(),
                },
            )
        return {
            "status": "ok",
            "result": result,
            "trace_id": get_trace_id(),
        }
    except ValueError as exc:
        return JSONResponse(
            status_code=400,
            content={
                "code": "INVALID_ARGUMENT",
                "message": str(exc),
                "trace_id": get_trace_id(),
            },
        )
    except JumpServerClientError as exc:
        return JSONResponse(
            status_code=502,
            content={
                "status": "error",
                "message": str(exc),
                "trace_id": get_trace_id(),
            },
        )


@app.post("/api/v1/admin/tasks/{task_id}/refresh-retry")
def admin_refresh_and_retry_task(task_id: str):
    if not settings.app_allow_admin_debug_endpoints:
        return JSONResponse(
            status_code=403,
            content={"code": "FORBIDDEN", "message": "admin debug endpoints are disabled", "trace_id": get_trace_id()},
        )

    client = JumpServerClient()
    try:
        with session_scope() as session:
            task = session.get(Task, task_id)
            if not task:
                return JSONResponse(
                    status_code=404,
                    content={
                        "code": "NOT_FOUND",
                        "message": "task not found",
                        "trace_id": get_trace_id(),
                    },
                )

            if task.status in ("pending", "planning", "executing"):
                return JSONResponse(
                    status_code=409,
                    content={
                        "code": "TASK_IN_PROGRESS",
                        "message": f"task status={task.status} is still in progress",
                        "task_id": task.id,
                        "trace_id": task.trace_id or get_trace_id(),
                    },
                )

            if task.status != "failed":
                return JSONResponse(
                    status_code=409,
                    content={
                        "code": "TASK_NOT_RETRYABLE",
                        "message": f"task status={task.status} does not support refresh-retry",
                        "task_id": task.id,
                        "trace_id": task.trace_id or get_trace_id(),
                    },
                )

            previous_failure_code = infer_failure_code(task.reason) or "UNKNOWN"
            retryable_codes = set(TASK_REFRESH_RETRYABLE_CODES)
            if previous_failure_code not in retryable_codes:
                return JSONResponse(
                    status_code=409,
                    content={
                        "code": "TASK_NOT_RETRYABLE",
                        "message": (
                            f"task failure_code={previous_failure_code} is not eligible for refresh-retry; "
                            f"allowed={sorted(retryable_codes)}"
                        ),
                        "task_id": task.id,
                        "failure_code": previous_failure_code,
                        "trace_id": task.trace_id or get_trace_id(),
                    },
                )

            running = session.scalar(
                select(Execution).where(Execution.task_id == task.id, Execution.status == "running").limit(1)
            )
            if running:
                return JSONResponse(
                    status_code=409,
                    content={
                        "code": "TASK_IN_PROGRESS",
                        "message": "task has running execution",
                        "task_id": task.id,
                        "execution_id": running.id,
                        "trace_id": task.trace_id or get_trace_id(),
                    },
                )

            refresh_result = refresh_asset_once(
                session=session,
                client=client,
                jms_asset_id=task.target_asset_id,
                search_limit=max(1, settings.execution_gate_refresh_search_limit),
            )
            if not refresh_result.get("found"):
                return JSONResponse(
                    status_code=404,
                    content={
                        "code": "ASSET_NOT_FOUND",
                        "message": f"asset not found on jumpserver: {task.target_asset_id}",
                        "task_id": task.id,
                        "trace_id": task.trace_id or get_trace_id(),
                    },
                )

            task.status = "pending"
            task.reason = (
                f"retry requested after asset refresh; previous_failure_code={previous_failure_code}"
            )[:1024]
            session.flush()

            tick_result = run_orchestrator_tick(session=session, client=client)
            session.flush()

            final_task = session.get(Task, task.id)
            failure_code = infer_failure_code(final_task.reason) if final_task else None
            reason = strip_failure_prefix(final_task.reason) if (final_task and failure_code) else (final_task.reason if final_task else "")

            return {
                "status": "ok",
                "task_id": task.id,
                "previous_failure_code": previous_failure_code,
                "refresh_result": refresh_result,
                "orchestrator_result": tick_result,
                "task": {
                    "task_id": final_task.id if final_task else task.id,
                    "status": final_task.status if final_task else "unknown",
                    "failure_code": failure_code,
                    "reason": reason,
                    "target_asset_id": final_task.target_asset_id if final_task else task.target_asset_id,
                    "run_as_system_user_id": (
                        final_task.run_as_system_user_id if final_task else task.run_as_system_user_id
                    ),
                    "trace_id": final_task.trace_id if final_task else task.trace_id,
                },
                "trace_id": task.trace_id or get_trace_id(),
            }
    except ValueError as exc:
        return JSONResponse(
            status_code=400,
            content={
                "code": "INVALID_ARGUMENT",
                "message": str(exc),
                "trace_id": get_trace_id(),
            },
        )
    except JumpServerClientError as exc:
        return JSONResponse(
            status_code=502,
            content={
                "status": "error",
                "message": str(exc),
                "trace_id": get_trace_id(),
            },
        )


@app.post("/api/v1/admin/tasks/refresh-retry/batch")
def admin_refresh_and_retry_tasks_batch(payload: BatchRefreshRetryTasksRequest, request: Request):
    if not settings.app_allow_admin_debug_endpoints:
        return JSONResponse(
            status_code=403,
            content={"code": "FORBIDDEN", "message": "admin debug endpoints are disabled", "trace_id": get_trace_id()},
        )

    operator_id = _extract_operator_id(request)
    source_ip = _extract_source_ip(request)
    client = JumpServerClient()
    trace_id = get_trace_id() or ""

    try:
        with session_scope() as session:
            result = run_task_refresh_retry_batch(
                session=session,
                client=client,
                endpoint="/api/v1/admin/tasks/refresh-retry/batch",
                operator_id=operator_id,
                source_ip=source_ip,
                task_ids=payload.task_ids,
                hours=payload.hours,
                source=payload.source,
                failure_codes=payload.failure_codes,
                limit=payload.limit,
                window_size=payload.window_size,
                max_windows=payload.max_windows,
                same_asset_max_retries=payload.same_asset_max_retries,
                task_cooldown_minutes=payload.task_cooldown_minutes,
                dry_run=payload.dry_run,
                trace_id=trace_id,
            )
        result["trace_id"] = trace_id or get_trace_id()
        return result
    except JumpServerClientError as exc:
        return JSONResponse(
            status_code=502,
            content={
                "status": "error",
                "message": str(exc),
                "trace_id": get_trace_id(),
            },
        )


@app.get("/api/v1/admin/tasks/refresh-retry/audits")
def list_task_refresh_retry_audits(
    operator_id: str | None = Query(default=None, min_length=1, max_length=64),
    task_id: str | None = Query(default=None, min_length=1, max_length=64),
    action: str | None = Query(default=None, min_length=1, max_length=48),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    if not settings.app_allow_admin_debug_endpoints:
        return JSONResponse(
            status_code=403,
            content={"code": "FORBIDDEN", "message": "admin debug endpoints are disabled", "trace_id": get_trace_id()},
        )

    with session_scope() as session:
        stmt = select(TaskRetryAudit)
        count_stmt = select(func.count()).select_from(TaskRetryAudit)
        if operator_id:
            stmt = stmt.where(TaskRetryAudit.operator_id == operator_id)
            count_stmt = count_stmt.where(TaskRetryAudit.operator_id == operator_id)

        if task_id or action:
            audit_id_subquery = select(TaskRetryAuditItem.audit_id).distinct()
            if task_id:
                audit_id_subquery = audit_id_subquery.where(TaskRetryAuditItem.task_id == task_id)
            if action:
                audit_id_subquery = audit_id_subquery.where(TaskRetryAuditItem.action == action)
            stmt = stmt.where(TaskRetryAudit.id.in_(audit_id_subquery))
            count_stmt = count_stmt.where(TaskRetryAudit.id.in_(audit_id_subquery))

        total = int(session.scalar(count_stmt) or 0)
        audits = list(
            session.scalars(
                stmt.order_by(TaskRetryAudit.created_at.desc(), TaskRetryAudit.id.desc())
                .offset(offset)
                .limit(limit)
            )
        )
        return {
            "items": [_build_task_retry_audit_response(item) for item in audits],
            "total": total,
            "limit": limit,
            "offset": offset,
            "operator_id_filter": operator_id,
            "task_id_filter": task_id,
            "action_filter": action,
            "trace_id": get_trace_id(),
        }


@app.get("/api/v1/admin/tasks/refresh-retry/audits/{audit_id}")
def get_task_refresh_retry_audit(
    audit_id: str,
    item_limit: int = Query(default=200, ge=1, le=1000),
    item_offset: int = Query(default=0, ge=0),
):
    if not settings.app_allow_admin_debug_endpoints:
        return JSONResponse(
            status_code=403,
            content={"code": "FORBIDDEN", "message": "admin debug endpoints are disabled", "trace_id": get_trace_id()},
        )

    with session_scope() as session:
        audit = session.get(TaskRetryAudit, audit_id)
        if not audit:
            return JSONResponse(
                status_code=404,
                content={"code": "NOT_FOUND", "message": "task refresh retry audit not found", "trace_id": get_trace_id()},
            )
        count_stmt = (
            select(func.count())
            .select_from(TaskRetryAuditItem)
            .where(TaskRetryAuditItem.audit_id == audit_id)
        )
        total_items = int(session.scalar(count_stmt) or 0)
        items = list(
            session.scalars(
                select(TaskRetryAuditItem)
                .where(TaskRetryAuditItem.audit_id == audit_id)
                .order_by(TaskRetryAuditItem.created_at.asc(), TaskRetryAuditItem.id.asc())
                .offset(item_offset)
                .limit(item_limit)
            )
        )
        return {
            "audit": _build_task_retry_audit_response(audit),
            "items": [_build_task_retry_audit_item_response(item) for item in items],
            "total_items": total_items,
            "item_limit": item_limit,
            "item_offset": item_offset,
            "trace_id": get_trace_id(),
        }


@app.get("/api/v1/admin/tasks/refresh-retry/audits/{audit_id}/export")
def export_task_refresh_retry_audit(
    audit_id: str,
    format: str = Query(default="csv", pattern="^(csv|json)$"),
):
    if not settings.app_allow_admin_debug_endpoints:
        return JSONResponse(
            status_code=403,
            content={"code": "FORBIDDEN", "message": "admin debug endpoints are disabled", "trace_id": get_trace_id()},
        )

    with session_scope() as session:
        audit = session.get(TaskRetryAudit, audit_id)
        if not audit:
            return JSONResponse(
                status_code=404,
                content={"code": "NOT_FOUND", "message": "task refresh retry audit not found", "trace_id": get_trace_id()},
            )
        items = list(
            session.scalars(
                select(TaskRetryAuditItem)
                .where(TaskRetryAuditItem.audit_id == audit_id)
                .order_by(TaskRetryAuditItem.created_at.asc(), TaskRetryAuditItem.id.asc())
            )
        )
        audit_payload = _build_task_retry_audit_response(audit)
        item_payloads = [_build_task_retry_audit_item_response(item) for item in items]

        if format == "json":
            return {
                "audit": audit_payload,
                "items": item_payloads,
                "total_items": len(item_payloads),
                "trace_id": get_trace_id(),
            }

        csv_text = _render_task_retry_audit_csv(audit=audit_payload, items=item_payloads)
        headers = {"Content-Disposition": f'attachment; filename="task-refresh-retry-{audit_id}.csv"'}
        return PlainTextResponse(content=csv_text, media_type="text/csv; charset=utf-8", headers=headers)


@app.post("/api/v1/admin/orchestrator/tick")
def admin_orchestrator_tick():
    if not settings.app_allow_admin_debug_endpoints:
        return JSONResponse(
            status_code=403,
            content={"code": "FORBIDDEN", "message": "admin debug endpoints are disabled", "trace_id": get_trace_id()},
        )

    client = JumpServerClient()
    try:
        with session_scope() as session:
            result = run_orchestrator_tick(session=session, client=client)
        return {
            "status": "ok",
            "result": result,
            "trace_id": get_trace_id(),
        }
    except JumpServerClientError as exc:
        return JSONResponse(
            status_code=502,
            content={
                "status": "error",
                "message": str(exc),
                "trace_id": get_trace_id(),
            },
        )


@app.post("/api/v1/admin/callback/tick")
def admin_callback_tick():
    if not settings.app_allow_admin_debug_endpoints:
        return JSONResponse(
            status_code=403,
            content={"code": "FORBIDDEN", "message": "admin debug endpoints are disabled", "trace_id": get_trace_id()},
        )

    try:
        with session_scope() as session:
            result = run_callback_tick(session=session)
        return {
            "status": "ok",
            "result": result,
            "trace_id": get_trace_id(),
        }
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": str(exc),
                "trace_id": get_trace_id(),
            },
        )


@app.post("/api/v1/admin/callback/deliveries/{delivery_id}/replay")
def admin_replay_callback_delivery(
    delivery_id: str,
    request: Request,
    payload: ReplayCallbackDeliveryRequest | None = None,
):
    if not settings.app_allow_admin_debug_endpoints:
        return JSONResponse(
            status_code=403,
            content={"code": "FORBIDDEN", "message": "admin debug endpoints are disabled", "trace_id": get_trace_id()},
        )

    with session_scope() as session:
        operator_id = _extract_operator_id(request)
        source_ip = _extract_source_ip(request)
        delivery = session.get(CallbackDelivery, delivery_id)
        if not delivery:
            return JSONResponse(
                status_code=404,
                content={
                    "code": "NOT_FOUND",
                    "message": "callback delivery not found",
                    "trace_id": get_trace_id(),
                },
            )

        if delivery.status == "success":
            _insert_callback_replay_audit(
                session=session,
                endpoint="/api/v1/admin/callback/deliveries/{delivery_id}/replay",
                operator_id=operator_id,
                source_ip=source_ip,
                dry_run=False,
                matched=1,
                replayed=0,
                skipped_non_replayable=1,
                blocked_by_guardrail=False,
                guardrail_reason="delivery status is success",
                filters={"delivery_id": delivery.id},
                delivery_ids=[delivery.id],
            )
            return JSONResponse(
                status_code=409,
                content={
                    "code": "DELIVERY_NOT_REPLAYABLE",
                    "message": "successful delivery cannot be replayed",
                    "delivery_id": delivery.id,
                    "status": delivery.status,
                    "trace_id": get_trace_id(),
                },
            )

        delivery.status = "pending"
        if payload and payload.reset_attempts:
            delivery.attempts = 0
        delivery.next_retry_at = datetime.now(timezone.utc)
        delivery.last_http_status = None
        delivery.last_error = ""
        audit = _insert_callback_replay_audit(
            session=session,
            endpoint="/api/v1/admin/callback/deliveries/{delivery_id}/replay",
            operator_id=operator_id,
            source_ip=source_ip,
            dry_run=False,
            matched=1,
            replayed=1,
            skipped_non_replayable=0,
            blocked_by_guardrail=False,
            guardrail_reason="",
            filters={"delivery_id": delivery.id, "reset_attempts": bool(payload and payload.reset_attempts)},
            delivery_ids=[delivery.id],
        )
        session.flush()

        return {
            "status": "ok",
            "audit_id": audit.id,
            "item": _build_callback_delivery_response(delivery),
            "trace_id": get_trace_id(),
        }


@app.get("/api/v1/admin/callback/deliveries")
def admin_list_callback_deliveries(
    status: str = Query(default="", max_length=16),
    task_id: str = Query(default="", max_length=64),
    error_contains: str = Query(default="", max_length=128),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    if not settings.app_allow_admin_debug_endpoints:
        return JSONResponse(
            status_code=403,
            content={"code": "FORBIDDEN", "message": "admin debug endpoints are disabled", "trace_id": get_trace_id()},
        )

    with session_scope() as session:
        stmt = select(CallbackDelivery)
        count_stmt = select(func.count()).select_from(CallbackDelivery)

        if status:
            stmt = stmt.where(CallbackDelivery.status == status)
            count_stmt = count_stmt.where(CallbackDelivery.status == status)
        if task_id:
            stmt = stmt.where(CallbackDelivery.task_id == task_id)
            count_stmt = count_stmt.where(CallbackDelivery.task_id == task_id)
        if error_contains:
            pattern = f"%{error_contains.lower()}%"
            stmt = stmt.where(func.lower(CallbackDelivery.last_error).like(pattern))
            count_stmt = count_stmt.where(func.lower(CallbackDelivery.last_error).like(pattern))

        total = int(session.scalar(count_stmt) or 0)
        items = list(
            session.scalars(
                stmt.order_by(CallbackDelivery.created_at.desc(), CallbackDelivery.id.desc())
                .offset(offset)
                .limit(limit)
            )
        )
        return {
            "items": [_build_callback_delivery_response(item) for item in items],
            "total": total,
            "limit": limit,
            "offset": offset,
            "status_filter": status or None,
            "task_id_filter": task_id or None,
            "error_contains_filter": error_contains or None,
            "trace_id": get_trace_id(),
        }


@app.post("/api/v1/admin/callback/deliveries/replay")
def admin_batch_replay_callback_deliveries(payload: ReplayCallbackDeliveriesRequest, request: Request):
    if not settings.app_allow_admin_debug_endpoints:
        return JSONResponse(
            status_code=403,
            content={"code": "FORBIDDEN", "message": "admin debug endpoints are disabled", "trace_id": get_trace_id()},
        )

    with session_scope() as session:
        operator_id = _extract_operator_id(request)
        source_ip = _extract_source_ip(request)
        stmt = select(CallbackDelivery)
        if payload.delivery_ids:
            stmt = stmt.where(CallbackDelivery.id.in_(payload.delivery_ids))
        elif payload.status:
            stmt = stmt.where(CallbackDelivery.status == payload.status)

        if payload.task_id:
            stmt = stmt.where(CallbackDelivery.task_id == payload.task_id)
        if payload.error_contains:
            pattern = f"%{payload.error_contains.lower()}%"
            stmt = stmt.where(func.lower(CallbackDelivery.last_error).like(pattern))

        matched = list(
            session.scalars(
                stmt.order_by(CallbackDelivery.created_at.desc(), CallbackDelivery.id.desc()).limit(payload.limit)
            )
        )
        non_replayable = [item for item in matched if item.status == "success"]
        replayable = [item for item in matched if item.status != "success"]
        filters = {
            "delivery_ids": payload.delivery_ids,
            "status": payload.status or None,
            "task_id": payload.task_id or None,
            "error_contains": payload.error_contains or None,
            "limit": payload.limit,
            "reset_attempts": payload.reset_attempts,
        }

        if not payload.dry_run and len(replayable) > max(1, settings.callback_replay_max_apply):
            audit = _insert_callback_replay_audit(
                session=session,
                endpoint="/api/v1/admin/callback/deliveries/replay",
                operator_id=operator_id,
                source_ip=source_ip,
                dry_run=False,
                matched=len(matched),
                replayed=0,
                skipped_non_replayable=len(non_replayable),
                blocked_by_guardrail=True,
                guardrail_reason=f"replayable={len(replayable)} exceeds max={settings.callback_replay_max_apply}",
                filters=filters,
                delivery_ids=[item.id for item in matched],
            )
            return JSONResponse(
                status_code=400,
                content={
                    "code": "CALLBACK_REPLAY_LIMIT_EXCEEDED",
                    "message": f"replayable deliveries exceed guardrail max={settings.callback_replay_max_apply}",
                    "matched": len(matched),
                    "replayable": len(replayable),
                    "guardrail_max_apply": settings.callback_replay_max_apply,
                    "audit_id": audit.id,
                    "trace_id": get_trace_id(),
                },
            )

        if not payload.dry_run:
            now_utc = datetime.now(timezone.utc)
            for delivery in replayable:
                delivery.status = "pending"
                if payload.reset_attempts:
                    delivery.attempts = 0
                delivery.next_retry_at = now_utc
                delivery.last_http_status = None
                delivery.last_error = ""
            if replayable:
                session.flush()

        audit = _insert_callback_replay_audit(
            session=session,
            endpoint="/api/v1/admin/callback/deliveries/replay",
            operator_id=operator_id,
            source_ip=source_ip,
            dry_run=payload.dry_run,
            matched=len(matched),
            replayed=0 if payload.dry_run else len(replayable),
            skipped_non_replayable=len(non_replayable),
            blocked_by_guardrail=False,
            guardrail_reason="",
            filters=filters,
            delivery_ids=[item.id for item in matched],
        )

        return {
            "status": "ok",
            "audit_id": audit.id,
            "dry_run": payload.dry_run,
            "matched": len(matched),
            "replayed": 0 if payload.dry_run else len(replayable),
            "skipped_non_replayable": len(non_replayable),
            "filters": filters,
            "items": [_build_callback_delivery_response(item) for item in replayable],
            "skipped_items": [_build_callback_delivery_response(item) for item in non_replayable],
            "trace_id": get_trace_id(),
        }


@app.get("/api/v1/admin/callback/replay-audits")
def admin_list_callback_replay_audits(
    operator_id: str = Query(default="", max_length=64),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    if not settings.app_allow_admin_debug_endpoints:
        return JSONResponse(
            status_code=403,
            content={"code": "FORBIDDEN", "message": "admin debug endpoints are disabled", "trace_id": get_trace_id()},
        )

    with session_scope() as session:
        stmt = select(CallbackReplayAudit)
        count_stmt = select(func.count()).select_from(CallbackReplayAudit)
        if operator_id:
            stmt = stmt.where(CallbackReplayAudit.operator_id == operator_id)
            count_stmt = count_stmt.where(CallbackReplayAudit.operator_id == operator_id)

        total = int(session.scalar(count_stmt) or 0)
        items = list(
            session.scalars(
                stmt.order_by(CallbackReplayAudit.created_at.desc(), CallbackReplayAudit.id.desc())
                .offset(offset)
                .limit(limit)
            )
        )
        return {
            "items": [_build_callback_replay_audit_response(item) for item in items],
            "total": total,
            "limit": limit,
            "offset": offset,
            "operator_id_filter": operator_id or None,
            "trace_id": get_trace_id(),
        }


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("unhandled error: %s", exc)
    return JSONResponse(
        status_code=500,
        content={
            "code": "INTERNAL_ERROR",
            "message": "unexpected server error",
            "trace_id": get_trace_id(),
        },
    )
