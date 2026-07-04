import { useMemo, useState } from 'react'
import { Alert, Button, Card, Descriptions, Drawer, Form, Input, InputNumber, Modal, Popconfirm, Select, Space, Statistic, Switch, Table, Tag, Typography, Upload, message } from 'antd'
import { DeleteOutlined, DownloadOutlined, PlusOutlined, UploadOutlined } from '@ant-design/icons'
import apiClient from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { envPackageFileUrl, operatorHeaders, useCreateEnvPackage, useDeleteEnvPackage, useDeviceProfiles, useEnvPackages, useManagedDevices } from '../hooks/useEnvironmentPackages'
import { formatPackageType, packageTypeFilterOptions, packageTypeOptions } from '../constants/packageTypes'
import { formatVisibility, visibilityOptions, visibilityTagColor } from '../constants/visibility'
import type { EnvPackage, EnvPackagePayload } from '../types/environmentPackage'

const { Title, Text } = Typography

const statusColor: Record<string, string> = {
  active: 'green',
  draft: 'gold',
  inactive: 'default',
  ok: 'green',
  missing_checksum: 'orange',
  missing_script: 'orange',
  missing_compatibility: 'gold',
}

function StatusTag({ value }: { value?: string }) {
  return <Tag color={statusColor[value || ''] ?? 'blue'}>{value || '-'}</Tag>
}

function formatDateTime(value?: string) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', { hour12: false })
}

function toPayload(values: Record<string, unknown>): EnvPackagePayload {
  return {
    ...values,
    install_order: Number(values.install_order ?? 100),
    requires_root: Boolean(values.requires_root),
    requires_reboot: Boolean(values.requires_reboot),
    offline_supported: values.offline_supported !== false,
  }
}

function canManagePackage(item: EnvPackage, username?: string, isAdmin = false): boolean {
  return Boolean(isAdmin || (username && item.owner_id === username))
}

function ScriptPreview({ title, value }: { title: string; value?: string }) {
  return (
    <Card size="small" title={title}>
      <pre style={{ margin: 0, whiteSpace: 'pre-wrap', maxHeight: 220, overflow: 'auto' }}>{value || '未填写'}</pre>
    </Card>
  )
}

export default function EnvironmentPackagesPage() {
  const auth = useAuth()
  const operator = auth.user ? { ...auth.user, access_token: auth.token } : null
  const [selected, setSelected] = useState<EnvPackage | null>(null)
  const [open, setOpen] = useState(false)
  const [form] = Form.useForm()
  const [deviceFilter, setDeviceFilter] = useState('')
  const [profileFilter, setProfileFilter] = useState('')
  const [packageTypeFilter, setPackageTypeFilter] = useState('')

  const packages = useEnvPackages(operator, { device_id: deviceFilter, profile_id: profileFilter, package_type: packageTypeFilter })
  const devices = useManagedDevices()
  const profiles = useDeviceProfiles()
  const createPackage = useCreateEnvPackage(operator)
  const deletePackage = useDeleteEnvPackage(operator)
  const data = packages.data ?? []
  const stats = useMemo(
    () => ({
      total: data.length,
      active: data.filter((item) => item.status === 'active').length,
      issues: data.filter((item) => item.quality_status !== 'ok').length,
    }),
    [data],
  )

  const profileOptions = (profiles.data ?? []).map((profile) => ({ value: profile.profile_id, label: profile.label }))

  const openCreate = () => {
    form.resetFields()
    form.setFieldsValue({
      checksum_type: 'sha256',
      status: 'draft',
      visibility: 'private',
      offline_supported: true,
      install_order: 100,
      depends_on: '',
      install_script: '',
      verify_script: '',
      uninstall_script: '',
    })
    setOpen(true)
  }

  const handleUpload = async (options: any) => {
    const formData = new FormData()
    formData.append('file', options.file)
    try {
      const { data: response } = await apiClient.post('/environment-packages/uploads', formData, {
        headers: { ...operatorHeaders(operator), 'Content-Type': 'multipart/form-data' },
      })
      form.setFieldsValue({
        file_uri: response.item.file_uri,
        file_name: response.item.file_name,
        checksum_type: response.item.checksum_type,
        checksum: response.item.checksum,
      })
      message.success('文件已上传并计算 checksum')
      options.onSuccess?.(response)
    } catch (error) {
      message.error('上传失败')
      options.onError?.(error)
    }
  }

  const submit = async () => {
    const values = await form.validateFields()
    await createPackage.mutateAsync(toPayload(values))
    message.success('安装包已创建')
    setOpen(false)
  }

  const removePackage = async (item: EnvPackage) => {
    try {
      await deletePackage.mutateAsync(item.package_id)
      if (selected?.package_id === item.package_id) setSelected(null)
      message.success('环境包资产已删除')
    } catch (error: any) {
      const code = error?.response?.data?.code
      const text = code === 'PACKAGE_IN_USE'
        ? '该环境包资产已被交付包使用，不可删除。'
        : (error?.response?.data?.message || '删除失败')
      message.error(text)
    }
  }

  const canDownload = (item: EnvPackage) => Boolean(item.file_uri && item.file_uri.startsWith('filesystem://'))
  const canManage = (item: EnvPackage) => canManagePackage(item, auth.user?.username, auth.isAdmin)

  const editorPageUrl = (item: EnvPackage) => `/environment-packages/${item.package_id}/editor`

  const downloadPackage = (item: EnvPackage) => {
    if (!canDownload(item)) {
      message.warning('该环境包没有可下载的本地文件')
      return
    }
    const url = auth.token ? `${envPackageFileUrl(item.package_id)}?access_token=${encodeURIComponent(auth.token)}` : envPackageFileUrl(item.package_id)
    window.open(url, '_blank')
  }

  const columns = [
    {
      title: '安装包',
      dataIndex: 'name',
      render: (_: string, item: EnvPackage) => (
        <Space direction="vertical" size={0}>
          <Button type="link" style={{ padding: 0 }} onClick={() => setSelected(item)}>{item.name}</Button>
          <Text type="secondary">{item.package_code}</Text>
        </Space>
      ),
    },
    { title: '类型', dataIndex: 'package_type', render: (value: string) => <Tag color={value === 'patch' ? 'purple' : 'blue'}>{formatPackageType(value)}</Tag> },
    { title: '版本', dataIndex: 'version' },
    { title: '顺序', dataIndex: 'install_order', sorter: (a: EnvPackage, b: EnvPackage) => (a.install_order ?? 100) - (b.install_order ?? 100) },
    {
      title: '最后更新时间',
      dataIndex: 'updated_at',
      render: (value: string) => formatDateTime(value),
      sorter: (a: EnvPackage, b: EnvPackage) => new Date(a.updated_at || 0).getTime() - new Date(b.updated_at || 0).getTime(),
    },
    {
      title: '适配设备配置',
      render: (_: unknown, item: EnvPackage) => item.device_profiles.length
        ? item.device_profiles.map((profile) => <Tag key={profile.profile_id}>{profile.name}</Tag>)
        : <Tag color="gold">未配置</Tag>,
    },
    { title: '质量状态', dataIndex: 'quality_status', render: (value: string) => <StatusTag value={value} /> },
    { title: '状态', dataIndex: 'status', render: (value: string) => <StatusTag value={value} /> },
    { title: '可见性', dataIndex: 'visibility', render: (value: string) => <Tag color={visibilityTagColor(value)}>{formatVisibility(value)}</Tag> },
    { title: 'Owner', dataIndex: 'owner_id' },
    {
      title: '操作',
      render: (_: unknown, item: EnvPackage) => (
        <Space>
          <Button size="small" onClick={() => setSelected(item)}>查看</Button>
          {canManage(item) && <Button data-testid={`edit-package-${item.package_id}`} size="small" type="primary" href={editorPageUrl(item)} target="_blank" rel="noopener noreferrer">编辑</Button>}
          <Button size="small" icon={<DownloadOutlined />} disabled={!canDownload(item)} onClick={() => downloadPackage(item)}>下载</Button>
          {canManage(item) && <Popconfirm title="确认删除此环境包资产？" description="已被交付包使用的资产会被系统拒绝删除。" onConfirm={() => removePackage(item)}>
            <Button data-testid={`delete-package-${item.package_id}`} size="small" danger icon={<DeleteOutlined />} loading={deletePackage.isPending}>删除</Button>
          </Popconfirm>}
        </Space>
      ),
    },
  ]

  return (
    <div style={{ padding: 24 }}>
      <Space direction="vertical" size={16} style={{ width: '100%' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <div>
            <Title level={3} style={{ marginBottom: 4 }}>环境包资产</Title>
            <Text type="secondary">当前用户：{auth.user?.display_name || auth.user?.username}。页面默认展示自己的资产，以及其他用户共享给你的资产；共享资产可看、可下、可引用，但不可修改。</Text>
          </div>
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>上传安装包</Button>
        </div>

        <Alert type="warning" showIcon message="复杂编辑已移至独立编辑工作台。点击环境包的“编辑”会新开页面，信息编辑与文件编辑分开管理。" />

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
          <Card><Statistic title="全部可见资产" value={stats.total} /></Card>
          <Card><Statistic title="可用于组合" value={stats.active} /></Card>
          <Card><Statistic title="质量问题" value={stats.issues} /></Card>
        </div>

        <Card>
          <Space wrap style={{ marginBottom: 16 }}>
            <Select allowClear showSearch style={{ width: 260 }} placeholder="按设备筛选环境包" value={deviceFilter || undefined} onChange={(value) => { setDeviceFilter(value || ''); setProfileFilter('') }} options={(devices.data ?? []).map((item) => ({ value: item.device_id, label: `${item.name || item.device_code} / ${item.os_type} ${item.os_version} / ${item.accelerator_model}` }))} />
            <Select allowClear showSearch style={{ width: 320 }} placeholder="按适配配置筛选环境包" value={profileFilter || undefined} onChange={(value) => { setProfileFilter(value || ''); setDeviceFilter('') }} options={profileOptions} />
            <Select style={{ width: 160 }} value={packageTypeFilter} onChange={setPackageTypeFilter} options={packageTypeFilterOptions} />
            {(deviceFilter || profileFilter || packageTypeFilter) && <Button onClick={() => { setDeviceFilter(''); setProfileFilter(''); setPackageTypeFilter('') }}>清空筛选</Button>}
          </Space>
          <Table rowKey="package_id" loading={packages.isLoading} dataSource={data} columns={columns} pagination={{ pageSize: 8 }} />
        </Card>
      </Space>

      <Drawer
        title={selected?.name}
        open={Boolean(selected)}
        width={680}
        onClose={() => setSelected(null)}
        extra={selected && (
          <Space>
            {canManage(selected) && <Button data-testid={`edit-package-${selected.package_id}`} type="primary" href={editorPageUrl(selected)} target="_blank" rel="noopener noreferrer">编辑</Button>}
            <Button icon={<DownloadOutlined />} disabled={!canDownload(selected)} onClick={() => downloadPackage(selected)}>下载环境包</Button>
            {canManage(selected) && <Popconfirm title="确认删除此环境包资产？" description="已被交付包使用的资产会被系统拒绝删除。" onConfirm={() => removePackage(selected)}>
              <Button data-testid={`delete-package-${selected.package_id}`} danger icon={<DeleteOutlined />} loading={deletePackage.isPending}>删除</Button>
            </Popconfirm>}
          </Space>
        )}
      >
        {selected && (
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            <Descriptions
              bordered
              column={1}
              size="small"
              items={[
                { key: 'code', label: '包编码', children: selected.package_code },
                { key: 'type', label: '类型/版本', children: `${formatPackageType(selected.package_type)} / ${selected.version}` },
                { key: 'order', label: '安装顺序', children: selected.install_order ?? 100 },
                { key: 'depends', label: '依赖关系', children: selected.depends_on || '无' },
                { key: 'file', label: '文件 URI', children: selected.file_uri || '-' },
                { key: 'checksum', label: 'Checksum', children: selected.checksum ? `${selected.checksum_type}:${selected.checksum}` : <Tag color="gold">未填写</Tag> },
                { key: 'owner', label: '资产归属', children: selected.owner_id },
                { key: 'visibility', label: '可见性', children: <Tag color={visibilityTagColor(selected.visibility)}>{formatVisibility(selected.visibility)}</Tag> },
                { key: 'created', label: '创建时间', children: formatDateTime(selected.created_at) },
                { key: 'updated', label: '最后更新时间', children: formatDateTime(selected.updated_at) },
                {
                  key: 'profiles',
                  label: '适配设备配置',
                  children: selected.device_profiles.length
                    ? selected.device_profiles.map((profile) => <Tag key={profile.profile_id}>{profile.label}</Tag>)
                    : <Tag color="gold">未配置</Tag>,
                },
              ]}
            />
            {!canManage(selected) && <Alert type="info" showIcon message="这是其他用户共享给你的只读资产：可查看、下载、引用，但不可编辑或删除。" />}
            {canManage(selected) && <Alert type="info" showIcon message="如需修改信息、脚本或包内文件，请点击“编辑”进入独立工作台。" />}
            <ScriptPreview title="真实安装脚本" value={selected.install_script} />
            <ScriptPreview title="真实校验脚本" value={selected.verify_script} />
            <ScriptPreview title="卸载脚本" value={selected.uninstall_script} />
          </Space>
        )}
      </Drawer>

      <Modal
        title="上传安装包"
        open={open}
        onCancel={() => setOpen(false)}
        onOk={submit}
        confirmLoading={createPackage.isPending}
        width={860}
        okText="创建"
      >
        <Form form={form} layout="vertical">
          <Alert style={{ marginBottom: 16 }} type="info" showIcon message="适配条件来自设备管理模块；这里只能选择已有设备配置。创建后请进入独立编辑工作台维护脚本与包内容。" />
          <Upload.Dragger multiple={false} maxCount={1} customRequest={handleUpload} style={{ marginBottom: 16 }}>
            <p><UploadOutlined style={{ fontSize: 24 }} /></p>
            <p>点击或拖拽上传安装包文件</p>
          </Upload.Dragger>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            <Form.Item name="name" label="包名称" rules={[{ required: true }]}><Input /></Form.Item>
            <Form.Item name="package_code" label="包编码" rules={[{ required: true }]}><Input /></Form.Item>
            <Form.Item name="package_type" label="包类型" rules={[{ required: true }]}><Select options={packageTypeOptions} /></Form.Item>
            <Form.Item name="version" label="版本" rules={[{ required: true }]}><Input /></Form.Item>
            <Form.Item name="file_uri" label="文件 URI"><Input prefix={<UploadOutlined />} /></Form.Item>
            <Form.Item name="file_name" label="文件名"><Input /></Form.Item>
            <Form.Item name="checksum_type" label="Checksum 类型"><Select options={[{ value: 'sha256' }, { value: 'md5' }]} /></Form.Item>
            <Form.Item name="checksum" label="Checksum"><Input /></Form.Item>
            <Form.Item name="install_order" label="安装顺序"><InputNumber min={0} style={{ width: '100%' }} /></Form.Item>
            <Form.Item name="depends_on" label="依赖关系"><Input placeholder='例如：["python-runtime"]' /></Form.Item>
            <Form.Item name="device_profile_ids" label="适配设备配置" rules={[{ required: true, message: '请选择至少一个设备配置' }]} style={{ gridColumn: '1 / -1' }}>
              <Select mode="multiple" showSearch loading={profiles.isLoading} placeholder="选择设备配置，不允许手填" notFoundContent="暂无可选设备配置，请先在设备管理中新增" options={profileOptions} />
            </Form.Item>
            <Form.Item name="install_script" label="安装脚本" style={{ gridColumn: '1 / -1' }}><Input.TextArea rows={4} /></Form.Item>
            <Form.Item name="verify_script" label="成功检查脚本" style={{ gridColumn: '1 / -1' }}><Input.TextArea rows={4} /></Form.Item>
            <Form.Item name="uninstall_script" label="卸载脚本" style={{ gridColumn: '1 / -1' }}><Input.TextArea rows={2} /></Form.Item>
            <Form.Item name="status" label="状态"><Select options={[{ value: 'draft' }, { value: 'active' }, { value: 'inactive' }]} /></Form.Item>
            <Form.Item name="visibility" label="可见性"><Select options={visibilityOptions} /></Form.Item>
            <Form.Item name="requires_root" label="需要 root" valuePropName="checked"><Switch /></Form.Item>
            <Form.Item name="requires_reboot" label="需要重启" valuePropName="checked"><Switch /></Form.Item>
            <Form.Item name="offline_supported" label="支持离线" valuePropName="checked"><Switch /></Form.Item>
          </div>
        </Form>
      </Modal>
    </div>
  )
}
