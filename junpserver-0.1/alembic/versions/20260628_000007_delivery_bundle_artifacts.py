from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260628_000007"
down_revision = "20260628_000006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("delivery_bundle", sa.Column("build_status", sa.String(32), nullable=False, server_default="not_built"))
    op.add_column("delivery_bundle", sa.Column("artifact_uri", sa.String(1024), nullable=False, server_default=""))
    op.add_column("delivery_bundle", sa.Column("artifact_name", sa.String(255), nullable=False, server_default=""))
    op.add_column("delivery_bundle", sa.Column("artifact_size", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("delivery_bundle", sa.Column("artifact_checksum", sa.String(255), nullable=False, server_default=""))
    op.add_column("delivery_bundle", sa.Column("build_log", sa.Text(), nullable=False, server_default=""))
    op.add_column("delivery_bundle", sa.Column("built_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("delivery_bundle", "built_at")
    op.drop_column("delivery_bundle", "build_log")
    op.drop_column("delivery_bundle", "artifact_checksum")
    op.drop_column("delivery_bundle", "artifact_size")
    op.drop_column("delivery_bundle", "artifact_name")
    op.drop_column("delivery_bundle", "artifact_uri")
    op.drop_column("delivery_bundle", "build_status")
