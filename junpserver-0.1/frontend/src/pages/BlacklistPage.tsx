import { useState } from 'react'
import { Typography, Button, Skeleton, Alert } from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import { useBlacklist, useUpdateBlacklistRule } from '../hooks/usePolicies'
import BlacklistCard from '../components/BlacklistCard'
import BlacklistFormModal from '../components/BlacklistFormModal'
import type { BlacklistRule } from '../types/policy'

const { Title, Text } = Typography

/**
 * BlacklistPage - Command blacklist management page
 *
 * Features:
 * - Card grid display of blacklist rules
 * - New rule button opens modal form
 * - Enable/disable toggle on cards
 * - Edit rule by clicking card
 */
export default function BlacklistPage() {
  const [formModalOpen, setFormModalOpen] = useState(false)
  const [editRule, setEditRule] = useState<BlacklistRule | undefined>()
  const [formMode, setFormMode] = useState<'create' | 'edit'>('create')

  const { data: rules, isLoading, isError, error, refetch } = useBlacklist()
  const updateRule = useUpdateBlacklistRule()

  // Handle enable/disable toggle
  const handleToggleEnabled = (ruleId: string, enabled: boolean) => {
    updateRule.mutate({
      ruleId,
      payload: { enabled },
    })
  }

  // Handle card click for editing
  const handleEditRule = (rule: BlacklistRule) => {
    setEditRule(rule)
    setFormMode('edit')
    setFormModalOpen(true)
  }

  // Handle new rule creation
  const handleCreateNew = () => {
    setEditRule(undefined)
    setFormMode('create')
    setFormModalOpen(true)
  }

  return (
    <div style={{ padding: '24px' }}>
      {/* Page header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <Title level={3} style={{ margin: 0 }}>命令黑名单治理</Title>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={handleCreateNew}
        >
          新建规则
        </Button>
      </div>

      {/* Loading state - skeleton cards */}
      {isLoading && (
        <div data-testid="skeleton-container" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))', gap: '16px' }}>
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
      {!isLoading && !isError && rules && rules.length === 0 && (
        <div style={{ textAlign: 'center', padding: '48px 0' }}>
          <Text type="secondary">
            暂无黑名单规则，点击新建按钮创建
          </Text>
        </div>
      )}

      {/* Card grid */}
      {!isLoading && !isError && rules && rules.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '16px' }}>
          {rules.map((rule) => (
            <BlacklistCard
              key={rule.rule_id}
              rule={rule}
              onToggleEnabled={handleToggleEnabled}
              onEdit={handleEditRule}
            />
          ))}
        </div>
      )}

      {/* Create/Edit modal */}
      <BlacklistFormModal
        open={formModalOpen}
        mode={formMode}
        initialValues={editRule}
        onClose={() => setFormModalOpen(false)}
        onSuccess={() => {
          setFormModalOpen(false)
          refetch()
        }}
      />
    </div>
  )
}