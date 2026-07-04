from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class EnvironmentImplementation(Base):
    __tablename__ = "environment_implementation"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    device_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    environment_spec_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    requirement_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    implementation_status: Mapped[str] = mapped_column(String(32), nullable=False, default="planned")
    implemented_by: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    implemented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    install_method: Mapped[str] = mapped_column(String(128), nullable=False, default="manual")
    actual_os_version: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    actual_driver_version: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    actual_runtime_version: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    actual_framework_version: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    actual_inference_server: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    actual_container_image: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    config_summary: Mapped[str] = mapped_column(String(2048), nullable=False, default="")
    artifact_uri: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    log_uri: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    diff_summary: Mapped[str] = mapped_column(String(2048), nullable=False, default="")
    issue_summary: Mapped[str] = mapped_column(String(2048), nullable=False, default="")
    created_by: Mapped[str] = mapped_column(String(64), nullable=False, default="system")
    updated_by: Mapped[str] = mapped_column(String(64), nullable=False, default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
