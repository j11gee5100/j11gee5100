"""env package skeleton fields

Revision ID: 20260628_000004
Revises: 20260627_000003
Create Date: 2026-06-28 01:20:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260628_000004"
down_revision = "20260627_000003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("env_package", sa.Column("check_script", sa.Text(), nullable=False, server_default=""))
    op.add_column("env_package", sa.Column("depends_on", sa.Text(), nullable=False, server_default=""))
    op.add_column("env_package", sa.Column("install_order", sa.Integer(), nullable=False, server_default="100"))


def downgrade() -> None:
    op.drop_column("env_package", "install_order")
    op.drop_column("env_package", "depends_on")
    op.drop_column("env_package", "check_script")
