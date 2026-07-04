---
phase: 03-approval-center
plan: 01
subsystem: frontend/types-hooks
tags: [approval, types, react-query, hooks, tdd]
requires: []
provides:
  - approval types definition
  - approval TanStack Query hooks
  - approval routes configuration
affects: []
tech-stack:
  added:
    - TanStack Query hooks for approval API
  patterns:
    - TDD approach for types and hooks
    - Query key factory pattern
    - Mutation with invalidate pattern
key-files:
  created:
    - frontend/src/types/approval.ts
    - frontend/src/types/approval.test.ts
    - frontend/src/hooks/useApprovals.ts
    - frontend/src/hooks/useApprovals.test.tsx
  modified:
    - frontend/src/App.tsx
decisions:
  - 使用 TDD 方法实现类型定义和 hooks
  - 遵循TanStack Query 最佳实践：query key factory + mutation invalidate
metrics:
  duration: ~5 minutes
  tasks_completed: 3
  files_created: 4
  files_modified: 1
completed_at: 2026-04-08T00:43:00Z
---

# Phase 03 Plan 01: 审批中心数据层基础类型与 Hooks

## 一句话总结

定义审批相关的 TypeScript 类型、TanStack Query hooks 和路由配置，为后续 UI 组件提供数据基础。

## 完成的任务

### Task 1: 定义审批相关类型

创建 `frontend/src/types/approval.ts`，包含：
- `ApprovalStatus` 类型 (pending | approved | rejected | expired)
- `Approval` 主接口（根据接口文档 §8.5.7 定义所有字段）
- `ApprovalAction` 接口（时间线记录）
- `ApprovalListResponse` 分页响应类型
- `ApproveRequest`, `RejectRequest`, `EscalateRequest` 操作请求类型
- `ApprovalFilters` 查询参数类型

采用 TDD 方法，先创建测试文件验证类型导出，再实现类型定义。

**Commit:** ef76d61

### Task 2: 创建审批 TanStack Query hooks

创建 `frontend/src/hooks/useApprovals.ts`，实现：
- `approvalKeys` query key factory（all/pending/pendingByLevel/detail）
- `useApprovals(level)` - 获取指定层级待审批列表（staleTime: 30s）
- `useApprovalDetail(approvalId)` - 获取审批详情含时间线（staleTime: 10s）
- `useApprove()` mutation - 通过审批，invalidate pending 和 detail queries
- `useReject()` mutation - 驳回审批（comment 必填）
- `useEscalate()` mutation - 升级审批

遵循现有 useTemplates.ts 和 useGovernance.ts 的模式。

**Commit:** fbd9658

### Task 3: 更新路由配置指向审批页面

更新 `frontend/src/App.tsx`，添加注释说明：
- `/approvals` 路由已有 PlaceholderPage 占位符，Plan 03-02 将替换为 ApprovalListPage
- `/approvals/:approvalId` 路由使用抽屉展示，保留占位符
- 菜单项"审批中心"已存在（key: '/approvals'）

**Commit:** 44b4390

## 技术要点

### Query Key Factory 模式

```typescript
export const approvalKeys = {
  all: ['approvals'] as const,
  pending: () => [...approvalKeys.all, 'pending'] as const,
  pendingByLevel: (level: number) => [...approvalKeys.pending(), { current_level: level }] as const,
  details: () => [...approvalKeys.all, 'detail'] as const,
  detail: (id: string) => [...approvalKeys.details(), id] as const,
}
```

### Mutation Invalidate Pattern

```typescript
export function useApprove() {
  const queryClient = useQueryClient()
  return useMutation<Approval, Error, { approvalId: string; comment?: string }>({
    mutationFn: async ({ approvalId, comment }) => {
      const { data } = await apiClient.post<Approval>(`/approvals/${approvalId}/approve`, { comment })
      return data
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: approvalKeys.pending() })
      queryClient.invalidateQueries({ queryKey: approvalKeys.detail(variables.approvalId) })
    },
  })
}
```

## Deviations from Plan

None - plan executed exactly as written.

## 验收标准达成

- [x] frontend/src/types/approval.ts 存在且包含 Approval、ApprovalStatus、ApprovalAction 类型定义
- [x] frontend/src/hooks/useApprovals.ts 存在且导出 approvalKeys、useApprovals、useApprovalDetail、useApprove、useReject、useEscalate
- [x] frontend/src/App.tsx 包含 /approvals 和 /approvals/:approvalId 路由配置
- [x] 所有类型和 hooks 符合 Phase 02 建立的模式

## Threat Model Consideration

根据计划中的 threat_model：
- T-03-01-01 (Tampering): 类型定义仅约束 TypeScript，运行时数据由后端验证 — 已 accept
- T-03-01-02 (Elevation): current_level 参数由 UI 限定为 1/2，不允许用户手动输入 — hooks 设计遵循此约束

## Next Steps

Plan 03-02 将基于此数据层创建：
- ApprovalListPage 组件（列表展示 + L1/L2 Tab）
- ApprovalActionDrawer 组件（详情展示 + 通过/驳回/升级操作）
- 替换 PlaceholderPage 为真实页面组件

---

**结束时间:** 2026-04-08T00:43:00Z

## Self-Check: PASSED

- [x] frontend/src/types/approval.ts 存在
- [x] frontend/src/hooks/useApprovals.ts 存在
- [x] .planning/phases/03-approval-center/03-01-SUMMARY.md 存在
- [x] Commits ef76d61, fbd9658, 44b4390 已验证