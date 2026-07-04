from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TaskRetryAuditItem(Base):
    __tablename__ = "task_retry_audit_item"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    audit_id: Mapped[str] = mapped_column(String(36), ForeignKey("task_retry_audit.id"), nullable=False)
    task_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    target_asset_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    action: Mapped[str] = mapped_column(String(48), nullable=False, default="")
    failure_code: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    final_status: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    final_failure_code: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    message: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
