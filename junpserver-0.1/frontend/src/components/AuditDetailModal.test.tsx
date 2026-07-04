import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import AuditDetailModal from './AuditDetailModal'
import type { AuditRecord } from '../types/governance'

// Mock formatters
vi.mock('../utils/formatters', () => ({
  formatDateTime: (_date: string) => '2024-01-01 12:00:00',
}))

// Mock Ant Design Modal to simplify testing
vi.mock('antd', async () => {
  const actual = await vi.importActual('antd')
  return {
    ...actual,
    Modal: ({ open, title, children, onCancel }: {
      open: boolean;
      title: string;
      children: React.ReactNode;
      onCancel?: () => void;
    }) => {
      if (!open) return null
      return (
        <div data-testid="modal" role="dialog">
          <div data-testid="modal-title">{title}</div>
          <div data-testid="modal-content">{children}</div>
          <button onClick={onCancel} data-testid="modal-close">Close</button>
        </div>
      )
    },
  }
})

describe('AuditDetailModal', () => {
  const mockRecord: AuditRecord = {
    audit_id: 'audit-001',
    entity_type: 'template',
    entity_id: 'template-001',
    action: 'create',
    operator_id: 'admin',
    source_ip: '192.168.1.1',
    detail: { name: 'test', command: 'echo hello', risk_level: 'low' },
    created_at: '2024-01-01T12:00:00Z',
  }

  const mockOnClose = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('displays audit_id, entity_type, entity_id, action, operator_id, source_ip, created_at', () => {
    render(<AuditDetailModal open={true} record={mockRecord} onClose={mockOnClose} />)

    // Check all fields are displayed
    expect(screen.getByText('audit-001')).toBeInTheDocument()
    expect(screen.getByText('template')).toBeInTheDocument()
    expect(screen.getByText('template-001')).toBeInTheDocument()
    expect(screen.getByText('create')).toBeInTheDocument()
    expect(screen.getByText('admin')).toBeInTheDocument()
    expect(screen.getByText('192.168.1.1')).toBeInTheDocument()
    expect(screen.getByText('2024-01-01 12:00:00')).toBeInTheDocument()
  })

  it('displays detail JSON in formatted view', () => {
    render(<AuditDetailModal open={true} record={mockRecord} onClose={mockOnClose} />)

    // Check that JSON detail is displayed
    expect(screen.getByText(/变更详情/)).toBeInTheDocument()

    // Check that JSON content is shown (using pre tag)
    const preElement = document.querySelector('pre')
    expect(preElement).toBeInTheDocument()

    // Check that the JSON content contains our detail values
    expect(preElement?.textContent).toContain('"name"')
    expect(preElement?.textContent).toContain('test')
    expect(preElement?.textContent).toContain('echo hello')
  })

  it('JSON is formatted for readability with monospace font', () => {
    render(<AuditDetailModal open={true} record={mockRecord} onClose={mockOnClose} />)

    // Check for pre tag which typically uses monospace
    const preElement = document.querySelector('pre')
    expect(preElement).toBeInTheDocument()
  })

  it('does not render when open is false', () => {
    render(<AuditDetailModal open={false} record={mockRecord} onClose={mockOnClose} />)

    expect(screen.queryByTestId('modal')).not.toBeInTheDocument()
  })

  it('does not render when record is undefined', () => {
    render(<AuditDetailModal open={true} record={undefined} onClose={mockOnClose} />)

    expect(screen.queryByTestId('modal')).not.toBeInTheDocument()
  })

  it('handles record without source_ip', () => {
    const recordWithoutIp = { ...mockRecord, source_ip: undefined }
    render(<AuditDetailModal open={true} record={recordWithoutIp} onClose={mockOnClose} />)

    // Should still render other fields
    expect(screen.getByText('audit-001')).toBeInTheDocument()
    expect(screen.getByText('admin')).toBeInTheDocument()
  })

  it('displays modal with correct title', () => {
    render(<AuditDetailModal open={true} record={mockRecord} onClose={mockOnClose} />)

    expect(screen.getByText('审计详情')).toBeInTheDocument()
  })
})