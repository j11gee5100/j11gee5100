import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import TemplateCard from './TemplateCard'
import type { Template } from '../types/template'

// Mock Ant Design Switch component
vi.mock('antd', async () => {
  const actual = await vi.importActual('antd')
  return {
    ...actual,
    Switch: ({ checked, onChange, disabled }: {
      checked: boolean;
      onChange?: (checked: boolean) => void;
      disabled?: boolean;
    }) => (
      <input
        type="checkbox"
        data-testid="switch-toggle"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange?.(e.target.checked)}
      />
    ),
  }
})

describe('TemplateCard', () => {
  const mockTemplate: Template = {
    template_id: 'test-template-001',
    name: 'Test Template',
    description: 'A test template description',
    command: 'echo "hello"',
    risk_level: 'low',
    enabled: true,
    updated_by: 'admin',
    updated_at: '2024-01-01T00:00:00Z',
  }

  const mockOnToggleEnabled = vi.fn()
  const mockOnEdit = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('displays template_id, name, risk_level (as RiskBadge), and enabled status', () => {
    render(
      <TemplateCard
        template={mockTemplate}
        onToggleEnabled={mockOnToggleEnabled}
      />
    )

    // Check template_id is displayed (in gray)
    expect(screen.getByText('test-template-001')).toBeInTheDocument()

    // Check name is displayed
    expect(screen.getByText('Test Template')).toBeInTheDocument()

    // Check RiskBadge displays risk level (LOW text)
    expect(screen.getByText('LOW')).toBeInTheDocument()

    // Check enabled status text
    expect(screen.getByText(/已启用/)).toBeInTheDocument()
  })

  it('shows disabled status when template is disabled', () => {
    const disabledTemplate = { ...mockTemplate, enabled: false }
    render(
      <TemplateCard
        template={disabledTemplate}
        onToggleEnabled={mockOnToggleEnabled}
      />
    )

    expect(screen.getByText(/已停用/)).toBeInTheDocument()
  })

  it('has Switch toggle in card that controls enabled status', () => {
    render(
      <TemplateCard
        template={mockTemplate}
        onToggleEnabled={mockOnToggleEnabled}
      />
    )

    // Find the switch toggle
    const switchToggle = screen.getByTestId('switch-toggle')

    // Verify initial state
    expect(switchToggle).toBeChecked()

    // Click to toggle
    fireEvent.click(switchToggle)

    // Verify callback is called with correct params
    expect(mockOnToggleEnabled).toHaveBeenCalledWith('test-template-001', false)
  })

  it('calls onToggleEnabled with correct params when switch is toggled off', () => {
    const enabledTemplate = { ...mockTemplate, enabled: true }
    render(
      <TemplateCard
        template={enabledTemplate}
        onToggleEnabled={mockOnToggleEnabled}
      />
    )

    const switchToggle = screen.getByTestId('switch-toggle')
    fireEvent.click(switchToggle)

    expect(mockOnToggleEnabled).toHaveBeenCalledWith('test-template-001', false)
  })

  it('calls onToggleEnabled with correct params when switch is toggled on', () => {
    const disabledTemplate = { ...mockTemplate, enabled: false }
    render(
      <TemplateCard
        template={disabledTemplate}
        onToggleEnabled={mockOnToggleEnabled}
      />
    )

    const switchToggle = screen.getByTestId('switch-toggle')
    fireEvent.click(switchToggle)

    expect(mockOnToggleEnabled).toHaveBeenCalledWith('test-template-001', true)
  })

  it('handles medium risk level correctly', () => {
    const mediumTemplate = { ...mockTemplate, risk_level: 'medium' as const }
    render(
      <TemplateCard
        template={mediumTemplate}
        onToggleEnabled={mockOnToggleEnabled}
      />
    )

    expect(screen.getByText('MEDIUM')).toBeInTheDocument()
  })

  it('handles high risk level correctly', () => {
    const highTemplate = { ...mockTemplate, risk_level: 'high' as const }
    render(
      <TemplateCard
        template={highTemplate}
        onToggleEnabled={mockOnToggleEnabled}
      />
    )

    expect(screen.getByText('HIGH')).toBeInTheDocument()
  })

  it('calls onEdit when card is clicked for editing', () => {
    render(
      <TemplateCard
        template={mockTemplate}
        onToggleEnabled={mockOnToggleEnabled}
        onEdit={mockOnEdit}
      />
    )

    // Click on the card body (not the switch)
    const card = screen.getByRole('article')
    fireEvent.click(card)

    expect(mockOnEdit).toHaveBeenCalledWith(mockTemplate)
  })
})