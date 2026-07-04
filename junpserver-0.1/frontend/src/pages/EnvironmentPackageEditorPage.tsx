import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Alert, Button, Card, Form, Input, Modal, Radio, Select, Space, Spin, Tag, Typography, message } from 'antd'
import { CaretDownOutlined, CaretRightOutlined, DeleteOutlined, FileAddOutlined, FolderAddOutlined, SaveOutlined } from '@ant-design/icons'
import { useAuth } from '../auth/AuthContext'
import { formatPackageType, packageTypeOptions } from '../constants/packageTypes'
import { visibilityOptions } from '../constants/visibility'
import {
  useCommitPackageWorkspace,
  useCreatePackageWorkspace,
  useCreateWorkspaceContent,
  useDeleteWorkspaceContent,
  useDeviceProfiles,
  useEnvPackage,
  useRenameWorkspaceContent,
  useSaveWorkspaceContent,
  useUpdateEnvPackage,
  useWorkspaceContent,
} from '../hooks/useEnvironmentPackages'
import type { EnvPackagePayload, WorkspaceContentModel } from '../types/environmentPackage'

const { Title, Text } = Typography

type SaveMode = 'in_place' | 'new_version'

function formatDateTime(value?: string) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', { hour12: false })
}

function contentChildren(model?: WorkspaceContentModel): WorkspaceContentModel[] {
  if (!model || model.type !== 'directory' || !Array.isArray(model.content)) return []
  return model.content
}

function WorkspaceTreeNode({ packageId, workspaceId, operator, item, selectedPath, onSelect, level = 0 }: {
  packageId: string
  workspaceId: string
  operator: { username: string; role: string; access_token?: string } | null
  item: WorkspaceContentModel
  selectedPath: string
  onSelect: (path: string) => void
  level?: number
}) {
  const [expanded, setExpanded] = useState(level < 1)
  const dirContent = useWorkspaceContent(packageId, expanded && item.type === 'directory' ? workspaceId : '', item.path, operator)
  const children = contentChildren(dirContent.data)
  const isSelected = selectedPath === item.path
  const isDirectory = item.type === 'directory'

  return (
    <div>
      <button
        type="button"
        onClick={() => {
          if (isDirectory) setExpanded((value) => !value)
          else onSelect(item.path)
        }}
        style={{
          width: '100%',
          border: 0,
          background: isSelected ? '#eaf2ff' : 'transparent',
          borderLeft: isSelected ? '3px solid #1677ff' : '3px solid transparent',
          textAlign: 'left',
          padding: `7px 10px 7px ${10 + level * 16}px`,
          cursor: 'pointer',
          color: isDirectory ? '#475467' : '#172033',
          display: 'flex',
          alignItems: 'center',
          gap: 6,
        }}
        title={item.path}
      >
        <span style={{ width: 12, display: 'inline-flex' }}>{isDirectory ? (expanded ? <CaretDownOutlined /> : <CaretRightOutlined />) : null}</span>
        <span>{isDirectory ? '📁' : '📄'}</span>
        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{item.name || item.path}</span>
      </button>
      {isDirectory && expanded && (
        <div>
          {dirContent.isLoading && <div style={{ padding: `4px 10px 4px ${28 + level * 16}px`, color: '#98a2b3', fontSize: 12 }}>加载中...</div>}
          {children.map((child) => (
            <WorkspaceTreeNode key={child.path} packageId={packageId} workspaceId={workspaceId} operator={operator} item={child} selectedPath={selectedPath} onSelect={onSelect} level={level + 1} />
          ))}
        </div>
      )}
    </div>
  )
}

function FileTree({ packageId, workspaceId, operator, root, selectedPath, onSelect }: {
  packageId: string
  workspaceId: string
  operator: { username: string; role: string; access_token?: string } | null
  root?: WorkspaceContentModel
  selectedPath: string
  onSelect: (path: string) => void
}) {
  const items = contentChildren(root)
  return (
    <div style={{ overflow: 'auto', padding: '8px 0' }}>
      {!workspaceId && <div style={{ padding: 12, color: '#98a2b3' }}>正在创建编辑工作区...</div>}
      {workspaceId && items.length === 0 && <div style={{ padding: 12, color: '#98a2b3' }}>暂无文件</div>}
      {items.map((item) => (
        <WorkspaceTreeNode key={item.path} packageId={packageId} workspaceId={workspaceId} operator={operator} item={item} selectedPath={selectedPath} onSelect={onSelect} />
      ))}
    </div>
  )
}

export default function EnvironmentPackageEditorPage() {
  const { packageId = '' } = useParams()
  const navigate = useNavigate()
  const auth = useAuth()
  const operator = auth.user ? { ...auth.user, access_token: auth.token } : null
  const packageQuery = useEnvPackage(packageId, operator)
  const profiles = useDeviceProfiles()
  const createWorkspace = useCreatePackageWorkspace(operator)
  const updatePackage = useUpdateEnvPackage(operator)
  const saveContent = useSaveWorkspaceContent(operator)
  const createContent = useCreateWorkspaceContent(operator)
  const deleteContent = useDeleteWorkspaceContent(operator)
  const renameContent = useRenameWorkspaceContent(operator)
  const commitWorkspace = useCommitPackageWorkspace(operator)
  const [workspaceId, setWorkspaceId] = useState('')
  const [selectedPath, setSelectedPath] = useState('')
  const [editorText, setEditorText] = useState('')
  const [dirty, setDirty] = useState(false)
  const [saveMode, setSaveMode] = useState<SaveMode>('new_version')
  const [newVersion, setNewVersion] = useState('')
  const [remark, setRemark] = useState('')
  const [infoForm] = Form.useForm()

  const rootContent = useWorkspaceContent(packageId, workspaceId, '', operator)
  const selectedContent = useWorkspaceContent(packageId, workspaceId, selectedPath, operator)
  const item = packageQuery.data
  const profileOptions = (profiles.data ?? []).map((profile) => ({ value: profile.profile_id, label: profile.label }))

  useEffect(() => {
    if (!item || workspaceId || createWorkspace.isPending) return
    createWorkspace.mutateAsync(item.package_id).then((workspace) => setWorkspaceId(workspace.workspace_id)).catch(() => message.error('创建包编辑工作区失败'))
  }, [item, workspaceId, createWorkspace])

  useEffect(() => {
    if (!item) return
    infoForm.setFieldsValue({ ...item, device_profile_ids: item.device_profiles.map((profile) => profile.profile_id) })
    setSaveMode(item.status === 'draft' ? 'in_place' : 'new_version')
    setNewVersion(`${item.version}-rev1`)
  }, [item, infoForm])

  useEffect(() => {
    if (!selectedContent.data || selectedContent.data.type !== 'file') return
    if (selectedContent.data.format !== 'text') {
      setEditorText('当前为二进制或非 UTF-8 文件，暂不支持文本编辑。')
      setDirty(false)
      return
    }
    setEditorText(String(selectedContent.data.content ?? ''))
    setDirty(false)
  }, [selectedContent.data])

  const saveInfo = async () => {
    const values = await infoForm.validateFields()
    const payload: EnvPackagePayload = { ...values, install_order: Number(values.install_order ?? 100) }
    await updatePackage.mutateAsync({ packageId, payload })
    message.success('信息已保存')
    packageQuery.refetch()
  }

  const saveSelectedFile = async () => {
    if (!workspaceId || !selectedPath) return
    await saveContent.mutateAsync({ packageId, workspaceId, path: selectedPath, content: editorText })
    setDirty(false)
    message.success('文件已保存到工作区')
  }

  const addFile = () => {
    Modal.confirm({
      title: '新增文件',
      content: <Input id="new-workspace-file" placeholder="例如 README.md 或 conf/app.conf" />,
      onOk: async () => {
        const name = (document.getElementById('new-workspace-file') as HTMLInputElement)?.value?.trim()
        if (!name) return Promise.reject(new Error('请输入文件名'))
        await createContent.mutateAsync({ packageId, workspaceId, parentPath: '', name, type: 'file', content: '' })
        rootContent.refetch()
      },
    })
  }

  const addFolder = () => {
    Modal.confirm({
      title: '新增目录',
      content: <Input id="new-workspace-folder" placeholder="例如 conf" />,
      onOk: async () => {
        const name = (document.getElementById('new-workspace-folder') as HTMLInputElement)?.value?.trim()
        if (!name) return Promise.reject(new Error('请输入目录名'))
        await createContent.mutateAsync({ packageId, workspaceId, parentPath: '', name, type: 'directory' })
        rootContent.refetch()
      },
    })
  }

  const renameSelected = () => {
    if (!selectedPath) return
    Modal.confirm({
      title: '重命名/移动文件',
      content: <Input id="rename-workspace-file" defaultValue={selectedPath} />,
      onOk: async () => {
        const newPath = (document.getElementById('rename-workspace-file') as HTMLInputElement)?.value?.trim()
        if (!newPath) return Promise.reject(new Error('请输入新路径'))
        await renameContent.mutateAsync({ packageId, workspaceId, path: selectedPath, newPath })
        setSelectedPath(newPath)
        rootContent.refetch()
      },
    })
  }

  const deleteSelected = async () => {
    if (!selectedPath) return
    await deleteContent.mutateAsync({ packageId, workspaceId, path: selectedPath })
    setSelectedPath('')
    setEditorText('')
    rootContent.refetch()
    message.success('文件已删除')
  }

  const commit = async () => {
    if (dirty) await saveSelectedFile()
    await commitWorkspace.mutateAsync({ packageId, workspaceId, payload: { save_mode: saveMode, new_version: saveMode === 'new_version' ? newVersion : '', remark } })
    message.success(saveMode === 'new_version' ? '已提交为新版本' : '已原地更新环境包')
    navigate('/environment-packages')
  }

  if (packageQuery.isLoading || !item) return <div style={{ minHeight: 480, display: 'grid', placeItems: 'center' }}><Spin tip="加载环境包资产..." /></div>

  return (
    <div style={{ height: '100vh', display: 'grid', gridTemplateRows: '48px 1fr 180px', background: '#f5f7fb', overflow: 'hidden' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '0 16px', background: '#111827', color: '#fff' }}>
        <Title level={5} style={{ color: '#fff', margin: 0 }}>环境包编辑工作台</Title>
        <Text style={{ color: '#cbd5e1' }}>{item.name} / {item.package_code}</Text>
        <Tag color="blue">{formatPackageType(item.package_type)}</Tag><Tag color="green">{item.status}</Tag>{dirty && <Tag color="orange">文件未保存</Tag>}
        <div style={{ flex: 1 }} />
        <Button onClick={() => navigate('/environment-packages')}>返回列表</Button>
        <Button type="primary" icon={<SaveOutlined />} loading={commitWorkspace.isPending} onClick={commit}>提交工作区</Button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr 360px', minHeight: 0 }}>
        <Card size="small" title="资产与文件导航" style={{ borderRadius: 0, overflow: 'hidden' }} bodyStyle={{ padding: 0, height: '100%', display: 'grid', gridTemplateRows: 'auto 1fr auto' }}>
          <div style={{ padding: 12 }}><Input placeholder="搜索文件 / 字段 / 脚本" /></div>
          <FileTree packageId={packageId} workspaceId={workspaceId} operator={operator} root={rootContent.data} selectedPath={selectedPath} onSelect={setSelectedPath} />
          <Space style={{ padding: 12, borderTop: '1px solid #f0f0f0' }} wrap>
            <Button size="small" icon={<FileAddOutlined />} onClick={addFile} disabled={!workspaceId}>文件</Button>
            <Button size="small" icon={<FolderAddOutlined />} onClick={addFolder} disabled={!workspaceId}>目录</Button>
            <Button size="small" onClick={renameSelected} disabled={!selectedPath}>重命名</Button>
            <Button size="small" danger icon={<DeleteOutlined />} onClick={deleteSelected} disabled={!selectedPath}>删除</Button>
          </Space>
        </Card>

        <div style={{ display: 'grid', gridTemplateRows: '42px 1fr', minWidth: 0, background: '#0f172a' }}>
          <div style={{ background: '#fff', borderBottom: '1px solid #e5e7eb', display: 'flex', alignItems: 'center', padding: '0 12px', gap: 8 }}>
            <Text strong>{selectedPath || '请选择左侧文件'}</Text>
            {selectedContent.data?.format === 'base64' && <Tag color="orange">二进制</Tag>}
            <div style={{ flex: 1 }} />
            <Button size="small" type="primary" disabled={!selectedPath || selectedContent.data?.format === 'base64'} loading={saveContent.isPending} onClick={saveSelectedFile}>保存文件</Button>
          </div>
          <textarea
            value={editorText}
            disabled={!selectedPath || selectedContent.data?.format === 'base64'}
            onChange={(event) => { setEditorText(event.target.value); setDirty(true) }}
            spellCheck={false}
            style={{ width: '100%', height: '100%', resize: 'none', border: 0, outline: 'none', padding: 16, background: '#0f172a', color: '#dbeafe', fontFamily: 'Consolas, monospace', fontSize: 13, lineHeight: 1.6 }}
          />
        </div>

        <div style={{ overflow: 'auto', background: '#fff', borderLeft: '1px solid #e5e7eb', padding: 12 }}>
          <Card size="small" title="信息编辑" style={{ marginBottom: 12 }}>
            <Form form={infoForm} layout="vertical">
              <Form.Item name="name" label="包名称" rules={[{ required: true }]}><Input /></Form.Item>
              <Form.Item name="package_type" label="包类型"><Select options={packageTypeOptions} /></Form.Item>
              <Form.Item name="version" label="版本"><Input /></Form.Item>
              <Form.Item name="device_profile_ids" label="适配配置"><Select mode="multiple" options={profileOptions} /></Form.Item>
              <Form.Item name="status" label="状态"><Select options={[{ value: 'draft' }, { value: 'active' }, { value: 'inactive' }]} /></Form.Item>
              <Form.Item name="visibility" label="可见性"><Select options={visibilityOptions} /></Form.Item>
              <Button block onClick={saveInfo} loading={updatePackage.isPending}>保存信息</Button>
            </Form>
          </Card>
          <Card size="small" title="提交策略" style={{ marginBottom: 12 }}>
            {item.status !== 'draft' && <Alert type="warning" showIcon style={{ marginBottom: 12 }} message="该资产可能已被交付包引用，建议另存新版本。" />}
            <Space direction="vertical" style={{ width: '100%' }}>
              <Radio.Group value={saveMode} onChange={(event) => setSaveMode(event.target.value)} options={[{ label: '原地修改', value: 'in_place' }, { label: '另存新版本', value: 'new_version' }]} />
              {saveMode === 'new_version' && <Input value={newVersion} onChange={(event) => setNewVersion(event.target.value)} placeholder="新版本号" />}
              <Input.TextArea value={remark} onChange={(event) => setRemark(event.target.value)} rows={3} placeholder="修改备注" />
            </Space>
          </Card>
          <Card size="small" title="资产状态">
            <p>Checksum：{item.checksum ? `${item.checksum_type}:${item.checksum.slice(0, 16)}...` : '未填写'}</p>
            <p>最后更新时间：{formatDateTime(item.updated_at)}</p>
            <p>工作区：{workspaceId || '创建中...'}</p>
          </Card>
        </div>
      </div>

      <div style={{ borderTop: '1px solid #d9e1ec', background: '#fff', padding: 12, overflow: 'auto' }}>
        <Space direction="vertical" size={4}>
          <Text strong>工作区说明</Text>
          <Text type="secondary">当前页面采用 Jupyter Contents 风格：所有增删改先发生在解包工作区；点击“提交工作区”后才重新打包并更新环境包资产。</Text>
          <Text type="secondary">文件编辑与信息编辑已分离：右侧保存信息只改资产元数据，中间保存文件只改工作区文件。</Text>
        </Space>
      </div>
    </div>
  )
}
