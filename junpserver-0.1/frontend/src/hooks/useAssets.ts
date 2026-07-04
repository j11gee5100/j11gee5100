import { useQuery } from '@tanstack/react-query'
import apiClient from '../api/client'
import type { Asset, AssetListResponse } from '../types/task'

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