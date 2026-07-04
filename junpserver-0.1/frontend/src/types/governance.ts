import type { PaginatedResponse } from './api'

/**
 * Audit record type definition
 * Used for tracking template/policy changes
 */
export interface AuditRecord {
  audit_id: string
  entity_type: string
  entity_id: string
  action: string
  operator_id: string
  source_ip?: string
  detail: Record<string, unknown>
  created_at: string
}

/**
 * Audit log list response with pagination
 */
export interface AuditListResponse extends PaginatedResponse<AuditRecord> {}

/**
 * Time range filter for audit logs
 */
export type TimeRange = '1h' | '24h' | '7d'

/**
 * Audit log filter parameters
 */
export interface AuditFilters {
  entity_type?: string
  entity_id?: string
  action?: string
  operator_id?: string
  time_range?: TimeRange
  limit?: number
  offset?: number
}

/**
 * Convert time_range to hours for API
 */
export function timeRangeToHours(timeRange: TimeRange): number {
  switch (timeRange) {
    case '1h':
      return 1
    case '24h':
      return 24
    case '7d':
      return 168
    default:
      return 24
  }
}