import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import TemplateFormModal from './TemplateFormModal'
import type { Template } from '../types/template'

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

// Mock Ant Design components
vi.mock('antd', async () => {
  const actual = await vi.importActual('antd')
  return {
    ...actual,
    Modal: ({ open, title, children, onCancel }: {
      open: boolean;
      title: string;
      children: React.ReactNode;
      onCancel?: () => void;
    }) => (
      open ? (
        <div data-testid="modal-container" role="dialog">
          <div data-testid="modal-title">{title}</div>
          <button data-testid="modal-close" onClick={onCancel}>X</button>
          {children}
        </div>
      ) : null
    ),
  }
})

// Mock PolicyEvaluationModal
vi.mock('./PolicyEvaluationModal', () => ({
  default: ({ open, onClose }: { open: boolean; onClose: () => void }) => (
    open ? (
      <div data-testid="policy-evaluation-modal">
        PolicyEvaluation Modal Open
        <button data-testid="policy-close" onClick={onClose}>Close Policy</button>
      </div>
    ) : null
  ),
}))

describe('TemplateFormModal', () => {
  const mockOnClose = vi.fn()
  const mockOnSuccess = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Form fields', () => {
    it('contains Input for template_id', () => {
      renderWithQueryClient(
        <TemplateFormModal
          open={true}
          mode="create"
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      )

      // Find template_id input field
      expect(screen.getByLabelText(/模板ID/)).toBeInTheDocument()
    })

    it('contains Input for name', () => {
      renderWithQueryClient(
        <TemplateFormModal
          open={true}
          mode="create"
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      )

      expect(screen.getByLabelText(/名称/)).toBeInTheDocument()
    })

    it('contains TextArea for description', () => {
      renderWithQueryClient(
        <TemplateFormModal
          open={true}
          mode="create"
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      )

      expect(screen.getByLabelText(/描述/)).toBeInTheDocument()
    })

    it('contains Input for command', () => {
      renderWithQueryClient(
        <TemplateFormModal
          open={true}
          mode="create"
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      )

      expect(screen.getByLabelText(/命令/)).toBeInTheDocument()
    })

    it('contains Select for risk_level with options low/medium/high', () => {
      renderWithQueryClient(
        <TemplateFormModal
          open={true}
          mode="create"
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      )

      // Find risk_level select field
      expect(screen.getByLabelText(/风险等级/)).toBeInTheDocument()
    })
  })

  describe('Form layout', () => {
    it('has two sections: basic info (top) and command area (bottom)', () => {
      renderWithQueryClient(
        <TemplateFormModal
          open={true}
          mode="create"
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      )

      // Check for basic info section
      expect(screen.getByText(/基础信息/)).toBeInTheDocument()

      // Check for command section
      expect(screen.getByText(/命令配置/)).toBeInTheDocument()
    })
  })

  describe('Preview button', () => {
    it('opens PolicyEvaluationModal with command content when clicked', async () => {
      renderWithQueryClient(
        <TemplateFormModal
          open={true}
          mode="create"
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      )

      // Fill in command field
      const commandInput = screen.getByLabelText(/命令/)
      fireEvent.change(commandInput, { target: { value: 'echo test' } })

      // Click preview button
      const previewButton = screen.getByText(/预览/)
      fireEvent.click(previewButton)

      // PolicyEvaluationModal should be open
      await waitFor(() => {
        expect(screen.getByTestId('policy-evaluation-modal')).toBeInTheDocument()
      })
    })
  })

  describe('Create mode', () => {
    it('shows "新建模板" as title', () => {
      renderWithQueryClient(
        <TemplateFormModal
          open={true}
          mode="create"
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      )

      expect(screen.getByText('新建模板')).toBeInTheDocument()
    })

    it('template_id is editable in create mode', () => {
      renderWithQueryClient(
        <TemplateFormModal
          open={true}
          mode="create"
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      )

      const templateIdInput = screen.getByLabelText(/模板ID/)
      expect(templateIdInput).not.toBeDisabled()
    })
  })

  describe('Edit mode', () => {
    const mockInitialValues: Template = {
      template_id: 'existing-template',
      name: 'Existing Template',
      description: 'Existing description',
      command: 'echo existing',
      risk_level: 'medium',
      enabled: true,
    }

    it('shows "编辑模板" as title', () => {
      renderWithQueryClient(
        <TemplateFormModal
          open={true}
          mode="edit"
          initialValues={mockInitialValues}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      )

      expect(screen.getByText('编辑模板')).toBeInTheDocument()
    })

    it('template_id is disabled in edit mode', () => {
      renderWithQueryClient(
        <TemplateFormModal
          open={true}
          mode="edit"
          initialValues={mockInitialValues}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      )

      const templateIdInput = screen.getByLabelText(/模板ID/)
      expect(templateIdInput).toBeDisabled()
    })

    it('form is populated with initial values in edit mode', () => {
      renderWithQueryClient(
        <TemplateFormModal
          open={true}
          mode="edit"
          initialValues={mockInitialValues}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      )

      // Check initial values are displayed
      expect(screen.getByDisplayValue('existing-template')).toBeInTheDocument()
      expect(screen.getByDisplayValue('Existing Template')).toBeInTheDocument()
      expect(screen.getByDisplayValue('Existing description')).toBeInTheDocument()
      expect(screen.getByDisplayValue('echo existing')).toBeInTheDocument()
    })
  })

  describe('Modal visibility', () => {
    it('is not visible when open=false', () => {
      renderWithQueryClient(
        <TemplateFormModal
          open={false}
          mode="create"
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      )

      expect(screen.queryByTestId('modal-container')).not.toBeInTheDocument()
    })

    it('calls onClose when close button is clicked', () => {
      renderWithQueryClient(
        <TemplateFormModal
          open={true}
          mode="create"
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      )

      const closeButton = screen.getByTestId('modal-close')
      fireEvent.click(closeButton)

      expect(mockOnClose).toHaveBeenCalled()
    })
  })
})