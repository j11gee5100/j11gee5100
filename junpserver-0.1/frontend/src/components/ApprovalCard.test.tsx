import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import ApprovalCard from './ApprovalCard'
import type { Approval } from '../types/approval'

// Mock Ant Design components
vi.mock('antd', async () => {
  const actual = await vi.importActual('antd')
  return {
    ...actual,
    Card: ({ children, hoverable, onClick, style }: {
      children: React.ReactNode;
      hoverable?: boolean;
      onClick?: () => void;
      style?: React.CSSProperties;
    }) => (
      <div
        role="article"
        data-testid="approval-card"
        data-hoverable={hoverable}
        onClick={onClick}
        style={style}
      >
        {children}
      </div>
    ),
    Button: ({ children, onClick, disabled, type, icon }: {
      children: React.ReactNode;
      onClick?: (e: React.MouseEvent) => void;
      disabled?: boolean;
      type?: string;
      icon?: React.ReactNode;
    }) => (
      <button
        data-testid={`button-${type || 'default'}`}
        disabled={disabled}
        onClick={onClick}
        data-type={type}
      >
        {icon && <span data-testid="button-icon">{icon}</span>}
        {children}
      </button>
    ),
    Typography: {
      Text: ({ children, type, style }: {
        children: React.ReactNode;
        type?: string;
        style?: React.CSSProperties;
      }) => (
        <span data-testid={`text-${type || 'default'}`} style={style}>
          {children}
        </span>
      ),
      Title: ({ children, level }: {
        children: React.ReactNode;
        level?: number;
      }) => (
        <h5 data-testid={`title-level-${level || 5}`}>
          {children}
        </h5>
      ),
    },
    Tag: ({ children, color }: {
      children: React.ReactNode;
      color?: string;
    }) => (
      <span data-testid={`tag-${color}`} data-color={color}>
        {children}
      </span>
    ),
  }
})

// Mock RiskBadge component
vi.mock('./RiskBadge', () => ({
  default: ({ level }: { level: string }) => (
    <span data-testid={`risk-badge-${level}`}>
      {level.toUpperCase()}
    </span>
  ),
}))

describe('ApprovalCard', () => {
  const mockApproval: Approval = {
    approval_id: 'approval-001',
    task_id: 'task-001',
    status: 'pending',
    current_level: 1,
    max_level: 2,
    escalation_count: 0,
    source: 'alert',
    risk_level: 'high',
    created_at: '2026-04-08T00:00:00Z',
    expires_at: '2026-04-10T00:00:00Z',
  }

  const mockOnApprove = vi.fn()
  const mockOnReject = vi.fn()
  const mockOnViewDetails = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('基础信息展示', () => {
    it('显示 approval_id 和 task_id', () => {
      render(
        <ApprovalCard
          approval={mockApproval}
          onApprove={mockOnApprove}
          onReject={mockOnReject}
        />
      )

      // approval_id 显示
      expect(screen.getByText('approval-001')).toBeInTheDocument()
      // task_id 显示（包含"任务:"前缀）
      expect(screen.getByText(/task-001/)).toBeInTheDocument()
    })

    it('显示来源标签（中文映射）', () => {
      render(
        <ApprovalCard
          approval={mockApproval}
          onApprove={mockOnApprove}
          onReject={mockOnReject}
        />
      )

      // source 'alert' 映射为中文"告警"
      expect(screen.getByText('告警')).toBeInTheDocument()
    })

    it('显示风险等级徽章（使用 RiskBadge 组件）', () => {
      render(
        <ApprovalCard
          approval={mockApproval}
          onApprove={mockOnApprove}
          onReject={mockOnReject}
        />
      )

      // RiskBadge 被调用并显示 HIGH
      expect(screen.getByTestId('risk-badge-high')).toBeInTheDocument()
      expect(screen.getByText('HIGH')).toBeInTheDocument()
    })

    it('显示当前审批层级信息', () => {
      render(
        <ApprovalCard
          approval={mockApproval}
          onApprove={mockOnApprove}
          onReject={mockOnReject}
        />
      )

      // 显示层级 L1/L2
      expect(screen.getByText(/Level 1/i)).toBeInTheDocument()
    })
  })

  describe('超时状态显示', () => {
    it('未超时时显示剩余时间', () => {
      render(
        <ApprovalCard
          approval={mockApproval}
          onApprove={mockOnApprove}
          onReject={mockOnReject}
        />
      )

      // 应显示剩余时间相关的元素
      expect(screen.getByText(/剩余/i)).toBeInTheDocument()
    })

    it('已超时时显示超时标签', () => {
      const expiredApproval: Approval = {
        ...mockApproval,
        expires_at: '2025-01-01T00:00:00Z', // 过期时间在过去
      }

      render(
        <ApprovalCard
          approval={expiredApproval}
          onApprove={mockOnApprove}
          onReject={mockOnReject}
        />
      )

      expect(screen.getByText(/已超时/i)).toBeInTheDocument()
    })

    it('无 expires_at 时不显示超时信息', () => {
      const noExpiresApproval: Approval = {
        ...mockApproval,
        expires_at: undefined,
      }

      render(
        <ApprovalCard
          approval={noExpiresApproval}
          onApprove={mockOnApprove}
          onReject={mockOnReject}
        />
      )

      // 不应显示超时相关文本
      expect(screen.queryByText(/剩余/i)).not.toBeInTheDocument()
      expect(screen.queryByText(/已超时/i)).not.toBeInTheDocument()
    })
  })

  describe('操作按钮', () => {
    it('显示通过和驳回按钮', () => {
      render(
        <ApprovalCard
          approval={mockApproval}
          onApprove={mockOnApprove}
          onReject={mockOnReject}
        />
      )

      // 按钮存在
      expect(screen.getByText(/通过/i)).toBeInTheDocument()
      expect(screen.getByText(/驳回/i)).toBeInTheDocument()
    })

    it('点击通过按钮触发 onApprove 回调', () => {
      render(
        <ApprovalCard
          approval={mockApproval}
          onApprove={mockOnApprove}
          onReject={mockOnReject}
        />
      )

      const approveBtn = screen.getByText(/通过/i)
      fireEvent.click(approveBtn)

      expect(mockOnApprove).toHaveBeenCalledWith('approval-001')
    })

    it('点击驳回按钮触发 onReject 回调', () => {
      render(
        <ApprovalCard
          approval={mockApproval}
          onApprove={mockOnApprove}
          onReject={mockOnReject}
        />
      )

      const rejectBtn = screen.getByText(/驳回/i)
      fireEvent.click(rejectBtn)

      expect(mockOnReject).toHaveBeenCalledWith('approval-001')
    })

    it('按钮点击阻止冒泡（不触发卡片整体点击）', () => {
      render(
        <ApprovalCard
          approval={mockApproval}
          onApprove={mockOnApprove}
          onReject={mockOnReject}
          onViewDetails={mockOnViewDetails}
        />
      )

      const approveBtn = screen.getByText(/通过/i)
      fireEvent.click(approveBtn)

      // 卡片点击回调不被触发
      expect(mockOnViewDetails).not.toHaveBeenCalled()
      expect(mockOnApprove).toHaveBeenCalled()
    })
  })

  describe('按钮禁用逻辑', () => {
    it('pending 状态下按钮可操作', () => {
      render(
        <ApprovalCard
          approval={mockApproval}
          onApprove={mockOnApprove}
          onReject={mockOnReject}
        />
      )

      const approveBtn = screen.getByText(/通过/i)
      const rejectBtn = screen.getByText(/驳回/i)

      expect(approveBtn).not.toBeDisabled()
      expect(rejectBtn).not.toBeDisabled()
    })

    it('approved 状态下按钮禁用', () => {
      const approvedApproval: Approval = {
        ...mockApproval,
        status: 'approved',
      }

      render(
        <ApprovalCard
          approval={approvedApproval}
          onApprove={mockOnApprove}
          onReject={mockOnReject}
        />
      )

      const approveBtn = screen.getByText(/通过/i)
      const rejectBtn = screen.getByText(/驳回/i)

      expect(approveBtn).toBeDisabled()
      expect(rejectBtn).toBeDisabled()
    })

    it('rejected 状态下按钮禁用', () => {
      const rejectedApproval: Approval = {
        ...mockApproval,
        status: 'rejected',
      }

      render(
        <ApprovalCard
          approval={rejectedApproval}
          onApprove={mockOnApprove}
          onReject={mockOnReject}
        />
      )

      const approveBtn = screen.getByText(/通过/i)
      const rejectBtn = screen.getByText(/驳回/i)

      expect(approveBtn).toBeDisabled()
      expect(rejectBtn).toBeDisabled()
    })

    it('expired 状态下按钮禁用', () => {
      const expiredApproval: Approval = {
        ...mockApproval,
        status: 'expired',
      }

      render(
        <ApprovalCard
          approval={expiredApproval}
          onApprove={mockOnApprove}
          onReject={mockOnReject}
        />
      )

      const approveBtn = screen.getByText(/通过/i)
      const rejectBtn = screen.getByText(/驳回/i)

      expect(approveBtn).toBeDisabled()
      expect(rejectBtn).toBeDisabled()
    })
  })

  describe('卡片点击交互', () => {
    it('点击卡片触发 onViewDetails 回调', () => {
      render(
        <ApprovalCard
          approval={mockApproval}
          onApprove={mockOnApprove}
          onReject={mockOnReject}
          onViewDetails={mockOnViewDetails}
        />
      )

      const card = screen.getByTestId('approval-card')
      fireEvent.click(card)

      expect(mockOnViewDetails).toHaveBeenCalledWith(mockApproval)
    })

    it('无 onViewDetails 回调时卡片可点击但无操作', () => {
      render(
        <ApprovalCard
          approval={mockApproval}
          onApprove={mockOnApprove}
          onReject={mockOnReject}
        />
      )

      const card = screen.getByTestId('approval-card')
      // 点击不会报错
      fireEvent.click(card)
      // 无回调
      expect(mockOnApprove).not.toHaveBeenCalled()
      expect(mockOnReject).not.toHaveBeenCalled()
    })
  })

  describe('卡片样式属性', () => {
    it('卡片具有 hoverable 属性', () => {
      render(
        <ApprovalCard
          approval={mockApproval}
          onApprove={mockOnApprove}
          onReject={mockOnReject}
        />
      )

      const card = screen.getByTestId('approval-card')
      expect(card).toHaveAttribute('data-hoverable', 'true')
    })

    it('有 onViewDetails 时卡片 cursor 为 pointer', () => {
      render(
        <ApprovalCard
          approval={mockApproval}
          onApprove={mockOnApprove}
          onReject={mockOnReject}
          onViewDetails={mockOnViewDetails}
        />
      )

      const card = screen.getByTestId('approval-card')
      expect(card.style.cursor).toBe('pointer')
    })
  })
})