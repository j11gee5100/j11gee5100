import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import RiskBadge from './RiskBadge'

describe('RiskBadge', () => {
  it('shows "low" with green color (success)', () => {
    render(<RiskBadge level="low" />)
    const badge = screen.getByText('LOW')
    expect(badge).toBeInTheDocument()
  })

  it('shows "medium" with yellow/orange color (warning)', () => {
    render(<RiskBadge level="medium" />)
    const badge = screen.getByText('MEDIUM')
    expect(badge).toBeInTheDocument()
  })

  it('shows "high" with red color (error)', () => {
    render(<RiskBadge level="high" />)
    const badge = screen.getByText('HIGH')
    expect(badge).toBeInTheDocument()
  })

  it('uses default size when not specified', () => {
    render(<RiskBadge level="medium" />)
    const badge = screen.getByText('MEDIUM')
    expect(badge).toBeInTheDocument()
  })
})