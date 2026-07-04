import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import apiClient from '../api/client'
import type { DeliveryBundle, DeliveryBundleBuildJob, DeliveryBundlePayload, DeliveryBundleVersionPayload, DeviceProfile, DeviceProfilePayload, EnvPackage, EnvPackageArchiveTree, EnvPackagePayload, EnvPackageRevision, EnvPackageScriptEditPayload, ListResponse, ManagedDevice, ManagedDevicePayload, PackageWorkspace, ProbeResult, ProbeResultPayload, UserAccount, UserAccountPayload, WorkspaceCommitPayload, WorkspaceContentModel } from '../types/environmentPackage'

export type OperatorUser = Pick<UserAccount, 'username' | 'role'> & { access_token?: string }

export interface AssetFilterParams {
  device_id?: string
  profile_id?: string
  package_type?: string
}


export function operatorHeaders(user?: OperatorUser | null) {
  if (user?.access_token) return { Authorization: `Bearer ${user.access_token}` }
  const username = user?.username || 'zhangsan'
  const role = user?.role || (username === 'admin' ? 'admin' : 'user')
  return { 'x-operator-id': username, 'x-operator-role': role }
}


function encodeWorkspacePath(path: string) {
  return path.split('/').filter(Boolean).map((segment) => encodeURIComponent(segment)).join('/')
}

function isAdmin(user?: OperatorUser | null) {
  return user?.role === 'admin' || user?.username === 'admin'
}

export const envPackageKeys = {
  all: ['environment-packages'] as const,
  loginUsers: () => [...envPackageKeys.all, 'login-users'] as const,
  packages: (user?: OperatorUser | null, filters?: AssetFilterParams) => [...envPackageKeys.all, 'packages', user?.username || 'anonymous', filters?.device_id || '', filters?.profile_id || '', filters?.package_type || ''] as const,
  packageArchiveTree: (packageId?: string, user?: OperatorUser | null) => [...envPackageKeys.all, 'package-archive-tree', packageId || '', user?.username || 'anonymous'] as const,
  packageRevisions: (packageId?: string, user?: OperatorUser | null) => [...envPackageKeys.all, 'package-revisions', packageId || '', user?.username || 'anonymous'] as const,
  packageDetail: (packageId?: string, user?: OperatorUser | null) => [...envPackageKeys.all, 'package-detail', packageId || '', user?.username || 'anonymous'] as const,
  workspaceContent: (packageId?: string, workspaceId?: string, path?: string, user?: OperatorUser | null) => [...envPackageKeys.all, 'workspace-content', packageId || '', workspaceId || '', path || '', user?.username || 'anonymous'] as const,
  profiles: () => [...envPackageKeys.all, 'device-profiles'] as const,
  allProfiles: () => [...envPackageKeys.all, 'all-device-profiles'] as const,
  devices: () => [...envPackageKeys.all, 'devices'] as const,
  deliveryBundles: (user?: OperatorUser | null, filters?: AssetFilterParams) => [...envPackageKeys.all, 'delivery-bundles', user?.username || 'anonymous', filters?.device_id || '', filters?.profile_id || ''] as const,
  deliveryBundle: (bundleId?: string, user?: OperatorUser | null) => [...envPackageKeys.all, 'delivery-bundle', bundleId || '', user?.username || 'anonymous'] as const,
  deliveryBundleBuildJob: (bundleId?: string, user?: OperatorUser | null) => [...envPackageKeys.all, 'delivery-bundle-build-job', bundleId || '', user?.username || 'anonymous'] as const,
  probeResults: (user?: OperatorUser | null) => [...envPackageKeys.all, 'probe-results', user?.username || 'anonymous'] as const,
  adminUsers: () => [...envPackageKeys.all, 'admin-users'] as const,
  adminAssets: () => [...envPackageKeys.all, 'admin-assets'] as const,
}

export function useLoginUsers() {
  return useQuery({
    queryKey: envPackageKeys.loginUsers(),
    queryFn: async () => {
      const { data } = await apiClient.get<ListResponse<UserAccount>>('/users/login-options', { params: { limit: 500 } })
      return data.items ?? []
    },
  })
}

export function useEnvPackages(user?: OperatorUser | null, filters: AssetFilterParams = {}) {
  return useQuery({
    queryKey: envPackageKeys.packages(user, filters),
    queryFn: async () => {
      const { data } = await apiClient.get<ListResponse<EnvPackage>>('/environment-packages/packages', {
        headers: operatorHeaders(user),
        params: { limit: 200, include_shared: true, device_id: filters.device_id || undefined, profile_id: filters.profile_id || undefined, package_type: filters.package_type || undefined },
      })
      return data.items ?? []
    },
  })
}

export function useDeviceProfiles() {
  return useQuery({
    queryKey: envPackageKeys.profiles(),
    queryFn: async () => {
      const { data } = await apiClient.get<ListResponse<DeviceProfile>>('/environment-packages/device-profiles', { params: { enabled: true, limit: 200 } })
      return data.items ?? []
    },
  })
}

export function useAllDeviceProfiles() {
  return useQuery({
    queryKey: envPackageKeys.allProfiles(),
    queryFn: async () => {
      const { data } = await apiClient.get<ListResponse<DeviceProfile>>('/environment-packages/device-profiles', { params: { limit: 200 } })
      return data.items ?? []
    },
  })
}

export function useManagedDevices() {
  return useQuery({
    queryKey: envPackageKeys.devices(),
    queryFn: async () => {
      const { data } = await apiClient.get<ListResponse<ManagedDevice>>('/environment-packages/devices', { params: { limit: 200 } })
      return data.items ?? []
    },
  })
}

export function useCreateDevice(user?: OperatorUser | null) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (payload: ManagedDevicePayload) => (await apiClient.post('/environment-packages/devices', payload, { headers: operatorHeaders(user) })).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: envPackageKeys.devices() }),
  })
}

export function useUpdateDevice(user?: OperatorUser | null) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ deviceId, payload }: { deviceId: string; payload: ManagedDevicePayload }) => (await apiClient.patch(`/environment-packages/devices/${deviceId}`, payload, { headers: operatorHeaders(user) })).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: envPackageKeys.devices() }),
  })
}

export function useCreateProfileFromDevice(user?: OperatorUser | null) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ deviceId, payload }: { deviceId: string; payload?: { profile_code?: string; name?: string; enabled?: boolean } }) => (await apiClient.post(`/environment-packages/devices/${deviceId}/profile`, payload ?? {}, { headers: operatorHeaders(user) })).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: envPackageKeys.profiles() })
      queryClient.invalidateQueries({ queryKey: envPackageKeys.allProfiles() })
    },
  })
}

export function useCreateDeviceProfile(user?: OperatorUser | null) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (payload: DeviceProfilePayload) => (await apiClient.post('/environment-packages/device-profiles', payload, { headers: operatorHeaders(user) })).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: envPackageKeys.profiles() })
      queryClient.invalidateQueries({ queryKey: envPackageKeys.allProfiles() })
    },
  })
}

export function useUpdateDeviceProfile(user?: OperatorUser | null) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ profileId, payload }: { profileId: string; payload: DeviceProfilePayload }) => (await apiClient.patch(`/environment-packages/device-profiles/${profileId}`, payload, { headers: operatorHeaders(user) })).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: envPackageKeys.profiles() })
      queryClient.invalidateQueries({ queryKey: envPackageKeys.allProfiles() })
      queryClient.invalidateQueries({ queryKey: envPackageKeys.adminAssets() })
    },
  })
}

export function useDeleteDeviceProfile(user?: OperatorUser | null) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (profileId: string) => (await apiClient.delete(`/environment-packages/device-profiles/${profileId}`, { headers: operatorHeaders(user) })).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: envPackageKeys.profiles() })
      queryClient.invalidateQueries({ queryKey: envPackageKeys.allProfiles() })
      queryClient.invalidateQueries({ queryKey: envPackageKeys.adminAssets() })
    },
  })
}

export function useCreateEnvPackage(user?: OperatorUser | null) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (payload: EnvPackagePayload) => (await apiClient.post('/environment-packages/packages', payload, { headers: operatorHeaders(user) })).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: envPackageKeys.packages(user) }),
  })
}

export function useUpdateEnvPackage(user?: OperatorUser | null) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ packageId, payload }: { packageId: string; payload: EnvPackagePayload }) => (await apiClient.patch(`/environment-packages/packages/${packageId}`, payload, { headers: operatorHeaders(user) })).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: envPackageKeys.packages(user) }),
  })
}

export function useDeleteEnvPackage(user?: OperatorUser | null) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (packageId: string) => (await apiClient.delete(`/environment-packages/packages/${packageId}`, { headers: operatorHeaders(user) })).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: envPackageKeys.packages(user) }),
  })
}

export function useEnvPackage(packageId?: string, user?: OperatorUser | null) {
  return useQuery({
    queryKey: envPackageKeys.packageDetail(packageId, user),
    enabled: Boolean(packageId),
    queryFn: async () => {
      const { data } = await apiClient.get<{ item: EnvPackage }>(`/environment-packages/packages/${packageId}`, { headers: operatorHeaders(user) })
      return data.item
    },
  })
}

export function useEnvPackageArchiveTree(packageId?: string, user?: OperatorUser | null) {
  return useQuery({
    queryKey: envPackageKeys.packageArchiveTree(packageId, user),
    enabled: Boolean(packageId),
    retry: false,
    queryFn: async () => {
      const { data } = await apiClient.get<{ item: EnvPackageArchiveTree }>(`/environment-packages/packages/${packageId}/archive-tree`, { headers: operatorHeaders(user) })
      return data.item
    },
  })
}

export function useEnvPackageRevisions(packageId?: string, user?: OperatorUser | null) {
  return useQuery({
    queryKey: envPackageKeys.packageRevisions(packageId, user),
    enabled: Boolean(packageId),
    queryFn: async () => {
      const { data } = await apiClient.get<{ items: EnvPackageRevision[] }>(`/environment-packages/packages/${packageId}/revisions`, { headers: operatorHeaders(user) })
      return data.items ?? []
    },
  })
}

export function useEditEnvPackageScripts(user?: OperatorUser | null) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ packageId, payload }: { packageId: string; payload: EnvPackageScriptEditPayload }) => (await apiClient.post(`/environment-packages/packages/${packageId}/script-edit`, payload, { headers: operatorHeaders(user) })).data,
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: envPackageKeys.all })
      queryClient.invalidateQueries({ queryKey: envPackageKeys.packageRevisions(variables.packageId, user) })
    },
  })
}

export function useReplaceEnvPackageFile(user?: OperatorUser | null) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ packageId, formData }: { packageId: string; formData: FormData }) => (await apiClient.post(`/environment-packages/packages/${packageId}/file-replace`, formData, { headers: { ...operatorHeaders(user), 'Content-Type': 'multipart/form-data' } })).data,
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: envPackageKeys.all })
      queryClient.invalidateQueries({ queryKey: envPackageKeys.packageArchiveTree(variables.packageId, user) })
      queryClient.invalidateQueries({ queryKey: envPackageKeys.packageRevisions(variables.packageId, user) })
    },
  })
}

export function useCreatePackageWorkspace(user?: OperatorUser | null) {
  return useMutation({
    mutationFn: async (packageId: string) => (await apiClient.post<{ item: PackageWorkspace }>(`/environment-packages/packages/${packageId}/workspaces`, {}, { headers: operatorHeaders(user) })).data.item,
  })
}

export function useWorkspaceContent(packageId?: string, workspaceId?: string, path = '', user?: OperatorUser | null) {
  return useQuery({
    queryKey: envPackageKeys.workspaceContent(packageId, workspaceId, path, user),
    enabled: Boolean(packageId && workspaceId),
    queryFn: async () => {
      const suffix = path ? `/${encodeWorkspacePath(path)}` : ''
      const { data } = await apiClient.get<{ item: WorkspaceContentModel }>(`/environment-packages/packages/${packageId}/workspaces/${workspaceId}/contents${suffix}`, { headers: operatorHeaders(user) })
      return data.item
    },
  })
}

export function useSaveWorkspaceContent(user?: OperatorUser | null) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ packageId, workspaceId, path, content, format = 'text', type = 'file' }: { packageId: string; workspaceId: string; path: string; content: string; format?: string; type?: string }) => {
      const { data } = await apiClient.put<{ item: WorkspaceContentModel }>(`/environment-packages/packages/${packageId}/workspaces/${workspaceId}/contents/${encodeWorkspacePath(path)}`, { content, format, type }, { headers: operatorHeaders(user) })
      return data.item
    },
    onSuccess: (_data, vars) => queryClient.invalidateQueries({ queryKey: envPackageKeys.workspaceContent(vars.packageId, vars.workspaceId, '', user) }),
  })
}

export function useCreateWorkspaceContent(user?: OperatorUser | null) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ packageId, workspaceId, parentPath, name, type, content = '' }: { packageId: string; workspaceId: string; parentPath: string; name: string; type: 'file' | 'directory'; content?: string }) => {
      const suffix = parentPath ? `/${encodeWorkspacePath(parentPath)}` : ''
      const { data } = await apiClient.post<{ item: WorkspaceContentModel }>(`/environment-packages/packages/${packageId}/workspaces/${workspaceId}/contents${suffix}`, { name, type, content, format: 'text' }, { headers: operatorHeaders(user) })
      return data.item
    },
    onSuccess: (_data, vars) => queryClient.invalidateQueries({ queryKey: envPackageKeys.workspaceContent(vars.packageId, vars.workspaceId, '', user) }),
  })
}

export function useDeleteWorkspaceContent(user?: OperatorUser | null) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ packageId, workspaceId, path }: { packageId: string; workspaceId: string; path: string }) => (await apiClient.delete(`/environment-packages/packages/${packageId}/workspaces/${workspaceId}/contents/${encodeWorkspacePath(path)}`, { headers: operatorHeaders(user) })).data,
    onSuccess: (_data, vars) => queryClient.invalidateQueries({ queryKey: envPackageKeys.workspaceContent(vars.packageId, vars.workspaceId, '', user) }),
  })
}

export function useRenameWorkspaceContent(user?: OperatorUser | null) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ packageId, workspaceId, path, newPath }: { packageId: string; workspaceId: string; path: string; newPath: string }) => (await apiClient.patch(`/environment-packages/packages/${packageId}/workspaces/${workspaceId}/contents/${encodeWorkspacePath(path)}`, { path: newPath }, { headers: operatorHeaders(user) })).data,
    onSuccess: (_data, vars) => queryClient.invalidateQueries({ queryKey: envPackageKeys.workspaceContent(vars.packageId, vars.workspaceId, '', user) }),
  })
}

export function useCommitPackageWorkspace(user?: OperatorUser | null) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ packageId, workspaceId, payload }: { packageId: string; workspaceId: string; payload: WorkspaceCommitPayload }) => (await apiClient.post(`/environment-packages/packages/${packageId}/workspaces/${workspaceId}/commit`, payload, { headers: operatorHeaders(user) })).data,
    onSuccess: (_data, vars) => {
      queryClient.invalidateQueries({ queryKey: envPackageKeys.all })
      queryClient.invalidateQueries({ queryKey: envPackageKeys.packageDetail(vars.packageId, user) })
    },
  })
}

export function useDeliveryBundles(user?: OperatorUser | null, filters: AssetFilterParams = {}) {
  return useQuery({
    queryKey: envPackageKeys.deliveryBundles(user, filters),
    queryFn: async () => {
      const { data } = await apiClient.get<ListResponse<DeliveryBundle>>('/environment-packages/delivery-bundles', {
        headers: operatorHeaders(user),
        params: { limit: 200, device_id: filters.device_id || undefined, profile_id: filters.profile_id || undefined },
      })
      return data.items ?? []
    },
  })
}

export function useDeliveryBundle(bundleId?: string, user?: OperatorUser | null) {
  return useQuery({
    queryKey: envPackageKeys.deliveryBundle(bundleId, user),
    enabled: Boolean(bundleId),
    queryFn: async () => {
      const { data } = await apiClient.get<{ item: DeliveryBundle }>(`/environment-packages/delivery-bundles/${bundleId}`, { headers: operatorHeaders(user) })
      return data.item
    },
  })
}

export function useCreateDeliveryBundle(user?: OperatorUser | null) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (payload: DeliveryBundlePayload) => (await apiClient.post('/environment-packages/delivery-bundles', payload, { headers: operatorHeaders(user) })).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: envPackageKeys.deliveryBundles(user) }),
  })
}

export function useUpdateDeliveryBundle(user?: OperatorUser | null) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ bundleId, payload }: { bundleId: string; payload: DeliveryBundlePayload }) => (await apiClient.patch(`/environment-packages/delivery-bundles/${bundleId}`, payload, { headers: operatorHeaders(user) })).data,
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: envPackageKeys.deliveryBundles(user) })
      queryClient.invalidateQueries({ queryKey: envPackageKeys.deliveryBundle(variables.bundleId, user) })
    },
  })
}

export function useBuildDeliveryBundle(user?: OperatorUser | null) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (bundleId: string) => (await apiClient.post(`/environment-packages/delivery-bundles/${bundleId}/build`, {}, { headers: operatorHeaders(user) })).data,
    onSuccess: (_data, bundleId) => {
      queryClient.invalidateQueries({ queryKey: envPackageKeys.deliveryBundles(user) })
      queryClient.invalidateQueries({ queryKey: envPackageKeys.deliveryBundle(bundleId, user) })
      queryClient.invalidateQueries({ queryKey: envPackageKeys.deliveryBundleBuildJob(bundleId, user) })
    },
  })
}

export function useLatestDeliveryBundleBuildJob(bundleId?: string, user?: OperatorUser | null, enabled = true) {
  return useQuery({
    queryKey: envPackageKeys.deliveryBundleBuildJob(bundleId, user),
    enabled: Boolean(bundleId) && enabled,
    refetchInterval: (query) => {
      const status = query.state.data?.job_status
      return status === 'queued' || status === 'running' ? 1000 : false
    },
    queryFn: async () => {
      const { data } = await apiClient.get<{ item: DeliveryBundleBuildJob | null }>(`/environment-packages/delivery-bundles/${bundleId}/build-jobs/latest`, { headers: operatorHeaders(user) })
      return data.item
    },
  })
}

export function useDeliverDeliveryBundle(user?: OperatorUser | null) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (bundleId: string) => (await apiClient.post(`/environment-packages/delivery-bundles/${bundleId}/deliver`, {}, { headers: operatorHeaders(user) })).data,
    onSuccess: (_data, bundleId) => {
      queryClient.invalidateQueries({ queryKey: envPackageKeys.deliveryBundles(user) })
      queryClient.invalidateQueries({ queryKey: envPackageKeys.deliveryBundle(bundleId, user) })
    },
  })
}

export function useDeleteDeliveryBundle(user?: OperatorUser | null) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (bundleId: string) => (await apiClient.delete(`/environment-packages/delivery-bundles/${bundleId}`, { headers: operatorHeaders(user) })).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: envPackageKeys.deliveryBundles(user) }),
  })
}

export function useCreateDeliveryBundleVersion(user?: OperatorUser | null) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ bundleId, payload }: { bundleId: string; payload: DeliveryBundleVersionPayload }) => (await apiClient.post(`/environment-packages/delivery-bundles/${bundleId}/new-version`, payload, { headers: operatorHeaders(user) })).data,
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: envPackageKeys.deliveryBundles(user) })
      queryClient.invalidateQueries({ queryKey: envPackageKeys.deliveryBundle(variables.bundleId, user) })
    },
  })
}

export function deliveryBundleArtifactUrl(bundleId: string) {
  return `/api/v1/environment-packages/delivery-bundles/${bundleId}/artifact`
}

export function envPackageFileUrl(packageId: string) {
  return `/api/v1/environment-packages/packages/${packageId}/file`
}

export function useProbeResults(user?: OperatorUser | null) {
  return useQuery({
    queryKey: envPackageKeys.probeResults(user),
    queryFn: async () => {
      const { data } = await apiClient.get<ListResponse<ProbeResult>>('/environment-packages/probe-results', { headers: operatorHeaders(user), params: { limit: 200 } })
      return data.items ?? []
    },
  })
}

export function useCreateProbeResult(user?: OperatorUser | null) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (payload: ProbeResultPayload) => (await apiClient.post('/environment-packages/probe-results', payload, { headers: operatorHeaders(user) })).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: envPackageKeys.probeResults(user) }),
  })
}

export function useAdminUsers(user?: OperatorUser | null) {
  return useQuery({
    queryKey: envPackageKeys.adminUsers(),
    enabled: isAdmin(user),
    queryFn: async () => {
      const { data } = await apiClient.get<ListResponse<UserAccount>>('/users', { headers: operatorHeaders(user), params: { limit: 200 } })
      return data.items ?? []
    },
  })
}

export function useCreateUser(user?: OperatorUser | null) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (payload: UserAccountPayload) => (await apiClient.post('/users', payload, { headers: operatorHeaders(user) })).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: envPackageKeys.adminUsers() })
      queryClient.invalidateQueries({ queryKey: envPackageKeys.loginUsers() })
    },
  })
}

export function useUpdateUser(user?: OperatorUser | null) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ userId, payload }: { userId: string; payload: UserAccountPayload }) => (await apiClient.patch(`/users/${userId}`, payload, { headers: operatorHeaders(user) })).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: envPackageKeys.adminUsers() })
      queryClient.invalidateQueries({ queryKey: envPackageKeys.loginUsers() })
      queryClient.invalidateQueries({ queryKey: envPackageKeys.adminAssets() })
    },
  })
}

export function useAdminAssets(user?: OperatorUser | null) {
  return useQuery({
    queryKey: envPackageKeys.adminAssets(),
    enabled: isAdmin(user),
    queryFn: async () => {
      const { data } = await apiClient.get<ListResponse<EnvPackage>>('/environment-packages/admin/assets', { headers: operatorHeaders(user), params: { limit: 200 } })
      return data.items ?? []
    },
  })
}

export function useTransferAsset(user?: OperatorUser | null) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ packageId, targetOwnerId }: { packageId: string; targetOwnerId: string }) => (await apiClient.post(`/environment-packages/admin/assets/${packageId}/transfer`, { target_owner_id: targetOwnerId }, { headers: operatorHeaders(user) })).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: envPackageKeys.adminAssets() })
      queryClient.invalidateQueries({ queryKey: envPackageKeys.packages(user) })
    },
  })
}

export function useShareAsset(user?: OperatorUser | null) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ packageId, shared }: { packageId: string; shared: boolean }) => (await apiClient.post(`/environment-packages/admin/assets/${packageId}/share`, undefined, { headers: operatorHeaders(user), params: { shared } })).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: envPackageKeys.adminAssets() }),
  })
}
