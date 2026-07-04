import type { PaginatedResponse } from './api'

/**
 * 审批状态类型
 * - pending: 待审批
 * - approved: 已通过
 * - rejected: 已驳回
 * - expired: 已过期
 */
export type ApprovalStatus = 'pending' | 'approved' | 'rejected' | 'expired'

/**
 * 审批动作类型（时间线记录）
 */
export type ApprovalActionType = 'approved' | 'rejected' | 'escalated' | 'created'

/**
 * 审批动作接口（时间线记录）
 * 记录审批过程中的每个动作
 */
export interface ApprovalAction {
  /** 动作唯一标识 */
  action_id: string
  /** 动作类型 */
  action_type: ApprovalActionType
  /** 操作者 ID */
  operator_id: string
  /** 操作备注/驳回原因（可选） */
  comment?: string
  /** 动作时间 */
  created_at: string
}

/**
 * 审批主接口
 * 根据接口文档 docs/05-interface-spec.md §8.5.7 定义
 */
export interface Approval {
  /** 审批单唯一标识 */
  approval_id: string
  /** 关联任务 ID */
  task_id: string
  /** 当前状态 */
  status: ApprovalStatus
  /** 当前审批层级（如 1、2） */
  current_level: number
  /** 最大审批层级 */
  max_level: number
  /** 已升级次数 */
  escalation_count: number
  /** 下次可升级时间（ISO 格式，可选） */
  next_escalate_at?: string
  /** 过期时间（ISO 格式，可选） */
  expires_at?: string
  /** 来源：alert/manual/scheduled 等 */
  source: string
  /** 风险等级 */
  risk_level: string
  /** 创建时间 */
  created_at: string
  /** 更新时间（可选） */
  updated_at?: string
  /** 审批请求理由（可选） */
  request_reason?: string
  /** 审批动作时间线（可选） */
  actions?: ApprovalAction[]
}

/**
 * 审批列表响应类型
 * 继承分页响应
 */
export interface ApprovalListResponse extends PaginatedResponse<Approval> {}

/**
 * 审批操作请求类型
 */

/**
 * 通过审批请求
 */
export interface ApproveRequest {
  /** 操作备注（可选） */
  comment?: string
}

/**
 * 驳回审批请求
 * 驳回原因必填
 */
export interface RejectRequest {
  /** 驳回原因（必填） */
  comment: string
}

/**
 * 升级审批请求
 */
export interface EscalateRequest {
  /** 升级原因（可选） */
  comment?: string
}

/**
 * 审批查询参数类型
 */
export interface ApprovalFilters {
  /** 按层级筛选 */
  current_level?: number
  /** 按状态筛选 */
  status?: ApprovalStatus
}