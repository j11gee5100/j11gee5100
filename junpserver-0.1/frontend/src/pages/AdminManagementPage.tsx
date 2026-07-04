import { useMemo, useState } from 'react'
import { Button, Card, Form, Input, Modal, Select, Space, Switch, Table, Tabs, Tag, Typography, message } from 'antd'
import { useAuth } from '../auth/AuthContext'
import { useAdminAssets, useAdminUsers, useCreateUser, useShareAsset, useTransferAsset, useUpdateUser } from '../hooks/useEnvironmentPackages'
import { formatVisibility, visibilityTagColor } from '../constants/visibility'
import type { EnvPackage, UserAccount, UserAccountPayload } from '../types/environmentPackage'

const { Title, Text } = Typography
const roleOptions = [{ label: '管理员', value: 'admin' }, { label: '普通用户', value: 'user' }]

function toUserPayload(values: Record<string, unknown>, editing: boolean): UserAccountPayload {
  const payload = { ...values, enabled: values.enabled !== false } as UserAccountPayload
  if (editing) delete payload.username
  return payload
}

export default function AdminManagementPage() {
  const auth = useAuth()
  const operator = auth.user ? { ...auth.user, access_token: auth.token } : null
  const users = useAdminUsers(operator)
  const assets = useAdminAssets(operator)
  const createUser = useCreateUser(operator)
  const updateUser = useUpdateUser(operator)
  const transferAsset = useTransferAsset(operator)
  const shareAsset = useShareAsset(operator)

  const [editingUser, setEditingUser] = useState<UserAccount | null>(null)
  const [userOpen, setUserOpen] = useState(false)
  const [transferOpen, setTransferOpen] = useState(false)
  const [transferAssetItem, setTransferAssetItem] = useState<EnvPackage | null>(null)
  const [form] = Form.useForm()
  const [transferForm] = Form.useForm()

  const openCreateUser = () => {
    form.resetFields()
    form.setFieldsValue({ role: 'user', enabled: true })
    setEditingUser(null)
    setUserOpen(true)
  }

  const openEditUser = (item: UserAccount) => {
    form.setFieldsValue({ ...item, password: '' })
    setEditingUser(item)
    setUserOpen(true)
  }

  const submitUser = async () => {
    const values = await form.validateFields()
    if (editingUser) {
      await updateUser.mutateAsync({ userId: editingUser.user_id, payload: toUserPayload(values, true) })
      message.success('用户已更新')
    } else {
      await createUser.mutateAsync(toUserPayload(values, false))
      message.success('用户已创建')
    }
    setUserOpen(false)
  }

  const transferCandidates = useMemo(() => {
    if (!transferAssetItem) return []
    return (users.data ?? [])
      .filter((user) => user.enabled && user.username !== transferAssetItem.owner_id)
      .map((user) => ({
        value: user.username,
        label: `${user.display_name || user.username} (${user.username})${user.role === 'admin' ? ' / 管理员' : ''}`,
      }))
  }, [users.data, transferAssetItem])

  const openTransfer = (item: EnvPackage) => {
    setTransferAssetItem(item)
    transferForm.resetFields()
    const firstCandidate = (users.data ?? []).find((user) => user.enabled && user.username !== item.owner_id)
    transferForm.setFieldsValue({ target_owner_id: firstCandidate?.username })
    setTransferOpen(true)
  }

  const submitTransfer = async () => {
    if (!transferAssetItem) return
    const values = await transferForm.validateFields()
    await transferAsset.mutateAsync({ packageId: transferAssetItem.package_id, targetOwnerId: values.target_owner_id })
    message.success(`资产已转交给 ${values.target_owner_id}`)
    setTransferOpen(false)
    setTransferAssetItem(null)
  }

  const userColumns = [
    { title: '用户', dataIndex: 'username' },
    { title: '名称', dataIndex: 'display_name' },
    { title: '角色', dataIndex: 'role', render: (v: string) => <Tag color={v === 'admin' ? 'purple' : 'blue'}>{v}</Tag> },
    { title: '状态', dataIndex: 'enabled', render: (v: boolean) => <Tag color={v ? 'green' : 'red'}>{v ? 'active' : 'disabled'}</Tag> },
    { title: '最后登录', dataIndex: 'last_login_at', render: (v: string) => v || '-' },
    { title: '操作', render: (_: unknown, item: UserAccount) => <Button size="small" onClick={() => openEditUser(item)}>编辑</Button> },
  ]

  const assetColumns = [
    { title: '资产', dataIndex: 'name' },
    { title: '编码', dataIndex: 'package_code' },
    { title: 'Owner', dataIndex: 'owner_id' },
    { title: '可见性', dataIndex: 'visibility', render: (v: string) => <Tag color={visibilityTagColor(v)}>{formatVisibility(v)}</Tag> },
    {
      title: '操作',
      render: (_: unknown, item: EnvPackage) => {
        const candidateCount = (users.data ?? []).filter((user) => user.enabled && user.username !== item.owner_id).length
        return (
          <Space>
            <Button size="small" disabled={candidateCount === 0} onClick={() => openTransfer(item)}>
              {candidateCount === 0 ? '无可转交用户' : '转交资产'}
            </Button>
            <Button size="small" onClick={() => shareAsset.mutate({ packageId: item.package_id, shared: item.visibility !== 'shared' })}>
              {item.visibility === 'shared' ? '取消共享' : '共享'}
            </Button>
          </Space>
        )
      },
    },
  ]

  return (
    <div style={{ padding: 24 }}>
      <Space direction="vertical" size={16} style={{ width: '100%' }}>
        <div>
          <Title level={3} style={{ marginBottom: 4 }}>Admin 管理</Title>
          <Text type="secondary">仅 Admin 可见：用户管理与全局资产归属管理。</Text>
        </div>
        <Tabs items={[
          {
            key: 'users',
            label: '用户管理',
            children: <Card extra={<Button type="primary" onClick={openCreateUser}>新增用户</Button>}><Table rowKey="user_id" loading={users.isLoading} dataSource={users.data ?? []} columns={userColumns} pagination={{ pageSize: 8 }} /></Card>,
          },
          {
            key: 'assets',
            label: '全局资产管理',
            children: <Card extra={<Text type="secondary">当前支持环境包资产的共享与转交。</Text>}><Table rowKey="package_id" loading={assets.isLoading} dataSource={assets.data ?? []} columns={assetColumns} pagination={{ pageSize: 8 }} /></Card>,
          },
        ]} />
      </Space>

      <Modal title={editingUser ? '编辑用户' : '新增用户'} open={userOpen} onCancel={() => setUserOpen(false)} onOk={submitUser} confirmLoading={createUser.isPending || updateUser.isPending}>
        <Form form={form} layout="vertical">
          <Form.Item name="username" label="用户名" rules={[{ required: true }]}><Input disabled={Boolean(editingUser)} /></Form.Item>
          <Form.Item name="display_name" label="显示名"><Input /></Form.Item>
          <Form.Item name="password" label={editingUser ? '重置密码（留空不改）' : '初始密码'} rules={editingUser ? [] : [{ required: true, message: '请输入初始密码' }]}><Input.Password /></Form.Item>
          <Form.Item name="role" label="角色" rules={[{ required: true }]}><Select options={roleOptions} /></Form.Item>
          <Form.Item name="enabled" label="启用" valuePropName="checked"><Switch /></Form.Item>
        </Form>
      </Modal>

      <Modal title={transferAssetItem ? `转交资产：${transferAssetItem.name}` : '转交资产'} open={transferOpen} onCancel={() => { setTransferOpen(false); setTransferAssetItem(null) }} onOk={submitTransfer} confirmLoading={transferAsset.isPending}>
        <Form form={transferForm} layout="vertical">
          <Form.Item label="当前 Owner">
            <Input value={transferAssetItem?.owner_id || ''} disabled />
          </Form.Item>
          <Form.Item name="target_owner_id" label="转交给" rules={[{ required: true, message: '请选择目标用户' }]}>
            <Select showSearch options={transferCandidates} placeholder="请选择目标用户" optionFilterProp="label" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
