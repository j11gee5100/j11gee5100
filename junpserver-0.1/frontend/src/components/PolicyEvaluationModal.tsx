import { useEffect } from 'react'
import { Modal, Spin, Alert, Typography } from 'antd'
import { CheckCircleOutlined, StopOutlined } from '@ant-design/icons'
import { useEvaluatePolicy } from '../hooks/usePolicies'
import type { PolicyEvaluationResponse } from '../types/policy'
import RiskBadge from './RiskBadge'

interface PolicyEvaluationModalProps {
  open: boolean
  command: string
  commandTemplateId?: string
  requestedRiskLevel?: string
  onClose: () => void
  onEvaluated?: (result: PolicyEvaluationResponse) => void
}

/**
 * PolicyEvaluationModal - Strategy evaluation preview dialog
 *
 * Features:
 * - Auto-triggers evaluation when opened
 * - Shows allowed/block status with icons
 * - Displays block_reason and matched_rules when blocked
 * - Uses RiskBadge for final_risk_level display
 * - Shows approval_required indicator
 */
export default function PolicyEvaluationModal({
  open,
  command,
  commandTemplateId,
  requestedRiskLevel,
  onClose,
  onEvaluated,
}: PolicyEvaluationModalProps) {
  const { mutate, isPending, isError, error, data } = useEvaluatePolicy()

  // Trigger evaluation when modal opens
  useEffect(() => {
    if (open) {
      mutate({
        command,
        command_template_id: commandTemplateId,
        requested_risk_level: requestedRiskLevel as 'low' | 'medium' | 'high',
      })
    }
  }, [open, command, commandTemplateId, requestedRiskLevel, mutate])

  // Call onEvaluated when evaluation completes successfully
  useEffect(() => {
    if (data && onEvaluated) {
      onEvaluated(data)
    }
  }, [data, onEvaluated])

  return (
    <Modal
      title="策略评估预览"
      open={open}
      onCancel={onClose}
      footer={<button onClick={onClose}>关闭</button>}
      width={500}
    >
      {isPending && (
        <div style={{ textAlign: 'center', padding: '40px 0' }}>
          <Spin size="large" />
          <Typography.Text type="secondary" style={{ marginTop: 16, display: 'block' }}>
            正在评估策略...
          </Typography.Text>
        </div>
      )}

      {isError && (
        <Alert type="error" message="评估失败" description={error?.message || '未知错误'} />
      )}

      {data && !isPending && (
        <div>
          {/* Status indicator */}
          <div style={{ marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
            {data.allowed ? (
              <>
                <CheckCircleOutlined style={{ fontSize: 24, color: '#52c41a' }} />
                <Typography.Text strong style={{ color: '#52c41a' }}>
                  允许执行
                </Typography.Text>
              </>
            ) : (
              <>
                <StopOutlined style={{ fontSize: 24, color: '#ff4d4f' }} />
                <Typography.Text strong style={{ color: '#ff4d4f' }}>
                  被拦截
                </Typography.Text>
              </>
            )}
          </div>

          {/* Block reason and matched rules */}
          {data.allowed === false && (
            <>
              {data.block_reason && (
                <Alert
                  type="error"
                  message="拦截原因"
                  description={data.block_reason}
                  style={{ marginBottom: 12 }}
                />
              )}
              {data.matched_rules && data.matched_rules.length > 0 && (
                <>
                  <Typography.Text strong style={{ marginTop: 8, marginBottom: 4 }}>
                    匹配规则:
                  </Typography.Text>
                  <ul style={{ margin: 0, paddingLeft: '20px' }}>
                    {data.matched_rules.map((rule, idx) => (
                      <li key={idx}>
                        <Typography.Text>
                          {rule.pattern || rule.rule_id || rule.source || JSON.stringify(rule)}
                        </Typography.Text>
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </>
          )}

          {/* Risk level display */}
          <div style={{ marginBottom: 12 }}>
            <Typography.Text style={{ marginRight: 8 }}>风险等级:</Typography.Text>
            <RiskBadge level={data.final_risk_level as 'low' | 'medium' | 'high'} />
          </div>

          {/* Approval required indicator */}
          {data.approval_required && (
            <Alert type="warning" message="需要审批" description="此命令需要经过审批流程后才能执行" />
          )}
        </div>
      )}
    </Modal>
  )
}