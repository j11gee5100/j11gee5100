import type { ReactElement } from 'react'
import { Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { Button, Layout, Menu, Space, Spin, Tag, Typography } from 'antd'
import { AuthProvider, useAuth } from './auth/AuthContext'
import DashboardPage from './pages/DashboardPage'
import EnvironmentPackagesPage from './pages/EnvironmentPackagesPage'
import EnvironmentPackageEditorPage from './pages/EnvironmentPackageEditorPage'
import DeviceManagementPage from './pages/DeviceManagementPage'
import DeliveryBundlesPage from './pages/DeliveryBundlesPage'
import DeliveryBundleEditorPage from './pages/DeliveryBundleEditorPage'
import ProbeResultsPage from './pages/ProbeResultsPage'
import AdminManagementPage from './pages/AdminManagementPage'
import LoginPage from './pages/LoginPage'

const { Header, Sider, Content } = Layout

function ProtectedAdminRoute({ children }: { children: ReactElement }) {
  const auth = useAuth()
  if (!auth.isAdmin) return <Navigate to="/environment-packages" replace />
  return children
}

function AppLayout() {
  const navigate = useNavigate()
  const location = useLocation()
  const auth = useAuth()
  if (auth.isChecking) return <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center' }}><Spin tip="校验登录状态..." /></div>
  if (!auth.isAuthenticated) return <LoginPage />

  const isStandaloneEditor = location.pathname.startsWith('/environment-packages/') && location.pathname.endsWith('/editor')
  if (isStandaloneEditor) {
    return (
      <Routes>
        <Route path="/environment-packages/:packageId/editor" element={<EnvironmentPackageEditorPage />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    )
  }

  const menuItems = [
    { key: '/dashboard', label: '总览看板' },
    { key: '/environment-packages', label: '环境包资产' },
    { key: '/devices', label: '设备管理' },
    { key: '/probe-results', label: '探测结果' },
    { key: '/delivery-bundles', label: '交付包' },
    ...(auth.isAdmin ? [{ key: '/admin', label: 'Admin 管理' }] : []),
  ]
  const selectedKey = menuItems.find((item) => location.pathname === item.key || location.pathname.startsWith(`${item.key}/`))?.key || '/dashboard'

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider width={200} style={{ background: '#fff' }}>
        <div style={{ padding: 16, textAlign: 'center' }}><Typography.Title level={4} style={{ margin: 0 }}>OpsPaw</Typography.Title></div>
        <Menu mode="inline" selectedKeys={[selectedKey]} items={menuItems} onClick={({ key }) => navigate(key)} style={{ borderRight: 0 }} />
      </Sider>
      <Layout>
        <Header style={{ background: '#fff', padding: '0 24px', borderBottom: '1px solid #f0f0f0', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography.Title level={4} style={{ margin: 0 }}>AI 推理环境交付平台</Typography.Title>
          <Space><span>{auth.user?.display_name || auth.user?.username}</span><Tag color={auth.isAdmin ? 'purple' : 'blue'}>{auth.user?.role}</Tag><Button size="small" onClick={auth.logout}>退出登录</Button></Space>
        </Header>
        <Content style={{ margin: 16, background: '#fff', borderRadius: 8 }}>
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/environment-packages" element={<EnvironmentPackagesPage />} />
            <Route path="/environment-packages/:packageId/editor" element={<EnvironmentPackageEditorPage />} />
            <Route path="/devices" element={<DeviceManagementPage />} />
            <Route path="/probe-results" element={<ProbeResultsPage />} />
            <Route path="/delivery-bundles" element={<DeliveryBundlesPage />} />
            <Route path="/delivery-bundles/:bundleId" element={<DeliveryBundleEditorPage />} />
            <Route path="/admin" element={<ProtectedAdminRoute><AdminManagementPage /></ProtectedAdminRoute>} />
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </Content>
      </Layout>
    </Layout>
  )
}

function App() { return <AuthProvider><AppLayout /></AuthProvider> }
export default App
