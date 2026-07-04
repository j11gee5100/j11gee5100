import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import TemplateCenterPage from '../pages/TemplateCenterPage'

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
import * as useTemplatesModule from '../hooks/useTemplates'

// Mock useTemplates hooks
vi.mock('../hooks/useTemplates', () => ({
  useTemplatesInfinite: vi.fn(),
  useUpdateTemplate: vi.fn(),
  useCreateTemplate: vi.fn(),
}))

// Mock TemplateCard to simplify tests
vi.mock('../components/TemplateCard', () => ({
  default: ({ template, onToggleEnabled }: {
    template: { template_id: string; name: string; risk_level: string; enabled: boolean };
    onToggleEnabled: (id: string, enabled: boolean) => void;
  }) => (
    <div data-testid={`template-card-${template.template_id}`}>
      <span>{template.template_id}</span>
      <span>{template.name}</span>
      <span>{template.risk_level}</span>
      <span>{template.enabled ? '已启用' : '已停用'}</span>
      <input
        type="checkbox"
        data-testid="switch-toggle"
        checked={template.enabled}
        onChange={(e) => onToggleEnabled(template.template_id, e.target.checked)}
      />
    </div>
  ),
}))

// Mock TemplateFormModal
vi.mock('../components/TemplateFormModal', () => ({
  default: ({ open, mode }: { open: boolean; mode: string }) => (
    open ? <div data-testid="form-modal">{mode === 'create' ? '新建模板' : '编辑模板'}</div> : null
  ),
}))

describe('TemplateCenterPage', () => {
  const mockTemplates = [
    {
      template_id: 'template-1',
      name: 'First Template',
      description: 'First desc',
      command: 'echo first',
      risk_level: 'low',
      enabled: true,
    },
    {
      template_id: 'template-2',
      name: 'Second Template',
      description: 'Second desc',
      command: 'echo second',
      risk_level: 'medium',
      enabled: false,
    },
  ]

  beforeEach(() => {
    vi.clearAllMocks()
    // Default mock implementations
    vi.mocked(useTemplatesModule.useTemplatesInfinite).mockReturnValue({
      data: {
        pages: [{
          items: mockTemplates,
          total: 2,
          page: 1,
          page_size: 20,
        }],
      },
      isLoading: false,
      isFetchingNextPage: false,
      hasNextPage: false,
      fetchNextPage: vi.fn(),
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useTemplatesModule.useTemplatesInfinite>)
    vi.mocked(useTemplatesModule.useUpdateTemplate).mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof useTemplatesModule.useUpdateTemplate>)
    vi.mocked(useTemplatesModule.useCreateTemplate).mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof useTemplatesModule.useCreateTemplate>)
  })

  describe('Page layout', () => {
    it('shows card grid layout with templates', () => {
      renderWithQueryClient(<TemplateCenterPage />)

      // Check for page title
      expect(screen.getByText('模板中心')).toBeInTheDocument()

      // Check for templates rendered
      expect(screen.getByText('template-1')).toBeInTheDocument()
      expect(screen.getByText('First Template')).toBeInTheDocument()
      expect(screen.getByText('template-2')).toBeInTheDocument()
      expect(screen.getByText('Second Template')).toBeInTheDocument()
    })

    it('shows risk levels on template cards', () => {
      renderWithQueryClient(<TemplateCenterPage />)

      expect(screen.getByText('low')).toBeInTheDocument()
      expect(screen.getByText('medium')).toBeInTheDocument()
    })

    it('shows enabled/disabled status on cards', () => {
      renderWithQueryClient(<TemplateCenterPage />)

      expect(screen.getByText('已启用')).toBeInTheDocument()
      expect(screen.getByText('已停用')).toBeInTheDocument()
    })
  })

  describe('New button', () => {
    it('has "新建模板" button that opens TemplateFormModal', async () => {
      renderWithQueryClient(<TemplateCenterPage />)

      // Find the create button
      const createButton = screen.getByRole('button', { name: /新建模板/ })
      expect(createButton).toBeInTheDocument()

      // Click to open modal
      fireEvent.click(createButton)

      // Modal should be open
      await waitFor(() => {
        expect(screen.getByTestId('form-modal')).toBeInTheDocument()
      })
    })
  })

  describe('Enable/disable toggle', () => {
    it('toggling enabled switch updates template via mutation', async () => {
      const mockMutate = vi.fn()
      vi.mocked(useTemplatesModule.useUpdateTemplate).mockReturnValue({
        mutate: mockMutate,
        isPending: false,
      } as unknown as ReturnType<typeof useTemplatesModule.useUpdateTemplate>)

      renderWithQueryClient(<TemplateCenterPage />)

      // Find the switch on a template card
      const switches = screen.getAllByTestId('switch-toggle')

      // Click the first switch
      fireEvent.click(switches[0])

      await waitFor(() => {
        expect(mockMutate).toHaveBeenCalled()
      })
    })
  })

  describe('Empty state', () => {
    it('shows friendly message when no templates exist', () => {
      vi.mocked(useTemplatesModule.useTemplatesInfinite).mockReturnValue({
        data: undefined,
        isLoading: false,
        isFetchingNextPage: false,
        hasNextPage: false,
        fetchNextPage: vi.fn(),
        refetch: vi.fn(),
      } as unknown as ReturnType<typeof useTemplatesModule.useTemplatesInfinite>)

      renderWithQueryClient(<TemplateCenterPage />)

      expect(screen.getByText(/暂无模板/)).toBeInTheDocument()
    })
  })

  describe('Loading state', () => {
    it('shows skeleton cards during loading', () => {
      vi.mocked(useTemplatesModule.useTemplatesInfinite).mockReturnValue({
        data: undefined,
        isLoading: true,
        isFetchingNextPage: false,
        hasNextPage: false,
        fetchNextPage: vi.fn(),
        refetch: vi.fn(),
      } as unknown as ReturnType<typeof useTemplatesModule.useTemplatesInfinite>)

      renderWithQueryClient(<TemplateCenterPage />)

      // Skeleton placeholders should be visible
      expect(screen.getByTestId('skeleton-container')).toBeInTheDocument()
    })
  })

  describe('Infinite scroll', () => {
    it('has load more button as backup for infinite scroll', async () => {
      const mockFetchNextPage = vi.fn()
      vi.mocked(useTemplatesModule.useTemplatesInfinite).mockReturnValue({
        data: {
          pages: [{
            items: [{
              template_id: 'template-1',
              name: 'First Template',
              command: 'echo first',
              risk_level: 'low',
              enabled: true,
            }],
            total: 50,
            page: 1,
            page_size: 20,
          }],
        },
        isLoading: false,
        isFetchingNextPage: false,
        hasNextPage: true,
        fetchNextPage: mockFetchNextPage,
        refetch: vi.fn(),
      } as unknown as ReturnType<typeof useTemplatesModule.useTemplatesInfinite>)

      renderWithQueryClient(<TemplateCenterPage />)

      // Find "加载更多" button
      const loadMoreButton = screen.getByRole('button', { name: /加载更多/ })
      expect(loadMoreButton).toBeInTheDocument()

      // Click to trigger fetch
      fireEvent.click(loadMoreButton)

      await waitFor(() => {
        expect(mockFetchNextPage).toHaveBeenCalled()
      })
    })

    it('hides load more button when no more pages', () => {
      vi.mocked(useTemplatesModule.useTemplatesInfinite).mockReturnValue({
        data: {
          pages: [{
            items: [{
              template_id: 'template-1',
              name: 'First Template',
              command: 'echo first',
              risk_level: 'low',
              enabled: true,
            }],
            total: 1,
            page: 1,
            page_size: 20,
          }],
        },
        isLoading: false,
        isFetchingNextPage: false,
        hasNextPage: false,
        fetchNextPage: vi.fn(),
        refetch: vi.fn(),
      } as unknown as ReturnType<typeof useTemplatesModule.useTemplatesInfinite>)

      renderWithQueryClient(<TemplateCenterPage />)

      // Load more button should NOT be visible when hasNextPage is false
      expect(screen.queryByRole('button', { name: /加载更多/ })).not.toBeInTheDocument()
    })
  })
})