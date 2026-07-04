from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MetricsPreaggregationRun(Base):
    __tablename__ = "metrics_preaggregation_run"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ok")
    hourly_lookback_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=72)
    daily_lookback_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    failure_hour_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_day_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    retry_hour_item_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    retry_day_item_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    retry_hour_audit_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    retry_day_audit_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

