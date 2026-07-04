import { Card, Switch, Tag, Typography } from 'antd'
import type { BlacklistRule } from '../types/policy'

interface BlacklistCardProps {
  rule: BlacklistRule
  onToggleEnabled: (id: string, enabled: boolean) => void
  onEdit?: (rule: BlacklistRule) => void
}

const { Text } = Typography

/**
 * BlacklistCard displays a blacklist rule with enable/disable toggle
 *
 * Card structure:
 * - Top-right: Switch for enable/disable
 * - Content: pattern (monospace), hard_block label, enabled status
 *
 * Hard block: "硬拦截" (error/red)
 * Soft block: "软拦截" (processing/blue)
 */
export default function BlacklistCard({
  rule,
  onToggleEnabled,
  onEdit,
}: BlacklistCardProps) {
  const handleToggleChange = (checked: boolean) => {
    onToggleEnabled(rule.rule_id, checked)
  }

  const handleCardClick = () => {
    if (onEdit) {
      onEdit(rule)
    }
  }

  const statusText = rule.enabled ? '已启用' : '已停用'

  // Hard block = error color (red), Soft block = processing color (blue)
  const blockLabel = rule.hard_block ? '硬拦截' : '软拦截'
  const blockColor = rule.hard_block ? 'error' : 'processing'

  return (
    <Card
      role="article"
      hoverable
      style={{
        border: '1px solid #f0f0f0',
        cursor: onEdit ? 'pointer' : 'default',
      }}
      onClick={handleCardClick}
      extra={
        <Switch
          checked={rule.enabled}
          onChange={handleToggleChange}
          onClick={(_, e) => e.stopPropagation()}
        />
      }
    >
      {/* First row: pattern (monospace) */}
      <div style={{ marginBottom: 8 }}>
        <Text style={{ fontFamily: 'monospace', fontSize: 14 }}>
          {rule.pattern}
        </Text>
      </div>

      {/* Second row: Hard/soft block label */}
      <div style={{ marginBottom: 8 }}>
        <Tag color={blockColor} style={{ borderRadius: 0 }}>
          {blockLabel}
        </Tag>
      </div>

      {/* Third row: enabled status text */}
      <Text type={rule.enabled ? 'success' : 'secondary'}>
        {statusText}
      </Text>
    </Card>
  )
}