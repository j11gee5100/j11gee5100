from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ApprovalActionAudit(Base):
    __tablename__ = "approval_action_audit"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    approval_id: Mapped[str] = mapped_column(String(36), ForeignKey("approval_request.id"), nullable=False)
    task_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    action: Mapped[str] = mapped_column(String(24), nullable=False, default="created")
    operator_id: Mapped[str] = mapped_column(String(64), nullable=False, default="unknown")
    source_ip: Mapped[str] = mapped_column(String(64), nullable=False, default="unknown")
    reason: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

