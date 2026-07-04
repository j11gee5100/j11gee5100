import type { PaginatedResponse } from './api'

/**
 * Command template type definition
 * Used for managing controlled command templates
 */
export interface Template {
  template_id: string
  name: string
  description?: string
  command: string
  risk_level: 'low' | 'medium' | 'high'
  enabled: boolean
  updated_by?: string
  updated_at?: string
}

/**
 * Template form data for create/edit operations
 * Excludes auto-generated fields (updated_by, updated_at)
 */
export interface TemplateFormData {
  template_id: string
  name: string
  description?: string
  command: string
  risk_level: 'low' | 'medium' | 'high'
  enabled: boolean
}

/**
 * Template list response with pagination
 */
export interface TemplateListResponse extends PaginatedResponse<Template> {}

/**
 * Template create request payload
 */
export interface TemplateCreateRequest {
  template_id: string
  name: string
  description?: string
  command: string
  risk_level: 'low' | 'medium' | 'high'
  enabled?: boolean
}

/**
 * Template update request payload
 * All fields are optional for partial update
 */
export interface TemplateUpdateRequest {
  name?: string
  description?: string
  command?: string
  risk_level?: 'low' | 'medium' | 'high'
  enabled?: boolean
}