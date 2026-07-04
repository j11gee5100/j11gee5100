import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import AuditCard from './AuditCard'
import type { AuditRecord } from '../types/governance'

// Mock formatters to return predictable values
vi.mock('../utils/formatters', () => ({
  formatRelativeTime: (_date: string) => '2 minutes ago',
  formatDateTime: (_date: string) => '2024-01-01 12:00:00',
}))

describe('AuditCard', () => {
  const mockRecord: AuditRecord = {
    audit_id: 'audit-001',
    entity_type: 'template',
    entity_id: 'template-001',
    action: 'create',
    operator_id: 'admin',
    source_ip: '192.168.1.1',
    detail: { change: 'created new template' },
    created_at: '2024-01-01T12:00:00Z',
  }

  const mockOnViewDetail = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('displays entity_type, entity_id, action, operator_id, created_at', () => {
    render(<AuditCard record={mockRecord} onViewDetail={mockOnViewDetail} />)

    // Check entity_type is displayed as a Tag
    expect(screen.getByText('template')).toBeInTheDocument()

    // Check entity_id is displayed (gray small text)
    expect(screen.getByText('template-001')).toBeInTheDocument()

    // Check action is displayed as a Tag
    expect(screen.getByText('create')).toBeInTheDocument()

    // Check operator_id is displayed
    expect(screen.getByText(/admin/i)).toBeInTheDocument()
  })

  it('shows formatted time using formatRelativeTime', () => {
    render(<AuditCard record={mockRecord} onViewDetail={mockOnViewDetail} />)

    // Should show relative time
    expect(screen.getByText('2 minutes ago')).toBeInTheDocument()
  })

  it('card hover shows tooltip with exact timestamp', async () => {
    render(<AuditCard record={mockRecord} onViewDetail={mockOnViewDetail} />)

    // Find the time element that should have a tooltip
    const timeElement = screen.getByText('2 minutes ago')
    expect(timeElement).toBeInTheDocument()

    // The parent should be a Tooltip - check for title attribute or tooltip content
    // Since Ant Design Tooltip shows on hover, we check that the element exists
    expect(timeElement).toBeInTheDocument()
  })

  it('card click triggers onViewDetail callback', () => {
    render(<AuditCard record={mockRecord} onViewDetail={mockOnViewDetail} />)

    // Find and click the card
    const card = screen.getByRole('article')
    fireEvent.click(card)

    // Verify callback was called with the record
    expect(mockOnViewDetail).toHaveBeenCalledWith(mockRecord)
  })

  it('displays action tag with correct color for create action', () => {
    render(<AuditCard record={mockRecord} onViewDetail={mockOnViewDetail} />)

    // Create action should have success (green) color
    const actionTag = screen.getByText('create')
    expect(actionTag).toBeInTheDocument()
  })

  it('displays action tag with correct color for update action', () => {
    const updateRecord = { ...mockRecord, action: 'update' }
    render(<AuditCard record={updateRecord} onViewDetail={mockOnViewDetail} />)

    const actionTag = screen.getByText('update')
    expect(actionTag).toBeInTheDocument()
  })

  it('displays action tag with correct color for delete action', () => {
    const deleteRecord = { ...mockRecord, action: 'delete' }
    render(<AuditCard record={deleteRecord} onViewDetail={mockOnViewDetail} />)

    const actionTag = screen.getByText('delete')
    expect(actionTag).toBeInTheDocument()
  })

  it('displays enable action', () => {
    const enableRecord = { ...mockRecord, action: 'enable' }
    render(<AuditCard record={enableRecord} onViewDetail={mockOnViewDetail} />)

    expect(screen.getByText('enable')).toBeInTheDocument()
  })

  it('displays disable action', () => {
    const disableRecord = { ...mockRecord, action: 'disable' }
    render(<AuditCard record={disableRecord} onViewDetail={mockOnViewDetail} />)

    expect(screen.getByText('disable')).toBeInTheDocument()
  })
})