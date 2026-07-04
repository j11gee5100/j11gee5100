export interface DeviceProfile {
  profile_id: string
  profile_code: string
  name: string
  label: string
  hardware_vendor: string
  cpu_arch: string
  os_type: string
  os_version: string
  accelerator_vendor: string
  accelerator_model: string
  driver_version: string
  password_configured?: boolean
  last_login_at?: string
  password_changed_at?: string
  enabled: boolean
}

export type DeviceProfilePayload = Partial<Omit<DeviceProfile, 'profile_id' | 'label'>>

export interface ManagedDevice {
  device_id: string
  device_code: string
  name: string
  hostname: string
  ip: string
  asset_id: string
  jms_asset_id: string
  owner_team: string
  location: string
  os_type: string
  os_version: string
  cpu_arch: string
  cpu_model: string
  memory_gb: string
  storage_summary: string
  accelerator_vendor: string
  accelerator_model: string
  accelerator_count: string
  accelerator_memory_gb: string
  driver_version: string
  firmware_version: string
  status: string
  notes: string
}

export type ManagedDevicePayload = Partial<Omit<ManagedDevice, 'device_id'>>

export interface EnvPackage {
  package_id: string
  package_code: string
  name: string
  package_type: string
  version: string
  file_uri: string
  file_name: string
  checksum_type: string
  checksum: string
  check_script: string
  install_script: string
  verify_script: string
  uninstall_script: string
  depends_on: string
  install_order: number
  requires_root: boolean
  requires_reboot: boolean
  offline_supported: boolean
  status: string
  visibility: string
  owner_id: string
  quality_status: string
  device_profiles: DeviceProfile[]
  created_at?: string
  updated_at?: string
}

export interface EnvPackageArchiveItem {
  path: string
  name: string
  size: number
  is_dir: boolean
  mtime: number
  highlight?: boolean
}

export interface EnvPackageArchiveTree {
  archive_type: string
  file_name: string
  items: EnvPackageArchiveItem[]
  warnings: string[]
}

export interface EnvPackageRevision {
  revision_id: string
  package_id: string
  revision_no: number
  operation_type: string
  save_mode: string
  old_file_uri: string
  new_file_uri: string
  old_checksum: string
  new_checksum: string
  changed_files: string[]
  script_diff: Record<string, string>
  remark: string
  created_by: string
  created_at?: string
}

export interface EnvPackageScriptEditPayload {
  install_script: string
  verify_script: string
  uninstall_script: string
  save_mode: 'in_place' | 'new_version'
  new_version?: string
  remark?: string
}

export interface UserAccount {
  user_id: string
  username: string
  display_name: string
  role: string
  enabled: boolean
}

export type UserAccountPayload = Partial<Omit<UserAccount, 'user_id'>> & { password?: string }

export interface PackageWorkspace {
  workspace_id: string
  package_id: string
  root: string
  meta: Record<string, unknown>
}

export interface WorkspaceContentModel {
  name: string
  path: string
  type: 'file' | 'directory'
  writable: boolean
  size?: number
  content?: string | WorkspaceContentModel[] | null
  format?: string | null
  mimetype?: string | null
}

export interface WorkspaceCommitPayload {
  save_mode: 'in_place' | 'new_version'
  new_version?: string
  remark?: string
}

export interface DeliveryBundle {
  bundle_id: string
  bundle_code: string
  name: string
  version: string
  target_device_id: string
  target_profile_id: string
  bundle_type: string
  lifecycle_status: string
  delivered_by: string
  delivered_at?: string
  parent_bundle_id: string
  status: string
  build_status: string
  artifact_uri: string
  artifact_name: string
  artifact_size: number
  artifact_checksum: string
  build_log: string
  built_at?: string
  owner_id: string
  package_ids: string[]
  manifest: {
    steps?: Array<{
      order?: number
      step?: number
      package_code?: string
      name?: string
      version?: string
      package_type?: string
      path?: string
      execution_mode?: string
      manual_install?: boolean
      manual_reason?: string
      manual_package_path?: string
      manual_payload_path?: string
      manual_install_command?: string
      manual_verify_command?: string
      display_install_command?: string
      display_verify_command?: string
      manual_notes?: string[]
      [key: string]: unknown
    }>
    application_resources?: Array<{
      order?: number
      package_code?: string
      name?: string
      version?: string
      package_type?: string
      path?: string
      execution_mode?: string
      resource_only?: boolean
      manual_reason?: string
      manual_notes?: string[]
      [key: string]: unknown
    }>
    target?: Record<string, unknown>
    [key: string]: unknown
  }
  updated_at?: string
}

export interface DeliveryBundlePayload {
  bundle_code?: string
  name?: string
  version?: string
  target_device_id?: string
  target_profile_id?: string
  bundle_type?: string
  package_ids: string[]
}

export interface DeliveryBundleBuildJob {
  job_id: string
  bundle_id: string
  job_status: string
  progress_percent: number
  current_step: string
  current_message: string
  log_text: string
  artifact_uri: string
  artifact_name: string
  artifact_size: number
  artifact_checksum: string
  started_at?: string
  finished_at?: string
  created_by: string
}

export interface DeliveryBundleVersionPayload {
  bundle_code: string
  version: string
  name?: string
}

export interface ProbeResult {
  result_id: string
  result_code: string
  device_id: string
  name: string
  raw_json: string
  os_type: string
  os_version: string
  cpu_arch: string
  accelerator_vendor: string
  accelerator_model: string
  driver_version: string
  owner_id: string
  updated_at?: string
}

export interface ProbeResultPayload {
  result_code: string
  name?: string
  device_id?: string
  raw_json: string
}

export interface ListResponse<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}

export type EnvPackagePayload = Partial<EnvPackage> & { device_profile_ids?: string[] }
