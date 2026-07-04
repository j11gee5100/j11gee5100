from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SyncSnapshot(Base):
    __tablename__ = "sync_snapshot"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="jumpserver")
    snapshot_type: Mapped[str] = mapped_column(String(64), nullable=False, default="sync_tick")

    offset: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_offset: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    page_size: Mapped[int] = mapped_column(Integer, nullable=False, default=50)

    fetched_assets: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fetched_system_users: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fetched_relations: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    upstream_total_assets: Mapped[int | None] = mapped_column(Integer, nullable=True)
    local_total_assets: Mapped[int | None] = mapped_column(Integer, nullable=True)
    local_total_system_users: Mapped[int | None] = mapped_column(Integer, nullable=True)
    local_total_relations: Mapped[int | None] = mapped_column(Integer, nullable=True)

    consistency_status: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")
    consistency_delta_assets: Mapped[int | None] = mapped_column(Integer, nullable=True)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    detail: Mapped[str] = mapped_column(String(1024), nullable=False, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
