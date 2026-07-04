export interface InferenceDevice {
  device_id: string
  device_code: string
  name: string
  hostname: string
  ip: string
  status: string
  os_type?: string
  os_version?: string
  accelerator_vendor?: string
  accelerator_model?: string
  accelerator_count?: string
  driver_version?: string
  owner_team?: string
  location?: string
  updated_at?: string
}

export interface EnvironmentSpec {
  spec_id: string
  name: string
  version?: string
  runtime_name?: string
  runtime?: string
  framework?: string
  inference_server?: string
  accelerator_vendor?: string
  accelerator_model?: string
  driver_version?: string
  enabled: boolean
  updated_at?: string
}

export interface ModelDeploymentRequirement {
  requirement_id: string
  model_id: string
  model_name: string
  model_version?: string
  environment_spec_id?: string
  accelerator_vendor?: string
  accelerator_model?: string
  min_accelerator_memory_gb?: string
  status: string
  updated_at?: string
}

export interface EnvironmentImplementation {
  implementation_id: string
  implementation_name?: string
  device_id: string
  environment_spec_id?: string
  requirement_id?: string
  implementation_status: string
  actual_inference_server?: string
  actual_driver_version?: string
  artifact_uri?: string
  updated_at?: string
}

export interface EnvironmentHandover {
  handover_id: string
  handover_no: string
  title: string
  implementation_id?: string
  device_id?: string
  status: string
  test_result: string
  recipient?: string
  target_owner?: string
  accepted_by?: string
  updated_at?: string
}

export interface InferenceListResponse<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}
