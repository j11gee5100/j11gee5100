from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class GovernanceAudit(Base):
    __tablename__ = "governance_audit"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    action: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    operator_id: Mapped[str] = mapped_column(String(64), nullable=False, default="unknown")
    source_ip: Mapped[str] = mapped_column(String(64), nullable=False, default="unknown")
    detail_json: Mapped[str] = mapped_column(String(4096), nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
