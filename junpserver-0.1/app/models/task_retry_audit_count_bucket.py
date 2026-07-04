from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TaskRetryAuditCountBucket(Base):
    __tablename__ = "task_retry_audit_count_bucket"
    __table_args__ = (
        UniqueConstraint(
            "granularity",
            "bucket_start",
            "operator_id",
            "dry_run",
            "source_selector",
            name="uq_task_retry_audit_count_bucket",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    granularity: Mapped[str] = mapped_column(String(8), nullable=False, default="hour")
    bucket_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    operator_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    dry_run: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_selector: Mapped[str] = mapped_column(String(32), nullable=False, default="*")
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

