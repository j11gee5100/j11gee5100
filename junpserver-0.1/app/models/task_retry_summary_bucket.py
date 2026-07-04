from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TaskRetrySummaryBucket(Base):
    __tablename__ = "task_retry_summary_bucket"
    __table_args__ = (
        UniqueConstraint(
            "granularity",
            "bucket_start",
            "source",
            "action",
            "failure_code",
            "operator_id",
            "dry_run",
            name="uq_task_retry_summary_bucket",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    granularity: Mapped[str] = mapped_column(String(8), nullable=False, default="hour")
    bucket_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    action: Mapped[str] = mapped_column(String(48), nullable=False, default="")
    failure_code: Mapped[str] = mapped_column(String(32), nullable=False, default="UNKNOWN")
    operator_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    dry_run: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

