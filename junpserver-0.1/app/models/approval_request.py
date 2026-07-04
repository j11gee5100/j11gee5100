from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ApprovalRequest(Base):
    __tablename__ = "approval_request"
    __table_args__ = (
        UniqueConstraint("task_id", name="uq_approval_request_task_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    task_id: Mapped[str] = mapped_column(String(36), ForeignKey("task.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    requested_by: Mapped[str] = mapped_column(String(64), nullable=False, default="unknown")
    source_ip: Mapped[str] = mapped_column(String(64), nullable=False, default="unknown")
    decided_by: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    decision_reason: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    current_level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    max_level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    escalation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_escalate_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
