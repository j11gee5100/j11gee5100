import { useMutation, useQuery } from '@tanstack/react-query'
import apiClient from '../api/client'
import type {
  Task,
  TaskCreateRequest,
  TaskCreateResponse,
  Asset,
  AssetListResponse,
} from '../types/task'

/**
 * Query key factory for tasks
 */
export const taskKeys = {
  all: ['tasks'] as const,
  lists: () => [...taskKeys.all, 'list'] as const,
  list: (filters: Record<string, unknown>) => [...taskKeys.lists(), filters] as const,
  details: () => [...taskKeys.all, 'detail'] as const,
  detail: (id: string) => [...taskKeys.details(), id] as const,
}

/**
 * 创建任务
 * POST /api/v1/tasks
 */
export function useCreateTask() {
  return useMutation<TaskCreateResponse, Error, TaskCreateRequest>({
    mutationFn: async (payload: TaskCreateRequest) => {
      const { data } = await apiClient.post<TaskCreateResponse>('/tasks', payload)
      return data
    },
    // 成功时不 invalidate，因为会跳转到其他页面
  })
}

/**
 * 查询任务详情
 * GET /api/v1/tasks/{task_id}
 */
export function useTask(taskId: string) {
  return useQuery<Task>({
    queryKey: taskKeys.detail(taskId),
    queryFn: async () => {
      const { data } = await apiClient.get<Task>(`/tasks/${taskId}`)
      return data
    },
    enabled: !!taskId,
  })
}

/**
 * 查询资产列表
 * GET /api/v1/assets
 */
export function useAssets() {
  return useQuery<Asset[]>({
    queryKey: ['assets'],
    queryFn: async () => {
      const { data } = await apiClient.get<AssetListResponse>('/assets', {
        params: {
          limit: 500,
        },
      })
      // 兼容两种响应格式：items 数组或直接数组
      return data.items ?? (data as unknown as Asset[])
    },
    staleTime: 60000, // 60秒内数据视为新鲜
  })
}