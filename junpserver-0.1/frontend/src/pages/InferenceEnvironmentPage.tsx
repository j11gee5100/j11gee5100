import { useState } from 'react'
import { Button, Card, Form, Input, Modal, Select, Space, Table, Tabs, Tag, Typography, message } from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import {
  useCreateEnvironmentHandover,
  useCreateEnvironmentImplementation,
  useCreateEnvironmentSpec,
  useCreateInferenceDevice,
  useCreateModelDeploymentRequirement,
  useEnvironmentHandovers,
  useEnvironmentImplementations,
  useEnvironmentSpecs,
  useInferenceDevices,
  useModelDeploymentRequirements,
} from '../hooks/useInferenceEnvironment'

const { Title, Text } = Typography

type CreateKind = 'device' | 'spec' | 'requirement' | 'implementation' | 'handover'

const statusColor: Record<string, string> = {
  active: 'green',
  ready: 'green',
  accepted: 'green',
  handed_over: 'blue',
  pending: 'gold',
  planned: 'gold',
  implementing: 'processing',
  rejected: 'red',
  inactive: 'default',
}

function StatusTag({ value }: { value?: string }) {
  const label = value || '-'
  return <Tag color={statusColor[label] ?? 'default'}>{label}</Tag>
}

export default function InferenceEnvironmentPage() {
  const [createKind, setCreateKind] = useState<CreateKind | null>(null)
  const [form] = Form.useForm()

  const devices = useInferenceDevices()
  const specs = useEnvironmentSpecs()
  const requirements = useModelDeploymentRequirements()
  const implementations = useEnvironmentImplementations()
  const handovers = useEnvironmentHandovers()

  const createDevice = useCreateInferenceDevice()
  const createSpec = useCreateEnvironmentSpec()
  const createRequirement = useCreateModelDeploymentRequirement()
  const createImplementation = useCreateEnvironmentImplementation()
  const createHandover = useCreateEnvironmentHandover()

  const openCreate = (kind: CreateKind) => {
    form.resetFields()
    setCreateKind(kind)
  }

  const closeCreate = () => setCreateKind(null)

  const submitCreate = async () => {
    const values = await form.validateFields()
    const mutations = {
      device: createDevice,
      spec: createSpec,
      requirement: createRequirement,
      implementation: createImplementation,
      handover: createHandover,
    }
    await mutations[createKind as CreateKind].mutateAsync(values)
    message.success('已创建')
    closeCreate()
  }

  const modalTitle = {
    device: '新增推理设备',
    spec: '新增环境规格',
    requirement: '新增模型部署要求',
    implementation: '新增实施记录',
    handover: '新增交接单',
  }[createKind ?? 'device']

  return (
    <div style={{ padding: 24 }}>
      <Space direction="vertical" size={16} style={{ width: '100%' }}>
        <div>
          <Title level={3} style={{ marginBottom: 4 }}>AI 推理环境管理</Title>
          <Text type="secondary">管理推理设备、环境规格、模型部署要求、实施记录和总装交接。</Text>
        </div>

        <Tabs
          items={[
            {
              key: 'devices',
              label: '推理设备',
              children: (
                <Card extra={<Button icon={<PlusOutlined />} type="primary" onClick={() => openCreate('device')}>新增设备</Button>}>
                  <Table
                    rowKey="device_id"
                    loading={devices.isLoading}
                    dataSource={devices.data ?? []}
                    columns={[
                      { title: '设备编号', dataIndex: 'device_code' },
                      { title: '名称', dataIndex: 'name' },
                      { title: '主机/IP', render: (_, r) => `${r.hostname || '-'} / ${r.ip || '-'}` },
                      { title: '系统', render: (_, r) => `${r.os_type || '-'} ${r.os_version || ''}` },
                      { title: '推理卡', render: (_, r) => `${r.accelerator_vendor || '-'} ${r.accelerator_model || ''} x${r.accelerator_count || '-'}` },
                      { title: '驱动', dataIndex: 'driver_version' },
                      { title: '状态', dataIndex: 'status', render: (v) => <StatusTag value={v} /> },
                    ]}
                    pagination={{ pageSize: 10 }}
                  />
                </Card>
              ),
            },
            {
              key: 'specs',
              label: '环境规格',
              children: (
                <Card extra={<Button icon={<PlusOutlined />} type="primary" onClick={() => openCreate('spec')}>新增规格</Button>}>
                  <Table
                    rowKey="spec_id"
                    loading={specs.isLoading}
                    dataSource={specs.data ?? []}
                    columns={[
                      { title: '规格ID', dataIndex: 'spec_id' },
                      { title: '名称', dataIndex: 'name' },
                      { title: '版本', dataIndex: 'version' },
                      { title: '运行时', render: (_, r) => `${r.runtime_name || r.runtime || '-'} / ${r.framework || '-'}` },
                      { title: '推理服务', dataIndex: 'inference_server' },
                      { title: '硬件要求', render: (_, r) => `${r.accelerator_vendor || '-'} ${r.accelerator_model || ''}` },
                      { title: '启用', dataIndex: 'enabled', render: (v) => <Tag color={v ? 'green' : 'default'}>{v ? 'enabled' : 'disabled'}</Tag> },
                    ]}
                    pagination={{ pageSize: 10 }}
                  />
                </Card>
              ),
            },
            {
              key: 'requirements',
              label: '模型部署要求',
              children: (
                <Card extra={<Button icon={<PlusOutlined />} type="primary" onClick={() => openCreate('requirement')}>新增要求</Button>}>
                  <Table
                    rowKey="requirement_id"
                    loading={requirements.isLoading}
                    dataSource={requirements.data ?? []}
                    columns={[
                      { title: '要求ID', dataIndex: 'requirement_id' },
                      { title: '模型', render: (_, r) => `${r.model_name || r.model_id || '-'}:${r.model_version || '-'}` },
                      { title: '环境规格', dataIndex: 'environment_spec_id' },
                      { title: '推理卡', render: (_, r) => `${r.accelerator_vendor || '-'} ${r.accelerator_model || ''}` },
                      { title: '最低显存', dataIndex: 'min_accelerator_memory_gb' },
                      { title: '状态', dataIndex: 'status', render: (v) => <StatusTag value={v} /> },
                    ]}
                    pagination={{ pageSize: 10 }}
                  />
                </Card>
              ),
            },
            {
              key: 'implementations',
              label: '实施记录',
              children: (
                <Card extra={<Button icon={<PlusOutlined />} type="primary" onClick={() => openCreate('implementation')}>新增实施</Button>}>
                  <Table
                    rowKey="implementation_id"
                    loading={implementations.isLoading}
                    dataSource={implementations.data ?? []}
                    columns={[
                      { title: '实施ID', dataIndex: 'implementation_id' },
                      { title: '名称', dataIndex: 'implementation_name' },
                      { title: '设备ID', dataIndex: 'device_id' },
                      { title: '环境规格', dataIndex: 'environment_spec_id' },
                      { title: '推理服务', dataIndex: 'actual_inference_server' },
                      { title: '驱动', dataIndex: 'actual_driver_version' },
                      { title: '状态', dataIndex: 'implementation_status', render: (v) => <StatusTag value={v} /> },
                    ]}
                    pagination={{ pageSize: 10 }}
                  />
                </Card>
              ),
            },
            {
              key: 'handovers',
              label: '总装交接',
              children: (
                <Card extra={<Button icon={<PlusOutlined />} type="primary" onClick={() => openCreate('handover')}>新增交接单</Button>}>
                  <Table
                    rowKey="handover_id"
                    loading={handovers.isLoading}
                    dataSource={handovers.data ?? []}
                    columns={[
                      { title: '交接单号', dataIndex: 'handover_no' },
                      { title: '标题', dataIndex: 'title' },
                      { title: '实施ID', dataIndex: 'implementation_id' },
                      { title: '接收方', render: (_, r) => r.recipient || r.target_owner || '-' },
                      { title: '测试结果', dataIndex: 'test_result', render: (v) => <StatusTag value={v} /> },
                      { title: '状态', dataIndex: 'status', render: (v) => <StatusTag value={v} /> },
                    ]}
                    pagination={{ pageSize: 10 }}
                  />
                </Card>
              ),
            },
          ]}
        />
      </Space>

      <Modal title={modalTitle} open={createKind !== null} onCancel={closeCreate} onOk={submitCreate} confirmLoading={createDevice.isPending || createSpec.isPending || createRequirement.isPending || createImplementation.isPending || createHandover.isPending}>
        <Form form={form} layout="vertical">
          {createKind === 'device' && (
            <>
              <Form.Item name="device_code" label="设备编号" rules={[{ required: true }]}><Input /></Form.Item>
              <Form.Item name="name" label="名称"><Input /></Form.Item>
              <Form.Item name="hostname" label="主机名"><Input /></Form.Item>
              <Form.Item name="ip" label="IP"><Input /></Form.Item>
              <Form.Item name="os_type" label="系统类型"><Input placeholder="Linux / Windows" /></Form.Item>
              <Form.Item name="accelerator_vendor" label="推理卡厂商"><Input placeholder="NVIDIA / Ascend / AMD" /></Form.Item>
              <Form.Item name="accelerator_model" label="推理卡型号"><Input /></Form.Item>
              <Form.Item name="accelerator_count" label="推理卡数量"><Input /></Form.Item>
              <Form.Item name="driver_version" label="驱动版本"><Input /></Form.Item>
            </>
          )}
          {createKind === 'spec' && (
            <>
              <Form.Item name="spec_id" label="规格ID"><Input placeholder="留空自动生成" /></Form.Item>
              <Form.Item name="name" label="名称" rules={[{ required: true }]}><Input /></Form.Item>
              <Form.Item name="runtime" label="运行时"><Input placeholder="CUDA / CANN / ROCm" /></Form.Item>
              <Form.Item name="framework" label="框架"><Input placeholder="TensorRT / ONNX Runtime / PyTorch" /></Form.Item>
              <Form.Item name="inference_server" label="推理服务"><Input placeholder="Triton / vLLM / 自研服务" /></Form.Item>
              <Form.Item name="accelerator_vendor" label="推理卡厂商"><Input /></Form.Item>
              <Form.Item name="driver_version" label="驱动版本"><Input /></Form.Item>
              <Form.Item name="health_check" label="健康检查"><Input /></Form.Item>
            </>
          )}
          {createKind === 'requirement' && (
            <>
              <Form.Item name="requirement_id" label="要求ID"><Input placeholder="留空自动生成" /></Form.Item>
              <Form.Item name="model_id" label="模型ID"><Input /></Form.Item>
              <Form.Item name="model_name" label="模型名称"><Input /></Form.Item>
              <Form.Item name="model_version" label="模型版本"><Input /></Form.Item>
              <Form.Item name="environment_spec_id" label="环境规格ID"><Input /></Form.Item>
              <Form.Item name="required_accelerator_type" label="推理卡类型"><Input /></Form.Item>
              <Form.Item name="min_vram_gb" label="最低显存GB"><Input /></Form.Item>
            </>
          )}
          {createKind === 'implementation' && (
            <>
              <Form.Item name="implementation_name" label="实施名称"><Input /></Form.Item>
              <Form.Item name="device_id" label="设备ID"><Input /></Form.Item>
              <Form.Item name="spec_id" label="环境规格ID"><Input /></Form.Item>
              <Form.Item name="requirement_id" label="模型要求ID"><Input /></Form.Item>
              <Form.Item name="engine" label="推理服务"><Input /></Form.Item>
              <Form.Item name="engine_version" label="服务版本"><Input /></Form.Item>
              <Form.Item name="actual_driver_version" label="实际驱动版本"><Input /></Form.Item>
              <Form.Item name="status" label="状态" initialValue="implemented"><Select options={[{ value: 'planned' }, { value: 'implemented' }, { value: 'ready' }, { value: 'failed' }]} /></Form.Item>
            </>
          )}
          {createKind === 'handover' && (
            <>
              <Form.Item name="handover_no" label="交接单号"><Input placeholder="留空自动生成" /></Form.Item>
              <Form.Item name="title" label="标题"><Input /></Form.Item>
              <Form.Item name="implementation_id" label="实施ID"><Input /></Form.Item>
              <Form.Item name="target_owner" label="接收方"><Input /></Form.Item>
              <Form.Item name="test_result" label="测试结果" initialValue="pending"><Select options={[{ value: 'pending' }, { value: 'passed' }, { value: 'failed' }]} /></Form.Item>
              <Form.Item name="reason" label="说明"><Input.TextArea rows={3} /></Form.Item>
            </>
          )}
        </Form>
      </Modal>
    </div>
  )
}
