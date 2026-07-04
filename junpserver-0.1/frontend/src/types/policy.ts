import type { PaginatedResponse } from './api'

/**
 * Blacklist rule type definition
 * Used for command pattern blocking rules
 */
export interface BlacklistRule {
  rule_id: string
  pattern: string
  hard_block: boolean
  enabled: boolean
  updated_by?: string
  updated_at?: string
}

/**
 * Blacklist rule list response with pagination
 */
export interface BlacklistListResponse extends PaginatedResponse<BlacklistRule> {}

/**
 * Blacklist rule create request payload
 */
export interface BlacklistCreateRequest {
  pattern: string
  hard_block: boolean
  enabled?: boolean
}

/**
 * Blacklist rule update request payload
 * All fields are optional for partial update
 */
export interface BlacklistUpdateRequest {
  pattern?: string
  hard_block?: boolean
  enabled?: boolean
}

/**
 * Policy evaluation request payload
 * Used to preview if a command would be blocked
 */
export interface PolicyEvaluationRequest {
  command?: string
  command_template_id?: string
  requested_risk_level?: 'low' | 'medium' | 'high'
}

/**
 * Matched rule from policy evaluation
 * Each rule contains source, pattern, and block type information
 */
export interface MatchedRule {
  source?: string
  rule_id?: string
  pattern?: string
  hard_block?: boolean
  description?: string
}

/**
 * Policy evaluation response
 * Contains evaluation result and risk determination
 */
export interface PolicyEvaluationResponse {
  allowed: boolean
  block_reason?: string
  matched_rules: MatchedRule[]
  requested_risk_level: string
  inferred_risk_level: string
  final_risk_level: string
  approval_required: boolean
}