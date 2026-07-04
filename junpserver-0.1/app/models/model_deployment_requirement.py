from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ModelDeploymentRequirement(Base):
    __tablename__ = "model_deployment_requirement"
    __table_args__ = (UniqueConstraint("requirement_id", name="uq_model_deployment_requirement_requirement_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    requirement_id: Mapped[str] = mapped_column(String(64), nullable=False)
    model_id: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    model_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    model_version: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    model_platform_url: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    model_artifact_uri: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    environment_spec_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    accelerator_vendor: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    accelerator_model: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    min_accelerator_count: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    min_accelerator_memory_gb: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    performance_baseline: Mapped[str] = mapped_column(String(2048), nullable=False, default="")
    deployment_notes: Mapped[str] = mapped_column(String(2048), nullable=False, default="")
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="manual")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    created_by: Mapped[str] = mapped_column(String(64), nullable=False, default="system")
    updated_by: Mapped[str] = mapped_column(String(64), nullable=False, default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
