from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Task(Base):
    __tablename__ = "task"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_task_idempotency_key"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="web")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    risk_level: Mapped[str] = mapped_column(String(32), nullable=False, default="readonly")
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    command_template_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    command: Mapped[str] = mapped_column(String(2048), nullable=False, default="")
    target_asset_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    run_as_system_user_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    reason: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
