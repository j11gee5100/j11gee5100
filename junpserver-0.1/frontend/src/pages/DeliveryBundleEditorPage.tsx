import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Alert, Button, Card, Descriptions, Form, Input, List, Modal, Progress, Select, Space, Table, Tag, Typography, message } from 'antd'
import { ArrowDownOutlined, ArrowLeftOutlined, ArrowUpOutlined, DeleteOutlined, DownloadOutlined, PlusOutlined, SaveOutlined, ToolOutlined } from '@ant-design/icons'
import { useAuth } from '../auth/AuthContext'
import { formatPackageType, packageTypeFilterOptions } from '../constants/packageTypes'
import { deliveryBundleArtifactUrl, useBuildDeliveryBundle, useCreateDeliveryBundleVersion, useDeliverDeliveryBundle, useDeliveryBundle, useDeviceProfiles, useEnvPackages, useLatestDeliveryBundleBuildJob, useManagedDevices, useUpdateDeliveryBundle } from '../hooks/useEnvironmentPackages'
import type { DeliveryBundle, EnvPackage } from '../types/environmentPackage'

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

interface ApplicationResource {
  order?: number
  step?: number
  package_code?: string
  name?: string
  version?: string
  package_type?: string
  path?: string
  execution_mode?: string
  manual_install?: boolean
  manual_reason?: string
  manual_package_path?: string
  manual_payload_path?: string
  manual_install_command?: string
  manual_verify_command?: string
  display_install_command?: string
  display_verify_command?: string
  manual_notes?: string[]
}

function manualExecutionTag(item: EnvPackage) {
  return item.package_type === 'application_package' ? <Tag color="gold">应用资源</Tag> : <Tag color="green">自动执行</Tag>
}

function extractApplicationResources(bundle?: DeliveryBundle | null, selectedPackages: EnvPackage[] = []): ApplicationResource[] {
  const manifestResources = (bundle?.manifest?.application_resources ?? []) as ApplicationResource[]
  if (manifestResources.length) return manifestResources
  return selectedPackages
    .filter((item) => item.package_type === 'application_package')
    .map((item, index) => ({
      order: index + 1,
      package_code: item.package_code,
      name: item.name,
      version: item.version,
      package_type: item.package_type,
      execution_mode: 'resource_only',
      resource_only: true,
      manual_reason: '应用包只随交付包携带，不进入根 install.sh / run_bundle.py 自动安装流程。',
      path: `application_packages/${String(index + 1).padStart(3, '0')}-${item.package_code}`,
      manual_notes: ['应用包部署方式以交付包内上传的部署文档为准。'],
    }))
}

function scriptStatus(item: EnvPackage) {
  const missing = []
  if (!item.install_script) missing.push('安装')
  if (!item.verify_script) missing.push('成功检查')
  return missing.length ? <Tag color="orange">缺{missing.join('/')}</Tag> : <Tag color="green">两段脚本齐全</Tag>
}

function buildManifest(values: Record<string, unknown>, selectedPackages: EnvPackage[]) {
  return {
    bundle_code: values.bundle_code || '',
    name: values.name || '',
    version: values.version || '1.0.0',
    bundle_type: values.bundle_type || 'first_install',
    status: 'draft',
    target: {
      device_id: values.target_device_id || '',
      profile_id: values.target_profile_id || '',
    },
    packages: selectedPackages.filter((item) => item.package_type !== 'application_package').map((item, index) => ({
      step: index + 1,
      package_id: item.package_id,
      package_code: item.package_code,
      name: item.name,
      version: item.version,
      package_type: item.package_type,
      install_order: item.install_order,
      depends_on: item.depends_on,
      install_script: item.install_script,
      verify_script: item.verify_script,
      runtime_rule: '大包总控脚本读取 state.json；success 跳过，非 success 执行 install_script -> verify_script',
    })),
    application_resources: selectedPackages.filter((item) => item.package_type === 'application_package').map((item, index) => ({
      order: index + 1,
      package_id: item.package_id,
      package_code: item.package_code,
      name: item.name,
      version: item.version,
      package_type: item.package_type,
      path: `application_packages/${String(index + 1).padStart(3, '0')}-${item.package_code}`,
      runtime_rule: '仅随交付包携带；不进入根 install.sh / run_bundle.py；部署方式以部署文档为准',
    })),
  }
}

export default function DeliveryBundleEditorPage() {
  const { bundleId } = useParams()
  const navigate = useNavigate()
  const auth = useAuth()
  const operator = auth.user ? { ...auth.user, access_token: auth.token } : null
  const bundle = useDeliveryBundle(bundleId, operator)
  const packages = useEnvPackages(operator)
  const devices = useManagedDevices()
  const profiles = useDeviceProfiles()
  const updateBundle = useUpdateDeliveryBundle(operator)
  const buildBundle = useBuildDeliveryBundle(operator)
  const deliverBundle = useDeliverDeliveryBundle(operator)
  const createVersion = useCreateDeliveryBundleVersion(operator)
  const latestJob = useLatestDeliveryBundleBuildJob(bundleId, operator)
  const [form] = Form.useForm()
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [packageTypeFilter, setPackageTypeFilter] = useState('')
  const [versionModalOpen, setVersionModalOpen] = useState(false)
  const [versionForm] = Form.useForm()
  const watchedValues = Form.useWatch([], form) || {}
  const targetProfileId = Form.useWatch('target_profile_id', form) as string | undefined
  const isDelivered = bundle.data?.lifecycle_status === 'delivered'
  const isBuilding = bundle.data?.build_status === 'queued' || bundle.data?.build_status === 'running' || latestJob.data?.job_status === 'queued' || latestJob.data?.job_status === 'running'
  const isReadonly = Boolean(isDelivered || isBuilding)

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

  const packageMap = useMemo(() => new Map((packages.data ?? []).map((item) => [item.package_id, item])), [packages.data])
  const selectedPackages = selectedIds.map((id) => packageMap.get(id)).filter(Boolean) as EnvPackage[]
  const selectedSet = new Set(selectedIds)
  const availablePackages = (packages.data ?? []).filter((item) => {
    if (selectedSet.has(item.package_id)) return false
    if (!targetProfileId) return false
    const matchesProfile = item.device_profiles.some((profile) => profile.profile_id === targetProfileId)
    if (!matchesProfile) return false
    if (packageTypeFilter && item.package_type !== packageTypeFilter) return false
    return true
  })
  const manifest = useMemo(() => buildManifest({ ...watchedValues, bundle_code: bundle.data?.bundle_code }, selectedPackages), [watchedValues, selectedPackages, bundle.data?.bundle_code])
  const applicationResources = useMemo(() => extractApplicationResources(bundle.data as DeliveryBundle | undefined, selectedPackages), [bundle.data, selectedPackages])

  useEffect(() => {
    if (!bundle.data) return
    form.setFieldsValue({
      bundle_code: bundle.data.bundle_code,
      name: bundle.data.name,
      version: bundle.data.version,
      bundle_type: bundle.data.bundle_type || 'first_install',
      target_device_id: bundle.data.target_device_id || undefined,
      target_profile_id: bundle.data.target_profile_id || undefined,
    })
    setSelectedIds(bundle.data.package_ids ?? [])
  }, [bundle.data, form])

  const move = (packageId: string, direction: -1 | 1) => {
    if (isReadonly) return
    setSelectedIds((ids) => {
      const index = ids.indexOf(packageId)
      const nextIndex = index + direction
      if (index < 0 || nextIndex < 0 || nextIndex >= ids.length) return ids
      const next = [...ids]
      const [removed] = next.splice(index, 1)
      next.splice(nextIndex, 0, removed)
      return next
    })
  }

  const remove = (packageId: string) => { if (!isReadonly) setSelectedIds((ids) => ids.filter((id) => id !== packageId)) }
  const add = (packageId: string) => { if (!isReadonly) setSelectedIds((ids) => ids.includes(packageId) ? ids : [...ids, packageId]) }

  const save = async () => {
    if (!bundleId || isReadonly) return
    if (!selectedIds.length) {
      message.error('至少选择一个安装项')
      return
    }
    const values = await form.validateFields()
    await updateBundle.mutateAsync({
      bundleId,
      payload: {
        name: values.name,
        version: values.version,
        bundle_type: values.bundle_type || 'first_install',
        target_device_id: values.target_device_id || '',
        target_profile_id: values.target_profile_id || '',
        package_ids: selectedIds,
      },
    })
    message.success('交付包编排已保存')
  }

  const build = async () => {
    if (!bundleId || isReadonly) return
    await save()
    await buildBundle.mutateAsync(bundleId)
    message.success('制作任务已提交，请在任务面板查看进度')
  }

  const download = () => {
    if (!bundleId || !bundle.data?.artifact_name) return
    const url = auth.token ? `${deliveryBundleArtifactUrl(bundleId)}?access_token=${encodeURIComponent(auth.token)}` : deliveryBundleArtifactUrl(bundleId)
    window.open(url, '_blank')
  }

  const deliver = async () => {
    if (!bundleId) return
    await deliverBundle.mutateAsync(bundleId)
    message.success('交付包已确认交付，资产已锁定')
  }

  const createNewVersion = async () => {
    if (!bundleId) return
    const values = await versionForm.validateFields()
    const response = await createVersion.mutateAsync({ bundleId, payload: values })
    message.success('新版本已创建')
    setVersionModalOpen(false)
    navigate(`/delivery-bundles/${response.item.bundle_id}`)
  }

  const selectedColumns = [
    { title: '顺序', render: (_: unknown, __: EnvPackage, index: number) => index + 1, width: 70 },
    { title: '安装项', render: (_: unknown, item: EnvPackage) => <Space direction="vertical" size={0}><Text strong>{item.name}</Text><Text type="secondary">{item.package_code} / {item.version}</Text></Space> },
    { title: '类型', dataIndex: 'package_type', width: 120, render: (value: string) => formatPackageType(value) },
    { title: '资产顺序', dataIndex: 'install_order', width: 90 },
    { title: '脚本完整性', render: (_: unknown, item: EnvPackage) => scriptStatus(item), width: 140 },
    { title: '执行模式', render: (_: unknown, item: EnvPackage) => manualExecutionTag(item), width: 110 },
    {
      title: '操作',
      width: 220,
      render: (_: unknown, item: EnvPackage, index: number) => (
        <Space>
          <Button size="small" icon={<ArrowUpOutlined />} disabled={isReadonly || index === 0} onClick={() => move(item.package_id, -1)}>上移</Button>
          <Button size="small" icon={<ArrowDownOutlined />} disabled={isReadonly || index === selectedPackages.length - 1} onClick={() => move(item.package_id, 1)}>下移</Button>
          <Button size="small" danger icon={<DeleteOutlined />} disabled={isReadonly} onClick={() => remove(item.package_id)}>移除</Button>
        </Space>
      ),
    },
  ]

  const availableColumns = [
    { title: '安装项', render: (_: unknown, item: EnvPackage) => <Space direction="vertical" size={0}><Text strong>{item.name}</Text><Text type="secondary">{item.package_code} / {item.version}</Text></Space> },
    { title: '类型', dataIndex: 'package_type', width: 120, render: (value: string) => formatPackageType(value) },
    { title: '顺序', dataIndex: 'install_order', width: 80 },
    { title: '质量', dataIndex: 'quality_status', render: (value: string) => <Tag color={value === 'ok' ? 'green' : 'orange'}>{value}</Tag>, width: 130 },
    { title: '脚本', render: (_: unknown, item: EnvPackage) => scriptStatus(item), width: 140 },
    { title: '执行模式', render: (_: unknown, item: EnvPackage) => manualExecutionTag(item), width: 110 },
    { title: '操作', render: (_: unknown, item: EnvPackage) => <Button size="small" icon={<PlusOutlined />} disabled={isReadonly} onClick={() => add(item.package_id)}>加入</Button>, width: 90 },
  ]

  return (
    <div style={{ padding: 24 }}>
      <Space direction="vertical" size={16} style={{ width: '100%' }}>
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/delivery-bundles')}>返回列表</Button>
          <Title level={3} style={{ margin: 0 }}>交付包编辑编排</Title>
        </Space>
        <Alert type={isDelivered ? 'success' : 'info'} showIcon message={isDelivered ? '该交付包已交付，资产已锁定；如需修改请创建新版本。' : '这里编辑交付包类型和大包 manifest 编排；制作安装包会进入后台任务，可查看进度和日志。'} />

        <Card title="基础信息" loading={bundle.isLoading} extra={<Space><Button icon={<SaveOutlined />} disabled={isReadonly} loading={updateBundle.isPending} onClick={save}>保存编排</Button><Button type="primary" icon={<ToolOutlined />} disabled={isReadonly} loading={buildBundle.isPending || updateBundle.isPending} onClick={build}>{isBuilding ? '制作中' : '制作安装包'}</Button><Button icon={<DownloadOutlined />} disabled={bundle.data?.build_status !== 'success'} onClick={download}>下载完整包</Button><Button disabled={isDelivered || bundle.data?.build_status !== 'success'} onClick={deliver}>确认交付</Button>{isDelivered && <Button onClick={() => { versionForm.setFieldsValue({ bundle_code: `${bundle.data?.bundle_code}-vnext`, version: bundle.data?.version }); setVersionModalOpen(true) }}>创建新版本</Button>}</Space>}>
          <Form form={form} layout="vertical">
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16 }}>
              <Form.Item name="bundle_code" label="交付包编码"><Input disabled /></Form.Item>
              <Form.Item name="name" label="交付包名称" rules={[{ required: true }]}><Input disabled={isReadonly} /></Form.Item>
              <Form.Item name="version" label="版本"><Input disabled={isReadonly} /></Form.Item>
              <Form.Item name="bundle_type" label="交付类型" rules={[{ required: true }]}><Select disabled={isReadonly} options={bundleTypeOptions} /></Form.Item>
              <Form.Item name="target_device_id" label="目标设备"><Select disabled={isReadonly} allowClear showSearch onChange={(value) => { form.setFieldsValue({ target_profile_id: inferProfileIdFromDevice(value) }); setSelectedIds([]) }} options={(devices.data ?? []).map((item) => ({ value: item.device_id, label: `${item.name || item.device_code} / ${item.accelerator_model}` }))} /></Form.Item>
              <Form.Item name="target_profile_id" label="适配配置" rules={[{ required: true, message: '请选择适配配置后再编排安装项' }]}><Select disabled={isReadonly} allowClear showSearch onChange={() => { form.setFieldsValue({ target_device_id: undefined }); setSelectedIds([]) }} options={(profiles.data ?? []).map((item) => ({ value: item.profile_id, label: item.label }))} /></Form.Item>
            </div>
          </Form>
        </Card>

        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1.4fr) minmax(360px, 0.9fr)', gap: 16 }}>
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            <Card title={`已选小包编排（${selectedPackages.length}）`}>
              <Table rowKey="package_id" dataSource={selectedPackages} columns={selectedColumns} pagination={false} />
            </Card>
            <Card title="可选安装项资产" extra={<Select style={{ width: 160 }} value={packageTypeFilter} onChange={setPackageTypeFilter} options={packageTypeFilterOptions} />}>
              {!targetProfileId && <Alert style={{ marginBottom: 12 }} type="warning" showIcon message="请先选择适配配置；可选安装项会按该配置加载。" />}
              {targetProfileId && <Alert style={{ marginBottom: 12 }} type="info" showIcon message="当前列表只显示匹配所选适配配置的安装项，可继续按包类型筛选。" />}
              <Table rowKey="package_id" loading={packages.isLoading} dataSource={availablePackages} columns={availableColumns} pagination={{ pageSize: 6 }} />
            </Card>
          </Space>

          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            <Card title="大包制作与执行状态">
              <Descriptions column={1} size="small" bordered items={[
                { key: 'asset', label: '资产状态', children: <Tag color={isDelivered ? 'green' : 'gold'}>{isDelivered ? '已交付' : '制作中'}</Tag> },
                { key: 'type', label: '交付类型', children: <Tag color={bundleTypeColor[bundle.data?.bundle_type || 'first_install'] || 'default'}>{bundleTypeLabel[bundle.data?.bundle_type || 'first_install']}</Tag> },
                { key: 'build', label: '制作状态', children: <Tag color={bundle.data?.build_status === 'success' ? 'green' : 'default'}>{bundle.data?.build_status || 'not_built'}</Tag> },
                { key: 'artifact', label: '产物', children: bundle.data?.artifact_name || '-' },
                { key: 'size', label: '大小', children: bundle.data?.artifact_size ? `${Math.ceil(bundle.data.artifact_size / 1024)} KB` : '-' },
                { key: 'checksum', label: '校验', children: bundle.data?.artifact_checksum || '-' },
                { key: 'state', label: '状态文件', children: 'state.json 只记录自动安装小包 status' },
                { key: 'skip', label: 'success', children: '跳过该小包，继续下一个' },
                { key: 'retry', label: '非 success', children: '重新执行该小包 install -> verify' },
                { key: 'fail', label: '失败', children: '记录失败阶段和日志，中断大包安装' },
                { key: 'app', label: '应用包', children: '只放入 application_packages/，不受根 install.sh / run_bundle.py 管理' },
              ]} />
              {bundle.data?.build_log && <pre style={{ marginTop: 12, maxHeight: 180, overflow: 'auto', background: '#fafafa', padding: 12 }}>{bundle.data.build_log}</pre>}
            </Card>
            <Card title="后台制作任务">
              {latestJob.data ? (
                <Space direction="vertical" style={{ width: '100%' }}>
                  <Progress percent={latestJob.data.progress_percent || 0} status={latestJob.data.job_status === 'failed' ? 'exception' : latestJob.data.job_status === 'success' ? 'success' : 'active'} />
                  <Descriptions column={1} size="small" bordered items={[
                    { key: 'status', label: '任务状态', children: <Tag>{latestJob.data.job_status}</Tag> },
                    { key: 'step', label: '当前步骤', children: latestJob.data.current_step || '-' },
                    { key: 'message', label: '当前消息', children: latestJob.data.current_message || '-' },
                    { key: 'artifact', label: '产物', children: latestJob.data.artifact_name || '-' },
                  ]} />
                  <pre style={{ maxHeight: 220, overflow: 'auto', background: '#fafafa', padding: 12, margin: 0 }}>{latestJob.data.log_text || '暂无日志'}</pre>
                </Space>
              ) : <Text type="secondary">暂无制作任务。点击“制作安装包”后会在这里显示进度和日志。</Text>}
            </Card>
            <Card title={`应用包资源（${applicationResources.length}）`}>
              {applicationResources.length ? (
                <List
                  dataSource={applicationResources}
                  renderItem={(resource) => (
                    <List.Item>
                      <Space direction="vertical" size={8} style={{ width: '100%' }}>
                        <Space wrap>
                          <Text strong>{resource.name || resource.package_code}</Text>
                          <Tag color="gold">应用资源</Tag>
                          <Tag>{resource.package_type || 'application_package'}</Tag>
                        </Space>
                        <Descriptions column={1} size="small" bordered items={[
                          { key: 'path', label: '资源路径', children: resource.path || resource.manual_package_path || '-' },
                          { key: 'runtime', label: '自动安装', children: '不进入根目录 install.sh / scripts/run_bundle.py，不写入自动安装 state.json。' },
                          { key: 'reason', label: '说明', children: resource.manual_reason || '应用包只作为交付资源携带；部署方式以后由上传的部署文档说明。' },
                          { key: 'notes', label: '注意事项', children: (resource.manual_notes?.length ? resource.manual_notes.join('；') : '保留原始应用包目录结构、交互输入和业务安装逻辑。') },
                        ]} />
                      </Space>
                    </List.Item>
                  )}
                />
              ) : <Text type="secondary">当前交付包没有应用包资源。</Text>}
            </Card>
            <Card title="manifest 实时预览">
              <pre style={{ maxHeight: 620, overflow: 'auto', margin: 0 }}>{JSON.stringify(manifest, null, 2)}</pre>
            </Card>
          </Space>
        </div>
      </Space>
      <Modal title="创建新版本" open={versionModalOpen} onCancel={() => setVersionModalOpen(false)} onOk={createNewVersion} confirmLoading={createVersion.isPending}>
        <Form form={versionForm} layout="vertical">
          <Form.Item name="bundle_code" label="新交付包编码" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="version" label="新版本" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="name" label="新交付包名称（可选）"><Input /></Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
