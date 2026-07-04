import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import {
  approvalKeys,
  useApprovals,
  useApprovalDetail,
  useApprove,
  useReject,
  useEscalate,
} from './useApprovals'
import type { Approval } from '../types/approval'

// Mock apiClient
vi.mock('../api/client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}))

import apiClient from '../api/client'

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  })
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
}

describe('useApprovals hooks', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('approvalKeys query key factory', () => {
    it('should define all base key', () => {
      expect(approvalKeys.all).toEqual(['approvals'])
    })

    it('should define pending key', () => {
      expect(approvalKeys.pending()).toEqual(['approvals', 'pending'])
    })

    it('should define pendingByLevel key with level', () => {
      expect(approvalKeys.pendingByLevel(1)).toEqual(['approvals', 'pending', { current_level: 1 }])
    })

    it('should define detail key with id', () => {
      expect(approvalKeys.detail('test-id')).toEqual(['approvals', 'detail', 'test-id'])
    })
  })

  describe('useApprovals', () => {
    it('should fetch pending approvals by level', async () => {
      const mockApprovals: Approval[] = [
        {
          approval_id: 'approval-1',
          task_id: 'task-1',
          status: 'pending',
          current_level: 1,
          max_level: 2,
          escalation_count: 0,
          source: 'api',
          risk_level: 'readonly',
          created_at: '2026-04-08T00:00:00Z',
        },
      ]

      vi.mocked(apiClient.get).mockResolvedValueOnce({ data: mockApprovals })

      const { result } = renderHook(() => useApprovals(1), {
        wrapper: createWrapper(),
      })

      await waitFor(() => expect(result.current.isSuccess).toBe(true))

      expect(apiClient.get).toHaveBeenCalledWith('/approvals/pending', {
        params: { current_level: 1 },
      })
      expect(result.current.data).toEqual(mockApprovals)
    })
  })

  describe('useApprovalDetail', () => {
    it('should fetch approval detail by id', async () => {
      const mockApproval: Approval = {
        approval_id: 'approval-1',
        task_id: 'task-1',
        status: 'pending',
        current_level: 1,
        max_level: 2,
        escalation_count: 0,
        source: 'api',
        risk_level: 'readonly',
        created_at: '2026-04-08T00:00:00Z',
        actions: [],
      }

      vi.mocked(apiClient.get).mockResolvedValueOnce({ data: mockApproval })

      const { result } = renderHook(() => useApprovalDetail('approval-1'), {
        wrapper: createWrapper(),
      })

      await waitFor(() => expect(result.current.isSuccess).toBe(true))

      expect(apiClient.get).toHaveBeenCalledWith('/approvals/approval-1')
      expect(result.current.data).toEqual(mockApproval)
    })
  })

  describe('useApprove mutation', () => {
    it('should call approve API and invalidate queries', async () => {
      const mockApproval: Approval = {
        approval_id: 'approval-1',
        task_id: 'task-1',
        status: 'approved',
        current_level: 1,
        max_level: 2,
        escalation_count: 0,
        source: 'api',
        risk_level: 'readonly',
        created_at: '2026-04-08T00:00:00Z',
      }

      vi.mocked(apiClient.post).mockResolvedValueOnce({ data: mockApproval })

      const { result } = renderHook(() => useApprove(), {
        wrapper: createWrapper(),
      })

      result.current.mutate({ approvalId: 'approval-1', comment: 'approved' })

      await waitFor(() => expect(result.current.isSuccess).toBe(true))

      expect(apiClient.post).toHaveBeenCalledWith('/approvals/approval-1/approve', {
        comment: 'approved',
      })
    })
  })

  describe('useReject mutation', () => {
    it('should call reject API with required comment', async () => {
      const mockApproval: Approval = {
        approval_id: 'approval-1',
        task_id: 'task-1',
        status: 'rejected',
        current_level: 1,
        max_level: 2,
        escalation_count: 0,
        source: 'api',
        risk_level: 'readonly',
        created_at: '2026-04-08T00:00:00Z',
      }

      vi.mocked(apiClient.post).mockResolvedValueOnce({ data: mockApproval })

      const { result } = renderHook(() => useReject(), {
        wrapper: createWrapper(),
      })

      result.current.mutate({ approvalId: 'approval-1', comment: 'rejected reason' })

      await waitFor(() => expect(result.current.isSuccess).toBe(true))

      expect(apiClient.post).toHaveBeenCalledWith('/approvals/approval-1/reject', {
        comment: 'rejected reason',
      })
    })
  })

  describe('useEscalate mutation', () => {
    it('should call escalate API', async () => {
      const mockApproval: Approval = {
        approval_id: 'approval-1',
        task_id: 'task-1',
        status: 'pending',
        current_level: 2,
        max_level: 2,
        escalation_count: 1,
        source: 'api',
        risk_level: 'readonly',
        created_at: '2026-04-08T00:00:00Z',
      }

      vi.mocked(apiClient.post).mockResolvedValueOnce({ data: mockApproval })

      const { result } = renderHook(() => useEscalate(), {
        wrapper: createWrapper(),
      })

      result.current.mutate({ approvalId: 'approval-1', comment: 'escalate reason' })

      await waitFor(() => expect(result.current.isSuccess).toBe(true))

      expect(apiClient.post).toHaveBeenCalledWith('/approvals/approval-1/escalate', {
        comment: 'escalate reason',
      })
    })
  })
})