import type { PaginatedResponse } from './api'

/**
 * 任务创建请求
 * 用于通过模板或自定义命令创建任务
 */
export interface TaskCreateRequest {
  /** 命令模板ID（可选，推荐使用模板） */
  command_template_id?: string
  /** 自定义命令内容（可选，模板为空时可填写） */
  command?: string
  /** 目标资产ID（必填） */
  target_asset_id: string
  /** 执行使用的系统用户ID（必填） */
  run_as_system_user_id: string
  /** 风险等级（可选，默认 'medium'） */
  risk_level?: 'low' | 'medium' | 'high'
  /** 幂等性键（可选，用于防止重复创建） */
  idempotency_key?: string
}

/**
 * 任务创建响应
 * 包含任务ID和审批信息
 */
export interface TaskCreateResponse {
  /** 创建的任务ID */
  task_id: string
  /** 是否需要审批 */
  approval_required: boolean
  /** 审批单ID（当 approval_required=true 时返回） */
  approval_id?: string
}

/**
 * 任务详情
 */
export interface Task {
  /** 任务ID */
  task_id: string
  /** 命令模板ID（可选） */
  command_template_id?: string
  /** 执行命令 */
  command: string
  /** 目标资产ID */
  target_asset_id: string
  /** 执行使用的系统用户ID */
  run_as_system_user_id: string
  /** 风险等级 */
  risk_level: 'low' | 'medium' | 'high'
  /** 任务状态 */
  status: 'pending' | 'executing' | 'success' | 'failed' | 'canceled'
  /** 失败码（仅 status=failed 时） */
  failure_code?: string
  /** 原因/错误信息 */
  reason?: string
  /** 任务来源 */
  source?: string
  /** 创建时间 */
  created_at: string
  /** 更新时间 */
  updated_at: string
}

/**
 * 资产信息
 * 用于资产选择下拉列表
 */
export interface Asset {
  /** 资产ID */
  asset_id: string
  /** 主机名 */
  hostname: string
  /** IP地址 */
  ip: string
  /** 资产状态 */
  status: string
}

/**
 * 资产列表响应
 */
export interface AssetListResponse extends PaginatedResponse<Asset> {}

/**
 * 系统用户信息
 * 用于系统用户选择下拉列表
 */
export interface SystemUser {
  /** 系统用户ID */
  system_user_id: string
  /** 显示名称 */
  name: string
  /** 用户名 */
  username: string
}

/**
 * 系统用户列表响应
 */
export interface SystemUserListResponse {
  /** 资产ID */
  asset_id: string
  /** 可用系统用户列表 */
  system_users: SystemUser[]
}