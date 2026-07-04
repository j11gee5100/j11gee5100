"""delivery bundle and probe result skeleton

Revision ID: 20260628_000005
Revises: 20260628_000004
Create Date: 2026-06-28 01:40:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260628_000005"
down_revision = "20260628_000004"
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
        "delivery_bundle",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("bundle_code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(128), nullable=False, server_default=""),
        sa.Column("version", sa.String(128), nullable=False, server_default=""),
        sa.Column("target_device_id", sa.String(36), nullable=False, server_default=""),
        sa.Column("target_profile_id", sa.String(36), nullable=False, server_default=""),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("manifest_json", sa.Text(), nullable=False, server_default=""),
        sa.Column("owner_id", sa.String(64), nullable=False, server_default=""),
        *audit_cols(),
        *timestamps(),
        sa.UniqueConstraint("bundle_code", "owner_id", name="uq_delivery_bundle_code_owner"),
    )
    op.create_table(
        "delivery_bundle_item",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("bundle_id", sa.String(36), nullable=False),
        sa.Column("package_id", sa.String(36), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("bundle_id", "package_id", name="uq_delivery_bundle_package"),
    )
    op.create_table(
        "probe_result",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("result_code", sa.String(64), nullable=False),
        sa.Column("device_id", sa.String(36), nullable=False, server_default=""),
        sa.Column("name", sa.String(128), nullable=False, server_default=""),
        sa.Column("raw_json", sa.Text(), nullable=False, server_default=""),
        sa.Column("os_type", sa.String(64), nullable=False, server_default=""),
        sa.Column("os_version", sa.String(128), nullable=False, server_default=""),
        sa.Column("cpu_arch", sa.String(64), nullable=False, server_default=""),
        sa.Column("accelerator_vendor", sa.String(64), nullable=False, server_default=""),
        sa.Column("accelerator_model", sa.String(128), nullable=False, server_default=""),
        sa.Column("driver_version", sa.String(128), nullable=False, server_default=""),
        sa.Column("owner_id", sa.String(64), nullable=False, server_default=""),
        *audit_cols(),
        *timestamps(),
        sa.UniqueConstraint("result_code", "owner_id", name="uq_probe_result_code_owner"),
    )


def downgrade() -> None:
    op.drop_table("probe_result")
    op.drop_table("delivery_bundle_item")
    op.drop_table("delivery_bundle")
