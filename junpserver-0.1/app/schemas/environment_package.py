from __future__ import annotations

from pydantic import BaseModel, Field


class CreateDeviceProfileRequest(BaseModel):
    profile_code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    hardware_vendor: str = Field(default="", max_length=128)
    cpu_arch: str = Field(default="", max_length=64)
    os_type: str = Field(default="", max_length=64)
    os_version: str = Field(default="", max_length=128)
    accelerator_vendor: str = Field(default="", max_length=64)
    accelerator_model: str = Field(default="", max_length=128)
    driver_version: str = Field(default="", max_length=128)
    enabled: bool = True


class UpdateDeviceProfileRequest(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    hardware_vendor: str | None = Field(default=None, max_length=128)
    cpu_arch: str | None = Field(default=None, max_length=64)
    os_type: str | None = Field(default=None, max_length=64)
    os_version: str | None = Field(default=None, max_length=128)
    accelerator_vendor: str | None = Field(default=None, max_length=64)
    accelerator_model: str | None = Field(default=None, max_length=128)
    driver_version: str | None = Field(default=None, max_length=128)
    enabled: bool | None = None


class CreateManagedDeviceRequest(BaseModel):
    device_code: str = Field(min_length=1, max_length=64)
    name: str = Field(default="", max_length=128)
    hostname: str = Field(default="", max_length=255)
    ip: str = Field(default="", max_length=255)
    asset_id: str = Field(default="", max_length=36)
    jms_asset_id: str = Field(default="", max_length=64)
    owner_team: str = Field(default="", max_length=128)
    location: str = Field(default="", max_length=255)
    os_type: str = Field(default="", max_length=64)
    os_version: str = Field(default="", max_length=128)
    cpu_arch: str = Field(default="", max_length=64)
    cpu_model: str = Field(default="", max_length=255)
    memory_gb: str = Field(default="", max_length=32)
    storage_summary: str = Field(default="", max_length=512)
    accelerator_vendor: str = Field(default="", max_length=64)
    accelerator_model: str = Field(default="", max_length=128)
    accelerator_count: str = Field(default="", max_length=32)
    accelerator_memory_gb: str = Field(default="", max_length=32)
    driver_version: str = Field(default="", max_length=128)
    firmware_version: str = Field(default="", max_length=128)
    status: str = Field(default="active", max_length=32)
    notes: str = Field(default="", max_length=2048)


class UpdateManagedDeviceRequest(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    hostname: str | None = Field(default=None, max_length=255)
    ip: str | None = Field(default=None, max_length=255)
    asset_id: str | None = Field(default=None, max_length=36)
    jms_asset_id: str | None = Field(default=None, max_length=64)
    owner_team: str | None = Field(default=None, max_length=128)
    location: str | None = Field(default=None, max_length=255)
    os_type: str | None = Field(default=None, max_length=64)
    os_version: str | None = Field(default=None, max_length=128)
    cpu_arch: str | None = Field(default=None, max_length=64)
    cpu_model: str | None = Field(default=None, max_length=255)
    memory_gb: str | None = Field(default=None, max_length=32)
    storage_summary: str | None = Field(default=None, max_length=512)
    accelerator_vendor: str | None = Field(default=None, max_length=64)
    accelerator_model: str | None = Field(default=None, max_length=128)
    accelerator_count: str | None = Field(default=None, max_length=32)
    accelerator_memory_gb: str | None = Field(default=None, max_length=32)
    driver_version: str | None = Field(default=None, max_length=128)
    firmware_version: str | None = Field(default=None, max_length=128)
    status: str | None = Field(default=None, max_length=32)
    notes: str | None = Field(default=None, max_length=2048)


class CreateProfileFromDeviceRequest(BaseModel):
    profile_code: str = Field(default="", max_length=64)
    name: str = Field(default="", max_length=128)
    enabled: bool = True


class CreateEnvPackageRequest(BaseModel):
    package_code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    package_type: str = Field(default="custom", max_length=64)
    version: str = Field(min_length=1, max_length=128)
    file_uri: str = Field(default="", max_length=1024)
    file_name: str = Field(default="", max_length=255)
    checksum_type: str = Field(default="sha256", max_length=32)
    checksum: str = Field(default="", max_length=255)
    check_script: str = Field(default="")
    install_script: str = Field(default="")
    verify_script: str = Field(default="")
    uninstall_script: str = Field(default="")
    depends_on: str = Field(default="")
    install_order: int = Field(default=100, ge=0)
    requires_root: bool = False
    requires_reboot: bool = False
    offline_supported: bool = True
    status: str = Field(default="draft", max_length=32)
    visibility: str = Field(default="private", max_length=32)
    device_profile_ids: list[str] = Field(default_factory=list)


class UpdateEnvPackageRequest(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    package_type: str | None = Field(default=None, max_length=64)
    version: str | None = Field(default=None, max_length=128)
    file_uri: str | None = Field(default=None, max_length=1024)
    file_name: str | None = Field(default=None, max_length=255)
    checksum_type: str | None = Field(default=None, max_length=32)
    checksum: str | None = Field(default=None, max_length=255)
    check_script: str | None = None
    install_script: str | None = None
    verify_script: str | None = None
    uninstall_script: str | None = None
    depends_on: str | None = None
    install_order: int | None = Field(default=None, ge=0)
    requires_root: bool | None = None
    requires_reboot: bool | None = None
    offline_supported: bool | None = None
    status: str | None = Field(default=None, max_length=32)
    visibility: str | None = Field(default=None, max_length=32)
    device_profile_ids: list[str] | None = None


class EditEnvPackageScriptsRequest(BaseModel):
    install_script: str = Field(default="")
    verify_script: str = Field(default="")
    uninstall_script: str = Field(default="")
    save_mode: str = Field(default="in_place", max_length=32)
    new_version: str = Field(default="", max_length=128)
    remark: str = Field(default="", max_length=2048)


class ReplaceEnvPackageFileRequest(BaseModel):
    target_path: str = Field(min_length=1, max_length=1024)
    save_mode: str = Field(default="in_place", max_length=32)
    new_version: str = Field(default="", max_length=128)
    remark: str = Field(default="", max_length=2048)


class WorkspaceContentSaveRequest(BaseModel):
    content: str = Field(default="")
    format: str = Field(default="text", max_length=32)
    type: str = Field(default="file", max_length=32)


class WorkspaceContentCreateRequest(BaseModel):
    type: str = Field(default="file", max_length=32)
    name: str = Field(default="", max_length=255)
    content: str = Field(default="")
    format: str = Field(default="text", max_length=32)


class WorkspaceContentRenameRequest(BaseModel):
    path: str = Field(min_length=1, max_length=1024)


class CommitPackageWorkspaceRequest(BaseModel):
    save_mode: str = Field(default="in_place", max_length=32)
    new_version: str = Field(default="", max_length=128)
    remark: str = Field(default="", max_length=2048)


class SetPackageCompatibilitiesRequest(BaseModel):
    device_profile_ids: list[str] = Field(default_factory=list)


class TransferAssetRequest(BaseModel):
    target_owner_id: str = Field(min_length=1, max_length=64)


class CreateDeliveryBundleRequest(BaseModel):
    bundle_code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    version: str = Field(default="1.0.0", max_length=128)
    bundle_type: str = Field(default="first_install", max_length=32)
    target_device_id: str = Field(default="", max_length=36)
    target_profile_id: str = Field(default="", max_length=36)
    package_ids: list[str] = Field(default_factory=list, min_length=1)


class UpdateDeliveryBundleRequest(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    version: str | None = Field(default=None, max_length=128)
    bundle_type: str | None = Field(default=None, max_length=32)
    target_device_id: str | None = Field(default=None, max_length=36)
    target_profile_id: str | None = Field(default=None, max_length=36)
    package_ids: list[str] | None = None


class CreateDeliveryBundleVersionRequest(BaseModel):
    bundle_code: str = Field(min_length=1, max_length=64)
    version: str = Field(min_length=1, max_length=128)
    name: str | None = Field(default=None, max_length=128)


class CreateProbeResultRequest(BaseModel):
    result_code: str = Field(min_length=1, max_length=64)
    name: str = Field(default="", max_length=128)
    device_id: str = Field(default="", max_length=36)
    raw_json: str = Field(min_length=1)
    reason: str = Field(default="", max_length=1024)
