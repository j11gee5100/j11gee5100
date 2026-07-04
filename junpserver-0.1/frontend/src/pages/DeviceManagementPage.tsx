import { useState } from 'react'
import { Alert, Button, Card, Empty, Form, Input, Modal, Popconfirm, Select, Space, Switch, Table, Tabs, Tag, Typography, message } from 'antd'
import { DeleteOutlined, PlusOutlined } from '@ant-design/icons'
import { useAuth } from '../auth/AuthContext'
import { useAllDeviceProfiles, useCreateDevice, useCreateDeviceProfile, useCreateProfileFromDevice, useDeleteDeviceProfile, useManagedDevices, useUpdateDevice, useUpdateDeviceProfile } from '../hooks/useEnvironmentPackages'
import type { DeviceProfile, DeviceProfilePayload, ManagedDevice, ManagedDevicePayload } from '../types/environmentPackage'

const { Title, Text } = Typography
const archOptions = [{ value: 'x86_64' }, { value: 'aarch64' }, { value: 'arm64' }]
const statusOptions = [{ value: 'active' }, { value: 'inactive' }, { value: 'maintenance' }]
function toDevicePayload(values: Record<string, unknown>, editing: boolean): ManagedDevicePayload { const payload = { ...values, status: values.status || 'active' } as ManagedDevicePayload; if (editing) delete payload.device_code; return payload }
function toProfilePayload(values: Record<string, unknown>, editing: boolean): DeviceProfilePayload { const payload = { ...values, enabled: values.enabled !== false } as DeviceProfilePayload; if (editing) delete payload.profile_code; return payload }

export default function DeviceManagementPage() {
  const auth = useAuth()
  const operator = auth.user ? { ...auth.user, access_token: auth.token } : null
  const isAdmin = auth.isAdmin
  const devices = useManagedDevices()
  const profiles = useAllDeviceProfiles()
  const createDevice = useCreateDevice(operator)
  const updateDevice = useUpdateDevice(operator)
  const createProfileFromDevice = useCreateProfileFromDevice(operator)
  const createProfile = useCreateDeviceProfile(operator)
  const updateProfile = useUpdateDeviceProfile(operator)
  const deleteProfile = useDeleteDeviceProfile(operator)
  const [editingDevice, setEditingDevice] = useState<ManagedDevice | null>(null)
  const [deviceOpen, setDeviceOpen] = useState(false)
  const [editingProfile, setEditingProfile] = useState<DeviceProfile | null>(null)
  const [profileOpen, setProfileOpen] = useState(false)
  const [deviceForm] = Form.useForm()
  const [profileForm] = Form.useForm()

  const openCreateDevice = () => { deviceForm.resetFields(); deviceForm.setFieldsValue({ status: 'active' }); setEditingDevice(null); setDeviceOpen(true) }
  const openEditDevice = (item: ManagedDevice) => { deviceForm.setFieldsValue(item); setEditingDevice(item); setDeviceOpen(true) }
  const openCreateProfile = () => { profileForm.resetFields(); profileForm.setFieldsValue({ enabled: true }); setEditingProfile(null); setProfileOpen(true) }
  const openEditProfile = (item: DeviceProfile) => { profileForm.setFieldsValue(item); setEditingProfile(item); setProfileOpen(true) }
  const submitDevice = async () => { const values = await deviceForm.validateFields(); if (editingDevice) { await updateDevice.mutateAsync({ deviceId: editingDevice.device_id, payload: toDevicePayload(values, true) }); message.success('设备已更新') } else { await createDevice.mutateAsync(toDevicePayload(values, false)); message.success('设备已创建') } setDeviceOpen(false) }
  const submitProfile = async () => { const values = await profileForm.validateFields(); if (editingProfile) { await updateProfile.mutateAsync({ profileId: editingProfile.profile_id, payload: toProfilePayload(values, true) }); message.success('适配配置已更新') } else { await createProfile.mutateAsync(toProfilePayload(values, false)); message.success('适配配置已创建') } setProfileOpen(false) }
  const removeProfile = async (item: DeviceProfile) => { try { await deleteProfile.mutateAsync(item.profile_id); message.success('适配配置已删除') } catch (error: any) { const code = error?.response?.data?.code; message.error(code === 'DEVICE_PROFILE_IN_USE' ? '该适配配置已被环境包或交付包使用，不可删除。' : (error?.response?.data?.message || '删除失败')) } }

  const deviceColumns = [
    { title: '设备', render: (_: unknown, item: ManagedDevice) => <Space direction="vertical" size={0}><Text strong>{item.name || item.device_code}</Text><Text type="secondary">{item.device_code} / {item.hostname || '-'}</Text></Space> },
    { title: 'IP', dataIndex: 'ip' }, { title: '位置/团队', render: (_: unknown, item: ManagedDevice) => `${item.location || '-'} / ${item.owner_team || '-'}` },
    { title: '系统/架构', render: (_: unknown, item: ManagedDevice) => `${item.os_type} ${item.os_version} / ${item.cpu_arch}` }, { title: '推理卡', render: (_: unknown, item: ManagedDevice) => `${item.accelerator_vendor} ${item.accelerator_model} × ${item.accelerator_count || '-'}` },
    { title: '驱动', dataIndex: 'driver_version', render: (v: string) => v || '-' }, { title: '状态', dataIndex: 'status', render: (v: string) => <Tag color={v === 'active' ? 'green' : 'gold'}>{v}</Tag> },
    { title: '操作', render: (_: unknown, item: ManagedDevice) => isAdmin ? <Space><Button size="small" onClick={() => openEditDevice(item)}>编辑</Button><Button size="small" type="primary" onClick={() => createProfileFromDevice.mutate({ deviceId: item.device_id })}>生成适配配置</Button></Space> : <Tag>只读</Tag> },
  ]
  const profileColumns = [
    { title: '配置编码', dataIndex: 'profile_code' }, { title: '名称', dataIndex: 'name' }, { title: '硬件厂商', dataIndex: 'hardware_vendor' }, { title: '系统/架构', render: (_: unknown, item: DeviceProfile) => `${item.os_type} ${item.os_version} / ${item.cpu_arch}` },
    { title: '推理卡', render: (_: unknown, item: DeviceProfile) => `${item.accelerator_vendor} ${item.accelerator_model}` }, { title: '驱动', dataIndex: 'driver_version', render: (v: string) => v || '-' }, { title: '状态', dataIndex: 'enabled', render: (v: boolean) => <Tag color={v ? 'green' : 'red'}>{v ? '启用' : '停用'}</Tag> },
    { title: '操作', render: (_: unknown, item: DeviceProfile) => isAdmin ? <Space><Button size="small" type="primary" onClick={() => openEditProfile(item)}>编辑</Button><Popconfirm title="确认删除此设备适配配置？" description="已被环境包或交付包使用的配置会被系统拒绝删除。" onConfirm={() => removeProfile(item)}><Button size="small" danger icon={<DeleteOutlined />} loading={deleteProfile.isPending}>删除</Button></Popconfirm></Space> : <Tag>只读</Tag> },
  ]

  return <div style={{ padding: 24 }}><Space direction="vertical" size={16} style={{ width: '100%' }}><div><Title level={3} style={{ marginBottom: 4 }}>设备管理</Title><Text type="secondary">管理真实推理设备台账，并维护安装包可选择的设备适配配置。</Text></div><Alert type="info" showIcon message="Admin 可新增/编辑设备，并可从设备一键生成适配配置；普通用户只读。" /><Tabs items={[{ key: 'devices', label: '推理设备台账', children: <Card extra={isAdmin ? <Button type="primary" icon={<PlusOutlined />} onClick={openCreateDevice}>新增设备</Button> : null}><Table rowKey="device_id" loading={devices.isLoading} dataSource={devices.data ?? []} columns={deviceColumns} pagination={{ pageSize: 8 }} locale={{ emptyText: <Empty description="暂无设备" /> }} /></Card> }, { key: 'profiles', label: '设备适配配置', children: <Card extra={isAdmin ? <Button type="primary" icon={<PlusOutlined />} onClick={openCreateProfile}>新增适配配置</Button> : null}><Table rowKey="profile_id" loading={profiles.isLoading} dataSource={profiles.data ?? []} columns={profileColumns} pagination={{ pageSize: 8 }} /></Card> }]} /></Space>
    <Modal title={editingDevice ? '编辑设备' : '新增设备'} open={deviceOpen} onCancel={() => setDeviceOpen(false)} onOk={submitDevice} confirmLoading={createDevice.isPending || updateDevice.isPending} width={820}><Form form={deviceForm} layout="vertical"><div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}><Form.Item name="device_code" label="设备编码" rules={[{ required: true }]}><Input disabled={Boolean(editingDevice)} /></Form.Item><Form.Item name="name" label="设备名称"><Input /></Form.Item><Form.Item name="hostname" label="Hostname"><Input /></Form.Item><Form.Item name="ip" label="IP"><Input /></Form.Item><Form.Item name="owner_team" label="归属团队"><Input /></Form.Item><Form.Item name="location" label="位置"><Input /></Form.Item><Form.Item name="cpu_arch" label="系统架构"><Select options={archOptions} /></Form.Item><Form.Item name="os_type" label="系统类型"><Input /></Form.Item><Form.Item name="os_version" label="系统版本"><Input /></Form.Item><Form.Item name="accelerator_vendor" label="推理卡厂商"><Input /></Form.Item><Form.Item name="accelerator_model" label="推理卡型号"><Input /></Form.Item><Form.Item name="accelerator_count" label="卡数量"><Input /></Form.Item><Form.Item name="accelerator_memory_gb" label="显存 GB"><Input /></Form.Item><Form.Item name="driver_version" label="驱动版本"><Input /></Form.Item><Form.Item name="status" label="状态"><Select options={statusOptions} /></Form.Item><Form.Item name="notes" label="备注" style={{ gridColumn: '1 / -1' }}><Input.TextArea rows={3} /></Form.Item></div></Form></Modal>
    <Modal title={editingProfile ? '编辑适配配置' : '新增适配配置'} open={profileOpen} onCancel={() => setProfileOpen(false)} onOk={submitProfile} confirmLoading={createProfile.isPending || updateProfile.isPending} width={760}><Form form={profileForm} layout="vertical"><div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}><Form.Item name="profile_code" label="配置编码" rules={[{ required: true }]}><Input disabled={Boolean(editingProfile)} /></Form.Item><Form.Item name="name" label="配置名称" rules={[{ required: true }]}><Input /></Form.Item><Form.Item name="hardware_vendor" label="硬件厂商"><Input /></Form.Item><Form.Item name="cpu_arch" label="系统架构"><Select options={archOptions} /></Form.Item><Form.Item name="os_type" label="系统类型"><Input /></Form.Item><Form.Item name="os_version" label="系统版本"><Input /></Form.Item><Form.Item name="accelerator_vendor" label="推理卡厂商"><Input /></Form.Item><Form.Item name="accelerator_model" label="推理卡型号"><Input /></Form.Item><Form.Item name="driver_version" label="驱动版本"><Input /></Form.Item><Form.Item name="enabled" label="启用" valuePropName="checked"><Switch /></Form.Item></div></Form></Modal></div>
}
