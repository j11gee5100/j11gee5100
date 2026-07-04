import { Alert, Button, Card, Col, Empty, Progress, Row, Space, Spin, Statistic, Table, Tag, Typography } from 'antd'
import { useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { formatPackageType } from '../constants/packageTypes'
import { useDeliveryBundles, useDeviceProfiles, useEnvPackages, useManagedDevices, useProbeResults } from '../hooks/useEnvironmentPackages'
import type { DeliveryBundle, EnvPackage } from '../types/environmentPackage'

const { Title, Text } = Typography

function scriptReady(item: EnvPackage) {
  return Boolean(item.install_script && item.verify_script)
}

function buildStatusTag(status?: string) {
  const color = status === 'success' ? 'green' : status === 'failed' ? 'red' : status === 'building' ? 'blue' : 'default'
  return <Tag color={color}>{status || 'not_built'}</Tag>
}

export default function DashboardPage() {
  const navigate = useNavigate()
  const auth = useAuth()
  const operator = auth.user ? { ...auth.user, access_token: auth.token } : null
  const packages = useEnvPackages(operator)
  const devices = useManagedDevices()
  const profiles = useDeviceProfiles()
  const bundles = useDeliveryBundles(operator)
  const probes = useProbeResults(operator)

  const loading = packages.isLoading || devices.isLoading || profiles.isLoading || bundles.isLoading || probes.isLoading
  const hasError = packages.isError || devices.isError || profiles.isError || bundles.isError || probes.isError

  const data = useMemo(() => {
    const packageItems = packages.data ?? []
    const bundleItems = bundles.data ?? []
    const okPackages = packageItems.filter((item) => item.quality_status === 'ok').length
    const scriptReadyCount = packageItems.filter(scriptReady).length
    const builtBundles = bundleItems.filter((item) => item.build_status === 'success').length
    const draftBundles = bundleItems.filter((item) => item.status === 'draft' || item.build_status !== 'success').length
    const typeRows = Object.entries(packageItems.reduce<Record<string, number>>((acc, item) => {
      acc[item.package_type || 'custom'] = (acc[item.package_type || 'custom'] || 0) + 1
      return acc
    }, {})).map(([type, count]) => ({ type, count }))
    const recentBundles = [...bundleItems].sort((a, b) => (b.updated_at || '').localeCompare(a.updated_at || '')).slice(0, 6)
    const riskyPackages = packageItems.filter((item) => !scriptReady(item) || item.quality_status !== 'ok').slice(0, 6)
    return { packageItems, bundleItems, okPackages, scriptReadyCount, builtBundles, draftBundles, typeRows, recentBundles, riskyPackages }
  }, [packages.data, bundles.data])

  if (loading) return <div style={{ padding: 48, textAlign: 'center' }}><Spin tip="加载推理环境交付看板..." /></div>

  if (hasError) {
    return <div style={{ padding: 24 }}><Alert type="error" showIcon message="看板数据加载失败" description="请确认后端服务和登录状态正常。" /></div>
  }

  const packageQualityPercent = data.packageItems.length ? Math.round((data.okPackages / data.packageItems.length) * 100) : 0
  const scriptReadyPercent = data.packageItems.length ? Math.round((data.scriptReadyCount / data.packageItems.length) * 100) : 0
  const bundleBuiltPercent = data.bundleItems.length ? Math.round((data.builtBundles / data.bundleItems.length) * 100) : 0

  const typeColumns = [
    { title: '安装项类型', dataIndex: 'type', render: (value: string) => formatPackageType(value) },
    { title: '数量', dataIndex: 'count', width: 90 },
  ]

  const bundleColumns = [
    { title: '交付包', render: (_: unknown, item: DeliveryBundle) => <Space direction="vertical" size={0}><Button type="link" style={{ padding: 0 }} onClick={() => navigate(`/delivery-bundles/${item.bundle_id}`)}>{item.name}</Button><Text type="secondary">{item.bundle_code} / {item.version}</Text></Space> },
    { title: '构建状态', dataIndex: 'build_status', render: buildStatusTag, width: 120 },
    { title: '小包数', render: (_: unknown, item: DeliveryBundle) => item.package_ids.length, width: 90 },
    { title: '产物', render: (_: unknown, item: DeliveryBundle) => item.artifact_name || '-', width: 180 },
  ]

  const riskyColumns = [
    { title: '安装项', render: (_: unknown, item: EnvPackage) => <Space direction="vertical" size={0}><Text strong>{item.name}</Text><Text type="secondary">{item.package_code} / {item.version}</Text></Space> },
    { title: '类型', dataIndex: 'package_type', render: (value: string) => formatPackageType(value), width: 120 },
    { title: '质量', dataIndex: 'quality_status', render: (value: string) => <Tag color={value === 'ok' ? 'green' : 'orange'}>{value}</Tag>, width: 100 },
    { title: '脚本', render: (_: unknown, item: EnvPackage) => scriptReady(item) ? <Tag color="green">齐全</Tag> : <Tag color="orange">缺失</Tag>, width: 100 },
  ]

  return (
    <div style={{ padding: 24, background: '#f5f7fb', minHeight: '100%' }}>
      <Space direction="vertical" size={16} style={{ width: '100%' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <Title level={3} style={{ marginBottom: 4 }}>AI 推理环境交付看板</Title>
            <Text type="secondary">围绕设备画像、安装项资产、交付包制作和 Agent/MCP 交付闭环的实时概览。</Text>
          </div>
          <Space>
            <Button onClick={() => navigate('/environment-packages')}>管理环境包</Button>
            <Button type="primary" onClick={() => navigate('/delivery-bundles')}>进入交付包</Button>
          </Space>
        </div>

        <Row gutter={[16, 16]}>
          <Col xs={24} md={12} xl={6}><Card><Statistic title="环境包资产" value={data.packageItems.length} suffix="个" /><Progress percent={packageQualityPercent} size="small" status={packageQualityPercent < 70 ? 'exception' : 'success'} /><Text type="secondary">质量 OK 占比</Text></Card></Col>
          <Col xs={24} md={12} xl={6}><Card><Statistic title="设备 / 适配配置" value={`${devices.data?.length ?? 0} / ${profiles.data?.length ?? 0}`} /><Text type="secondary">设备画像与可筛选适配条件来源</Text></Card></Col>
          <Col xs={24} md={12} xl={6}><Card><Statistic title="交付包" value={data.bundleItems.length} suffix="个" /><Progress percent={bundleBuiltPercent} size="small" status={bundleBuiltPercent < 50 ? 'normal' : 'success'} /><Text type="secondary">已制作完整包占比</Text></Card></Col>
          <Col xs={24} md={12} xl={6}><Card><Statistic title="探测结果" value={probes.data?.length ?? 0} suffix="份" /><Text type="secondary">离线导入后生成设备画像依据</Text></Card></Col>
        </Row>

        <Row gutter={[16, 16]}>
          <Col xs={24} xl={8}>
            <Card title="资产工程化程度">
              <Space direction="vertical" style={{ width: '100%' }} size={14}>
                <div><Text>两段脚本齐全率</Text><Progress percent={scriptReadyPercent} status={scriptReadyPercent < 80 ? 'exception' : 'success'} /></div>
                <div><Text>环境包质量 OK</Text><Progress percent={packageQualityPercent} status={packageQualityPercent < 80 ? 'exception' : 'success'} /></div>
                <div><Text>交付包已制作</Text><Progress percent={bundleBuiltPercent} /></div>
                <Alert type="info" showIcon message={`当前仍有 ${data.draftBundles} 个交付包未形成完整安装包。`} />
              </Space>
            </Card>
          </Col>
          <Col xs={24} xl={8}>
            <Card title="安装项类型分布">
              {data.typeRows.length ? <Table size="small" rowKey="type" columns={typeColumns} dataSource={data.typeRows} pagination={false} /> : <Empty description="暂无安装项" />}
            </Card>
          </Col>
          <Col xs={24} xl={8}>
            <Card title="推荐操作">
              <Space direction="vertical" style={{ width: '100%' }}>
                <Alert type="success" showIcon message="先维护最小安装项资产" description="显卡驱动、Python 环境、ffmpeg/opencv 等资产应补齐文件、安装脚本、成功检查脚本和适配配置。" />
                <Alert type="info" showIcon message="再编排交付包" description="选择适配配置后筛选小包，保存编排并制作完整安装包。" />
                <Alert type="warning" showIcon message="最后交给实施人员" description="完整包内置 state.json 断点状态模型，失败后重新执行从失败小包继续。" />
              </Space>
            </Card>
          </Col>
        </Row>

        <Row gutter={[16, 16]}>
          <Col xs={24} xl={14}>
            <Card title="最近交付包">
              <Table rowKey="bundle_id" columns={bundleColumns} dataSource={data.recentBundles} pagination={false} locale={{ emptyText: '暂无交付包' }} />
            </Card>
          </Col>
          <Col xs={24} xl={10}>
            <Card title="待完善安装项">
              <Table rowKey="package_id" columns={riskyColumns} dataSource={data.riskyPackages} pagination={false} locale={{ emptyText: '安装项脚本和质量均正常' }} />
            </Card>
          </Col>
        </Row>
      </Space>
    </div>
  )
}
