import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import ApprovalListPage from './ApprovalListPage'
import * as useApprovalsModule from '../hooks/useApprovals'
import type { Approval } from '../types/approval'

// Mock dependencies
vi.mock('../hooks/useApprovals')
vi.mock('../components/ApprovalDrawer', () => ({
  default: vi.fn(() => <div data-testid="approval-drawer">ApprovalDrawer Mock</div>),
}))
vi.mock('../components/ApprovalCard', () => ({
  default: vi.fn(({ approval, onApprove, onReject, onViewDetails }: any) => (
    <div
      data-testid={`approval-card-${approval.approval_id}`}
      onClick={() => onViewDetails?.(approval)}
    >
      <span>{approval.approval_id}</span>
      <button onClick={(e) => { e.stopPropagation(); onApprove(approval.approval_id) }}>通过</button>
      <button onClick={(e) => { e.stopPropagation(); onReject(approval.approval_id) }}>驳回</button>
    </div>
  )),
}))

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  })
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
}

const mockApprovals: Approval[] = [
  {
    approval_id: 'approval-1',
    task_id: 'task-1',
    status: 'pending',
    current_level: 1,
    max_level: 2,
    escalation_count: 0,
    source: 'alert',
    risk_level: 'high',
    created_at: '2026-04-08T10:00:00Z',
  },
  {
    approval_id: 'approval-2',
    task_id: 'task-2',
    status: 'pending',
    current_level: 1,
    max_level: 2,
    escalation_count: 0,
    source: 'manual',
    risk_level: 'low',
    created_at: '2026-04-08T11:00:00Z',
  },
]

const mockL2Approvals: Approval[] = [
  {
    approval_id: 'approval-3',
    task_id: 'task-3',
    status: 'pending',
    current_level: 2,
    max_level: 2,
    escalation_count: 1,
    source: 'alert',
    risk_level: 'high',
    created_at: '2026-04-08T12:00:00Z',
  },
]

describe('ApprovalListPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('基础渲染', () => {
    it('应该渲染页面标题', () => {
      vi.mocked(useApprovalsModule.useApprovals).mockReturnValue({
        data: mockApprovals,
        isLoading: false,
        isError: false,
      } as any)

      render(<ApprovalListPage />, { wrapper: createWrapper() })

      expect(screen.getByText('审批中心')).toBeInTheDocument()
    })

    it('应该渲染 L1/L2 Tab 切换', () => {
      vi.mocked(useApprovalsModule.useApprovals).mockReturnValue({
        data: mockApprovals,
        isLoading: false,
        isError: false,
      } as any)

      render(<ApprovalListPage />, { wrapper: createWrapper() })

      expect(screen.getByRole('tab', { name: /L1 审批/ })).toBeInTheDocument()
      expect(screen.getByRole('tab', { name: /L2 审批/ })).toBeInTheDocument()
    })

    it('应该显示审批数量在 Tab 标签中', () => {
      vi.mocked(useApprovalsModule.useApprovals).mockReturnValue({
        data: mockApprovals,
        isLoading: false,
        isError: false,
      } as any)

      render(<ApprovalListPage />, { wrapper: createWrapper() })

      expect(screen.getByRole('tab', { name: /L1 审批 \(2\)/ })).toBeInTheDocument()
    })
  })

  describe('Tab 切换', () => {
    it('默认选中 L1 Tab', () => {
      vi.mocked(useApprovalsModule.useApprovals).mockReturnValue({
        data: mockApprovals,
        isLoading: false,
        isError: false,
      } as any)

      render(<ApprovalListPage />, { wrapper: createWrapper() })

      const l1Tab = screen.getByRole('tab', { name: /L1 审批/ })
      expect(l1Tab).toHaveAttribute('aria-selected', 'true')
    })

    it('点击 L2 Tab 后切换层级并刷新数据', async () => {
      vi.mocked(useApprovalsModule.useApprovals)
        .mockReturnValueOnce({
          data: mockApprovals,
          isLoading: false,
          isError: false,
        } as any)
        .mockReturnValueOnce({
          data: mockL2Approvals,
          isLoading: false,
          isError: false,
        } as any)

      render(<ApprovalListPage />, { wrapper: createWrapper() })

      const l2Tab = screen.getByRole('tab', { name: /L2 审批/ })
      fireEvent.click(l2Tab)

      await waitFor(() => {
        expect(useApprovalsModule.useApprovals).toHaveBeenCalledWith(2)
      })
    })
  })

  describe('卡片列表渲染', () => {
    it('应该使用 Grid 响应式布局渲染卡片', () => {
      vi.mocked(useApprovalsModule.useApprovals).mockReturnValue({
        data: mockApprovals,
        isLoading: false,
        isError: false,
      } as any)

      render(<ApprovalListPage />, { wrapper: createWrapper() })

      const container = screen.getByTestId('approval-card-grid')
      expect(container).toHaveStyle({
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
      })
    })

    it('应该渲染所有审批卡片', () => {
      vi.mocked(useApprovalsModule.useApprovals).mockReturnValue({
        data: mockApprovals,
        isLoading: false,
        isError: false,
      } as any)

      render(<ApprovalListPage />, { wrapper: createWrapper() })

      expect(screen.getByTestId('approval-card-approval-1')).toBeInTheDocument()
      expect(screen.getByTestId('approval-card-approval-2')).toBeInTheDocument()
    })
  })

  describe('操作处理', () => {
    it('点击通过按钮应该调用 approveMutation', async () => {
      const mockApprove = vi.fn((variables, options) => {
        // 模拟成功响应
        options?.onSuccess?.(mockApprovals[0], variables)
      })
      const mockRefetch = vi.fn()

      vi.mocked(useApprovalsModule.useApprovals).mockReturnValue({
        data: mockApprovals,
        isLoading: false,
        isError: false,
        refetch: mockRefetch,
      } as any)
      vi.mocked(useApprovalsModule.useApprove).mockReturnValue({
        mutate: mockApprove,
      } as any)

      render(<ApprovalListPage />, { wrapper: createWrapper() })

      const approveButton = screen.getAllByText('通过')[0]
      fireEvent.click(approveButton)

      await waitFor(() => {
        expect(mockApprove).toHaveBeenCalledWith(
          { approvalId: 'approval-1', comment: undefined },
          expect.objectContaining({
            onSuccess: expect.any(Function),
            onError: expect.any(Function),
          })
        )
      })
    })

    it('点击驳回按钮应该打开抽屉（需填写原因）', async () => {
      vi.mocked(useApprovalsModule.useApprovals).mockReturnValue({
        data: mockApprovals,
        isLoading: false,
        isError: false,
      } as any)

      render(<ApprovalListPage />, { wrapper: createWrapper() })

      const rejectButton = screen.getAllByText('驳回')[0]
      fireEvent.click(rejectButton)

      await waitFor(() => {
        expect(screen.getByTestId('approval-drawer')).toBeInTheDocument()
      })
    })

    it('点击卡片应该打开详情抽屉', async () => {
      vi.mocked(useApprovalsModule.useApprovals).mockReturnValue({
        data: mockApprovals,
        isLoading: false,
        isError: false,
      } as any)

      render(<ApprovalListPage />, { wrapper: createWrapper() })

      const card = screen.getByTestId('approval-card-approval-1')
      fireEvent.click(card)

      await waitFor(() => {
        expect(screen.getByTestId('approval-drawer')).toBeInTheDocument()
      })
    })
  })

  describe('409 冲突处理', () => {
    it('通过操作遇到 409 冲突应该显示 Toast 并刷新', async () => {
      const error = new Error('Conflict')
      ;(error as any).response = { status: 409 }

      const mockApprove = vi.fn((variables, options) => {
        // 模拟 409 冲突错误
        options?.onError?.(error, variables)
      })
      const mockRefetch = vi.fn()

      vi.mocked(useApprovalsModule.useApprovals).mockReturnValue({
        data: mockApprovals,
        isLoading: false,
        isError: false,
        refetch: mockRefetch,
      } as any)
      vi.mocked(useApprovalsModule.useApprove).mockReturnValue({
        mutate: mockApprove,
      } as any)

      render(<ApprovalListPage />, { wrapper: createWrapper() })

      const approveButton = screen.getAllByText('通过')[0]
      fireEvent.click(approveButton)

      await waitFor(() => {
        expect(mockRefetch).toHaveBeenCalled()
      })
    })
  })

  describe('状态处理', () => {
    it('Loading 状态应该显示骨架屏', () => {
      vi.mocked(useApprovalsModule.useApprovals).mockReturnValue({
        data: undefined,
        isLoading: true,
        isError: false,
      } as any)

      render(<ApprovalListPage />, { wrapper: createWrapper() })

      expect(screen.getByTestId('skeleton-container')).toBeInTheDocument()
    })

    it('空状态应该显示友好提示', () => {
      vi.mocked(useApprovalsModule.useApprovals).mockReturnValue({
        data: [],
        isLoading: false,
        isError: false,
      } as any)

      render(<ApprovalListPage />, { wrapper: createWrapper() })

      expect(screen.getByText('当前层级无待审批任务')).toBeInTheDocument()
    })

    it('错误状态应该显示错误提示', () => {
      vi.mocked(useApprovalsModule.useApprovals).mockReturnValue({
        data: undefined,
        isLoading: false,
        isError: true,
        error: new Error('Network error'),
      } as any)

      render(<ApprovalListPage />, { wrapper: createWrapper() })

      expect(screen.getByText(/加载失败/)).toBeInTheDocument()
    })
  })
})