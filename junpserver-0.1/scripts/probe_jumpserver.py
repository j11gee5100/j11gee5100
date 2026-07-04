from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from typing import Any

# Ensure project root is importable when running as a script.
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.services.jumpserver.client import JumpServerClient, JumpServerClientError


def print_json(title: str, payload: Any) -> None:
    print(f"\n=== {title} ===")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def run_basic_probe(client: JumpServerClient) -> None:
    print(f"\nDetected API mode: {client.get_api_mode()}")

    try:
        public_settings = client.get_public_settings()
        blacklist = public_settings.get("SECURITY_COMMAND_BLACKLIST")
        blacklist_items = blacklist if isinstance(blacklist, list) else []
        print_json(
            "public_settings_probe",
            {
                "SECURITY_COMMAND_EXECUTION": bool(public_settings.get("SECURITY_COMMAND_EXECUTION", False)),
                "SECURITY_COMMAND_BLACKLIST_COUNT": len(blacklist_items),
                "SECURITY_COMMAND_BLACKLIST_PREVIEW": blacklist_items[:10],
            },
        )
    except JumpServerClientError as exc:
        print(f"\nSkip public settings probe: {exc}")

    assets = client.list_assets(limit=5, offset=0)
    print_json(
        "assets",
        [asset.model_dump() for asset in assets],
    )

    if assets:
        first_asset_id = assets[0].id
        users = client.list_asset_system_users(first_asset_id)
        print_json(
            "system_users_of_first_asset",
            [user.model_dump() for user in users],
        )
    else:
        print("\nNo assets returned. Skip system user probing.")

    try:
        audits = client.list_audit_relations(limit=5, offset=0)
        print_json("audit_relations", audits)
    except JumpServerClientError as exc:
        print(f"\nSkip audit relation probe: {exc}")


def _as_dict(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        return payload
    return {}


def _classify_failure_message(message: str) -> str:
    normalized = (message or "").lower()
    if "permission denied" in normalized or "invalid/incorrect password" in normalized:
        return "AUTH_FAILED"
    if "timed out" in normalized or "timeout" in normalized:
        return "CONNECT_TIMEOUT"
    if "connection refused" in normalized:
        return "CONNECT_REFUSED"
    if "no route to host" in normalized:
        return "ROUTE_UNREACHABLE"
    if "forbidden" in normalized or "status=403" in normalized:
        return "PERMISSION_DENIED"
    return "OTHER"


def _extract_v4_failure_messages(summary: dict[str, Any]) -> list[str]:
    messages: list[str] = []

    dark = summary.get("dark")
    if isinstance(dark, dict):
        for value in dark.values():
            if isinstance(value, str) and value.strip():
                messages.append(value.strip())

    failures = summary.get("failures")
    if isinstance(failures, dict):
        for value in failures.values():
            if isinstance(value, str) and value.strip():
                messages.append(value.strip())

    return messages


def run_pending_diagnosis(client: JumpServerClient) -> None:
    mode = client.get_api_mode()
    health = _as_dict(client.get_health())
    print_json("health", health)

    executions_payload = _as_dict(client.list_command_executions(limit=10, offset=0))
    results = executions_payload.get("results") if isinstance(executions_payload.get("results"), list) else []
    print_json(
        "command_executions_brief",
        {
            "count": executions_payload.get("count"),
            "returned": len(results),
            "unfinished": len([x for x in results if isinstance(x, dict) and not x.get("is_finished", False)]),
            "sample_ids": [x.get("id") for x in results[:5] if isinstance(x, dict)],
        },
    )

    probe_ids: list[str] = []
    for item in results[:3]:
        if isinstance(item, dict) and isinstance(item.get("id"), str):
            probe_ids.append(item["id"])
    if mode == "legacy_v3":
        probe_ids.append(str(uuid.uuid4()))

        probe_rows: list[dict[str, Any]] = []
        for task_id in probe_ids:
            result_payload = _as_dict(client.get_celery_task_result(task_id))
            log_payload = _as_dict(client.get_celery_task_log(task_id))
            log_data = log_payload.get("data")
            if isinstance(log_data, str):
                log_data = log_data[:120]

            probe_rows.append(
                {
                    "task_id": task_id,
                    "result_state": result_payload.get("state"),
                    "result_value": result_payload.get("result"),
                    "log_data": log_data,
                }
            )
        print_json("celery_probe_rows", probe_rows)

        real_rows = [row for row in probe_rows[:-1] if isinstance(row, dict)]
        random_row = probe_rows[-1] if probe_rows else {}
        all_real_pending = all(row.get("result_state") == "PENDING" for row in real_rows)
        real_log_waiting = all(row.get("log_data") == "等待任务开始" for row in real_rows)
        random_pending = random_row.get("result_state") == "PENDING"
        random_waiting = random_row.get("log_data") == "等待任务开始"

        diagnosis = {
            "all_real_pending": all_real_pending,
            "all_real_waiting": real_log_waiting,
            "random_id_pending": random_pending,
            "random_id_waiting": random_waiting,
            "likely_root_cause": (
                "upstream celery queue/worker/result backend not advancing tasks"
                if (all_real_pending and real_log_waiting and random_pending and random_waiting)
                else "inconclusive; need more upstream signals"
            ),
        }
        print_json("pending_diagnosis", diagnosis)
        return

    v4_rows: list[dict[str, Any]] = []
    for task_id in probe_ids:
        detail = client.get_command_execution(task_id)
        detail_result = _as_dict(detail.result)
        status = detail_result.get("status")
        status_value = status.get("value") if isinstance(status, dict) else status
        summary = detail_result.get("summary")
        v4_rows.append(
            {
                "task_id": task_id,
                "is_finished": detail.is_finished,
                "is_success": detail_result.get("is_success"),
                "status": status_value,
                "summary": summary if isinstance(summary, dict) else detail_result,
            }
        )
    print_json("v4_execution_probe_rows", v4_rows)
    print_json(
        "pending_diagnosis",
        {
            "mode": "v4",
            "note": "v4 uses job-execution status instead of celery task-result probing",
            "running_items": len([row for row in v4_rows if not row.get("is_finished")]),
        },
    )

    status_counts: dict[str, int] = {}
    reason_counts: dict[str, int] = {}
    sample_failure_messages: list[str] = []
    for row in v4_rows:
        status_value = str(row.get("status") or "unknown")
        status_counts[status_value] = status_counts.get(status_value, 0) + 1

        summary = row.get("summary")
        if not isinstance(summary, dict):
            continue
        for message in _extract_v4_failure_messages(summary):
            reason_key = _classify_failure_message(message)
            reason_counts[reason_key] = reason_counts.get(reason_key, 0) + 1
            if len(sample_failure_messages) < 5:
                sample_failure_messages.append(message[:180])

    running_items = len([row for row in v4_rows if not row.get("is_finished")])
    if running_items == 0:
        if reason_counts:
            likely_root_cause = (
                "not celery pending; upstream executions are finished and failures are mostly target connectivity/auth problems"
            )
        else:
            likely_root_cause = "not celery pending; upstream executions are finished"
    else:
        likely_root_cause = "in-progress executions exist; inspect jumpserver task workers and queue depth"

    print_json(
        "v4_root_cause_hints",
        {
            "status_counts": status_counts,
            "reason_counts": reason_counts,
            "sample_failure_messages": sample_failure_messages,
            "likely_root_cause": likely_root_cause,
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe JumpServer APIs used by OpsPaw.")
    parser.add_argument(
        "--pending-diagnosis",
        action="store_true",
        help="Run celery PENDING diagnosis using real and random task IDs.",
    )
    args = parser.parse_args()

    client = JumpServerClient()
    try:
        run_basic_probe(client)
        if args.pending_diagnosis:
            run_pending_diagnosis(client)
        print("\nJumpServer probe completed.")
        return 0
    except JumpServerClientError as exc:
        print(f"\nJumpServer probe failed: {exc}")
        return 2
    except Exception as exc:  # pragma: no cover - defensive guard
        print(f"\nUnexpected error: {exc}")
        return 3


if __name__ == "__main__":
    sys.exit(main())
