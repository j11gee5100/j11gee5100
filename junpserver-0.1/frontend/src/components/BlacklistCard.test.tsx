import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import BlacklistCard from './BlacklistCard'
import type { BlacklistRule } from '../types/policy'

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

describe('BlacklistCard', () => {
  const mockRule: BlacklistRule = {
    rule_id: 'rule-001',
    pattern: 'rm -rf *',
    hard_block: true,
    enabled: true,
    updated_by: 'admin',
    updated_at: '2024-01-01T00:00:00Z',
  }

  const mockOnToggleEnabled = vi.fn()
  const mockOnEdit = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('displays pattern, hard_block status, enabled status', () => {
    render(
      <BlacklistCard
        rule={mockRule}
        onToggleEnabled={mockOnToggleEnabled}
      />
    )

    // Check pattern is displayed (in monospace font - but we just check text)
    expect(screen.getByText('rm -rf *')).toBeInTheDocument()

    // Check hard_block label - "硬拦截" for hard_block=true
    expect(screen.getByText('硬拦截')).toBeInTheDocument()

    // Check enabled status text
    expect(screen.getByText(/已启用/)).toBeInTheDocument()
  })

  it('Switch toggle controls enabled status', () => {
    render(
      <BlacklistCard
        rule={mockRule}
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
    expect(mockOnToggleEnabled).toHaveBeenCalledWith('rule-001', false)
  })

  it('hard_block=true shows "硬拦截" label (red)', () => {
    const hardBlockRule = { ...mockRule, hard_block: true }
    render(
      <BlacklistCard
        rule={hardBlockRule}
        onToggleEnabled={mockOnToggleEnabled}
      />
    )

    expect(screen.getByText('硬拦截')).toBeInTheDocument()
  })

  it('hard_block=false shows "软拦截" label (blue)', () => {
    const softBlockRule = { ...mockRule, hard_block: false }
    render(
      <BlacklistCard
        rule={softBlockRule}
        onToggleEnabled={mockOnToggleEnabled}
      />
    )

    expect(screen.getByText('软拦截')).toBeInTheDocument()
  })

  it('shows disabled status when rule is disabled', () => {
    const disabledRule = { ...mockRule, enabled: false }
    render(
      <BlacklistCard
        rule={disabledRule}
        onToggleEnabled={mockOnToggleEnabled}
      />
    )

    expect(screen.getByText(/已停用/)).toBeInTheDocument()
  })

  it('calls onToggleEnabled with correct params when toggled', () => {
    render(
      <BlacklistCard
        rule={mockRule}
        onToggleEnabled={mockOnToggleEnabled}
      />
    )

    const switchToggle = screen.getByTestId('switch-toggle')
    fireEvent.click(switchToggle)

    expect(mockOnToggleEnabled).toHaveBeenCalledWith('rule-001', false)
  })

  it('calls onEdit when card is clicked for editing', () => {
    render(
      <BlacklistCard
        rule={mockRule}
        onToggleEnabled={mockOnToggleEnabled}
        onEdit={mockOnEdit}
      />
    )

    // Click on the card body (not the switch)
    const card = screen.getByRole('article')
    fireEvent.click(card)

    expect(mockOnEdit).toHaveBeenCalledWith(mockRule)
  })
})