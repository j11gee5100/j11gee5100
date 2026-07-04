import { useState } from 'react'
import { Alert, Button, Card, Form, Input, Modal, Select, Space, Table, Tag, Typography, message } from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import { useAuth } from '../auth/AuthContext'
import { useCreateProbeResult, useManagedDevices, useProbeResults } from '../hooks/useEnvironmentPackages'
import type { ProbeResult } from '../types/environmentPackage'

const { Title, Text } = Typography

export default function ProbeResultsPage() {
  const auth = useAuth()
  const operator = auth.user ? { ...auth.user, access_token: auth.token } : null
  const results = useProbeResults(operator)
  const devices = useManagedDevices()
  const createResult = useCreateProbeResult(operator)
  const [open, setOpen] = useState(false)
  const [form] = Form.useForm()

  const openCreate = () => {
    form.resetFields()
    form.setFieldsValue({ raw_json: '{\n  "os_type": "Ubuntu",\n  "os_version": "22.04",\n  "cpu_arch": "x86_64",\n  "accelerator_vendor": "NVIDIA",\n  "accelerator_model": "A10",\n  "driver_version": "535.183"\n}' })
    setOpen(true)
  }

  const submit = async () => {
    const values = await form.validateFields()
    JSON.parse(values.raw_json)
    await createResult.mutateAsync(values)
    message.success('探测结果已导入')
    setOpen(false)
  }

  const columns = [
    { title: '结果', dataIndex: 'name', render: (_: string, item: ProbeResult) => <Space direction="vertical" size={0}><Text strong>{item.name}</Text><Text type="secondary">{item.result_code}</Text></Space> },
    { title: '系统', render: (_: unknown, item: ProbeResult) => `${item.os_type || '-'} ${item.os_version || ''}` },
    { title: '架构', dataIndex: 'cpu_arch' },
    { title: '推理卡', render: (_: unknown, item: ProbeResult) => <Tag>{`${item.accelerator_vendor || '-'} ${item.accelerator_model || ''}`}</Tag> },
    { title: '驱动/运行时', dataIndex: 'driver_version' },
    { title: 'Owner', dataIndex: 'owner_id' },
    { title: '原始 JSON', render: (_: unknown, item: ProbeResult) => <pre style={{ maxWidth: 360, maxHeight: 120, overflow: 'auto', margin: 0 }}>{item.raw_json}</pre> },
  ]

  return (
    <div style={{ padding: 24 }}>
      <Space direction="vertical" size={16} style={{ width: '100%' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <div>
            <Title level={3} style={{ marginBottom: 4 }}>探测结果</Title>
            <Text type="secondary">当前只导入远程设备离线探测 JSON，保存原始内容并展示核心字段。</Text>
          </div>
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>导入探测结果</Button>
        </div>
        <Alert type="warning" showIcon message="探测脚本库、自动连接远程设备、多厂商 schema 标准化暂不做；现场执行脚本后把 JSON 结果导入即可。" />
        <Card><Table rowKey="result_id" loading={results.isLoading} dataSource={results.data ?? []} columns={columns} pagination={{ pageSize: 8 }} /></Card>
      </Space>

      <Modal title="导入探测结果" open={open} onCancel={() => setOpen(false)} onOk={submit} confirmLoading={createResult.isPending} width={780} okText="导入">
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="结果名称"><Input /></Form.Item>
          <Form.Item name="result_code" label="结果编码" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="device_id" label="关联设备"><Select allowClear showSearch options={(devices.data ?? []).map((item) => ({ value: item.device_id, label: `${item.name || item.device_code} / ${item.accelerator_model}` }))} /></Form.Item>
          <Form.Item name="raw_json" label="探测 JSON" rules={[{ required: true }]}><Input.TextArea rows={12} /></Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
