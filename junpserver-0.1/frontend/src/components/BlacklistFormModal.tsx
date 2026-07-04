import { useState, useEffect } from 'react'
import { Modal, Form, Input, Switch, Typography, Button } from 'antd'
import { EyeOutlined } from '@ant-design/icons'
import { useCreateBlacklistRule, useUpdateBlacklistRule } from '../hooks/usePolicies'
import PolicyEvaluationModal from './PolicyEvaluationModal'
import type { BlacklistRule } from '../types/policy'

interface BlacklistFormModalProps {
  open: boolean
  mode: 'create' | 'edit'
  initialValues?: BlacklistRule
  onClose: () => void
  onSuccess: () => void
}

const { Text } = Typography

/**
 * BlacklistFormModal - Create/edit blacklist rule form with policy preview
 *
 * Features:
 * - Modal-based form for creating/editing blacklist rules
 * - Pattern input (command regex) with monospace font
 * - hard_block switch for interception type
 * - enabled switch for rule activation
 * - Preview button to test rule against policy evaluation
 */
export default function BlacklistFormModal({
  open,
  mode,
  initialValues,
  onClose,
  onSuccess,
}: BlacklistFormModalProps) {
  const [form] = Form.useForm()
  const [previewOpen, setPreviewOpen] = useState(false)
  const createRule = useCreateBlacklistRule()
  const updateRule = useUpdateBlacklistRule()

  // Populate form values when modal opens or initialValues changes
  useEffect(() => {
    if (open) {
      if (initialValues && mode === 'edit') {
        form.setFieldsValue({
          pattern: initialValues.pattern,
          hard_block: initialValues.hard_block,
          enabled: initialValues.enabled,
        })
      } else {
        form.resetFields()
      }
    }
  }, [open, initialValues, mode, form])

  // Handle form submission
  const handleSubmit = async () => {
    try {
      const values = await form.validateFields()

      if (mode === 'create') {
        await createRule.mutateAsync({
          pattern: values.pattern,
          hard_block: values.hard_block,
          enabled: values.enabled ?? true,
        })
      } else {
        await updateRule.mutateAsync({
          ruleId: initialValues!.rule_id,
          payload: {
            pattern: values.pattern,
            hard_block: values.hard_block,
            enabled: values.enabled,
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

  // Get current pattern value for preview
  const currentPattern = form.getFieldValue('pattern') || ''

  const title = mode === 'create' ? '新建规则' : '编辑规则'

  return (
    <>
      <Modal
        title={title}
        open={open}
        onCancel={onClose}
        width={500}
        destroyOnClose
        footer={
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
            <Button onClick={onClose}>取消</Button>
            <Button
              type="primary"
              onClick={handleSubmit}
              loading={createRule.isPending || updateRule.isPending}
            >
              {mode === 'create' ? '创建' : '保存'}
            </Button>
          </div>
        }
      >
        <Form
          form={form}
          layout="vertical"
          initialValues={{
            hard_block: true,
            enabled: true,
          }}
        >
          {/* Pattern input */}
          <Form.Item
            label="命令模式"
            name="pattern"
            rules={[{ required: true, message: '请输入命令模式' }]}
          >
            <Input
              placeholder="输入命令模式 (如 rm -rf *)"
              style={{ fontFamily: 'monospace' }}
            />
          </Form.Item>

          {/* Preview button */}
          <Button
            icon={<EyeOutlined />}
            onClick={handlePreview}
            style={{ marginBottom: 16 }}
          >
            测试预览
          </Button>

          {/* hard_block switch */}
          <Form.Item
            label="拦截类型"
            name="hard_block"
          >
            <Switch
              checkedChildren="硬拦截"
              unCheckedChildren="软拦截"
            />
          </Form.Item>
          <Text type="secondary" style={{ fontSize: 12, marginBottom: 16, display: 'block' }}>
            硬拦截将直接禁止执行，软拦截需要审批
          </Text>

          {/* enabled switch */}
          <Form.Item
            label="启用状态"
            name="enabled"
          >
            <Switch
              checkedChildren="启用"
              unCheckedChildren="停用"
            />
          </Form.Item>
        </Form>
      </Modal>

      {/* Policy Evaluation Preview Modal */}
      <PolicyEvaluationModal
        open={previewOpen}
        command={currentPattern}
        onClose={() => setPreviewOpen(false)}
      />
    </>
  )
}