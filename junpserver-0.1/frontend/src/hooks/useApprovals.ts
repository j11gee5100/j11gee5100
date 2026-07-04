import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import apiClient from '../api/client'
import type {
  Approval,
  ApproveRequest,
  RejectRequest,
  EscalateRequest,
} from '../types/approval'

/**
 * Query key factory for approvals
 * 使用 TanStack Query 的最佳实践模式
 */
export const approvalKeys = {
  /** 所有审批的基础 key */
  all: ['approvals'] as const,
  /** 待审批列表 key */
  pending: () => [...approvalKeys.all, 'pending'] as const,
  /** 按层级筛选的待审批列表 key */
  pendingByLevel: (level: number) => [...approvalKeys.pending(), { current_level: level }] as const,
  /** 详情列表 key */
  details: () => [...approvalKeys.all, 'detail'] as const,
  /** 单个审批详情 key */
  detail: (id: string) => [...approvalKeys.details(), id] as const,
}

/**
 * 获取指定层级的待审批列表
 * @param level - 审批层级（1 或 2）
 * @returns Approval 数组
 */
export function useApprovals(level: number) {
  return useQuery<Approval[]>({
    queryKey: approvalKeys.pendingByLevel(level),
    queryFn: async () => {
      const { data } = await apiClient.get<Approval[]>('/approvals/pending', {
        params: { current_level: level },
      })
      return data
    },
    staleTime: 30000, // 30 秒
  })
}

/**
 * 获取审批详情（含时间线）
 * @param approvalId - 审批单 ID
 * @returns Approval 对象
 */
export function useApprovalDetail(approvalId: string) {
  return useQuery<Approval>({
    queryKey: approvalKeys.detail(approvalId),
    queryFn: async () => {
      const { data } = await apiClient.get<Approval>(`/approvals/${approvalId}`)
      return data
    },
    staleTime: 10000, // 10 秒，详情变更频繁
  })
}

/**
 * 通过审批 mutation
 * 成功后 invalidate pending 和 detail queries
 */
export function useApprove() {
  const queryClient = useQueryClient()

  return useMutation<Approval, Error, { approvalId: string; comment?: string }>({
    mutationFn: async ({ approvalId, comment }) => {
      const { data } = await apiClient.post<Approval>(
        `/approvals/${approvalId}/approve`,
        { comment } as ApproveRequest
      )
      return data
    },
    onSuccess: (_, variables) => {
      // 刷新待审批列表
      queryClient.invalidateQueries({ queryKey: approvalKeys.pending() })
      // 刷新该审批详情
      queryClient.invalidateQueries({ queryKey: approvalKeys.detail(variables.approvalId) })
    },
  })
}

/**
 * 驳回审批 mutation
 * 驳回原因必填
 */
export function useReject() {
  const queryClient = useQueryClient()

  return useMutation<Approval, Error, { approvalId: string; comment: string }>({
    mutationFn: async ({ approvalId, comment }) => {
      const { data } = await apiClient.post<Approval>(
        `/approvals/${approvalId}/reject`,
        { comment } as RejectRequest
      )
      return data
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: approvalKeys.pending() })
      queryClient.invalidateQueries({ queryKey: approvalKeys.detail(variables.approvalId) })
    },
  })
}

/**
 * 升级审批 mutation
 */
export function useEscalate() {
  const queryClient = useQueryClient()

  return useMutation<Approval, Error, { approvalId: string; comment?: string }>({
    mutationFn: async ({ approvalId, comment }) => {
      const { data } = await apiClient.post<Approval>(
        `/approvals/${approvalId}/escalate`,
        { comment } as EscalateRequest
      )
      return data
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: approvalKeys.pending() })
      queryClient.invalidateQueries({ queryKey: approvalKeys.detail(variables.approvalId) })
    },
  })
}