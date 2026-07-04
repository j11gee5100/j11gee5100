from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class InferenceDevice(Base):
    __tablename__ = "inference_device"
    __table_args__ = (UniqueConstraint("device_code", name="uq_inference_device_device_code"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    device_code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    hostname: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    ip: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    asset_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    jms_asset_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    owner_team: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    location: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    os_type: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    os_version: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    cpu_arch: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    cpu_model: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    memory_gb: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    storage_summary: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    accelerator_vendor: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    accelerator_model: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    accelerator_count: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    accelerator_memory_gb: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    driver_version: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    firmware_version: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    notes: Mapped[str] = mapped_column(String(2048), nullable=False, default="")
    created_by: Mapped[str] = mapped_column(String(64), nullable=False, default="system")
    updated_by: Mapped[str] = mapped_column(String(64), nullable=False, default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
