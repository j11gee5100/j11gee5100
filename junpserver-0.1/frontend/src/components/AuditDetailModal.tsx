import { Modal, Descriptions, Card, Typography } from 'antd'
import type { AuditRecord } from '../types/governance'
import { formatDateTime } from '../utils/formatters'

interface AuditDetailModalProps {
  open: boolean
  record?: AuditRecord
  onClose: () => void
}

const { Text } = Typography

/**
 * AuditDetailModal displays full details of an audit record
 *
 * Modal structure per D-15:
 * - Title: "审计详情"
 * - Width: 600px
 * - Content:
 *   - Basic info section (Descriptions component)
 *   - JSON detail section (Card with pre-formatted JSON)
 */
export default function AuditDetailModal({
  open,
  record,
  onClose,
}: AuditDetailModalProps) {
  if (!open || !record) {
    return null
  }

  return (
    <Modal
      open={open}
      title="审计详情"
      onCancel={onClose}
      footer={null}
      width={600}
    >
      {/* Basic info section */}
      <Descriptions column={1} bordered size="small">
        <Descriptions.Item label="审计ID">
          <Text copyable>{record.audit_id}</Text>
        </Descriptions.Item>
        <Descriptions.Item label="实体类型">
          {record.entity_type}
        </Descriptions.Item>
        <Descriptions.Item label="实体ID">
          <Text copyable>{record.entity_id}</Text>
        </Descriptions.Item>
        <Descriptions.Item label="操作类型">
          {record.action}
        </Descriptions.Item>
        <Descriptions.Item label="操作者">
          {record.operator_id}
        </Descriptions.Item>
        {record.source_ip && (
          <Descriptions.Item label="来源IP">
            {record.source_ip}
          </Descriptions.Item>
        )}
        <Descriptions.Item label="操作时间">
          {formatDateTime(record.created_at)}
        </Descriptions.Item>
      </Descriptions>

      {/* JSON detail section */}
      <Card
        title="变更详情 (detail)"
        size="small"
        style={{ marginTop: 16 }}
      >
        <pre
          style={{
            margin: 0,
            padding: 12,
            background: '#f5f5f5',
            borderRadius: 4,
            fontSize: 12,
            overflow: 'auto',
            maxHeight: 300,
          }}
        >
          {JSON.stringify(record.detail, null, 2)}
        </pre>
      </Card>
    </Modal>
  )
}