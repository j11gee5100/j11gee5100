import { Modal, Typography, Space, Alert } from 'antd'
import RiskBadge from './RiskBadge'

const { Text } = Typography

interface RiskConfirmModalProps {
  open: boolean
  riskLevel: 'low' | 'medium' | 'high'
  command: string
  onConfirm: () => void
  onCancel: () => void
}

/**
 * RiskConfirmModal - 高风险任务确认弹窗
 *
 * 功能:
 * - 显示任务风险等级标签（使用RiskBadge）
 * - 显示命令内容预览
 * - 显示警告提示：高风险任务需要审批
 * - 提供确认和取消操作按钮
 *
 * Per D-12: 高风险任务在提交前显示风险确认弹窗
 */
export default function RiskConfirmModal({
  open,
  riskLevel,
  command,
  onConfirm,
  onCancel,
}: RiskConfirmModalProps) {
  return (
    <Modal
      title="高风险任务确认"
      open={open}
      onCancel={onCancel}
      onOk={onConfirm}
      okText="确认提交"
      cancelText="取消"
      width={500}
    >
      {/* 风险等级显示 */}
      <Space style={{ marginBottom: 16 }}>
        <Text strong>风险等级:</Text>
        <RiskBadge level={riskLevel} />
      </Space>

      {/* 命令内容预览 */}
      <div style={{ marginBottom: 16 }}>
        <Text strong style={{ marginBottom: 8, display: 'block' }}>命令内容:</Text>
        <div
          style={{
            padding: '12px',
            background: '#f5f5f5',
            borderRadius: '4px',
            maxHeight: '150px',
            overflow: 'auto',
          }}
        >
          <Text>{command || '无命令内容'}</Text>
        </div>
      </div>

      {/* 警告提示 */}
      <Alert
        type="warning"
        message="高风险操作警告"
        description="此任务为高风险操作，提交后需要经过审批流程才能执行。请确认您了解操作风险。"
        showIcon
      />
    </Modal>
  )
}