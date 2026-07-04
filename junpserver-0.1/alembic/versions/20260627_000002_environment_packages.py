"""environment package assets

Revision ID: 20260627_000002
Revises: 20260627_000001
Create Date: 2026-06-27 22:30:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260627_000002"
down_revision = "20260627_000001"
branch_labels = None
depends_on = None


def timestamps():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    ]


def audit_cols():
    return [
        sa.Column("created_by", sa.String(64), nullable=False, server_default="system"),
        sa.Column("updated_by", sa.String(64), nullable=False, server_default="system"),
    ]


def upgrade() -> None:
    op.create_table(
        "user_account",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("display_name", sa.String(128), nullable=False, server_default=""),
        sa.Column("role", sa.String(32), nullable=False, server_default="user"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="1"),
        *timestamps(),
        sa.UniqueConstraint("username", name="uq_user_account_username"),
    )
    op.create_table(
        "env_device_profile",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("profile_code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(128), nullable=False, server_default=""),
        sa.Column("hardware_vendor", sa.String(128), nullable=False, server_default=""),
        sa.Column("cpu_arch", sa.String(64), nullable=False, server_default=""),
        sa.Column("os_type", sa.String(64), nullable=False, server_default=""),
        sa.Column("os_version", sa.String(128), nullable=False, server_default=""),
        sa.Column("accelerator_vendor", sa.String(64), nullable=False, server_default=""),
        sa.Column("accelerator_model", sa.String(128), nullable=False, server_default=""),
        sa.Column("driver_version", sa.String(128), nullable=False, server_default=""),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="1"),
        *audit_cols(),
        *timestamps(),
        sa.UniqueConstraint("profile_code", name="uq_env_device_profile_code"),
    )
    op.create_table(
        "env_package",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("package_code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(128), nullable=False, server_default=""),
        sa.Column("package_type", sa.String(64), nullable=False, server_default="custom"),
        sa.Column("version", sa.String(128), nullable=False, server_default=""),
        sa.Column("file_uri", sa.String(1024), nullable=False, server_default=""),
        sa.Column("file_name", sa.String(255), nullable=False, server_default=""),
        sa.Column("checksum_type", sa.String(32), nullable=False, server_default="sha256"),
        sa.Column("checksum", sa.String(255), nullable=False, server_default=""),
        sa.Column("install_script", sa.Text(), nullable=False, server_default=""),
        sa.Column("verify_script", sa.Text(), nullable=False, server_default=""),
        sa.Column("uninstall_script", sa.Text(), nullable=False, server_default=""),
        sa.Column("requires_root", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("requires_reboot", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("offline_supported", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("visibility", sa.String(32), nullable=False, server_default="private"),
        sa.Column("owner_id", sa.String(64), nullable=False, server_default=""),
        *audit_cols(),
        *timestamps(),
        sa.UniqueConstraint("package_code", "version", "owner_id", name="uq_env_package_code_version_owner"),
    )
    op.create_table(
        "env_package_compatibility",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("package_id", sa.String(36), nullable=False),
        sa.Column("device_profile_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("package_id", "device_profile_id", name="uq_env_package_profile"),
    )


def downgrade() -> None:
    op.drop_table("env_package_compatibility")
    op.drop_table("env_package")
    op.drop_table("env_device_profile")
    op.drop_table("user_account")
