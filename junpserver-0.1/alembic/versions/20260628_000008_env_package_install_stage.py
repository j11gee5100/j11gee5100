"""env package install stage relation

Revision ID: 20260628_000008
Revises: 20260628_000007
Create Date: 2026-06-28 21:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260628_000008"
down_revision = "20260628_000007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("env_package", sa.Column("install_stage", sa.String(32), nullable=False, server_default="first_install"))
    op.add_column("env_package", sa.Column("replaces_package_ids", sa.Text(), nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("env_package", "replaces_package_ids")
    op.drop_column("env_package", "install_stage")
