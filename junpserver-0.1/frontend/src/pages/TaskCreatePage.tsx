import { useState, useEffect } from 'react'
import {
  Form,
  Input,
  Select,
  Button,
  Typography,
  Card,
  Space,
  Radio,
  Divider,
  message,
  Spin,
  Alert,
} from 'antd'
import { SafetyOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { useTemplates } from '../hooks/useTemplates'
import { useAssets } from '../hooks/useAssets'
import { useSystemUsersByAsset } from '../hooks/useSystemUsers'
import { useCreateTask } from '../hooks/useTasks'
import RiskBadge from '../components/RiskBadge'
import PolicyEvaluationModal from '../components/PolicyEvaluationModal'
import RiskConfirmModal from '../components/RiskConfirmModal'
import type { TaskCreateRequest } from '../types/task'
import type { PolicyEvaluationResponse } from '../types/policy'

const { Title, Text } = Typography

/**
 * TaskCreatePage - 任务创建页面
 *
 * 功能:
 * - 支持选择模板或输入自定义命令创建任务
 * - 资产和系统用户选择（必填字段）
 * - 必填字段有红色星号标记
 * - 校验失败显示错误提示
 *
 * Per D-01: 支持两种任务来源：模板或自定义命令
 * Per D-02: 模板选择使用 SearchSelect 下拉组件
 * Per D-03: 选择模板后自动填充命令字段（只读）
 * Per D-04: 资产选择使用 SearchSelect 组件
 * Per D-05: 系统用户选择使用 SearchSelect 组件
 * Per D-06: 必填字段标记红色星号，校验失败显示错误提示
 */
export default function TaskCreatePage() {
  const navigate = useNavigate()
  const [form] = Form.useForm()
  const [source, setSource] = useState<'template' | 'custom'>('template')
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | undefined>()
  const [selectedAssetId, setSelectedAssetId] = useState<string | undefined>()
  const [commandPreview, setCommandPreview] = useState<string>('')

  // 策略评估相关状态
  const [evalModalOpen, setEvalModalOpen] = useState(false)
  const [evalResult, setEvalResult] = useState<PolicyEvaluationResponse | undefined>()
  const [isBlocked, setIsBlocked] = useState(false)

  // 高风险确认弹窗状态
  const [confirmModalOpen, setConfirmModalOpen] = useState(false)

  // Hooks
  const templatesQuery = useTemplates()
  const assetsQuery = useAssets()
  const systemUsersQuery = useSystemUsersByAsset(selectedAssetId)
  const createTaskMutation = useCreateTask()

  // 模板列表（过滤已启用的）
  const templates = Array.isArray(templatesQuery.data)
    ? templatesQuery.data.filter((t) => t.enabled)
    : []
  // 资产列表
  const assets = Array.isArray(assetsQuery.data) ? assetsQuery.data : []
  // 系统用户列表
  const systemUsers = Array.isArray(systemUsersQuery.data) ? systemUsersQuery.data : []

  // 当选择模板时，自动填充命令预览
  useEffect(() => {
    if (source === 'template' && selectedTemplateId) {
      const template = templates.find((t) => t.template_id === selectedTemplateId)
      if (template) {
        setCommandPreview(template.command)
        form.setFieldValue('command', template.command)
      }
    }
  }, [source, selectedTemplateId, templates, form])

  // 当切换来源时，清空对应字段
  useEffect(() => {
    if (source === 'template') {
      form.setFieldValue('command', commandPreview)
    } else {
      form.setFieldValue('command_template_id', undefined)
      setCommandPreview('')
    }
  }, [source, form])

  // 处理模板选择变化
  const handleTemplateChange = (templateId: string) => {
    setSelectedTemplateId(templateId)
    const template = templates.find((t) => t.template_id === templateId)
    if (template) {
      setCommandPreview(template.command)
      form.setFieldValue('command', template.command)
    }
  }

  // 处理资产选择变化
  const handleAssetChange = (assetId: string) => {
    setSelectedAssetId(assetId)
    form.setFieldValue('run_as_system_user_id', undefined)
  }

  // 处理自定义命令变化
  const handleCustomCommandChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setCommandPreview(e.target.value)
  }

  // 处理策略预览按钮点击
  const handlePolicyPreview = () => {
    // 检查是否有命令或模板
    if (source === 'template' && !selectedTemplateId) {
      message.warning('请先选择模板')
      return
    }
    if (source === 'custom' && !commandPreview.trim()) {
      message.warning('请先填写命令内容')
      return
    }

    setEvalModalOpen(true)
  }

  // 处理评估结果
  const handleEvaluated = (result: PolicyEvaluationResponse) => {
    setEvalResult(result)
    setIsBlocked(!result.allowed)
    if (!result.allowed) {
      message.error('命令被策略拦截，无法提交')
    } else if (result.approval_required) {
      message.info('此命令需要审批')
    }
  }

  // 执行实际提交逻辑
  const executeSubmit = async () => {
    try {
      const values = await form.validateFields()

      const payload: TaskCreateRequest = {
        target_asset_id: values.target_asset_id,
        run_as_system_user_id: values.run_as_system_user_id,
        risk_level: evalResult!.final_risk_level as 'low' | 'medium' | 'high',
      }

      if (source === 'template') {
        payload.command_template_id = values.command_template_id
      } else {
        payload.command = values.command
      }

      const result = await createTaskMutation.mutateAsync(payload)

      // 根据返回结果跳转 per D-10, D-11
      if (result.approval_required && result.approval_id) {
        message.success('任务已提交审批，正在跳转...')
        navigate(`/approvals/${result.approval_id}`)
      } else {
        message.success(`任务创建成功，任务ID: ${result.task_id}`)
        navigate(`/governance/audits`)
      }
    } catch (error: unknown) {
      // 错误处理
      const err = error as { response?: { data?: { message?: string } }; message?: string }
      if (err.response?.data?.message) {
        message.error(`创建失败: ${err.response.data.message}`)
      } else if (err.message) {
        message.error(`创建失败: ${err.message}`)
      } else {
        message.error('创建失败，请稍后重试')
      }
    }
  }

  // 处理表单提交
  const handleSubmit = async () => {
    // 检查是否有评估结果
    if (!evalResult) {
      message.warning('请先进行策略预览')
      return
    }

    // 检查是否被拦截
    if (!evalResult.allowed) {
      message.error('命令被策略拦截，无法提交')
      return
    }

    // 高风险任务需要确认 per D-12
    if (evalResult.final_risk_level === 'high' && evalResult.approval_required) {
      setConfirmModalOpen(true)
      return
    }

    // 直接提交
    executeSubmit()
  }

  // 获取当前选中模板的风险等级
  const selectedTemplate = templates.find((t) => t.template_id === selectedTemplateId)

  return (
    <div style={{ padding: '24px' }}>
      {/* 页面标题 */}
      <Title level={3} style={{ marginBottom: '24px' }}>创建任务</Title>

      <Card>
        <Form
          form={form}
          layout="vertical"
          initialValues={{
            source: 'template',
          }}
        >
          {/* 任务来源选择区 */}
          <Text strong style={{ fontSize: 14 }}>任务来源</Text>
          <Divider style={{ margin: '8px 0 16px 0' }} />

          <Form.Item name="source" label="选择来源方式">
            <Radio.Group
              onChange={(e) => setSource(e.target.value)}
              value={source}
            >
              <Radio value="template">选择模板</Radio>
              <Radio value="custom">自定义命令</Radio>
            </Radio.Group>
          </Form.Item>

          {/* 模板选择字段 */}
          {source === 'template' && (
            <Form.Item
              label={
                <Space>
                  <span>选择模板</span>
                  <Text type="danger">*</Text>
                </Space>
              }
              name="command_template_id"
              rules={[{ required: true, message: '请选择执行模板' }]}
            >
              <Select
                placeholder={templates.length > 0 ? '选择命令模板' : '暂无可用模板'}
                showSearch
                filterOption={(input, option) =>
                  (option?.label as string)?.toLowerCase().includes(input.toLowerCase())
                }
                loading={templatesQuery.isLoading}
                disabled={templates.length === 0}
                onChange={handleTemplateChange}
                notFoundContent={
                  templatesQuery.isLoading ? (
                    <Spin size="small" />
                  ) : templates.length === 0 ? (
                    <Text type="secondary">暂无可用模板，请使用自定义命令</Text>
                  ) : null
                }
                options={templates.map((t) => ({
                  value: t.template_id,
                  label: t.name,
                }))}
                optionRender={(option) => (
                  <Space>
                    <span>{option.data.label}</span>
                    {templates.find((t) => t.template_id === option.value)?.risk_level && (
                      <RiskBadge
                        level={templates.find((t) => t.template_id === option.value)!.risk_level}
                      />
                    )}
                  </Space>
                )}
              />
            </Form.Item>
          )}

          {/* 无可用模板时提示 */}
          {source === 'template' && templates.length === 0 && !templatesQuery.isLoading && (
            <Alert
              type="info"
              message="暂无可用模板"
              description="当前没有启用的命令模板，您可以使用自定义命令方式创建任务。"
              showIcon
              style={{ marginBottom: 16 }}
            />
          )}

          {/* 自定义命令字段 */}
          {source === 'custom' && (
            <Form.Item
              label={
                <Space>
                  <span>命令内容</span>
                  <Text type="danger">*</Text>
                </Space>
              }
              name="command"
              rules={[{ required: true, message: '请输入执行命令' }]}
            >
              <Input.TextArea
                placeholder="输入要执行的命令"
                rows={4}
                onChange={handleCustomCommandChange}
              />
            </Form.Item>
          )}

          {/* 命令预览区 */}
          <Text strong style={{ fontSize: 14, marginTop: 16 }}>命令预览</Text>
          <Divider style={{ margin: '8px 0 16px 0' }} />

          <div
            style={{
              padding: '12px',
              background: '#f5f5f5',
              borderRadius: '4px',
              minHeight: '60px',
            }}
          >
            {source === 'template' && !selectedTemplateId && (
              <Text type="secondary">选择模板后显示命令内容</Text>
            )}
            {source === 'template' && selectedTemplateId && selectedTemplate && (
              <div>
                <Space>
                  <Text>模板: {selectedTemplate.name}</Text>
                  {/* 显示模板风险等级或评估后的风险等级 */}
                  {evalResult ? (
                    <RiskBadge level={evalResult.final_risk_level as 'low' | 'medium' | 'high'} />
                  ) : (
                    <RiskBadge level={selectedTemplate.risk_level} />
                  )}
                </Space>
                <Divider style={{ margin: '8px 0' }} />
                <Text copyable>{commandPreview || '无命令内容'}</Text>
              </div>
            )}
            {source === 'custom' && (
              <div>
                {/* 自定义命令时，显示评估后的风险等级 */}
                {evalResult && (
                  <Space style={{ marginBottom: 8 }}>
                    <Text>风险等级:</Text>
                    <RiskBadge level={evalResult.final_risk_level as 'low' | 'medium' | 'high'} />
                  </Space>
                )}
                <Text copyable>{commandPreview || '请输入命令内容'}</Text>
              </div>
            )}
          </div>

          {/* 目标资产与系统用户选择区 */}
          <Text strong style={{ fontSize: 14, marginTop: 24 }}>执行配置</Text>
          <Divider style={{ margin: '8px 0 16px 0' }} />

          <Form.Item
            label={
              <Space>
                <span>目标资产</span>
                <Text type="danger">*</Text>
              </Space>
            }
            name="target_asset_id"
            rules={[{ required: true, message: '请选择目标资产' }]}
          >
            <Select
              placeholder={assets.length > 0 ? '选择目标资产' : '暂无可用资产'}
              showSearch
              filterOption={(input, option) =>
                (option?.label as string)?.toLowerCase().includes(input.toLowerCase())
              }
              loading={assetsQuery.isLoading}
              disabled={assets.length === 0}
              onChange={handleAssetChange}
              notFoundContent={
                assetsQuery.isLoading ? (
                  <Spin size="small" />
                ) : assets.length === 0 ? (
                  <Text type="secondary">暂无可用资产</Text>
                ) : null
              }
              options={assets.map((a) => ({
                value: a.asset_id,
                label: `${a.hostname} (${a.ip})`,
              }))}
            />
          </Form.Item>

          {/* 无可用资产时提示 */}
          {assets.length === 0 && !assetsQuery.isLoading && (
            <Alert
              type="warning"
              message="暂无可用资产"
              description="当前没有可用的资产，请先在 JumpServer 中添加资产。"
              showIcon
              style={{ marginBottom: 16 }}
            />
          )}

          <Form.Item
            label={
              <Space>
                <span>系统用户</span>
                <Text type="danger">*</Text>
              </Space>
            }
            name="run_as_system_user_id"
            rules={[{ required: true, message: '请选择执行使用的系统用户' }]}
          >
            <Select
              placeholder={selectedAssetId ? '选择系统用户' : '先选择目标资产'}
              showSearch
              filterOption={(input, option) =>
                (option?.label as string)?.toLowerCase().includes(input.toLowerCase())
              }
              disabled={!selectedAssetId}
              loading={systemUsersQuery.isLoading}
              notFoundContent={
                systemUsersQuery.isLoading ? (
                  <Spin size="small" />
                ) : selectedAssetId ? (
                  '无可用系统用户'
                ) : (
                  '请先选择目标资产'
                )
              }
              options={systemUsers.map((u) => ({
                value: u.system_user_id,
                label: `${u.name} (${u.username})`,
              }))}
            />
          </Form.Item>

          {/* 策略评估结果显示 */}
          {evalResult && !evalModalOpen && (
            <>
              <Divider style={{ margin: '24px 0 16px 0' }} />
              {evalResult.allowed ? (
                <Alert
                  type="success"
                  message="策略评估通过"
                  description={
                    <Space direction="vertical" size="small">
                      <Space>
                        <Text>风险等级:</Text>
                        <RiskBadge level={evalResult.final_risk_level as 'low' | 'medium' | 'high'} />
                      </Space>
                      {evalResult.approval_required && (
                        <Text type="warning">此命令需要审批流程</Text>
                      )}
                    </Space>
                  }
                  showIcon
                />
              ) : (
                <Alert
                  type="error"
                  message="命令被策略拦截"
                  description={
                    <Space direction="vertical" size="small">
                      {evalResult.block_reason && (
                        <Text>{evalResult.block_reason}</Text>
                      )}
                      {evalResult.matched_rules.length > 0 && (
                        <div>
                          <Text strong>匹配规则:</Text>
                          <ul style={{ margin: '4px 0', paddingLeft: '20px' }}>
                            {evalResult.matched_rules.map((rule, idx) => (
                              <li key={idx}>
                                {typeof rule === 'string'
                                  ? rule
                                  : (rule as { pattern?: string; rule_id?: string }).pattern ||
                                    (rule as { rule_id?: string }).rule_id ||
                                    JSON.stringify(rule)}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </Space>
                  }
                  showIcon
                />
              )}
            </>
          )}

          {/* 提交按钮区 */}
          <Divider style={{ margin: '24px 0 16px 0' }} />
          <Space style={{ width: '100%', justifyContent: 'flex-end' }}>
            <Button onClick={() => navigate('/governance/audits')}>取消</Button>
            <Button
              icon={<SafetyOutlined />}
              onClick={handlePolicyPreview}
            >
              策略预览
            </Button>
            <Button
              type="primary"
              onClick={handleSubmit}
              disabled={isBlocked || !evalResult}
              loading={createTaskMutation.isPending}
            >
              {evalResult?.approval_required ? '提交审批' : '创建任务'}
            </Button>
          </Space>
        </Form>
      </Card>

      {/* 策略评估弹窗 */}
      <PolicyEvaluationModal
        open={evalModalOpen}
        command={commandPreview}
        commandTemplateId={selectedTemplateId}
        requestedRiskLevel={selectedTemplate?.risk_level}
        onClose={() => setEvalModalOpen(false)}
        onEvaluated={handleEvaluated}
      />

      {/* 高风险确认弹窗 */}
      <RiskConfirmModal
        open={confirmModalOpen}
        riskLevel={evalResult?.final_risk_level as 'low' | 'medium' | 'high'}
        command={commandPreview}
        onConfirm={() => {
          setConfirmModalOpen(false)
          executeSubmit()
        }}
        onCancel={() => setConfirmModalOpen(false)}
      />
    </div>
  )
}