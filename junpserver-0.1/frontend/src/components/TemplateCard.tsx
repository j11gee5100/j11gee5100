import { Card, Switch, Typography, Button, Popconfirm } from 'antd'
import { DeleteOutlined } from '@ant-design/icons'
import type { Template } from '../types/template'
import RiskBadge from './RiskBadge'

interface TemplateCardProps {
  template: Template
  onToggleEnabled: (id: string, enabled: boolean) => void
  onEdit?: (template: Template) => void
  onDelete?: (template: Template) => void
}

const { Text, Title } = Typography

/**
 * TemplateCard displays a command template with enable/disable toggle
 *
 * Card structure per D-01/D-03/D-04:
 * - Top-right: Switch for enable/disable
 * - Content: template_id (gray), name, risk level badge, enabled status
 */
export default function TemplateCard({
  template,
  onToggleEnabled,
  onEdit,
  onDelete,
}: TemplateCardProps) {
  const handleToggleChange = (checked: boolean) => {
    onToggleEnabled(template.template_id, checked)
  }

  const handleCardClick = () => {
    if (onEdit) {
      onEdit(template)
    }
  }

  const handleDelete = () => {
    if (onDelete) {
      onDelete(template)
    }
  }

  const statusText = template.enabled ? '已启用' : '已停用'

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
        <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
          <Switch
            checked={template.enabled}
            onChange={handleToggleChange}
            onClick={(_, e) => e.stopPropagation()}
          />
          {onDelete && (
            <Popconfirm
              title="删除模板"
              description="确认删除此模板吗？"
              onConfirm={handleDelete}
              okText="确认"
              cancelText="取消"
            >
              <Button
                type="text"
                danger
                icon={<DeleteOutlined />}
                onClick={(e) => e.stopPropagation()}
              />
            </Popconfirm>
          )}
        </div>
      }
    >
      {/* First row: template_id (gray) + name */}
      <div style={{ marginBottom: 8 }}>
        <Text type="secondary" style={{ fontSize: 12 }}>
          {template.template_id}
        </Text>
      </div>

      <Title level={5} style={{ margin: '0 0 8px 0' }}>
        {template.name}
      </Title>

      {/* Second row: RiskBadge */}
      <div style={{ marginBottom: 8 }}>
        <RiskBadge level={template.risk_level} />
      </div>

      {/* Third row: enabled status text */}
      <Text type={template.enabled ? 'success' : 'secondary'}>
        {statusText}
      </Text>
    </Card>
  )
}