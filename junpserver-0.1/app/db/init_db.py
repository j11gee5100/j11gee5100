from __future__ import annotations

from sqlalchemy import inspect, text

from app.db.base import Base
from app.db.session import engine
from app.models import (  # noqa: F401
    audit_link,
    asset_projection,
    approval_action_audit,
    approval_request,
    callback_delivery,
    callback_hook,
    callback_replay_audit,
    command_blacklist_rule,
    command_template,
    execution,
    failure_summary_bucket,
    governance_audit,
    env_package,
    env_device_profile,
    user_account,
    environment_handover,
    environment_implementation,
    model_deployment_requirement,
    environment_spec,
    inference_device,
    metrics_preaggregation_run,
    mcp_tool_call_audit,
    sync_checkpoint,
    sync_snapshot,
    system_user_projection,
    task,
    task_retry_audit_count_bucket,
    task_retry_audit,
    task_retry_audit_item,
    task_retry_summary_bucket,
)


def _column_exists(table_columns: set[str], column_name: str) -> bool:
    return column_name in table_columns


def _add_column_if_missing(
    *,
    conn,
    inspector,
    table_name: str,
    column_name: str,
    alter_sql: str,
) -> None:
    if table_name not in inspector.get_table_names():
        return
    existing = {col["name"] for col in inspector.get_columns(table_name)}
    if _column_exists(existing, column_name):
        return
    conn.execute(text(alter_sql))


def _ensure_incremental_schema() -> None:
    with engine.begin() as conn:
        inspector = inspect(conn)
        dialect = engine.dialect.name
        is_postgres = dialect.startswith("postgres")
        is_mysql = dialect.startswith("mysql")

        task_template_sql = (
            "ALTER TABLE task ADD COLUMN command_template_id VARCHAR(64) NOT NULL DEFAULT ''"
        )
        if is_postgres:
            task_template_sql = (
                "ALTER TABLE task ADD COLUMN IF NOT EXISTS command_template_id VARCHAR(64) NOT NULL DEFAULT ''"
            )
        _add_column_if_missing(
            conn=conn,
            inspector=inspector,
            table_name="task",
            column_name="command_template_id",
            alter_sql=task_template_sql,
        )

        approval_columns = [
            (
                "current_level",
                "ALTER TABLE approval_request ADD COLUMN current_level INTEGER NOT NULL DEFAULT 1",
                "ALTER TABLE approval_request ADD COLUMN IF NOT EXISTS current_level INTEGER NOT NULL DEFAULT 1",
            ),
            (
                "max_level",
                "ALTER TABLE approval_request ADD COLUMN max_level INTEGER NOT NULL DEFAULT 1",
                "ALTER TABLE approval_request ADD COLUMN IF NOT EXISTS max_level INTEGER NOT NULL DEFAULT 1",
            ),
            (
                "escalation_count",
                "ALTER TABLE approval_request ADD COLUMN escalation_count INTEGER NOT NULL DEFAULT 0",
                "ALTER TABLE approval_request ADD COLUMN IF NOT EXISTS escalation_count INTEGER NOT NULL DEFAULT 0",
            ),
            (
                "next_escalate_at",
                "ALTER TABLE approval_request ADD COLUMN next_escalate_at DATETIME NULL",
                "ALTER TABLE approval_request ADD COLUMN IF NOT EXISTS next_escalate_at TIMESTAMPTZ NULL",
            ),
        ]
        for column_name, generic_sql, postgres_sql in approval_columns:
            _add_column_if_missing(
                conn=conn,
                inspector=inspector,
                table_name="approval_request",
                column_name=column_name,
                alter_sql=postgres_sql if is_postgres else generic_sql,
            )

        env_package_columns = [
            (
                "check_script",
                "ALTER TABLE env_package ADD COLUMN check_script TEXT NOT NULL",
                "ALTER TABLE env_package ADD COLUMN IF NOT EXISTS check_script TEXT NOT NULL DEFAULT ''",
                "ALTER TABLE env_package ADD COLUMN check_script TEXT NOT NULL",
            ),
            (
                "depends_on",
                "ALTER TABLE env_package ADD COLUMN depends_on TEXT NOT NULL",
                "ALTER TABLE env_package ADD COLUMN IF NOT EXISTS depends_on TEXT NOT NULL DEFAULT ''",
                "ALTER TABLE env_package ADD COLUMN depends_on TEXT NOT NULL",
            ),
            (
                "install_order",
                "ALTER TABLE env_package ADD COLUMN install_order INTEGER NOT NULL DEFAULT 100",
                "ALTER TABLE env_package ADD COLUMN IF NOT EXISTS install_order INTEGER NOT NULL DEFAULT 100",
                "ALTER TABLE env_package ADD COLUMN install_order INTEGER NOT NULL DEFAULT 100",
            ),
        ]
        for column_name, generic_sql, postgres_sql, mysql_sql in env_package_columns:
            _add_column_if_missing(
                conn=conn,
                inspector=inspector,
                table_name="env_package",
                column_name=column_name,
                alter_sql=postgres_sql if is_postgres else (mysql_sql if is_mysql else generic_sql),
            )

        delivery_bundle_columns = [
            ("bundle_type", "ALTER TABLE delivery_bundle ADD COLUMN bundle_type VARCHAR(32) NOT NULL DEFAULT 'first_install'", "ALTER TABLE delivery_bundle ADD COLUMN IF NOT EXISTS bundle_type VARCHAR(32) NOT NULL DEFAULT 'first_install'"),
            ("lifecycle_status", "ALTER TABLE delivery_bundle ADD COLUMN lifecycle_status VARCHAR(32) NOT NULL DEFAULT 'making'", "ALTER TABLE delivery_bundle ADD COLUMN IF NOT EXISTS lifecycle_status VARCHAR(32) NOT NULL DEFAULT 'making'"),
            ("delivered_by", "ALTER TABLE delivery_bundle ADD COLUMN delivered_by VARCHAR(64) NOT NULL DEFAULT ''", "ALTER TABLE delivery_bundle ADD COLUMN IF NOT EXISTS delivered_by VARCHAR(64) NOT NULL DEFAULT ''"),
            ("delivered_at", "ALTER TABLE delivery_bundle ADD COLUMN delivered_at TIMESTAMP", "ALTER TABLE delivery_bundle ADD COLUMN IF NOT EXISTS delivered_at TIMESTAMP"),
            ("parent_bundle_id", "ALTER TABLE delivery_bundle ADD COLUMN parent_bundle_id VARCHAR(36) NOT NULL DEFAULT ''", "ALTER TABLE delivery_bundle ADD COLUMN IF NOT EXISTS parent_bundle_id VARCHAR(36) NOT NULL DEFAULT ''"),
            ("build_status", "ALTER TABLE delivery_bundle ADD COLUMN build_status VARCHAR(32) NOT NULL DEFAULT 'not_built'", "ALTER TABLE delivery_bundle ADD COLUMN IF NOT EXISTS build_status VARCHAR(32) NOT NULL DEFAULT 'not_built'"),
            ("artifact_uri", "ALTER TABLE delivery_bundle ADD COLUMN artifact_uri VARCHAR(1024) NOT NULL DEFAULT ''", "ALTER TABLE delivery_bundle ADD COLUMN IF NOT EXISTS artifact_uri VARCHAR(1024) NOT NULL DEFAULT ''"),
            ("artifact_name", "ALTER TABLE delivery_bundle ADD COLUMN artifact_name VARCHAR(255) NOT NULL DEFAULT ''", "ALTER TABLE delivery_bundle ADD COLUMN IF NOT EXISTS artifact_name VARCHAR(255) NOT NULL DEFAULT ''"),
            ("artifact_size", "ALTER TABLE delivery_bundle ADD COLUMN artifact_size INTEGER NOT NULL DEFAULT 0", "ALTER TABLE delivery_bundle ADD COLUMN IF NOT EXISTS artifact_size INTEGER NOT NULL DEFAULT 0"),
            ("artifact_checksum", "ALTER TABLE delivery_bundle ADD COLUMN artifact_checksum VARCHAR(255) NOT NULL DEFAULT ''", "ALTER TABLE delivery_bundle ADD COLUMN IF NOT EXISTS artifact_checksum VARCHAR(255) NOT NULL DEFAULT ''"),
            ("build_log", "ALTER TABLE delivery_bundle ADD COLUMN build_log TEXT NOT NULL", "ALTER TABLE delivery_bundle ADD COLUMN IF NOT EXISTS build_log TEXT NOT NULL DEFAULT ''", "ALTER TABLE delivery_bundle ADD COLUMN build_log TEXT NOT NULL"),
            ("built_at", "ALTER TABLE delivery_bundle ADD COLUMN built_at TIMESTAMP", "ALTER TABLE delivery_bundle ADD COLUMN IF NOT EXISTS built_at TIMESTAMP"),
        ]
        for column in delivery_bundle_columns:
            if len(column) == 3:
                column_name, generic_sql, postgres_sql = column
                mysql_sql = generic_sql
            else:
                column_name, generic_sql, postgres_sql, mysql_sql = column
            _add_column_if_missing(
                conn=conn,
                inspector=inspector,
                table_name="delivery_bundle",
                column_name=column_name,
                alter_sql=postgres_sql if is_postgres else (mysql_sql if is_mysql else generic_sql),
            )


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _ensure_incremental_schema()
