"""delivery bundle type

Revision ID: 20260629_000009
Revises: 20260628_000008
Create Date: 2026-06-29 00:20:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260629_000009"
down_revision = "20260628_000008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("delivery_bundle", sa.Column("bundle_type", sa.String(32), nullable=False, server_default="first_install"))


def downgrade() -> None:
    op.drop_column("delivery_bundle", "bundle_type")
