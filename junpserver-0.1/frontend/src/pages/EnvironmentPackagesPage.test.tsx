import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import EnvironmentPackagesPage from './EnvironmentPackagesPage'
import type { EnvPackage, DeviceProfile, ManagedDevice } from '../types/environmentPackage'

const mockUseAuth = vi.fn()
const mockUseEnvPackages = vi.fn()
const mockUseManagedDevices = vi.fn()
const mockUseDeviceProfiles = vi.fn()
const mockUseCreateEnvPackage = vi.fn()
const mockUseDeleteEnvPackage = vi.fn()

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => mockUseAuth(),
}))

vi.mock('../hooks/useEnvironmentPackages', () => ({
  envPackageFileUrl: (packageId: string) => `/api/v1/environment-packages/packages/${packageId}/file`,
  operatorHeaders: vi.fn(() => ({})),
  useEnvPackages: (...args: unknown[]) => mockUseEnvPackages(...args),
  useManagedDevices: () => mockUseManagedDevices(),
  useDeviceProfiles: () => mockUseDeviceProfiles(),
  useCreateEnvPackage: (...args: unknown[]) => mockUseCreateEnvPackage(...args),
  useDeleteEnvPackage: (...args: unknown[]) => mockUseDeleteEnvPackage(...args),
}))

const baseProfile: DeviceProfile = {
  profile_id: 'profile-1',
  profile_code: 'a10-ubuntu2204',
  name: 'A10 推理服务器',
  label: 'A10 推理服务器 / x86_64 / Ubuntu 22.04 / NVIDIA A10',
  hardware_vendor: 'Dell',
  cpu_arch: 'x86_64',
  os_type: 'Ubuntu',
  os_version: '22.04',
  accelerator_vendor: 'NVIDIA',
  accelerator_model: 'A10',
  driver_version: '535.183',
  enabled: true,
}

const baseDevice: ManagedDevice = {
  device_id: 'device-1',
  device_code: 'dev-a10-01',
  name: 'A10 推理服务器 01',
  hostname: 'a10-01',
  ip: '10.0.0.11',
  owner_team: '算法交付',
  location: '机房 A',
  os_type: 'Ubuntu',
  os_version: '22.04',
  cpu_arch: 'x86_64',
  accelerator_vendor: 'NVIDIA',
  accelerator_model: 'A10',
  accelerator_count: '1',
  accelerator_memory_gb: '24',
  driver_version: '535.183',
  status: 'active',
  notes: '',
}

function makePackage(overrides: Partial<EnvPackage>): EnvPackage {
  return {
    package_id: 'pkg-1',
    package_code: 'demo-pkg',
    name: 'Demo Package',
    package_type: 'runtime',
    version: '1.0.0',
    file_uri: 'filesystem:///data/demo.tar.gz',
    file_name: 'demo.tar.gz',
    checksum_type: 'sha256',
    checksum: 'abc',
    check_script: '',
    install_script: 'echo install',
    verify_script: 'echo verify',
    uninstall_script: '',
    depends_on: '',
    install_order: 100,
    requires_root: false,
    requires_reboot: false,
    offline_supported: true,
    status: 'active',
    visibility: 'private',
    owner_id: 'zhangsan',
    quality_status: 'ok',
    device_profiles: [baseProfile],
    created_at: '2026-07-03T00:00:00Z',
    updated_at: '2026-07-03T00:00:00Z',
    ...overrides,
  }
}

describe('EnvironmentPackagesPage shared package permissions', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.stubGlobal('open', vi.fn())
    mockUseAuth.mockReturnValue({
      user: { username: 'zhangsan', display_name: '张三', role: 'user' },
      token: 'token-demo',
      isAdmin: false,
    })
    mockUseManagedDevices.mockReturnValue({ data: [baseDevice], isLoading: false })
    mockUseDeviceProfiles.mockReturnValue({ data: [baseProfile], isLoading: false })
    mockUseCreateEnvPackage.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
    mockUseDeleteEnvPackage.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
  })

  it('hides edit/delete for shared packages owned by other users', async () => {
    mockUseEnvPackages.mockReturnValue({
      data: [
        makePackage({ package_id: 'pkg-own', package_code: 'own-pkg', name: '我的包', owner_id: 'zhangsan', visibility: 'private' }),
        makePackage({ package_id: 'pkg-shared', package_code: 'shared-pkg', name: '共享包', owner_id: 'lisi', visibility: 'shared' }),
      ],
      isLoading: false,
    })

    render(<EnvironmentPackagesPage />)

    expect(screen.getByText('环境包资产')).toBeInTheDocument()
    expect(screen.getByText(/共享资产可看、可下、可引用，但不可修改/)).toBeInTheDocument()

    expect(screen.getByTestId('edit-package-pkg-own')).toBeInTheDocument()
    expect(screen.getByTestId('delete-package-pkg-own')).toBeInTheDocument()
    expect(screen.queryByTestId('edit-package-pkg-shared')).not.toBeInTheDocument()
    expect(screen.queryByTestId('delete-package-pkg-shared')).not.toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: /下载/ })).toHaveLength(2)

    fireEvent.click(screen.getAllByRole('button', { name: /查\s*看/ })[1])
    expect(await screen.findByText('这是其他用户共享给你的只读资产：可查看、下载、引用，但不可编辑或删除。')).toBeInTheDocument()
    expect(screen.getByTestId('edit-package-pkg-own')).toBeInTheDocument()
    expect(screen.getByTestId('delete-package-pkg-own')).toBeInTheDocument()
    expect(screen.queryByTestId('edit-package-pkg-shared')).not.toBeInTheDocument()
    expect(screen.queryByTestId('delete-package-pkg-shared')).not.toBeInTheDocument()
  })
})
