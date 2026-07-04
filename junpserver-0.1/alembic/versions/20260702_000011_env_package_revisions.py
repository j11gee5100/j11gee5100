"""env package revisions

Revision ID: 20260702_000011
Revises: 20260629_000010
Create Date: 2026-07-02 10:30:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "20260702_000011"
down_revision = "20260629_000010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if inspector.has_table("env_package_revision"):
        existing_indexes = {item.get("name") for item in inspector.get_indexes("env_package_revision")}
        if "ix_env_package_revision_package_id" not in existing_indexes:
            op.create_index("ix_env_package_revision_package_id", "env_package_revision", ["package_id"])
        return

    op.create_table(
        "env_package_revision",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("package_id", sa.String(36), nullable=False),
        sa.Column("revision_no", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("operation_type", sa.String(32), nullable=False, server_default="script_edit"),
        sa.Column("save_mode", sa.String(32), nullable=False, server_default="in_place"),
        sa.Column("old_file_uri", sa.String(1024), nullable=False, server_default=""),
        sa.Column("new_file_uri", sa.String(1024), nullable=False, server_default=""),
        sa.Column("old_checksum", sa.String(255), nullable=False, server_default=""),
        sa.Column("new_checksum", sa.String(255), nullable=False, server_default=""),
        sa.Column("changed_files", sa.Text(), nullable=False),
        sa.Column("script_diff_json", sa.Text(), nullable=False),
        sa.Column("remark", sa.Text(), nullable=False),
        sa.Column("created_by", sa.String(64), nullable=False, server_default="system"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_env_package_revision_package_id", "env_package_revision", ["package_id"])


def downgrade() -> None:
    op.drop_index("ix_env_package_revision_package_id", table_name="env_package_revision")
    op.drop_table("env_package_revision")
