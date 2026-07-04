import { render, screen, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import PolicyEvaluationModal from './PolicyEvaluationModal'
import * as policyHooks from '../hooks/usePolicies'
import type { PolicyEvaluationResponse } from '../types/policy'

// Mock the useEvaluatePolicy hook
vi.mock('../hooks/usePolicies', () => ({
  useEvaluatePolicy: vi.fn(),
}))

describe('PolicyEvaluationModal', () => {
  const mockOnClose = vi.fn()

  const mockSuccessResponse: PolicyEvaluationResponse = {
    allowed: true,
    matched_rules: [],
    requested_risk_level: 'low',
    inferred_risk_level: 'low',
    final_risk_level: 'low',
    approval_required: false,
  }

  const mockBlockedResponse: PolicyEvaluationResponse = {
    allowed: false,
    block_reason: 'Command matches blacklist pattern: rm -rf',
    matched_rules: [{ rule_id: 'rule-001', pattern: 'rm.*' }, { rule_id: 'rule-002', pattern: '.*-rf.*' }],
    requested_risk_level: 'high',
    inferred_risk_level: 'high',
    final_risk_level: 'high',
    approval_required: false,
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows loading state during evaluation', async () => {
    vi.mocked(policyHooks.useEvaluatePolicy).mockReturnValue({
      mutate: vi.fn(),
      isPending: true,
      isError: false,
      error: null,
      data: undefined,
    } as unknown as ReturnType<typeof policyHooks.useEvaluatePolicy>)

    render(
      <PolicyEvaluationModal
        open={true}
        command="test command"
        onClose={mockOnClose}
      />
    )

    expect(screen.getByText('策略评估预览')).toBeInTheDocument()
    // Loading spinner should be visible
    expect(document.querySelector('.ant-spin')).toBeInTheDocument()
  })

  it('shows "允许执行" when allowed=true', async () => {
    const mockMutate = vi.fn()
    vi.mocked(policyHooks.useEvaluatePolicy).mockReturnValue({
      mutate: mockMutate,
      isPending: false,
      isError: false,
      error: null,
      data: mockSuccessResponse,
    } as unknown as ReturnType<typeof policyHooks.useEvaluatePolicy>)

    render(
      <PolicyEvaluationModal
        open={true}
        command="ls -la"
        onClose={mockOnClose}
      />
    )

    await waitFor(() => {
      expect(screen.getByText('允许执行')).toBeInTheDocument()
    })
  })

  it('shows block_reason and matched_rules when allowed=false', async () => {
    const mockMutate = vi.fn()
    vi.mocked(policyHooks.useEvaluatePolicy).mockReturnValue({
      mutate: mockMutate,
      isPending: false,
      isError: false,
      error: null,
      data: mockBlockedResponse,
    } as unknown as ReturnType<typeof policyHooks.useEvaluatePolicy>)

    render(
      <PolicyEvaluationModal
        open={true}
        command="rm -rf /"
        onClose={mockOnClose}
      />
    )

    await waitFor(() => {
      expect(screen.getByText('被拦截')).toBeInTheDocument()
      expect(screen.getByText('Command matches blacklist pattern: rm -rf')).toBeInTheDocument()
      expect(screen.getByText('rule-001')).toBeInTheDocument()
      expect(screen.getByText('rule-002')).toBeInTheDocument()
    })
  })

  it('uses RiskBadge to display final_risk_level', async () => {
    const mockMutate = vi.fn()
    vi.mocked(policyHooks.useEvaluatePolicy).mockReturnValue({
      mutate: mockMutate,
      isPending: false,
      isError: false,
      error: null,
      data: mockSuccessResponse,
    } as unknown as ReturnType<typeof policyHooks.useEvaluatePolicy>)

    render(
      <PolicyEvaluationModal
        open={true}
        command="hostname"
        onClose={mockOnClose}
      />
    )

    await waitFor(() => {
      expect(screen.getByText('LOW')).toBeInTheDocument()
    })
  })

  it('shows approval required message when approval_required=true', async () => {
    const mockApprovalResponse: PolicyEvaluationResponse = {
      allowed: true,
      matched_rules: [],
      requested_risk_level: 'medium',
      inferred_risk_level: 'medium',
      final_risk_level: 'medium',
      approval_required: true,
    }

    const mockMutate = vi.fn()
    vi.mocked(policyHooks.useEvaluatePolicy).mockReturnValue({
      mutate: mockMutate,
      isPending: false,
      isError: false,
      error: null,
      data: mockApprovalResponse,
    } as unknown as ReturnType<typeof policyHooks.useEvaluatePolicy>)

    render(
      <PolicyEvaluationModal
        open={true}
        command="kubectl restart"
        onClose={mockOnClose}
      />
    )

    await waitFor(() => {
      expect(screen.getByText('需要审批')).toBeInTheDocument()
    })
  })

  it('shows close button in footer', async () => {
    vi.mocked(policyHooks.useEvaluatePolicy).mockReturnValue({
      mutate: vi.fn(),
      isPending: true,
      isError: false,
      error: null,
      data: undefined,
    } as unknown as ReturnType<typeof policyHooks.useEvaluatePolicy>)

    render(
      <PolicyEvaluationModal
        open={true}
        command="test"
        onClose={mockOnClose}
      />
    )

    expect(screen.getByRole('button', { name: '关闭' })).toBeInTheDocument()
  })
})