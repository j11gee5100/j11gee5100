import { describe, it, expect } from 'vitest'
import type {
  Approval,
  ApprovalStatus,
  ApprovalAction,
  ApprovalFilters,
  ApproveRequest,
  RejectRequest,
  EscalateRequest,
} from './approval'

describe('approval types', () => {
  it('should export Approval interface with required fields', () => {
    // This is a compile-time test - if types are missing, TS will fail
    const approval: Approval = {
      approval_id: 'test-id',
      task_id: 'task-id',
      status: 'pending',
      current_level: 1,
      max_level: 2,
      escalation_count: 0,
      source: 'api',
      risk_level: 'readonly',
      created_at: '2026-04-08T00:00:00Z',
    }
    expect(approval.approval_id).toBe('test-id')
  })

  it('should export approval status types', () => {
    const pending: ApprovalStatus = 'pending'
    const approved: ApprovalStatus = 'approved'
    const rejected: ApprovalStatus = 'rejected'
    const expired: ApprovalStatus = 'expired'

    expect(pending).toBe('pending')
    expect(approved).toBe('approved')
    expect(rejected).toBe('rejected')
    expect(expired).toBe('expired')
  })

  it('should export ApprovalAction interface', () => {
    const action: ApprovalAction = {
      action_id: 'action-id',
      action_type: 'approved',
      operator_id: 'operator-id',
      created_at: '2026-04-08T00:00:00Z',
    }
    expect(action.action_type).toBe('approved')
  })

  it('should export ApprovalFilters interface', () => {
    const filters: ApprovalFilters = {
      current_level: 1,
      status: 'pending',
    }
    expect(filters.current_level).toBe(1)
  })

  it('should export request types', () => {
    const approveReq: ApproveRequest = {
      comment: 'approved',
    }
    const rejectReq: RejectRequest = {
      comment: 'rejected reason',
    }
    const escalateReq: EscalateRequest = {
      comment: 'escalate reason',
    }

    expect(approveReq.comment).toBe('approved')
    expect(rejectReq.comment).toBe('rejected reason')
    expect(escalateReq.comment).toBe('escalate reason')
  })
})