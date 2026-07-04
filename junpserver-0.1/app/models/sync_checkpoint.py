from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SyncCheckpoint(Base):
    __tablename__ = "sync_checkpoint"
    __table_args__ = (
        UniqueConstraint("source", "entity_type", name="uq_sync_checkpoint_source_entity"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="jumpserver")
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    cursor: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

