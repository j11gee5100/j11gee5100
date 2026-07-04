import { useQuery } from '@tanstack/react-query'
import apiClient from '../api/client'
import type { SystemUser, SystemUserListResponse } from '../types/task'

/**
 * 查询资产可用的系统用户列表
 * GET /api/v1/assets/{asset_id}/system-users
 * @param assetId 资产ID，为空时不发起请求
 */
export function useSystemUsersByAsset(assetId: string | undefined) {
  return useQuery<SystemUser[]>({
    queryKey: ['assets', assetId, 'system-users'],
    queryFn: async () => {
      if (!assetId) {
        return []
      }
      const { data } = await apiClient.get<SystemUserListResponse>(
        `/assets/${assetId}/system-users`
      )
      return data.system_users ?? []
    },
    // 仅当 assetId 有效时发起请求
    enabled: !!assetId,
    staleTime: 60000, // 60秒内数据视为新鲜
  })
}