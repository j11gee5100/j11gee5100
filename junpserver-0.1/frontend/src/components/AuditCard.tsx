import { Card, Tag, Typography, Tooltip } from 'antd'
import type { AuditRecord } from '../types/governance'
import { formatRelativeTime, formatDateTime } from '../utils/formatters'

interface AuditCardProps {
  record: AuditRecord
  onViewDetail: (record: AuditRecord) => void
}

const { Text } = Typography

/**
 * Gets the color for action tag based on action type
 * - create: success (green)
 * - update: processing (blue)
 * - delete: error (red)
 * - enable/disable: default
 */
function getActionColor(action: string): string {
  switch (action) {
    case 'create':
      return 'success'
    case 'update':
      return 'processing'
    case 'delete':
      return 'error'
    case 'enable':
      return 'success'
    case 'disable':
      return 'warning'
    default:
      return 'default'
  }
}

/**
 * AuditCard displays an audit record in card format
 *
 * Card structure per D-12:
 * - Row 1: entity_type (Tag) + entity_id (gray)
 * - Row 2: action (Tag with color coding)
 * - Row 3: operator_id
 * - Row 4: created_at (relative time with tooltip)
 *
 * Interaction:
 * - Hover: shadow effect
 * - Click: triggers onViewDetail callback
 */
export default function AuditCard({ record, onViewDetail }: AuditCardProps) {
  const handleClick = () => {
    onViewDetail(record)
  }

  return (
    <Card
      role="article"
      hoverable
      style={{
        border: '1px solid #f0f0f0',
        cursor: 'pointer',
      }}
      onClick={handleClick}
    >
      {/* First row: entity_type (Tag) + entity_id (gray small text) */}
      <div style={{ marginBottom: 8, display: 'flex', alignItems: 'center', gap: 8 }}>
        <Tag>{record.entity_type}</Tag>
        <Text type="secondary" style={{ fontSize: 12 }}>
          {record.entity_id}
        </Text>
      </div>

      {/* Second row: action with color-coded Tag */}
      <div style={{ marginBottom: 8 }}>
        <Tag color={getActionColor(record.action)}>{record.action}</Tag>
      </div>

      {/* Third row: operator_id */}
      <div style={{ marginBottom: 8 }}>
        <Text type="secondary">操作者: </Text>
        <Text>{record.operator_id}</Text>
      </div>

      {/* Fourth row: created_at with relative time and tooltip */}
      <Tooltip title={formatDateTime(record.created_at)}>
        <Text type="secondary" style={{ fontSize: 12 }}>
          {formatRelativeTime(record.created_at)}
        </Text>
      </Tooltip>
    </Card>
  )
}