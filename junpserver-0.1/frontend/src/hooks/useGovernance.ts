import { useQuery } from '@tanstack/react-query'
import apiClient from '../api/client'
import type { AuditListResponse, AuditFilters } from '../types/governance'

/**
 * Query key factory for governance
 */
export const governanceKeys = {
  all: ['governance'] as const,
  audits: () => [...governanceKeys.all, 'audits'] as const,
  auditsList: (filters: AuditFilters) => [...governanceKeys.audits(), filters] as const,
}

/**
 * Fetch audit logs with filters
 * Converts time_range to hours parameter for API
 */
export function useAuditLogs(filters: AuditFilters = {}) {
  return useQuery<AuditListResponse>({
    queryKey: governanceKeys.auditsList(filters),
    queryFn: async () => {
      const params: Record<string, unknown> = {}

      if (filters.entity_type) params.entity_type = filters.entity_type
      if (filters.entity_id) params.entity_id = filters.entity_id
      if (filters.action) params.action = filters.action
      if (filters.operator_id) params.operator_id = filters.operator_id
      if (filters.limit) params.limit = filters.limit
      if (filters.offset) params.offset = filters.offset

      // Convert time_range to hours
      if (filters.time_range) {
        const hoursMap: Record<string, number> = {
          '1h': 1,
          '24h': 24,
          '7d': 168,
        }
        params.hours = hoursMap[filters.time_range] || 24
      }

      const { data } = await apiClient.get<AuditListResponse>('/governance/audits', { params })
      return data
    },
    staleTime: 30000, // 30 seconds - audit logs change less frequently
  })
}

/**
 * Fetch audit logs with pagination
 * Returns items and pagination info
 */
export function useAuditLogsPaginated(
  page: number = 1,
  pageSize: number = 20,
  filters: Omit<AuditFilters, 'limit' | 'offset'> = {}
) {
  const offset = (page - 1) * pageSize

  return useQuery<AuditListResponse>({
    queryKey: governanceKeys.auditsList({ ...filters, limit: pageSize, offset }),
    queryFn: async () => {
      const params: Record<string, unknown> = {
        limit: pageSize,
        offset,
      }

      if (filters.entity_type) params.entity_type = filters.entity_type
      if (filters.entity_id) params.entity_id = filters.entity_id
      if (filters.action) params.action = filters.action
      if (filters.operator_id) params.operator_id = filters.operator_id
      if (filters.time_range) {
        const hoursMap: Record<string, number> = {
          '1h': 1,
          '24h': 24,
          '7d': 168,
        }
        params.hours = hoursMap[filters.time_range] || 24
      }

      const { data } = await apiClient.get<AuditListResponse>('/governance/audits', { params })
      return data
    },
    staleTime: 30000,
  })
}