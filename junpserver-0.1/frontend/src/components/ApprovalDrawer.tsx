import { useState } from 'react'
import { Drawer, Card, Descriptions, Button, Input, Typography, message } from 'antd'
import { useApprovalDetail, useApprove, useReject, useEscalate } from '../hooks/useApprovals'
import ApprovalTimeline from './ApprovalTimeline'
import type { Approval } from '../types/approval'
import { formatDateTime } from '../utils/formatters'

const { TextArea } = Input
const { Text } = Typography

/**
 * ApprovalDrawer - 审批详情抽屉
 *
 * Per D-05/D-06/D-07/D-08/D-09/D-11/D-12:
 * - 抽屉宽度 520px
 * - 包含基础信息卡、决策区、时间线
 * - 驳回时必填原因，其他可选
 * - 原因限制 500 字符
 * - 升级按钮在 current_level=max_level 时禁用
 * - approved/rejected/expired 状态禁用所有操作按钮
 * - 409 冲突 Toast 提示
 */
interface ApprovalDrawerProps {
  /** 抽屉打开状态 */
  open: boolean
  /** 审批单数据（可选） */
  approval?: Approval | null
  /** 关闭回调 */
  onClose: () => void
  /** 操作完成回调 */
  onOperationComplete?: () => void
}

export default function ApprovalDrawer({
  open,
  approval,
  onClose,
  onOperationComplete,
}: ApprovalDrawerProps) {
  // State
  const [comment, setComment] = useState('')

  // Hooks - 获取详情（含时间线）
  const { data: approvalDetail } = useApprovalDetail(approval?.approval_id || '')

  // Mutations
  const approveMutation = useApprove()
  const rejectMutation = useReject()
  const escalateMutation = useEscalate()

  // 使用详情数据或传入的 approval 对象
  const currentApproval = approvalDetail || approval

  // 按钮禁用逻辑
  const isOperationDisabled = currentApproval?.status !== 'pending'
  const cannotEscalate = (currentApproval?.current_level ?? 0) >= (currentApproval?.max_level ?? 0) || isOperationDisabled

  // 通过操作处理
  const handleApprove = () => {
    approveMutation.mutate(
      { approvalId: currentApproval!.approval_id, comment: comment || undefined },
      {
        onSuccess: () => {
          message.success('审批通过')
          setComment('')
          onOperationComplete?.()
        },
        onError: (err: any) => {
          if (err?.response?.status === 409) {
            message.warning('审批状态已变更')
            setComment('')
            onOperationComplete?.()
          } else {
            message.error(err?.message || '操作失败')
          }
        },
      }
    )
  }

  // 驳回操作处理
  const handleReject = () => {
    if (!comment.trim()) {
      message.error('请填写驳回原因')
      return
    }

    rejectMutation.mutate(
      { approvalId: currentApproval!.approval_id, comment },
      {
        onSuccess: () => {
          message.success('审批驳回')
          setComment('')
          onOperationComplete?.()
        },
        onError: (err: any) => {
          if (err?.response?.status === 409) {
            message.warning('审批状态已变更')
            setComment('')
            onOperationComplete?.()
          } else {
            message.error(err?.message || '操作失败')
          }
        },
      }
    )
  }

  // 升级操作处理
  const handleEscalate = () => {
    escalateMutation.mutate(
      { approvalId: currentApproval!.approval_id, comment: comment || undefined },
      {
        onSuccess: () => {
          message.success('审批已升级')
          setComment('')
          onOperationComplete?.()
        },
        onError: (err: any) => {
          if (err?.response?.status === 409) {
            message.warning('审批状态已变更')
            setComment('')
            onOperationComplete?.()
          } else {
            message.error(err?.message || '操作失败')
          }
        },
      }
    )
  }

  return (
    <Drawer
      open={open}
      title="审批详情"
      width={520}
      onClose={onClose}
      data-testid="approval-drawer"
    >
      {currentApproval && (
        <>
          {/* 基础信息卡 */}
          <Card title="基础信息" size="small">
            <Descriptions column={1} bordered size="small">
              <Descriptions.Item label="审批单">
                <Text copyable>{currentApproval.approval_id}</Text>
              </Descriptions.Item>
              <Descriptions.Item label="任务">
                <Text copyable>{currentApproval.task_id}</Text>
              </Descriptions.Item>
              <Descriptions.Item label="状态">
                {currentApproval.status}
              </Descriptions.Item>
              <Descriptions.Item label="当前层级">
                Level {currentApproval.current_level}
              </Descriptions.Item>
              <Descriptions.Item label="最大层级">
                Level {currentApproval.max_level}
              </Descriptions.Item>
              <Descriptions.Item label="来源">
                {currentApproval.source}
              </Descriptions.Item>
              <Descriptions.Item label="风险等级">
                {currentApproval.risk_level}
              </Descriptions.Item>
              {currentApproval.expires_at && (
                <Descriptions.Item label="过期时间">
                  {formatDateTime(currentApproval.expires_at)}
                </Descriptions.Item>
              )}
              <Descriptions.Item label="创建时间">
                {formatDateTime(currentApproval.created_at)}
              </Descriptions.Item>
            </Descriptions>
          </Card>

          {/* 决策区 */}
          <Card title="审批决策" size="small" style={{ marginTop: 16 }}>
            <TextArea
              placeholder="请输入审批原因（驳回时必填）"
              maxLength={500}
              showCount
              rows={4}
              value={comment}
              onChange={(e) => setComment(e.target.value)}
            />
            <div style={{ marginTop: 16, display: 'flex', gap: 8 }}>
              <Button
                type="primary"
                onClick={handleApprove}
                disabled={isOperationDisabled}
                loading={approveMutation.isPending}
              >
                通过
              </Button>
              <Button
                danger
                onClick={handleReject}
                disabled={isOperationDisabled}
                loading={rejectMutation.isPending}
              >
                驳回
              </Button>
              <Button
                onClick={handleEscalate}
                disabled={cannotEscalate}
                loading={escalateMutation.isPending}
              >
                升级
              </Button>
            </div>
          </Card>

          {/* 时间线 */}
          <Card title="审批动作" size="small" style={{ marginTop: 16 }}>
            <ApprovalTimeline actions={currentApproval.actions || []} />
          </Card>
        </>
      )}
    </Drawer>
  )
}