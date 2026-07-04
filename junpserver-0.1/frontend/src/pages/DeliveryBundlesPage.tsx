import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Alert, Button, Card, Form, Input, Modal, Popconfirm, Select, Space, Table, Tag, Typography, message } from 'antd'
import { DeleteOutlined, DownloadOutlined, PlusOutlined } from '@ant-design/icons'
import { useAuth } from '../auth/AuthContext'
import { formatPackageType, packageTypeFilterOptions } from '../constants/packageTypes'
import { deliveryBundleArtifactUrl, useCreateDeliveryBundle, useDeleteDeliveryBundle, useDeliveryBundles, useDeviceProfiles, useEnvPackages, useManagedDevices } from '../hooks/useEnvironmentPackages'
import type { DeliveryBundle } from '../types/environmentPackage'

const { Title, Text } = Typography

const bundleTypeOptions = [
  { label: '首装包', value: 'first_install' },
  { label: '升级包', value: 'upgrade' },
  { label: '覆盖包', value: 'overwrite' },
]

const bundleTypeLabel: Record<string, string> = {
  first_install: '首装包',
  upgrade: '升级包',
  overwrite: '覆盖包',
}

const bundleTypeColor: Record<string, string> = {
  first_install: 'blue',
  upgrade: 'purple',
  overwrite: 'red',
}


export default function DeliveryBundlesPage() {
  const navigate = useNavigate()
  const auth = useAuth()
  const operator = auth.user ? { ...auth.user, access_token: auth.token } : null
  const [deviceFilter, setDeviceFilter] = useState('')
  const [profileFilter, setProfileFilter] = useState('')
  const bundles = useDeliveryBundles(operator, { device_id: deviceFilter, profile_id: profileFilter })
  const packages = useEnvPackages(operator)
  const devices = useManagedDevices()
  const profiles = useDeviceProfiles()
  const createBundle = useCreateDeliveryBundle(operator)
  const [open, setOpen] = useState(false)
  const [packageTypeFilter, setPackageTypeFilter] = useState('')
  const [form] = Form.useForm()
  const targetProfileId = Form.useWatch('target_profile_id', form) as string | undefined

  const lifecycleLabel: Record<string, string> = { making: '制作中', delivered: '已交付' }
  const lifecycleColor: Record<string, string> = { making: 'gold', delivered: 'green' }
  const buildLabel: Record<string, string> = { not_built: '未制作', queued: '排队中', running: '制作中', success: '制作成功', failed: '制作失败' }
  const buildColor: Record<string, string> = { not_built: 'default', queued: 'blue', running: 'processing', success: 'green', failed: 'red' }

  const deleteBundle = useDeleteDeliveryBundle(operator)
  const filteredPackageOptions = (packages.data ?? [])
    .filter((item) => {
      if (!targetProfileId) return false
      if (!item.device_profiles.some((profile) => profile.profile_id === targetProfileId)) return false
      if (packageTypeFilter && item.package_type !== packageTypeFilter) return false
      return true
    })
    .slice()
    .sort((a, b) => (a.install_order ?? 100) - (b.install_order ?? 100))

  const inferProfileIdFromDevice = (deviceId?: string) => {
    const device = (devices.data ?? []).find((item) => item.device_id === deviceId)
    if (!device) return undefined
    return (profiles.data ?? []).find((profile) => (
      profile.enabled
      && profile.cpu_arch === device.cpu_arch
      && profile.os_type === device.os_type
      && profile.os_version === device.os_version
      && profile.accelerator_vendor === device.accelerator_vendor
      && profile.accelerator_model === device.accelerator_model
      && (!profile.driver_version || !device.driver_version || profile.driver_version === device.driver_version)
    ))?.profile_id
  }

  const openCreate = () => {
    form.resetFields()
    setPackageTypeFilter('')
    form.setFieldsValue({ version: '1.0.0', bundle_type: 'first_install', package_ids: [] })
    setOpen(true)
  }

  const submit = async () => {
    const values = await form.validateFields()
    await createBundle.mutateAsync(values)
    message.success('交付包草稿已保存')
    setOpen(false)
  }

  const downloadArtifact = (item: DeliveryBundle) => {
    if (!item.artifact_name || item.build_status !== 'success') return
    const url = auth.token ? `${deliveryBundleArtifactUrl(item.bundle_id)}?access_token=${encodeURIComponent(auth.token)}` : deliveryBundleArtifactUrl(item.bundle_id)
    window.open(url, '_blank')
  }

  const columns = [
    { title: '交付包', dataIndex: 'name', render: (_: string, item: DeliveryBundle) => <Space direction="vertical" size={0}><Text strong>{item.name}</Text><Text type="secondary">{item.bundle_code}</Text></Space> },
    { title: '版本', dataIndex: 'version' },
    { title: '交付类型', dataIndex: 'bundle_type', render: (value: string) => <Tag color={bundleTypeColor[value] || 'default'}>{bundleTypeLabel[value] || value || '-'}</Tag> },
    { title: '资产状态', dataIndex: 'lifecycle_status', render: (value: string) => <Tag color={lifecycleColor[value] || 'default'}>{lifecycleLabel[value] || value || '-'}</Tag> },
    { title: '制作状态', dataIndex: 'build_status', render: (value: string) => <Tag color={buildColor[value] || 'default'}>{buildLabel[value] || value || '-'}</Tag> },
    { title: '安装项', render: (_: unknown, item: DeliveryBundle) => item.package_ids.length },
    { title: '产物', render: (_: unknown, item: DeliveryBundle) => item.artifact_name || '-' },
    { title: 'Owner', dataIndex: 'owner_id' },
    { title: '操作', render: (_: unknown, item: DeliveryBundle) => (
      <Space>
        <Button type="primary" size="small" onClick={() => navigate(`/delivery-bundles/${item.bundle_id}`)}>{item.lifecycle_status === 'delivered' ? '查看详情' : '编辑编排'}</Button>
        <Button size="small" icon={<DownloadOutlined />} disabled={item.build_status !== 'success'} onClick={() => downloadArtifact(item)}>下载</Button>
        {item.lifecycle_status !== 'delivered' && (
          <Popconfirm title="确认删除制作中的交付包？" onConfirm={async () => { await deleteBundle.mutateAsync(item.bundle_id); message.success('交付包已删除') }}>
            <Button size="small" danger icon={<DeleteOutlined />}>删除</Button>
          </Popconfirm>
        )}
      </Space>
    ) },
  ]

  return (
    <div style={{ padding: 24 }}>
      <Space direction="vertical" size={16} style={{ width: '100%' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <div>
            <Title level={3} style={{ marginBottom: 4 }}>交付包</Title>
            <Text type="secondary">交付包是受控资产：制作中可编辑/删除，已交付不可删除，变更请创建新版本。</Text>
          </div>
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>新建交付包草稿</Button>
        </div>
        <Alert type="info" showIcon message="列表页只展示资产摘要；Manifest 与制作日志请进入编辑/详情页查看。制作安装包会进入后台任务并显示进度。" />
        <Card>
          <Space wrap style={{ marginBottom: 16 }}>
            <Select
              allowClear
              showSearch
              style={{ width: 260 }}
              placeholder="按设备筛选交付包"
              value={deviceFilter || undefined}
              onChange={(value) => { setDeviceFilter(value || ''); setProfileFilter('') }}
              options={(devices.data ?? []).map((item) => ({ value: item.device_id, label: `${item.name || item.device_code} / ${item.os_type} ${item.os_version} / ${item.accelerator_model}` }))}
            />
            <Select
              allowClear
              showSearch
              style={{ width: 320 }}
              placeholder="按适配配置筛选交付包"
              value={profileFilter || undefined}
              onChange={(value) => { setProfileFilter(value || ''); setDeviceFilter('') }}
              options={(profiles.data ?? []).map((item) => ({ value: item.profile_id, label: item.label }))}
            />
            {(deviceFilter || profileFilter) && <Button onClick={() => { setDeviceFilter(''); setProfileFilter('') }}>清空筛选</Button>}
          </Space>
          <Table rowKey="bundle_id" loading={bundles.isLoading} dataSource={bundles.data ?? []} columns={columns} pagination={{ pageSize: 6 }} />
        </Card>
      </Space>

      <Modal title="新建交付包草稿" open={open} onCancel={() => setOpen(false)} onOk={submit} confirmLoading={createBundle.isPending} width={920} okText="保存草稿">
        <Form form={form} layout="vertical">
          <Alert style={{ marginBottom: 16 }} type="info" showIcon message="交付包区分首装/升级/覆盖：同一设备适配历史中，首装包用于首次部署，升级包用于已有环境增量升级，覆盖包用于新装/重装时交付最终一体包。" />
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            <Form.Item name="name" label="交付包名称" rules={[{ required: true }]}><Input /></Form.Item>
            <Form.Item name="bundle_code" label="交付包编码" rules={[{ required: true }]}><Input /></Form.Item>
            <Form.Item name="version" label="版本"><Input /></Form.Item>
            <Form.Item name="bundle_type" label="交付类型" rules={[{ required: true }]}><Select options={bundleTypeOptions} /></Form.Item>
            <Form.Item name="target_device_id" label="目标设备"><Select allowClear showSearch onChange={(value) => form.setFieldsValue({ target_profile_id: inferProfileIdFromDevice(value), package_ids: [] })} options={(devices.data ?? []).map((item) => ({ value: item.device_id, label: `${item.name || item.device_code} / ${item.accelerator_model}` }))} /></Form.Item>
            <Form.Item name="target_profile_id" label="适配配置" rules={[{ required: true, message: '请选择适配配置后再选择安装项' }]}><Select allowClear showSearch onChange={() => form.setFieldsValue({ target_device_id: undefined, package_ids: [] })} options={(profiles.data ?? []).map((item) => ({ value: item.profile_id, label: item.label }))} /></Form.Item>
            <Form.Item label="安装项类型筛选"><Select value={packageTypeFilter} onChange={(value) => { setPackageTypeFilter(value); form.setFieldsValue({ package_ids: [] }) }} options={packageTypeFilterOptions} /></Form.Item>
            <Form.Item name="package_ids" label="安装项资产" rules={[{ required: true, message: '请选择至少一个安装项' }]} style={{ gridColumn: '1 / -1' }}>
              <Select
                mode="multiple"
                showSearch
                loading={packages.isLoading}
                disabled={!targetProfileId}
                placeholder={targetProfileId ? '只显示匹配所选适配配置的安装项' : '请先选择适配配置'}
                notFoundContent={targetProfileId ? '该适配配置下暂无匹配安装项' : '请先选择适配配置'}
                options={filteredPackageOptions.map((item) => ({ value: item.package_id, label: `${item.install_order ?? 100}｜${formatPackageType(item.package_type)}｜${item.name}｜${item.version}` }))}
              />
            </Form.Item>
          </div>
        </Form>

      </Modal>
    </div>
  )
}
