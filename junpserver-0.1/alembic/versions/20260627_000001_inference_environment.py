"""inference environment management

Revision ID: 20260627_000001
Revises: 20260402_000001
Create Date: 2026-06-27 21:20:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260627_000001"
down_revision = "20260402_000001"
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    ]


def _audit_columns() -> list[sa.Column]:
    return [
        sa.Column("created_by", sa.String(length=64), nullable=False, server_default="system"),
        sa.Column("updated_by", sa.String(length=64), nullable=False, server_default="system"),
    ]


def upgrade() -> None:
    op.create_table(
        "inference_device",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("device_code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("hostname", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("ip", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("asset_id", sa.String(length=36), nullable=False, server_default=""),
        sa.Column("jms_asset_id", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("owner_team", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("location", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("os_type", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("os_version", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("cpu_arch", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("cpu_model", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("memory_gb", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("storage_summary", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("accelerator_vendor", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("accelerator_model", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("accelerator_count", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("accelerator_memory_gb", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("driver_version", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("firmware_version", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("notes", sa.String(length=2048), nullable=False, server_default=""),
        *_audit_columns(),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("device_code", name="uq_inference_device_device_code"),
    )
    op.create_table(
        "environment_spec",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("spec_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("version", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("description", sa.String(length=2048), nullable=False, server_default=""),
        sa.Column("os_type", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("os_version", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("accelerator_vendor", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("accelerator_model", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("min_accelerator_count", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("min_accelerator_memory_gb", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("driver_version", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("runtime_name", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("runtime_version", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("python_version", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("framework", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("framework_version", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("inference_server", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("container_image", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("dependency_manifest", sa.String(length=4096), nullable=False, server_default=""),
        sa.Column("ports", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("startup_command", sa.String(length=2048), nullable=False, server_default=""),
        sa.Column("health_check", sa.String(length=2048), nullable=False, server_default=""),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="1"),
        *_audit_columns(),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("spec_id", name="uq_environment_spec_spec_id"),
    )
    op.create_table(
        "model_deployment_requirement",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("requirement_id", sa.String(length=64), nullable=False),
        sa.Column("model_id", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("model_name", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("model_version", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("model_platform_url", sa.String(length=1024), nullable=False, server_default=""),
        sa.Column("model_artifact_uri", sa.String(length=1024), nullable=False, server_default=""),
        sa.Column("environment_spec_id", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("accelerator_vendor", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("accelerator_model", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("min_accelerator_count", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("min_accelerator_memory_gb", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("performance_baseline", sa.String(length=2048), nullable=False, server_default=""),
        sa.Column("deployment_notes", sa.String(length=2048), nullable=False, server_default=""),
        sa.Column("source", sa.String(length=64), nullable=False, server_default="manual"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        *_audit_columns(),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("requirement_id", name="uq_model_deployment_requirement_requirement_id"),
    )
    op.create_table(
        "environment_implementation",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("device_id", sa.String(length=36), nullable=False, server_default=""),
        sa.Column("environment_spec_id", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("requirement_id", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("implementation_status", sa.String(length=32), nullable=False, server_default="planned"),
        sa.Column("implemented_by", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("implemented_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("install_method", sa.String(length=128), nullable=False, server_default="manual"),
        sa.Column("actual_os_version", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("actual_driver_version", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("actual_runtime_version", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("actual_framework_version", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("actual_inference_server", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("actual_container_image", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("config_summary", sa.String(length=2048), nullable=False, server_default=""),
        sa.Column("artifact_uri", sa.String(length=1024), nullable=False, server_default=""),
        sa.Column("log_uri", sa.String(length=1024), nullable=False, server_default=""),
        sa.Column("diff_summary", sa.String(length=2048), nullable=False, server_default=""),
        sa.Column("issue_summary", sa.String(length=2048), nullable=False, server_default=""),
        *_audit_columns(),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "environment_handover",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("handover_no", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("device_id", sa.String(length=36), nullable=False, server_default=""),
        sa.Column("implementation_id", sa.String(length=36), nullable=False, server_default=""),
        sa.Column("requirement_id", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("environment_spec_id", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("test_result", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("test_report_url", sa.String(length=1024), nullable=False, server_default=""),
        sa.Column("model_platform_url", sa.String(length=1024), nullable=False, server_default=""),
        sa.Column("package_manifest", sa.String(length=4096), nullable=False, server_default=""),
        sa.Column("validation_summary", sa.String(length=2048), nullable=False, server_default=""),
        sa.Column("recipient", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("accepted_by", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.String(length=2048), nullable=False, server_default=""),
        *_audit_columns(),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("handover_no", name="uq_environment_handover_handover_no"),
    )


def downgrade() -> None:
    op.drop_table("environment_handover")
    op.drop_table("environment_implementation")
    op.drop_table("model_deployment_requirement")
    op.drop_table("environment_spec")
    op.drop_table("inference_device")
