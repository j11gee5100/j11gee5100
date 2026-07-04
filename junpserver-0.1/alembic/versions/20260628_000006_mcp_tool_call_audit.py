"""mcp tool call audit

Revision ID: 20260628_000006
Revises: 20260628_000005
Create Date: 2026-06-28 10:45:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260628_000006"
down_revision = "20260628_000005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mcp_tool_call_audit",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("mcp_call_id", sa.String(64), nullable=False, server_default=""),
        sa.Column("session_id", sa.String(128), nullable=False, server_default=""),
        sa.Column("client_name", sa.String(128), nullable=False, server_default=""),
        sa.Column("operator_id", sa.String(64), nullable=False, server_default=""),
        sa.Column("operator_role", sa.String(32), nullable=False, server_default="user"),
        sa.Column("tool_name", sa.String(128), nullable=False, server_default=""),
        sa.Column("toolset", sa.String(64), nullable=False, server_default=""),
        sa.Column("risk_level", sa.String(32), nullable=False, server_default="low"),
        sa.Column("read_only", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("arguments_hash", sa.String(128), nullable=False, server_default=""),
        sa.Column("object_type", sa.String(64), nullable=False, server_default=""),
        sa.Column("object_id", sa.String(128), nullable=False, server_default=""),
        sa.Column("status", sa.String(32), nullable=False, server_default="started"),
        sa.Column("error_code", sa.String(64), nullable=False, server_default=""),
        sa.Column("trace_id", sa.String(64), nullable=False, server_default=""),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("details_json", sa.Text(), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_table("mcp_tool_call_audit")
