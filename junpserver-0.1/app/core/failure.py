from __future__ import annotations

import re


_FAILURE_CODE_PATTERN = re.compile(r"^\[(?P<code>[A-Z0-9_]+)\]\s*")


def format_failure_reason(code: str, message: str) -> str:
    normalized_code = (code or "UNKNOWN").strip().upper().replace("-", "_")
    normalized_message = (message or "").strip() or "unknown failure"
    return f"[{normalized_code}] {normalized_message}"


def parse_failure_code(reason: str | None) -> str | None:
    if not reason:
        return None
    match = _FAILURE_CODE_PATTERN.match(reason)
    if not match:
        return None
    return match.group("code")


def infer_failure_code(reason: str | None) -> str | None:
    explicit = parse_failure_code(reason)
    if explicit:
        return explicit
    if not reason:
        return None

    text = reason.strip().lower()
    if "failed to connect to the host via ssh" in text:
        return "CONNECTIVITY_ERROR"
    if "failed to connect to host" in text:
        return "CONNECTIVITY_ERROR"
    if "connection timed out" in text:
        return "CONNECTIVITY_ERROR"
    if "timed out" in text and "connect" in text:
        return "CONNECTIVITY_ERROR"
    if "connection refused" in text:
        return "CONNECTIVITY_ERROR"
    if "no route to host" in text:
        return "CONNECTIVITY_ERROR"
    if "network is unreachable" in text:
        return "CONNECTIVITY_ERROR"
    if "name or service not known" in text:
        return "CONNECTIVITY_ERROR"
    if "status=403" in text and "jumpserver" in text:
        return "PERMISSION_DENIED"
    if "you do not have access rights" in text:
        return "PERMISSION_DENIED"
    if "permission denied" in text:
        return "PERMISSION_DENIED"
    if "no permission" in text:
        return "PERMISSION_DENIED"
    if "forbidden" in text:
        return "PERMISSION_DENIED"
    if "没有权限" in text:
        return "PERMISSION_DENIED"
    if "无权限" in text:
        return "PERMISSION_DENIED"
    if "命令执行已禁用" in text:
        return "PERMISSION_DENIED"
    if "execution timeout" in text:
        return "EXECUTION_TIMEOUT"
    if "approval timeout" in text:
        return "APPROVAL_TIMEOUT"
    if "approval rejected" in text:
        return "APPROVAL_REJECTED"
    if "policy blocked" in text:
        return "POLICY_BLOCKED"
    if "blacklist" in text and "command" in text:
        return "POLICY_BLOCKED"
    if "missing required fields" in text:
        return "VALIDATION_ERROR"
    if "asset projection not found" in text:
        return "ASSET_NOT_FOUND"
    if "asset is inactive" in text:
        return "ASSET_INACTIVE"
    if "asset freshness expired" in text:
        return "ASSET_EXPIRED"
    if "asset freshness stale" in text:
        return "ASSET_STALE"
    if "execution id is empty" in text:
        return "UPSTREAM_BAD_RESPONSE"
    if "failed status=" in text and "jumpserver" in text:
        return "UPSTREAM_ERROR"
    if "unexpected server error" in text:
        return "INTERNAL_ERROR"
    return None


def strip_failure_prefix(reason: str | None) -> str:
    if not reason:
        return ""
    return _FAILURE_CODE_PATTERN.sub("", reason, count=1).strip()
