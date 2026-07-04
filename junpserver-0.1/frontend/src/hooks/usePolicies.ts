import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import apiClient from '../api/client'
import type {
  BlacklistRule,
  BlacklistListResponse,
  BlacklistCreateRequest,
  BlacklistUpdateRequest,
  PolicyEvaluationRequest,
  PolicyEvaluationResponse,
} from '../types/policy'

/**
 * Query key factory for policies
 */
export const policyKeys = {
  all: ['policies'] as const,
  blacklist: () => [...policyKeys.all, 'blacklist'] as const,
  blacklistList: (filters: Record<string, unknown>) => [...policyKeys.blacklist(), filters] as const,
  evaluate: () => [...policyKeys.all, 'evaluate'] as const,
}

/**
 * Fetch all blacklist rules
 */
export function useBlacklist() {
  return useQuery<BlacklistRule[]>({
    queryKey: policyKeys.blacklist(),
    queryFn: async () => {
      const { data } = await apiClient.get<BlacklistRule[] | BlacklistListResponse>('/policies/command-blacklist')
      // 兼容两种响应格式：数组或分页对象
      if (Array.isArray(data)) {
        return data
      }
      // 如果是分页格式，提取 items
      return (data as BlacklistListResponse).items ?? []
    },
    staleTime: 60000, // 60 seconds
  })
}

/**
 * Paginated blacklist rules
 */
export function useBlacklistPaginated(page: number = 1, pageSize: number = 20) {
  return useQuery<BlacklistListResponse>({
    queryKey: policyKeys.blacklistList({ page, pageSize }),
    queryFn: async () => {
      const { data } = await apiClient.get<BlacklistListResponse>('/policies/command-blacklist', {
        params: {
          page,
          page_size: pageSize,
        },
      })
      return data
    },
    staleTime: 60000,
  })
}

/**
 * Evaluate policy for a command
 * Returns whether the command would be blocked and risk determination
 */
export function useEvaluatePolicy() {
  return useMutation<PolicyEvaluationResponse, Error, PolicyEvaluationRequest>({
    mutationFn: async (payload: PolicyEvaluationRequest) => {
      const { data } = await apiClient.post<PolicyEvaluationResponse>(
        '/policies/evaluate',
        payload
      )
      return data
    },
  })
}

/**
 * Create a new blacklist rule
 */
export function useCreateBlacklistRule() {
  const queryClient = useQueryClient()

  return useMutation<BlacklistRule, Error, BlacklistCreateRequest>({
    mutationFn: async (payload: BlacklistCreateRequest) => {
      const { data } = await apiClient.post<BlacklistRule>('/policies/command-blacklist', payload)
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: policyKeys.blacklist() })
    },
  })
}

/**
 * Update an existing blacklist rule
 */
export function useUpdateBlacklistRule() {
  const queryClient = useQueryClient()

  return useMutation<BlacklistRule, Error, { ruleId: string; payload: BlacklistUpdateRequest }>({
    mutationFn: async ({ ruleId, payload }) => {
      const { data } = await apiClient.patch<BlacklistRule>(
        `/policies/command-blacklist/${ruleId}`,
        payload
      )
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: policyKeys.blacklist() })
    },
  })
}