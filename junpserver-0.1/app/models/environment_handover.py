from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class EnvironmentHandover(Base):
    __tablename__ = "environment_handover"
    __table_args__ = (UniqueConstraint("handover_no", name="uq_environment_handover_handover_no"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    handover_no: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    device_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    implementation_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    requirement_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    environment_spec_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    test_result: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    test_report_url: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    model_platform_url: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    package_manifest: Mapped[str] = mapped_column(String(4096), nullable=False, default="")
    validation_summary: Mapped[str] = mapped_column(String(2048), nullable=False, default="")
    recipient: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    accepted_by: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str] = mapped_column(String(2048), nullable=False, default="")
    created_by: Mapped[str] = mapped_column(String(64), nullable=False, default="system")
    updated_by: Mapped[str] = mapped_column(String(64), nullable=False, default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
