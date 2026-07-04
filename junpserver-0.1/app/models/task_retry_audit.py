from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TaskRetryAudit(Base):
    __tablename__ = "task_retry_audit"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    endpoint: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    operator_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    source_ip: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    dry_run: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    effective_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=24)
    source_filter: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    failure_codes_csv: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    window_size: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    max_windows: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    same_asset_max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    requested: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    missing_tasks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    matched_by_failure: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    queued: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_non_retryable: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_in_progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_asset_not_found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_rate_limited: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_asset_guardrail: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    filters_json: Mapped[str] = mapped_column(String(4096), nullable=False, default="{}")
    summary_json: Mapped[str] = mapped_column(String(4096), nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
