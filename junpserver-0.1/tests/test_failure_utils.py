from __future__ import annotations

from app.core.failure import (
    format_failure_reason,
    infer_failure_code,
    parse_failure_code,
    strip_failure_prefix,
)


def test_failure_reason_roundtrip():
    reason = format_failure_reason("execution-timeout", "jumpserver execution timeout")

    assert reason == "[EXECUTION_TIMEOUT] jumpserver execution timeout"
    assert parse_failure_code(reason) == "EXECUTION_TIMEOUT"
    assert strip_failure_prefix(reason) == "jumpserver execution timeout"


def test_failure_reason_without_prefix_returns_none_code():
    assert parse_failure_code("plain reason") is None
    assert strip_failure_prefix("plain reason") == "plain reason"


def test_infer_failure_code_for_legacy_reason_text():
    assert infer_failure_code("jumpserver execution timeout") == "EXECUTION_TIMEOUT"
    assert infer_failure_code("jumpserver POST /api/v1/ops/command-executions/ failed status=400") == "UPSTREAM_ERROR"


def test_infer_failure_code_for_permission_denied_cases():
    assert infer_failure_code("jumpserver POST /api/v1/ops/jobs/ failed status=403 body=forbidden") == "PERMISSION_DENIED"
    assert infer_failure_code("You do not have access rights") == "PERMISSION_DENIED"


def test_infer_failure_code_for_connectivity_cases():
    assert infer_failure_code("shell: Failed to connect to the host via ssh: connection timed out") == "CONNECTIVITY_ERROR"
    assert infer_failure_code("ssh: connect to host 10.10.10.10 port 22: Connection refused") == "CONNECTIVITY_ERROR"


def test_infer_failure_code_for_policy_blocked_cases():
    assert infer_failure_code("policy blocked: command matched hard blacklist pattern") == "POLICY_BLOCKED"
    assert infer_failure_code("command blacklist matched dangerous pattern") == "POLICY_BLOCKED"
