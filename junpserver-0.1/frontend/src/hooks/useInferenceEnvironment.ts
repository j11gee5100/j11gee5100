import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import apiClient from '../api/client'
import type {
  EnvironmentHandover,
  EnvironmentImplementation,
  EnvironmentSpec,
  InferenceDevice,
  InferenceListResponse,
  ModelDeploymentRequirement,
} from '../types/inferenceEnvironment'

const base = '/inference-environments'

export const inferenceEnvironmentKeys = {
  all: ['inference-environments'] as const,
  devices: () => [...inferenceEnvironmentKeys.all, 'devices'] as const,
  specs: () => [...inferenceEnvironmentKeys.all, 'specs'] as const,
  requirements: () => [...inferenceEnvironmentKeys.all, 'requirements'] as const,
  implementations: () => [...inferenceEnvironmentKeys.all, 'implementations'] as const,
  handovers: () => [...inferenceEnvironmentKeys.all, 'handovers'] as const,
}

async function list<T>(path: string): Promise<T[]> {
  const { data } = await apiClient.get<InferenceListResponse<T>>(path, { params: { limit: 100 } })
  return data.items ?? []
}

export function useInferenceDevices() {
  return useQuery({ queryKey: inferenceEnvironmentKeys.devices(), queryFn: () => list<InferenceDevice>(`${base}/devices`) })
}

export function useEnvironmentSpecs() {
  return useQuery({ queryKey: inferenceEnvironmentKeys.specs(), queryFn: () => list<EnvironmentSpec>(`${base}/specs`) })
}

export function useModelDeploymentRequirements() {
  return useQuery({ queryKey: inferenceEnvironmentKeys.requirements(), queryFn: () => list<ModelDeploymentRequirement>(`${base}/deployment-requirements`) })
}

export function useEnvironmentImplementations() {
  return useQuery({ queryKey: inferenceEnvironmentKeys.implementations(), queryFn: () => list<EnvironmentImplementation>(`${base}/implementations`) })
}

export function useEnvironmentHandovers() {
  return useQuery({ queryKey: inferenceEnvironmentKeys.handovers(), queryFn: () => list<EnvironmentHandover>(`${base}/handovers`) })
}

export function useCreateInferenceDevice() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (payload: Partial<InferenceDevice>) => (await apiClient.post(`${base}/devices`, payload)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: inferenceEnvironmentKeys.devices() }),
  })
}

export function useCreateEnvironmentSpec() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (payload: Partial<EnvironmentSpec>) => (await apiClient.post(`${base}/specs`, payload)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: inferenceEnvironmentKeys.specs() }),
  })
}

export function useCreateModelDeploymentRequirement() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (payload: Partial<ModelDeploymentRequirement>) => (await apiClient.post(`${base}/deployment-requirements`, payload)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: inferenceEnvironmentKeys.requirements() }),
  })
}

export function useCreateEnvironmentImplementation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (payload: Partial<EnvironmentImplementation>) => (await apiClient.post(`${base}/implementations`, payload)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: inferenceEnvironmentKeys.implementations() }),
  })
}

export function useCreateEnvironmentHandover() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (payload: Partial<EnvironmentHandover>) => (await apiClient.post(`${base}/handovers`, payload)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: inferenceEnvironmentKeys.handovers() }),
  })
}
