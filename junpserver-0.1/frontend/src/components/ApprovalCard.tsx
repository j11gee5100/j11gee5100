import { Card, Button, Typography, Tag } from 'antd'
import { CheckOutlined, CloseOutlined } from '@ant-design/icons'
import type { Approval } from '../types/approval'
import RiskBadge from './RiskBadge'
import dayjs from 'dayjs'

const { Text } = Typography

/**
 * ApprovalCard 展示审批单的基本信息，包含通过/驳回快速操作按钮和超时状态显示
 *
 * 组件结构：
 * - 卡片顶部：approval_id、task_id（灰色辅助文本）
 * - 核心信息区：来源标签、风险等级徽章、当前层级
 * - 超时状态区：剩余时间或已超时标签
 * - 操作按钮区：通过、驳回按钮
 *
 * 交互行为：
 * - 点击卡片整体 → 触发 onViewDetails 回调打开详情抽屉
 * - 点击通过 → 触发 onApprove(approvalId)
 * - 点击驳回 → 触发 onReject(approvalId)
 * - 按钮点击需要 stopPropagation 阻止冒泡
 *
 * 按钮禁用逻辑：
 * - status !== 'pending' 时禁用所有操作按钮
 * - expired 状态显示超时标签
 */
interface ApprovalCardProps {
  /** 审批单数据 */
  approval: Approval
  /** 通过审批回调 */
  onApprove: (approvalId: string) => void
  /** 驳回审批回调 */
  onReject: (approvalId: string) => void
  /** 查看详情回调（可选） */
  onViewDetails?: (approval: Approval) => void
}

/**
 * 计算剩余时间显示文本
 * @param expiresAt - 过期时间 ISO 格式
 * @returns 剩余时间描述或 null（无过期时间或已超时）
 */
function getRemainingTime(expiresAt?: string): { text: string; isExpired: boolean } | null {
  if (!expiresAt) return null

  const now = dayjs()
  const expires = dayjs(expiresAt)
  const remainingMinutes = expires.diff(now, 'minute')

  if (remainingMinutes <= 0) {
    return { text: '已超时', isExpired: true }
  }

  const hours = Math.floor(remainingMinutes / 60)
  const minutes = remainingMinutes % 60

  if (hours > 0) {
    return { text: `剩余 ${hours}h ${minutes}m`, isExpired: false }
  }

  return { text: `剩余 ${minutes}m`, isExpired: false }
}

export default function ApprovalCard({
  approval,
  onApprove,
  onReject,
  onViewDetails,
}: ApprovalCardProps) {
  // 判断是否可操作（仅 pending 状态可操作）
  const isOperationDisabled = approval.status !== 'pending'

  // 计算超时状态
  const remainingTime = getRemainingTime(approval.expires_at)

  // 卡片点击处理
  const handleCardClick = () => {
    if (onViewDetails) {
      onViewDetails(approval)
    }
  }

  // 通过按钮点击处理（阻止冒泡）
  const handleApproveClick = (e: React.MouseEvent) => {
    e.stopPropagation()
    onApprove(approval.approval_id)
  }

  // 驳回按钮点击处理（阻止冒泡）
  const handleRejectClick = (e: React.MouseEvent) => {
    e.stopPropagation()
    onReject(approval.approval_id)
  }

  // 来源标签文案映射
  const sourceLabelMap: Record<string, string> = {
    alert: '告警',
    manual: '手动',
    scheduled: '定时',
    api: 'API',
  }

  const sourceLabel = sourceLabelMap[approval.source] || approval.source

  return (
    <Card
      role="article"
      hoverable
      style={{
        border: '1px solid #f0f0f0',
        cursor: onViewDetails ? 'pointer' : 'default',
      }}
      onClick={handleCardClick}
    >
      {/* 第一行：approval_id（灰色辅助文本） */}
      <div style={{ marginBottom: 4 }}>
        <Text type="secondary" style={{ fontSize: 12 }}>
          {approval.approval_id}
        </Text>
      </div>

      {/* 第二行：task_id（灰色辅助文本） */}
      <div style={{ marginBottom: 8 }}>
        <Text type="secondary" style={{ fontSize: 12 }}>
          任务: {approval.task_id}
        </Text>
      </div>

      {/* 第三行：来源标签 + 风险等级徽章 + 当前层级 */}
      <div style={{ marginBottom: 8, display: 'flex', alignItems: 'center', gap: 8 }}>
        <Tag color="blue" style={{ borderRadius: 0 }}>
          {sourceLabel}
        </Tag>
        <RiskBadge level={approval.risk_level as 'low' | 'medium' | 'high'} />
        <Tag color="purple" style={{ borderRadius: 0 }}>
          Level {approval.current_level}
        </Tag>
      </div>

      {/* 第四行：超时状态 */}
      {remainingTime && (
        <div style={{ marginBottom: 8 }}>
          <Text
            type={remainingTime.isExpired ? 'danger' : 'success'}
            style={{ fontWeight: remainingTime.isExpired ? 500 : 400 }}
          >
            {remainingTime.text}
          </Text>
        </div>
      )}

      {/* 操作按钮区域（通过 + 驳回） */}
      <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
        <Button
          type="primary"
          icon={<CheckOutlined />}
          disabled={isOperationDisabled}
          onClick={handleApproveClick}
          style={{ flex: 1 }}
        >
          通过
        </Button>
        <Button
          danger
          icon={<CloseOutlined />}
          disabled={isOperationDisabled}
          onClick={handleRejectClick}
          style={{ flex: 1 }}
        >
          驳回
        </Button>
      </div>
    </Card>
  )
}