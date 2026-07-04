"""delivery bundle lifecycle and build jobs

Revision ID: 20260629_000010
Revises: 20260629_000009
Create Date: 2026-06-29 08:50:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260629_000010"
down_revision = "20260629_000009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("delivery_bundle", sa.Column("lifecycle_status", sa.String(32), nullable=False, server_default="making"))
    op.add_column("delivery_bundle", sa.Column("delivered_by", sa.String(64), nullable=False, server_default=""))
    op.add_column("delivery_bundle", sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("delivery_bundle", sa.Column("parent_bundle_id", sa.String(36), nullable=False, server_default=""))
    op.create_table(
        "delivery_bundle_build_job",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("bundle_id", sa.String(36), nullable=False),
        sa.Column("job_status", sa.String(32), nullable=False, server_default="queued"),
        sa.Column("progress_percent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("current_step", sa.String(128), nullable=False, server_default=""),
        sa.Column("current_message", sa.String(1024), nullable=False, server_default=""),
        sa.Column("log_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("artifact_uri", sa.String(1024), nullable=False, server_default=""),
        sa.Column("artifact_name", sa.String(255), nullable=False, server_default=""),
        sa.Column("artifact_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("artifact_checksum", sa.String(255), nullable=False, server_default=""),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(64), nullable=False, server_default="system"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("delivery_bundle_build_job")
    op.drop_column("delivery_bundle", "parent_bundle_id")
    op.drop_column("delivery_bundle", "delivered_at")
    op.drop_column("delivery_bundle", "delivered_by")
    op.drop_column("delivery_bundle", "lifecycle_status")
