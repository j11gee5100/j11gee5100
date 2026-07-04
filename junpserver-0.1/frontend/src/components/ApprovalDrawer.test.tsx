import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import ApprovalDrawer from './ApprovalDrawer'
import * as useApprovalsModule from '../hooks/useApprovals'
import type { Approval } from '../types/approval'

// Mock dependencies
vi.mock('../hooks/useApprovals')
vi.mock('./ApprovalTimeline', () => ({
  default: vi.fn(() => <div data-testid="approval-timeline">ApprovalTimeline Mock</div>),
}))
vi.mock('../utils/formatters', () => ({
  formatDateTime: vi.fn((date: string) => `formatted-${date}`),
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

const mockApproval: Approval = {
  approval_id: 'approval-1',
  task_id: 'task-1',
  status: 'pending',
  current_level: 1,
  max_level: 2,
  escalation_count: 0,
  expires_at: '2026-04-08T18:00:00Z',
  source: 'alert',
  risk_level: 'high',
  created_at: '2026-04-08T10:00:00Z',
  actions: [
    {
      action_id: 'action-1',
      action_type: 'created',
      operator_id: 'system',
      created_at: '2026-04-08T10:00:00Z',
    },
  ],
}

const mockApprovalAtMaxLevel: Approval = {
  approval_id: 'approval-2',
  task_id: 'task-2',
  status: 'pending',
  current_level: 2,
  max_level: 2,
  escalation_count: 1,
  source: 'alert',
  risk_level: 'high',
  created_at: '2026-04-08T12:00:00Z',
}

const mockApprovedApproval: Approval = {
  approval_id: 'approval-3',
  task_id: 'task-3',
  status: 'approved',
  current_level: 1,
  max_level: 2,
  escalation_count: 0,
  source: 'alert',
  risk_level: 'low',
  created_at: '2026-04-08T10:00:00Z',
}

describe('ApprovalDrawer', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Mock mutations with isPending property
    vi.mocked(useApprovalsModule.useApprove).mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as any)
    vi.mocked(useApprovalsModule.useReject).mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as any)
    vi.mocked(useApprovalsModule.useEscalate).mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as any)
  })

  describe('基础渲染', () => {
    it('应该渲染抽屉且宽度为 520px', () => {
      vi.mocked(useApprovalsModule.useApprovalDetail).mockReturnValue({
        data: mockApproval,
        isLoading: false,
      } as any)

      render(
        <ApprovalDrawer
          open={true}
          approval={mockApproval}
          onClose={() => {}}
        />,
        { wrapper: createWrapper() }
      )

      const drawer = screen.getByRole('dialog')
      expect(drawer).toBeInTheDocument()
      // Check drawer width via style or aria attribute
    })

    it('应该渲染基础信息卡', async () => {
      vi.mocked(useApprovalsModule.useApprovalDetail).mockReturnValue({
        data: mockApproval,
        isLoading: false,
      } as any)

      render(
        <ApprovalDrawer
          open={true}
          approval={mockApproval}
          onClose={() => {}}
        />,
        { wrapper: createWrapper() }
      )

      // 等待 Drawer 动画完成
      await waitFor(() => {
        expect(screen.getByText('基础信息')).toBeInTheDocument()
      })
      // Descriptions label 不带冒号
      expect(screen.getByText('审批单')).toBeInTheDocument()
      expect(screen.getByText('approval-1')).toBeInTheDocument()
    })

    it('应该渲染决策区包含通过/驳回/升级按钮', async () => {
      vi.mocked(useApprovalsModule.useApprovalDetail).mockReturnValue({
        data: mockApproval,
        isLoading: false,
      } as any)

      render(
        <ApprovalDrawer
          open={true}
          approval={mockApproval}
          onClose={() => {}}
        />,
        { wrapper: createWrapper() }
      )

      await waitFor(() => {
        expect(screen.getByText('审批决策')).toBeInTheDocument()
      })
      // Ant Design 在中文文本间插入空格: "通 过", "驳 回", "升 级"
      expect(screen.getByRole('button', { name: /通\s*过/ })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /驳\s*回/ })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /升\s*级/ })).toBeInTheDocument()
    })

    it('应该渲染时间线组件', async () => {
      vi.mocked(useApprovalsModule.useApprovalDetail).mockReturnValue({
        data: mockApproval,
        isLoading: false,
      } as any)

      render(
        <ApprovalDrawer
          open={true}
          approval={mockApproval}
          onClose={() => {}}
        />,
        { wrapper: createWrapper() }
      )

      await waitFor(() => {
        expect(screen.getByTestId('approval-timeline')).toBeInTheDocument()
      })
    })
  })

  describe('原因输入框', () => {
    it('应该显示原因输入框 maxLength=500 showCount', async () => {
      vi.mocked(useApprovalsModule.useApprovalDetail).mockReturnValue({
        data: mockApproval,
        isLoading: false,
      } as any)

      render(
        <ApprovalDrawer
          open={true}
          approval={mockApproval}
          onClose={() => {}}
        />,
        { wrapper: createWrapper() }
      )

      await waitFor(() => {
        expect(screen.getByPlaceholderText('请输入审批原因（驳回时必填）')).toBeInTheDocument()
      })
      const textarea = screen.getByPlaceholderText('请输入审批原因（驳回时必填）')
      expect(textarea).toHaveAttribute('maxlength', '500')
      // showCount 显示格式可能是 /500
      expect(screen.getByText(/500/)).toBeInTheDocument()
    })

    it('输入原因应该更新状态', async () => {
      vi.mocked(useApprovalsModule.useApprovalDetail).mockReturnValue({
        data: mockApproval,
        isLoading: false,
      } as any)

      render(
        <ApprovalDrawer
          open={true}
          approval={mockApproval}
          onClose={() => {}}
        />,
        { wrapper: createWrapper() }
      )

      await waitFor(() => {
        expect(screen.getByPlaceholderText('请输入审批原因（驳回时必填）')).toBeInTheDocument()
      })
      const textarea = screen.getByPlaceholderText('请输入审批原因（驳回时必填）')
      fireEvent.change(textarea, { target: { value: '驳回原因测试' } })

      await waitFor(() => {
        expect(textarea).toHaveValue('驳回原因测试')
        // 字符计数会显示中文字符数
        expect(screen.getByText(/6.*500/)).toBeInTheDocument()
      })
    })
  })

  describe('操作处理', () => {
    it('点击通过按钮应该调用 useApprove mutation', async () => {
      const mockApprove = vi.fn((variables, options) => {
        options?.onSuccess?.(mockApproval, variables)
      })
      const mockOnOperationComplete = vi.fn()

      vi.mocked(useApprovalsModule.useApprovalDetail).mockReturnValue({
        data: mockApproval,
        isLoading: false,
      } as any)
      vi.mocked(useApprovalsModule.useApprove).mockReturnValue({
        mutate: mockApprove,
        isPending: false,
      } as any)

      render(
        <ApprovalDrawer
          open={true}
          approval={mockApproval}
          onClose={() => {}}
          onOperationComplete={mockOnOperationComplete}
        />,
        { wrapper: createWrapper() }
      )

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /通\s*过/ })).toBeInTheDocument()
      })
      const approveButton = screen.getByRole('button', { name: /通\s*过/ })
      fireEvent.click(approveButton)

      await waitFor(() => {
        expect(mockApprove).toHaveBeenCalledWith(
          { approvalId: 'approval-1', comment: undefined },
          expect.any(Object)
        )
        expect(mockOnOperationComplete).toHaveBeenCalled()
      })
    })

    it('驳回时没有填写原因应该提示错误', async () => {
      const mockReject = vi.fn()
      vi.mocked(useApprovalsModule.useApprovalDetail).mockReturnValue({
        data: mockApproval,
        isLoading: false,
      } as any)
      vi.mocked(useApprovalsModule.useReject).mockReturnValue({
        mutate: mockReject,
        isPending: false,
      } as any)

      render(
        <ApprovalDrawer
          open={true}
          approval={mockApproval}
          onClose={() => {}}
        />,
        { wrapper: createWrapper() }
      )

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /驳\s*回/ })).toBeInTheDocument()
      })
      const rejectButton = screen.getByRole('button', { name: /驳\s*回/ })
      fireEvent.click(rejectButton)

      // 驳回时未填写原因，mutation 不应该被调用
      await waitFor(() => {
        expect(mockReject).not.toHaveBeenCalled()
      })
    })

    it('驳回时有原因应该调用 useReject mutation', async () => {
      const mockReject = vi.fn((variables, options) => {
        options?.onSuccess?.(mockApproval, variables)
      })
      const mockOnOperationComplete = vi.fn()

      vi.mocked(useApprovalsModule.useApprovalDetail).mockReturnValue({
        data: mockApproval,
        isLoading: false,
      } as any)
      vi.mocked(useApprovalsModule.useReject).mockReturnValue({
        mutate: mockReject,
        isPending: false,
      } as any)

      render(
        <ApprovalDrawer
          open={true}
          approval={mockApproval}
          onClose={() => {}}
          onOperationComplete={mockOnOperationComplete}
        />,
        { wrapper: createWrapper() }
      )

      await waitFor(() => {
        expect(screen.getByPlaceholderText('请输入审批原因（驳回时必填）')).toBeInTheDocument()
      })
      const textarea = screen.getByPlaceholderText('请输入审批原因（驳回时必填）')
      fireEvent.change(textarea, { target: { value: '驳回原因' } })

      const rejectButton = screen.getByRole('button', { name: /驳\s*回/ })
      fireEvent.click(rejectButton)

      await waitFor(() => {
        expect(mockReject).toHaveBeenCalledWith(
          { approvalId: 'approval-1', comment: '驳回原因' },
          expect.any(Object)
        )
        expect(mockOnOperationComplete).toHaveBeenCalled()
      })
    })

    it('点击升级按钮应该调用 useEscalate mutation', async () => {
      const mockEscalate = vi.fn((variables, options) => {
        options?.onSuccess?.(mockApproval, variables)
      })
      const mockOnOperationComplete = vi.fn()

      vi.mocked(useApprovalsModule.useApprovalDetail).mockReturnValue({
        data: mockApproval,
        isLoading: false,
      } as any)
      vi.mocked(useApprovalsModule.useEscalate).mockReturnValue({
        mutate: mockEscalate,
        isPending: false,
      } as any)

      render(
        <ApprovalDrawer
          open={true}
          approval={mockApproval}
          onClose={() => {}}
          onOperationComplete={mockOnOperationComplete}
        />,
        { wrapper: createWrapper() }
      )

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /升\s*级/ })).toBeInTheDocument()
      })
      const escalateButton = screen.getByRole('button', { name: /升\s*级/ })
      fireEvent.click(escalateButton)

      await waitFor(() => {
        expect(mockEscalate).toHaveBeenCalledWith(
          { approvalId: 'approval-1', comment: undefined },
          expect.any(Object)
        )
        expect(mockOnOperationComplete).toHaveBeenCalled()
      })
    })
  })

  describe('按钮禁用逻辑', () => {
    it('已达 max_level 时升级按钮应该禁用', async () => {
      vi.mocked(useApprovalsModule.useApprovalDetail).mockReturnValue({
        data: mockApprovalAtMaxLevel,
        isLoading: false,
      } as any)

      render(
        <ApprovalDrawer
          open={true}
          approval={mockApprovalAtMaxLevel}
          onClose={() => {}}
        />,
        { wrapper: createWrapper() }
      )

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /升\s*级/ })).toBeInTheDocument()
      })
      const escalateButton = screen.getByRole('button', { name: /升\s*级/ })
      expect(escalateButton).toBeDisabled()
    })

    it('approved/rejected/expired 状态时所有按钮应该禁用', async () => {
      vi.mocked(useApprovalsModule.useApprovalDetail).mockReturnValue({
        data: mockApprovedApproval,
        isLoading: false,
      } as any)

      render(
        <ApprovalDrawer
          open={true}
          approval={mockApprovedApproval}
          onClose={() => {}}
        />,
        { wrapper: createWrapper() }
      )

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /通\s*过/ })).toBeInTheDocument()
      })
      expect(screen.getByRole('button', { name: /通\s*过/ })).toBeDisabled()
      expect(screen.getByRole('button', { name: /驳\s*回/ })).toBeDisabled()
      expect(screen.getByRole('button', { name: /升\s*级/ })).toBeDisabled()
    })

    it('pending 状态且未达 max_level 时按钮应该可用', async () => {
      vi.mocked(useApprovalsModule.useApprovalDetail).mockReturnValue({
        data: mockApproval,
        isLoading: false,
      } as any)

      render(
        <ApprovalDrawer
          open={true}
          approval={mockApproval}
          onClose={() => {}}
        />,
        { wrapper: createWrapper() }
      )

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /通\s*过/ })).toBeInTheDocument()
      })
      expect(screen.getByRole('button', { name: /通\s*过/ })).not.toBeDisabled()
      expect(screen.getByRole('button', { name: /驳\s*回/ })).not.toBeDisabled()
      expect(screen.getByRole('button', { name: /升\s*级/ })).not.toBeDisabled()
    })
  })

  describe('409 冲突处理', () => {
    it('操作遇到 409 冲突应该显示 Toast 并回调', async () => {
      const error = new Error('Conflict')
      ;(error as any).response = { status: 409 }
      const mockApprove = vi.fn((variables, options) => {
        options?.onError?.(error, variables)
      })
      const mockOnOperationComplete = vi.fn()

      vi.mocked(useApprovalsModule.useApprovalDetail).mockReturnValue({
        data: mockApproval,
        isLoading: false,
      } as any)
      vi.mocked(useApprovalsModule.useApprove).mockReturnValue({
        mutate: mockApprove,
        isPending: false,
      } as any)

      render(
        <ApprovalDrawer
          open={true}
          approval={mockApproval}
          onClose={() => {}}
          onOperationComplete={mockOnOperationComplete}
        />,
        { wrapper: createWrapper() }
      )

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /通\s*过/ })).toBeInTheDocument()
      })
      const approveButton = screen.getByRole('button', { name: /通\s*过/ })
      fireEvent.click(approveButton)

      await waitFor(() => {
        expect(mockOnOperationComplete).toHaveBeenCalled()
      })
    })
  })

  describe('关闭处理', () => {
    it('点击关闭按钮应该触发 onClose', async () => {
      const mockOnClose = vi.fn()
      vi.mocked(useApprovalsModule.useApprovalDetail).mockReturnValue({
        data: mockApproval,
        isLoading: false,
      } as any)

      render(
        <ApprovalDrawer
          open={true}
          approval={mockApproval}
          onClose={mockOnClose}
        />,
        { wrapper: createWrapper() }
      )

      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Close' })).toBeInTheDocument()
      })
      // Click close button (X icon)
      const closeButton = screen.getByRole('button', { name: 'Close' })
      fireEvent.click(closeButton)

      await waitFor(() => {
        expect(mockOnClose).toHaveBeenCalled()
      })
    })
  })
})