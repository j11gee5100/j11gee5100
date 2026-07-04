from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class EnvDeviceProfile(Base):
    __tablename__ = "env_device_profile"
    __table_args__ = (UniqueConstraint("profile_code", name="uq_env_device_profile_code"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    profile_code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    hardware_vendor: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    cpu_arch: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    os_type: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    os_version: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    accelerator_vendor: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    accelerator_model: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    driver_version: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_by: Mapped[str] = mapped_column(String(64), nullable=False, default="system")
    updated_by: Mapped[str] = mapped_column(String(64), nullable=False, default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
