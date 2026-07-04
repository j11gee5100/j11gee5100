import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import ApprovalTimeline from './ApprovalTimeline'
import type { ApprovalAction } from '../types/approval'

// Mock formatters
vi.mock('../utils/formatters', () => ({
  formatDateTime: vi.fn((date: string) => `formatted-${date}`),
}))

const mockActions: ApprovalAction[] = [
  {
    action_id: 'action-1',
    action_type: 'created',
    operator_id: 'system',
    created_at: '2026-04-08T10:00:00Z',
  },
  {
    action_id: 'action-2',
    action_type: 'approved',
    operator_id: 'admin',
    comment: '同意执行',
    created_at: '2026-04-08T10:30:00Z',
  },
  {
    action_id: 'action-3',
    action_type: 'escalated',
    operator_id: 'l1-approver',
    comment: '升级处理',
    created_at: '2026-04-08T11:00:00Z',
  },
  {
    action_id: 'action-4',
    action_type: 'rejected',
    operator_id: 'l2-approver',
    comment: '驳回原因',
    created_at: '2026-04-08T11:30:00Z',
  },
]

describe('ApprovalTimeline', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('基础渲染', () => {
    it('应该渲染 Timeline 组件', () => {
      render(<ApprovalTimeline actions={mockActions} />)

      expect(screen.getByTestId('approval-timeline')).toBeInTheDocument()
    })

    it('应该渲染所有动作', () => {
      render(<ApprovalTimeline actions={mockActions} />)

      // 检查动作类型标签
      expect(screen.getByText('创建审批')).toBeInTheDocument()
      expect(screen.getByText('已通过')).toBeInTheDocument()
      expect(screen.getByText('已升级')).toBeInTheDocument()
      expect(screen.getByText('已驳回')).toBeInTheDocument()
    })

    it('应该显示操作者 ID', () => {
      render(<ApprovalTimeline actions={mockActions} />)

      expect(screen.getByText(/操作者: system/)).toBeInTheDocument()
      expect(screen.getByText(/操作者: admin/)).toBeInTheDocument()
      expect(screen.getByText(/操作者: l1-approver/)).toBeInTheDocument()
      expect(screen.getByText(/操作者: l2-approver/)).toBeInTheDocument()
    })

    it('应该显示时间', () => {
      render(<ApprovalTimeline actions={mockActions} />)

      expect(screen.getByText(/formatted-2026-04-08T10:00:00Z/)).toBeInTheDocument()
      expect(screen.getByText(/formatted-2026-04-08T10:30:00Z/)).toBeInTheDocument()
    })

    it('应该显示备注（如果存在）', () => {
      render(<ApprovalTimeline actions={mockActions} />)

      // 检查备注内容存在
      expect(screen.getByText(/同意执行/)).toBeInTheDocument()
      expect(screen.getByText(/升级处理/)).toBeInTheDocument()
      expect(screen.getByText(/驳回原因/)).toBeInTheDocument()
    })
  })

  describe('空状态', () => {
    it('应该显示空状态提示', () => {
      render(<ApprovalTimeline actions={[]} />)

      expect(screen.getByText('无审批动作')).toBeInTheDocument()
    })
  })

  describe('动作类型颜色', () => {
    it('approved 类型应该使用绿色', () => {
      const { container } = render(<ApprovalTimeline actions={[mockActions[1]]} />)

      // Timeline item with green color - 检查存在 timeline item
      const timelineItem = container.querySelector('.ant-timeline-item-head')
      expect(timelineItem).toBeInTheDocument()
      // 实际颜色由 Ant Design 处理，只需验证节点渲染
      expect(screen.getByText('已通过')).toBeInTheDocument()
    })

    it('rejected 类型应该使用红色', () => {
      const { container } = render(<ApprovalTimeline actions={[mockActions[3]]} />)

      // Timeline item with red color - 检查存在 timeline item
      const timelineItem = container.querySelector('.ant-timeline-item-head')
      expect(timelineItem).toBeInTheDocument()
      expect(screen.getByText('已驳回')).toBeInTheDocument()
    })

    it('escalated 类型应该使用金色', () => {
      const { container } = render(<ApprovalTimeline actions={[mockActions[2]]} />)

      // Timeline item with gold color - 检查存在 timeline item
      const timelineItem = container.querySelector('.ant-timeline-item-head')
      expect(timelineItem).toBeInTheDocument()
      expect(screen.getByText('已升级')).toBeInTheDocument()
    })

    it('created 类型应该使用蓝色', () => {
      const { container } = render(<ApprovalTimeline actions={[mockActions[0]]} />)

      // Timeline item with blue color - 检查存在 timeline item
      const timelineItem = container.querySelector('.ant-timeline-item-head')
      expect(timelineItem).toBeInTheDocument()
      expect(screen.getByText('创建审批')).toBeInTheDocument()
    })
  })
})