from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FailureSummaryBucket(Base):
    __tablename__ = "failure_summary_bucket"
    __table_args__ = (
        UniqueConstraint(
            "granularity",
            "bucket_start",
            "source",
            "risk_level",
            "failure_code",
            "unknown_reason",
            name="uq_failure_summary_bucket",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    granularity: Mapped[str] = mapped_column(String(8), nullable=False, default="hour")
    bucket_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    risk_level: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    failure_code: Mapped[str] = mapped_column(String(32), nullable=False, default="UNKNOWN")
    unknown_reason: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
