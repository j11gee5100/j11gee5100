import { useState } from 'react'
import { Card, Alert, Table, Tag, Spin, Select, Space, Typography } from 'antd'
import { useQuery } from '@tanstack/react-query'
import { useParams, useNavigate } from 'react-router-dom'
import dayjs from 'dayjs'

const { Title, Text, Paragraph } = Typography

/**
 * 失败详情 API 响应类型
 */
interface FailureDetail {
  failure_code: string
  title: string
  severity: 'serious' | 'normal' | 'minor'
  summary: string
  remediation_steps: string[]
  verification_steps: string[]
  failed_samples: Array<{
    task_id: string
    asset_hostname?: string
    asset_ip?: string
    executed_at: string
    status: string
    error_message?: string
  }>
  total_samples?: number
  trace_id: string
}

/**
 * 严重级别颜色映射
 */
const SEVERITY_COLORS = {
  serious: '#f5222d',
  normal: '#faad14',
  minor: '#52c41a',
}

const SEVERITY_LABELS = {
  serious: '严重',
  normal: '普通',
  minor: '轻微',
}

/**
 * 失败详情页组件
 *
 * 功能：
 * - 显示失败码标题、严重级别、摘要
 * - 推荐修复步骤和验证步骤
 * - 底部显示近期失败样本表格
 * - 支持按 hours/source 筛选刷新
 *
 * 需求覆盖：FAIL-01 ~ FAIL-05
 */
export default function FailureDetailPage() {
  const { failureCode } = useParams<{ failureCode: string }>()
  const navigate = useNavigate()
  const [hours, setHours] = useState<number>(24)
  const [source, setSource] = useState<string | undefined>(undefined)

  // 构建 API URL
  const apiUrl = `/api/v1/dashboard/failures/${failureCode}/detail`

  const { data, isLoading, error } = useQuery<FailureDetail>({
    queryKey: ['failure-detail', failureCode, hours, source],
    queryFn: async () => {
      const params = new URLSearchParams()
      if (hours) params.append('hours', hours.toString())
      if (source) params.append('source', source)

      const response = await fetch(`${apiUrl}?${params.toString()}`)
      if (!response.ok) {
        throw new Error('失败详情 API 调用失败')
      }
      return response.json()
    },
    refetchInterval: 60000, // 1 分钟刷新
  })

  // 失败样本表格列定义
  const sampleColumns = [
    {
      title: '任务 ID',
      dataIndex: 'task_id',
      key: 'task_id',
      render: (text: string) => (
        <a href={`/tasks/${text}`} data-testid="sample-task-id">
          {text}
        </a>
      ),
    },
    {
      title: '资产',
      key: 'asset',
      render: (_: unknown, record: any) => (
        <span data-testid="sample-asset">
          {record.asset_hostname || record.asset_ip || '-'}
        </span>
      ),
    },
    {
      title: '执行时间',
      dataIndex: 'executed_at',
      key: 'executed_at',
      render: (text: string) => (
        <span data-testid="sample-executed-at">
          {dayjs(text).format('YYYY-MM-DD HH:mm:ss')}
        </span>
      ),
      sorter: (a: any, b: any) =>
        dayjs(a.executed_at).valueOf() - dayjs(b.executed_at).valueOf(),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => (
        <Tag
          data-testid="sample-status"
          color={status === 'failed' ? 'red' : status === 'success' ? 'green' : 'default'}
        >
          {status}
        </Tag>
      ),
    },
    {
      title: '错误信息',
      dataIndex: 'error_message',
      key: 'error_message',
      ellipsis: true,
      render: (text?: string) => (
        <Text type="secondary" data-testid="sample-error">
          {text || '-'}
        </Text>
      ),
    },
  ]

  if (isLoading) {
    return (
      <div style={{ padding: '24px', textAlign: 'center' }}>
        <Spin size="large" tip="加载失败详情..." />
      </div>
    )
  }

  if (error) {
    return (
      <div style={{ padding: '24px' }}>
        <Alert
          message="加载失败"
          description={error instanceof Error ? error.message : '未知错误'}
          type="error"
          showIcon
        />
      </div>
    )
  }

  if (!data) {
    return (
      <div style={{ padding: '24px' }}>
        <Alert
          message="未找到数据"
          description="该失败码的详情数据不存在"
          type="warning"
          showIcon
        />
      </div>
    )
  }

  const severityColor = SEVERITY_COLORS[data.severity]
  const severityLabel = SEVERITY_LABELS[data.severity]

  return (
    <div style={{ padding: '24px' }}>
      {/* 返回按钮 */}
      <Space style={{ marginBottom: '16px' }}>
        <a onClick={() => navigate('/dashboard')}>← 返回看板</a>
      </Space>

      {/* 标题和严重级别 */}
      <Card
        data-testid="failure-detail-header"
        style={{
          borderLeft: `4px solid ${severityColor}`,
          marginBottom: '16px',
        }}
      >
        <Space direction="vertical" size="small" style={{ width: '100%' }}>
          <Space>
            <Title level={3} style={{ margin: 0 }} data-testid="failure-code-title">
              {data.failure_code}
            </Title>
            <Tag color={severityColor} data-testid="severity-tag">
              {severityLabel}
            </Tag>
          </Space>
          <Paragraph type="secondary" data-testid="failure-summary">
            {data.summary}
          </Paragraph>
        </Space>
      </Card>

      {/* 筛选器 */}
      <Card
        data-testid="failure-filters"
        style={{ marginBottom: '16px' }}
      >
        <Space size="large">
          <Space>
            <Text strong>时间范围:</Text>
            <Select
              value={hours}
              onChange={setHours}
              options={[
                { label: '最近 24 小时', value: 24 },
                { label: '最近 7 天', value: 168 },
                { label: '最近 30 天', value: 720 },
              ]}
              style={{ width: 150 }}
              data-testid="hours-filter"
            />
          </Space>
          <Space>
            <Text strong>调用来源:</Text>
            <Select
              value={source || 'all'}
              onChange={setSource}
              options={[
                { label: '全部', value: '' },
                { label: 'API', value: 'api' },
                { label: 'Web', value: 'web' },
              ]}
              style={{ width: 120 }}
              data-testid="source-filter"
            />
          </Space>
        </Space>
      </Card>

      {/* 修复步骤 */}
      <Card
        data-testid="remediation-steps-card"
        title="推荐修复步骤"
        style={{ marginBottom: '16px' }}
      >
        <ol data-testid="remediation-steps">
          {data.remediation_steps?.map((step, index) => (
            <li key={index} style={{ marginBottom: '8px' }}>
              {step}
            </li>
          )) || <Text type="secondary">暂无修复步骤</Text>}
        </ol>
      </Card>

      {/* 验证步骤 */}
      <Card
        data-testid="verification-steps-card"
        title="验证步骤"
        style={{ marginBottom: '16px' }}
      >
        <ol data-testid="verification-steps">
          {data.verification_steps?.map((step, index) => (
            <li key={index} style={{ marginBottom: '8px' }}>
              {step}
            </li>
          )) || <Text type="secondary">暂无验证步骤</Text>}
        </ol>
      </Card>

      {/* 失败样本表格 */}
      <Card
        data-testid="failure-samples-card"
        title={`近期失败样本 (共 ${data.total_samples || data.failed_samples?.length || 0} 条)`}
      >
        <Table
          dataSource={data.failed_samples || []}
          columns={sampleColumns}
          rowKey="task_id"
          pagination={{ pageSize: 10 }}
          size="small"
        />
      </Card>
    </div>
  )
}
