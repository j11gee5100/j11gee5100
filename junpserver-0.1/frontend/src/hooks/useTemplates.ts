import { useQuery, useMutation, useInfiniteQuery, useQueryClient } from '@tanstack/react-query'
import apiClient from '../api/client'
import type {
  Template,
  TemplateListResponse,
  TemplateCreateRequest,
  TemplateUpdateRequest
} from '../types/template'

/**
 * Query key factory for templates
 */
export const templateKeys = {
  all: ['templates'] as const,
  lists: () => [...templateKeys.all, 'list'] as const,
  list: (filters: Record<string, unknown>) => [...templateKeys.lists(), filters] as const,
  details: () => [...templateKeys.all, 'detail'] as const,
  detail: (id: string) => [...templateKeys.details(), id] as const,
}

/**
 * Fetch all command templates
 * Note: API returns paginated response { items, total, limit, offset }
 */
export function useTemplates() {
  return useQuery<Template[]>({
    queryKey: templateKeys.lists(),
    queryFn: async () => {
      const { data } = await apiClient.get<TemplateListResponse>('/templates/commands')
      // API returns paginated format, extract items array
      return data.items ?? []
    },
    staleTime: 60000, // 60 seconds
  })
}

/**
 * Infinite scroll for templates
 * Loads 20 templates per page
 */
export function useTemplatesInfinite(pageSize: number = 20) {
  return useInfiniteQuery<TemplateListResponse>({
    queryKey: templateKeys.list({ pageSize }),
    queryFn: async ({ pageParam = 1 }) => {
      const { data } = await apiClient.get<TemplateListResponse>('/templates/commands', {
        params: {
          page: pageParam,
          page_size: pageSize,
        },
      })
      return data
    },
    initialPageParam: 1,
    getNextPageParam: (lastPage) => {
      const totalPages = Math.ceil(lastPage.total / lastPage.page_size)
      return lastPage.page < totalPages ? lastPage.page + 1 : undefined
    },
  })
}

/**
 * Create a new command template
 */
export function useCreateTemplate() {
  const queryClient = useQueryClient()

  return useMutation<Template, Error, TemplateCreateRequest>({
    mutationFn: async (payload: TemplateCreateRequest) => {
      const { data } = await apiClient.post<Template>('/templates/commands', payload)
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: templateKeys.lists() })
    },
  })
}

/**
 * Update an existing command template
 * Also handles enable/disable via partial update
 */
export function useUpdateTemplate() {
  const queryClient = useQueryClient()

  return useMutation<Template, Error, { templateId: string; payload: TemplateUpdateRequest }>({
    mutationFn: async ({ templateId, payload }) => {
      const { data } = await apiClient.patch<Template>(
        `/templates/commands/${templateId}`,
        payload
      )
      return data
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: templateKeys.lists() })
      queryClient.invalidateQueries({ queryKey: templateKeys.detail(variables.templateId) })
    },
  })
}

/**
 * Delete an existing command template (hard delete)
 */
export function useDeleteTemplate() {
  const queryClient = useQueryClient()

  return useMutation<void, Error, { templateId: string }>({
    mutationFn: async ({ templateId }) => {
      await apiClient.delete(`/templates/commands/${templateId}`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: templateKeys.lists() })
    },
  })
}