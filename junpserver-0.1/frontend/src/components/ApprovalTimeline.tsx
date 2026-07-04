import { Timeline, Typography, Empty } from 'antd'
import type { ApprovalAction, ApprovalActionType } from '../types/approval'
import { formatDateTime } from '../utils/formatters'

const { Text } = Typography

/**
 * ApprovalTimeline - 审批动作时间线
 *
 * Per D-07:
 * - 时间线按 actions 数组渲染每个审批动作
 * - 每个节点显示 action_type、operator_id、时间、备注
 * - 时间线节点颜色按 action_type 区分
 * - 空状态显示 "无审批动作"
 */

/**
 * 获取动作类型对应的颜色
 */
function getActionColor(actionType: ApprovalActionType): string {
  const colorMap: Record<ApprovalActionType, string> = {
    approved: 'green',
    rejected: 'red',
    escalated: 'gold',
    created: 'blue',
  }
  return colorMap[actionType] || 'gray'
}

/**
 * 获取动作类型对应的中文标签
 */
function getActionLabel(actionType: ApprovalActionType): string {
  const labelMap: Record<ApprovalActionType, string> = {
    created: '创建审批',
    approved: '已通过',
    rejected: '已驳回',
    escalated: '已升级',
  }
  return labelMap[actionType] || actionType
}

interface ApprovalTimelineProps {
  /** 审批动作列表 */
  actions: ApprovalAction[]
}

export default function ApprovalTimeline({ actions }: ApprovalTimelineProps) {
  // 空状态处理
  if (actions.length === 0) {
    return <Empty description="无审批动作" />
  }

  // 构建 Timeline items
  const timelineItems = actions.map((action) => ({
    key: action.action_id,
    color: getActionColor(action.action_type),
    children: (
      <div>
        <Text strong>{getActionLabel(action.action_type)}</Text>
        <br />
        <Text type="secondary">操作者: {action.operator_id}</Text>
        <br />
        <Text type="secondary">{formatDateTime(action.created_at)}</Text>
        {action.comment && (
          <div style={{ marginTop: 8 }}>
            <Text>备注: {action.comment}</Text>
          </div>
        )}
      </div>
    ),
  }))

  return (
    <div data-testid="approval-timeline">
      <Timeline items={timelineItems} />
    </div>
  )
}