import { useState } from 'react'
import { Typography, Select, Input, Button, Skeleton, Alert, Card } from 'antd'
import { SearchOutlined, ReloadOutlined } from '@ant-design/icons'
import { useAuditLogs } from '../hooks/useGovernance'
import AuditCard from '../components/AuditCard'
import AuditDetailModal from '../components/AuditDetailModal'
import type { AuditRecord, AuditFilters, TimeRange } from '../types/governance'

const { Title, Text } = Typography

/**
 * Time range options for audit logs filter
 * Preset options per D-16: 1h, 24h, 7d
 */
const timeRangeOptions: { value: TimeRange; label: string }[] = [
  { value: '1h', label: '最近1小时' },
  { value: '24h', label: '最近24小时' },
  { value: '7d', label: '最近7天' },
]

/**
 * Entity type options for filter
 */
const entityTypeOptions: { value: string; label: string }[] = [
  { value: 'template', label: '模板' },
  { value: 'blacklist_rule', label: '黑名单规则' },
  { value: 'task', label: '任务' },
  { value: 'policy', label: '策略' },
]

/**
 * Action type options for filter
 */
const actionOptions: { value: string; label: string }[] = [
  { value: 'create', label: '创建' },
  { value: 'update', label: '更新' },
  { value: 'delete', label: '删除' },
  { value: 'enable', label: '启用' },
  { value: 'disable', label: '停用' },
]

/**
 * GovernanceAuditPage - Audit log management page
 *
 * Features per D-12~D-16:
 * - Independent filter area (entity_type, action, operator_id, time_range)
 * - Audit record card list with grid layout
 * - Time range preset selection (1h/24h/7d)
 * - JSON detail modal on card click
 * - Auto-refresh on filter changes
 */
export default function GovernanceAuditPage() {
  // Filter state
  const [entityType, setEntityType] = useState<string | undefined>()
  const [action, setAction] = useState<string | undefined>()
  const [operatorId, setOperatorId] = useState<string | undefined>()
  const [timeRange, setTimeRange] = useState<TimeRange | undefined>('24h')

  // Active filters for query
  const [activeFilters, setActiveFilters] = useState<AuditFilters>({
    time_range: '24h',
  })

  // Modal state
  const [detailModalOpen, setDetailModalOpen] = useState(false)
  const [selectedRecord, setSelectedRecord] = useState<AuditRecord | undefined>()

  // Fetch audit logs with active filters
  const { data, isLoading, isError, error, refetch } = useAuditLogs(activeFilters)

  // Handle query button click
  const handleQuery = () => {
    const filters: AuditFilters = {}
    if (entityType) filters.entity_type = entityType
    if (action) filters.action = action
    if (operatorId) filters.operator_id = operatorId
    if (timeRange) filters.time_range = timeRange
    setActiveFilters(filters)
  }

  // Handle reset button click
  const handleReset = () => {
    setEntityType(undefined)
    setAction(undefined)
    setOperatorId(undefined)
    setTimeRange('24h')
    setActiveFilters({ time_range: '24h' })
  }

  // Handle card click for detail view
  const handleViewDetail = (record: AuditRecord) => {
    setSelectedRecord(record)
    setDetailModalOpen(true)
  }

  // Handle modal close
  const handleModalClose = () => {
    setDetailModalOpen(false)
    setSelectedRecord(undefined)
  }

  return (
    <div style={{ padding: '24px' }}>
      {/* Page header */}
      <Title level={3} style={{ marginBottom: '24px' }}>治理审计日志</Title>

      {/* Independent filter area per D-13/D-14 */}
      <Card style={{ marginBottom: '24px' }}>
        <div style={{ display: 'flex', gap: '16px', alignItems: 'center', flexWrap: 'wrap' }}>
          {/* Entity type filter */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Text>实体类型:</Text>
            <Select
              allowClear
              placeholder="选择实体类型"
              options={entityTypeOptions}
              value={entityType}
              onChange={setEntityType}
              style={{ width: 120 }}
            />
          </div>

          {/* Action filter */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Text>操作类型:</Text>
            <Select
              allowClear
              placeholder="选择操作类型"
              options={actionOptions}
              value={action}
              onChange={setAction}
              style={{ width: 120 }}
            />
          </div>

          {/* Operator ID filter */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Text>操作者:</Text>
            <Input
              placeholder="输入操作者ID"
              value={operatorId}
              onChange={(e) => setOperatorId(e.target.value)}
              style={{ width: 150 }}
            />
          </div>

          {/* Time range filter per D-16 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Text>时间范围:</Text>
            <Select
              placeholder="选择时间范围"
              options={timeRangeOptions}
              value={timeRange}
              onChange={setTimeRange}
              style={{ width: 140 }}
            />
          </div>

          {/* Query and Reset buttons */}
          <Button
            type="primary"
            icon={<SearchOutlined />}
            onClick={handleQuery}
          >
            查询
          </Button>
          <Button onClick={handleReset}>
            重置
          </Button>
          <Button
            icon={<ReloadOutlined />}
            onClick={() => refetch()}
          >
            刷新
          </Button>
        </div>
      </Card>

      {/* Loading state - skeleton cards */}
      {isLoading && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))', gap: '16px' }}>
          {[1, 2, 3, 4].map((i) => (
            <div key={i} style={{ border: '1px solid #f0f0f0', borderRadius: '8px', padding: '16px' }}>
              <Skeleton active paragraph={{ rows: 3 }} />
            </div>
          ))}
        </div>
      )}

      {/* Error state */}
      {isError && (
        <Alert
          type="error"
          message="加载失败"
          description={error?.message || '未知错误'}
          action={
            <Button onClick={() => refetch()}>
              重试
            </Button>
          }
        />
      )}

      {/* Empty state */}
      {!isLoading && !isError && data && data.items.length === 0 && (
        <div style={{ textAlign: 'center', padding: '48px 0' }}>
          <Text type="secondary">
            暂无审计日志记录
          </Text>
        </div>
      )}

      {/* Card list per D-12 */}
      {!isLoading && !isError && data && data.items.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '16px' }}>
          {data.items.map((record) => (
            <AuditCard
              key={record.audit_id}
              record={record}
              onViewDetail={handleViewDetail}
            />
          ))}
        </div>
      )}

      {/* Total count */}
      {!isLoading && !isError && data && data.total > 0 && (
        <div style={{ marginTop: '16px' }}>
          <Text type="secondary">
            共 {data.total} 条记录
          </Text>
        </div>
      )}

      {/* Detail modal */}
      <AuditDetailModal
        open={detailModalOpen}
        record={selectedRecord}
        onClose={handleModalClose}
      />
    </div>
  )
}