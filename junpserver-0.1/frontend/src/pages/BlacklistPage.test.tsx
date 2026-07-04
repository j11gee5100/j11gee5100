import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import BlacklistPage from '../pages/BlacklistPage'

// Helper to render with QueryClientProvider
const renderWithQueryClient = (ui: React.ReactElement) => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      {ui}
    </QueryClientProvider>
  )
}

// Import hooks module for mock access
import * as usePoliciesModule from '../hooks/usePolicies'

// Mock usePolicies hooks
vi.mock('../hooks/usePolicies', () => ({
  useBlacklist: vi.fn(),
  useCreateBlacklistRule: vi.fn(),
  useUpdateBlacklistRule: vi.fn(),
}))

// Mock BlacklistCard to simplify tests
vi.mock('../components/BlacklistCard', () => ({
  default: ({ rule, onToggleEnabled }: {
    rule: { rule_id: string; pattern: string; hard_block: boolean; enabled: boolean };
    onToggleEnabled: (id: string, enabled: boolean) => void;
  }) => (
    <div data-testid={`blacklist-card-${rule.rule_id}`}>
      <span>{rule.rule_id}</span>
      <span>{rule.pattern}</span>
      <span>{rule.hard_block ? '硬拦截' : '软拦截'}</span>
      <span>{rule.enabled ? '已启用' : '已停用'}</span>
      <input
        type="checkbox"
        data-testid="switch-toggle"
        checked={rule.enabled}
        onChange={(e) => onToggleEnabled(rule.rule_id, e.target.checked)}
      />
    </div>
  ),
}))

// Mock BlacklistFormModal
vi.mock('../components/BlacklistFormModal', () => ({
  default: ({ open, mode }: { open: boolean; mode: string }) => (
    open ? <div data-testid="form-modal">{mode === 'create' ? '新建规则' : '编辑规则'}</div> : null
  ),
}))

describe('BlacklistPage', () => {
  const mockRules = [
    {
      rule_id: 'rule-1',
      pattern: 'rm -rf *',
      hard_block: true,
      enabled: true,
    },
    {
      rule_id: 'rule-2',
      pattern: 'dd if=/dev/zero',
      hard_block: false,
      enabled: false,
    },
  ]

  beforeEach(() => {
    vi.clearAllMocks()
    // Default mock implementations
    vi.mocked(usePoliciesModule.useBlacklist).mockReturnValue({
      data: mockRules,
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof usePoliciesModule.useBlacklist>)
    vi.mocked(usePoliciesModule.useUpdateBlacklistRule).mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof usePoliciesModule.useUpdateBlacklistRule>)
    vi.mocked(usePoliciesModule.useCreateBlacklistRule).mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof usePoliciesModule.useCreateBlacklistRule>)
  })

  describe('Page layout', () => {
    it('shows list of BlacklistCard components', () => {
      renderWithQueryClient(<BlacklistPage />)

      // Check for page title
      expect(screen.getByText('命令黑名单治理')).toBeInTheDocument()

      // Check for rules rendered
      expect(screen.getByTestId('blacklist-card-rule-1')).toBeInTheDocument()
      expect(screen.getByTestId('blacklist-card-rule-2')).toBeInTheDocument()
    })

    it('shows pattern and block type on each card', () => {
      renderWithQueryClient(<BlacklistPage />)

      expect(screen.getByText('rm -rf *')).toBeInTheDocument()
      expect(screen.getByText('dd if=/dev/zero')).toBeInTheDocument()
      expect(screen.getByText('硬拦截')).toBeInTheDocument()
      expect(screen.getByText('软拦截')).toBeInTheDocument()
    })

    it('shows enabled/disabled status on cards', () => {
      renderWithQueryClient(<BlacklistPage />)

      expect(screen.getByText('已启用')).toBeInTheDocument()
      expect(screen.getByText('已停用')).toBeInTheDocument()
    })
  })

  describe('New rule button', () => {
    it('has "新建规则" button that opens BlacklistFormModal in create mode', async () => {
      renderWithQueryClient(<BlacklistPage />)

      // Find the create button (not the modal text)
      const createButton = screen.getByRole('button', { name: /新建规则/ })
      expect(createButton).toBeInTheDocument()

      // Click to open modal
      fireEvent.click(createButton)

      // Modal should be open (check for data-testid to avoid duplicate text match)
      await waitFor(() => {
        expect(screen.getByTestId('form-modal')).toBeInTheDocument()
      })
    })
  })

  describe('Enable/disable toggle', () => {
    it('toggling enabled switch updates rule via PATCH', async () => {
      const mockMutate = vi.fn()
      vi.mocked(usePoliciesModule.useUpdateBlacklistRule).mockReturnValue({
        mutate: mockMutate,
        isPending: false,
      } as unknown as ReturnType<typeof usePoliciesModule.useUpdateBlacklistRule>)

      renderWithQueryClient(<BlacklistPage />)

      // Find the switch on a rule card
      const switches = screen.getAllByTestId('switch-toggle')

      // Click the first switch
      fireEvent.click(switches[0])

      await waitFor(() => {
        expect(mockMutate).toHaveBeenCalled()
      })
    })
  })

  describe('Empty state', () => {
    it('shows friendly message when no rules exist', () => {
      vi.mocked(usePoliciesModule.useBlacklist).mockReturnValue({
        data: [],
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
      } as unknown as ReturnType<typeof usePoliciesModule.useBlacklist>)

      renderWithQueryClient(<BlacklistPage />)

      expect(screen.getByText(/暂无黑名单规则/)).toBeInTheDocument()
    })
  })

  describe('Loading state', () => {
    it('shows skeleton cards during loading', () => {
      vi.mocked(usePoliciesModule.useBlacklist).mockReturnValue({
        data: undefined,
        isLoading: true,
        isError: false,
        error: null,
        refetch: vi.fn(),
      } as unknown as ReturnType<typeof usePoliciesModule.useBlacklist>)

      renderWithQueryClient(<BlacklistPage />)

      // Should show skeleton placeholders
      expect(screen.getByTestId('skeleton-container')).toBeInTheDocument()
    })
  })

  describe('Error state', () => {
    it('shows error message when loading fails', () => {
      vi.mocked(usePoliciesModule.useBlacklist).mockReturnValue({
        data: undefined,
        isLoading: false,
        isError: true,
        error: new Error('Network error'),
        refetch: vi.fn(),
      } as unknown as ReturnType<typeof usePoliciesModule.useBlacklist>)

      renderWithQueryClient(<BlacklistPage />)

      expect(screen.getByText(/加载失败/)).toBeInTheDocument()
    })

    it('shows retry button on error', () => {
      const mockRefetch = vi.fn()
      vi.mocked(usePoliciesModule.useBlacklist).mockReturnValue({
        data: undefined,
        isLoading: false,
        isError: true,
        error: new Error('Network error'),
        refetch: mockRefetch,
      } as unknown as ReturnType<typeof usePoliciesModule.useBlacklist>)

      renderWithQueryClient(<BlacklistPage />)

      // Ant Design renders button text with space: "重 试"
      const retryButton = screen.getByRole('button', { name: /重\s*试/ })
      expect(retryButton).toBeInTheDocument()

      fireEvent.click(retryButton)

      expect(mockRefetch).toHaveBeenCalled()
    })
  })
})