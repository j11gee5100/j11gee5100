from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CallbackReplayAudit(Base):
    __tablename__ = "callback_replay_audit"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    endpoint: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    operator_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    source_ip: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    dry_run: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    matched: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    replayed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_non_replayable: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    blocked_by_guardrail: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    guardrail_reason: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    filters_json: Mapped[str] = mapped_column(String(4096), nullable=False, default="{}")
    delivery_ids_json: Mapped[str] = mapped_column(String(8192), nullable=False, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
