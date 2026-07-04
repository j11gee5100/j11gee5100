"""user authentication fields
Revision ID: 20260627_000003
Revises: 20260627_000002
Create Date: 2026-06-27 23:55:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260627_000003"
down_revision = "20260627_000002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user_account", sa.Column("password_hash", sa.String(length=255), nullable=False, server_default=""))
    op.add_column("user_account", sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("user_account", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("user_account", "last_login_at")
    op.drop_column("user_account", "password_changed_at")
    op.drop_column("user_account", "password_hash")
