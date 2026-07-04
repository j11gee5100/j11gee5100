import { useState } from 'react'
import { Typography, Button, Skeleton, Spin, message } from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import { useTemplatesInfinite, useUpdateTemplate, useDeleteTemplate } from '../hooks/useTemplates'
import TemplateCard from '../components/TemplateCard'
import TemplateFormModal from '../components/TemplateFormModal'
import type { Template } from '../types/template'

const { Title } = Typography

/**
 * TemplateCenterPage - Command template management hub
 *
 * Per D-01: Card-based layout with grid
 * Per D-02: Infinite scroll loading via useInfiniteQuery
 * Per D-03: Enable/disable toggle on each card
 *
 * Features:
 * - Card grid display of templates
 * - New button opens modal form
 * - Enable/disable toggle on cards
 * - Infinite scroll with "load more" backup
 */
export default function TemplateCenterPage() {
  const [formModalOpen, setFormModalOpen] = useState(false)
  const [editTemplate, setEditTemplate] = useState<Template | undefined>()
  const [formMode, setFormMode] = useState<'create' | 'edit'>('create')

  const {
    data,
    isLoading,
    isFetchingNextPage,
    hasNextPage,
    fetchNextPage,
    refetch,
  } = useTemplatesInfinite()

  const updateTemplate = useUpdateTemplate()
  const deleteTemplate = useDeleteTemplate()

  // Handle enable/disable toggle
  const handleToggleEnabled = (templateId: string, enabled: boolean) => {
    updateTemplate.mutate({
      templateId,
      payload: { enabled },
    })
  }

  // Handle card click for editing
  const handleEditTemplate = (template: Template) => {
    setEditTemplate(template)
    setFormMode('edit')
    setFormModalOpen(true)
  }

  // Handle new template creation
  const handleCreateNew = () => {
    setEditTemplate(undefined)
    setFormMode('create')
    setFormModalOpen(true)
  }

  // Handle template deletion
  const handleDeleteTemplate = (template: Template) => {
    deleteTemplate.mutate(
      { templateId: template.template_id },
      {
        onSuccess: () => {
          message.success('模板已删除')
          refetch()
        },
        onError: (err: any) => {
          message.error(`删除失败：${err?.response?.data?.detail || err?.message || '未知错误'}`)
        },
      }
    )
  }

  // Flatten paginated data into single array
  const templates = data?.pages.flatMap((page) => page.items) ?? []

  return (
    <div style={{ padding: '24px' }}>
      {/* Page header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <Title level={3} style={{ margin: 0 }}>模板中心</Title>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={handleCreateNew}
        >
          新建模板
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

      {/* Empty state */}
      {!isLoading && templates.length === 0 && (
        <div style={{ textAlign: 'center', padding: '48px 0' }}>
          <Typography.Text type="secondary">
            暂无模板，点击新建按钮创建
          </Typography.Text>
        </div>
      )}

      {/* Card grid */}
      {!isLoading && templates.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '16px' }}>
          {templates.map((template) => (
            <TemplateCard
              key={template.template_id}
              template={template}
              onToggleEnabled={handleToggleEnabled}
              onEdit={handleEditTemplate}
              onDelete={handleDeleteTemplate}
            />
          ))}
        </div>
      )}

      {/* Load more button */}
      {!isLoading && hasNextPage && (
        <div style={{ textAlign: 'center', marginTop: '24px' }}>
          <Button
            onClick={() => fetchNextPage()}
            loading={isFetchingNextPage}
          >
            加载更多
          </Button>
        </div>
      )}

      {/* Bottom loading indicator */}
      {isFetchingNextPage && (
        <div style={{ textAlign: 'center', marginTop: '16px' }}>
          <Spin />
        </div>
      )}

      {/* Create/Edit modal */}
      <TemplateFormModal
        open={formModalOpen}
        mode={formMode}
        initialValues={editTemplate}
        onClose={() => setFormModalOpen(false)}
        onSuccess={() => {
          setFormModalOpen(false)
          refetch()
        }}
      />
    </div>
  )
}