import { useState, useEffect } from 'react'
import { Modal, Form, Input, Select, Typography, Divider, Button } from 'antd'
import { EyeOutlined } from '@ant-design/icons'
import { useCreateTemplate, useUpdateTemplate } from '../hooks/useTemplates'
import PolicyEvaluationModal from './PolicyEvaluationModal'
import type { Template } from '../types/template'
import type { PolicyEvaluationResponse } from '../types/policy'

interface TemplateFormModalProps {
  open: boolean
  mode: 'create' | 'edit'
  initialValues?: Template
  onClose: () => void
  onSuccess: () => void
}

const { Text } = Typography

/**
 * TemplateFormModal - Create/edit template form with policy preview
 *
 * Per D-05/D-08:
 * - Modal-based form (not separate page)
 * - Two-section layout: basic info (top) and command area (bottom)
 *
 * Per D-06: Command field uses single-line Input
 * Per D-07: Risk level as Select dropdown
 * Per D-09: Preview button triggers policy evaluation
 */
export default function TemplateFormModal({
  open,
  mode,
  initialValues,
  onClose,
  onSuccess,
}: TemplateFormModalProps) {
  const [form] = Form.useForm()
  const [previewOpen, setPreviewOpen] = useState(false)
  const [evalResult, setEvalResult] = useState<PolicyEvaluationResponse | null>(null)
  const createTemplate = useCreateTemplate()
  const updateTemplate = useUpdateTemplate()

  // Populate form values when modal opens or initialValues changes
  useEffect(() => {
    if (open) {
      if (initialValues && mode === 'edit') {
        form.setFieldsValue(initialValues)
      } else {
        form.resetFields()
      }
      // Reset evaluation result when modal opens
      setEvalResult(null)
    }
  }, [open, initialValues, mode, form])

  // Reset evaluation result when command changes
  useEffect(() => {
    setEvalResult(null)
  }, [form.getFieldValue('command')])

  // Handle form submission
  const handleSubmit = async () => {
    try {
      const values = await form.validateFields()

      if (mode === 'create') {
        await createTemplate.mutateAsync({
          template_id: values.template_id,
          name: values.name,
          description: values.description,
          command: values.command,
          risk_level: values.risk_level,
          enabled: true,
        })
      } else {
        await updateTemplate.mutateAsync({
          templateId: initialValues!.template_id,
          payload: {
            name: values.name,
            description: values.description,
            command: values.command,
            risk_level: values.risk_level,
          },
        })
      }

      onSuccess()
      onClose()
    } catch {
      // Form validation error or API error
    }
  }

  // Handle preview button click
  const handlePreview = () => {
    setPreviewOpen(true)
  }

  // Handle policy evaluation result
  const handleEvaluated = (result: PolicyEvaluationResponse) => {
    setEvalResult(result)
  }

  // Check if submit should be blocked
  const isSubmitBlocked = evalResult && evalResult.allowed === false
  const hasNotEvaluated = evalResult === null // 未进行策略评估

  // Get current command value for preview
  const currentCommand = form.getFieldValue('command') || ''
  const currentRiskLevel = form.getFieldValue('risk_level') || 'low'

  const title = mode === 'create' ? '新建模板' : '编辑模板'

  return (
    <>
      <Modal
        title={title}
        open={open}
        onCancel={onClose}
        width={600}
        destroyOnClose
        footer={
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            {isSubmitBlocked && (
              <Text type="danger" style={{ fontSize: 12 }}>
                命令被策略拦截，无法创建模板
              </Text>
            )}
            {hasNotEvaluated && (
              <Text type="warning" style={{ fontSize: 12 }}>
                请先点击"预览"按钮进行策略评估
              </Text>
            )}
            <div style={{ display: 'flex', gap: 8 }}>
              <Button onClick={onClose}>取消</Button>
              <Button
                type="primary"
                onClick={handleSubmit}
                loading={createTemplate.isPending || updateTemplate.isPending}
                disabled={isSubmitBlocked || hasNotEvaluated}
              >
                {mode === 'create' ? '创建' : '保存'}
              </Button>
            </div>
          </div>
        }
      >
        <Form
          form={form}
          layout="vertical"
          initialValues={{
            risk_level: 'low',
          }}
        >
          {/* Upper section: Basic Info */}
          <Text strong style={{ fontSize: 14 }}>基础信息</Text>
          <Divider style={{ margin: '8px 0 16px 0' }} />

          <Form.Item
            label="模板ID"
            name="template_id"
            rules={[{ required: true, message: '请输入模板ID' }]}
          >
            <Input
              placeholder="输入唯一标识符"
              disabled={mode === 'edit'}
            />
          </Form.Item>

          <Form.Item
            label="名称"
            name="name"
            rules={[{ required: true, message: '请输入名称' }]}
          >
            <Input placeholder="输入模板名称" />
          </Form.Item>

          <Form.Item
            label="描述"
            name="description"
          >
            <Input.TextArea
              placeholder="输入描述（可选）"
              rows={2}
            />
          </Form.Item>

          <Form.Item
            label="风险等级"
            name="risk_level"
            rules={[{ required: true, message: '请选择风险等级' }]}
          >
            <Select placeholder="选择风险等级">
              <Select.Option value="low">低风险</Select.Option>
              <Select.Option value="medium">中风险</Select.Option>
              <Select.Option value="high">高风险</Select.Option>
            </Select>
          </Form.Item>

          {/* Lower section: Command Area */}
          <Text strong style={{ fontSize: 14, marginTop: 16 }}>命令配置</Text>
          <Divider style={{ margin: '8px 0 16px 0' }} />

          <Form.Item
            label="命令"
            name="command"
            rules={[{ required: true, message: '请输入执行命令' }]}
          >
            <Input placeholder="输入执行命令" />
          </Form.Item>

          {/* Preview button per D-09 */}
          <Button
            icon={<EyeOutlined />}
            onClick={handlePreview}
            style={{ marginBottom: 16 }}
          >
            预览
          </Button>
        </Form>
      </Modal>

      {/* Policy Evaluation Preview Modal */}
      <PolicyEvaluationModal
        open={previewOpen}
        command={currentCommand}
        requestedRiskLevel={currentRiskLevel}
        onClose={() => setPreviewOpen(false)}
        onEvaluated={handleEvaluated}
      />
    </>
  )
}