from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class EnvironmentSpec(Base):
    __tablename__ = "environment_spec"
    __table_args__ = (UniqueConstraint("spec_id", name="uq_environment_spec_spec_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    spec_id: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    version: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    description: Mapped[str] = mapped_column(String(2048), nullable=False, default="")
    os_type: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    os_version: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    accelerator_vendor: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    accelerator_model: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    min_accelerator_count: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    min_accelerator_memory_gb: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    driver_version: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    runtime_name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    runtime_version: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    python_version: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    framework: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    framework_version: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    inference_server: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    container_image: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    dependency_manifest: Mapped[str] = mapped_column(String(4096), nullable=False, default="")
    ports: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    startup_command: Mapped[str] = mapped_column(String(2048), nullable=False, default="")
    health_check: Mapped[str] = mapped_column(String(2048), nullable=False, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_by: Mapped[str] = mapped_column(String(64), nullable=False, default="system")
    updated_by: Mapped[str] = mapped_column(String(64), nullable=False, default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
