from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class EnvPackage(Base):
    __tablename__ = "env_package"
    __table_args__ = (UniqueConstraint("package_code", "version", "owner_id", name="uq_env_package_code_version_owner"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    package_code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    package_type: Mapped[str] = mapped_column(String(64), nullable=False, default="custom")
    version: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    file_uri: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    file_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    checksum_type: Mapped[str] = mapped_column(String(32), nullable=False, default="sha256")
    checksum: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    check_script: Mapped[str] = mapped_column(Text, nullable=False, default="")
    install_script: Mapped[str] = mapped_column(Text, nullable=False, default="")
    verify_script: Mapped[str] = mapped_column(Text, nullable=False, default="")
    uninstall_script: Mapped[str] = mapped_column(Text, nullable=False, default="")
    depends_on: Mapped[str] = mapped_column(Text, nullable=False, default="")
    install_order: Mapped[int] = mapped_column(Integer, nullable=False, default=100, server_default="100")
    requires_root: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    requires_reboot: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    offline_supported: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    visibility: Mapped[str] = mapped_column(String(32), nullable=False, default="private")
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    created_by: Mapped[str] = mapped_column(String(64), nullable=False, default="system")
    updated_by: Mapped[str] = mapped_column(String(64), nullable=False, default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class EnvPackageRevision(Base):
    __tablename__ = "env_package_revision"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    package_id: Mapped[str] = mapped_column(String(36), nullable=False)
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    operation_type: Mapped[str] = mapped_column(String(32), nullable=False, default="script_edit", server_default="script_edit")
    save_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="in_place", server_default="in_place")
    old_file_uri: Mapped[str] = mapped_column(String(1024), nullable=False, default="", server_default="")
    new_file_uri: Mapped[str] = mapped_column(String(1024), nullable=False, default="", server_default="")
    old_checksum: Mapped[str] = mapped_column(String(255), nullable=False, default="", server_default="")
    new_checksum: Mapped[str] = mapped_column(String(255), nullable=False, default="", server_default="")
    changed_files: Mapped[str] = mapped_column(Text, nullable=False, default="")
    script_diff_json: Mapped[str] = mapped_column(Text, nullable=False, default="")
    remark: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_by: Mapped[str] = mapped_column(String(64), nullable=False, default="system", server_default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class EnvPackageCompatibility(Base):
    __tablename__ = "env_package_compatibility"
    __table_args__ = (UniqueConstraint("package_id", "device_profile_id", name="uq_env_package_profile"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    package_id: Mapped[str] = mapped_column(String(36), nullable=False)
    device_profile_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class DeliveryBundle(Base):
    __tablename__ = "delivery_bundle"
    __table_args__ = (UniqueConstraint("bundle_code", "owner_id", name="uq_delivery_bundle_code_owner"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    bundle_code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    version: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    bundle_type: Mapped[str] = mapped_column(String(32), nullable=False, default="first_install", server_default="first_install")
    target_device_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    target_profile_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    lifecycle_status: Mapped[str] = mapped_column(String(32), nullable=False, default="making", server_default="making")
    delivered_by: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    parent_bundle_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    manifest_json: Mapped[str] = mapped_column(Text, nullable=False, default="")
    build_status: Mapped[str] = mapped_column(String(32), nullable=False, default="not_built", server_default="not_built")
    artifact_uri: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    artifact_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    artifact_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    artifact_checksum: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    build_log: Mapped[str] = mapped_column(Text, nullable=False, default="")
    built_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    created_by: Mapped[str] = mapped_column(String(64), nullable=False, default="system")
    updated_by: Mapped[str] = mapped_column(String(64), nullable=False, default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class DeliveryBundleBuildJob(Base):
    __tablename__ = "delivery_bundle_build_job"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    bundle_id: Mapped[str] = mapped_column(String(36), nullable=False)
    job_status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued", server_default="queued")
    progress_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    current_step: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    current_message: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    log_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    artifact_uri: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    artifact_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    artifact_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    artifact_checksum: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False, default="system", server_default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class DeliveryBundleItem(Base):
    __tablename__ = "delivery_bundle_item"
    __table_args__ = (UniqueConstraint("bundle_id", "package_id", name="uq_delivery_bundle_package"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    bundle_id: Mapped[str] = mapped_column(String(36), nullable=False)
    package_id: Mapped[str] = mapped_column(String(36), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=100, server_default="100")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ProbeResult(Base):
    __tablename__ = "probe_result"
    __table_args__ = (UniqueConstraint("result_code", "owner_id", name="uq_probe_result_code_owner"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    result_code: Mapped[str] = mapped_column(String(64), nullable=False)
    device_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    raw_json: Mapped[str] = mapped_column(Text, nullable=False, default="")
    os_type: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    os_version: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    cpu_arch: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    accelerator_vendor: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    accelerator_model: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    driver_version: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    created_by: Mapped[str] = mapped_column(String(64), nullable=False, default="system")
    updated_by: Mapped[str] = mapped_column(String(64), nullable=False, default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
