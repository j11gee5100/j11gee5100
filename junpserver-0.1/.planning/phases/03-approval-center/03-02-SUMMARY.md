---
phase: 03-approval-center
plan: 02
subsystem: frontend/components
tags: [approval, card, tdd, react, ant-design]
requires:
  - 03-01 (Approval types and hooks)
provides:
  - ApprovalCard UI component for approval list display
affects:
  - ApprovalListPage (Plan 03-03)
tech-stack:
  added:
    - ApprovalCard component with action buttons
  patterns:
    - TDD approach for UI component
    - Card layout pattern from TemplateCard
    - StopPropagation pattern for nested click handlers
key-files:
  created:
    - frontend/src/components/ApprovalCard.tsx
    - frontend/src/components/ApprovalCard.test.tsx
    - frontend/src/types/approval.ts (Rule 3 fix)
    - frontend/src/types/approval.test.ts (Rule 3 fix)
  modified: []
decisions:
  - 使用 TDD 方法实现 ApprovalCard 组件
  - 来源标签使用中文映射（alert→告警, manual→手动, scheduled→定时, api→API）
  - 超时状态显示剩余时间或已超时标签
  - 按钮禁用逻辑基于 status === 'pending' 判断
metrics:
  duration: ~4 minutes (216s)
  tasks_completed: 1
  files_created: 4
  files_modified: 0
completed_at: 2026-04-08T00:53:27Z
---

# Phase 03 Plan 02: 审批卡片组件

## 一句话总结

创建 ApprovalCard 组件，展示审批单基本信息并提供通过/驳回快速操作按钮，遵循 Phase 02 卡片设计风格。

## 完成的任务

### Task 1: 实现 ApprovalCard 组件（TDD）

使用 TDD 方法创建 `frontend/src/components/ApprovalCard.tsx`：

**RED 阶段：**
- 创建测试文件 ApprovalCard.test.tsx
- 19 个测试场景覆盖基础信息、超时状态、操作按钮、禁用逻辑、交互行为、样式属性
- 验证测试因模块不存在而失败

**GREEN 阶段：**
- 实现 ApprovalCard 组件，满足所有测试场景
- 针对 2 个测试失败进行修复（中文显示适配）
- 19 个测试全部通过

**组件结构（per D-01/D-03/D-04/D-11/D-13）:**
- 卡片顶部：approval_id、task_id（灰色辅助文本）
- 核心信息区：来源标签（中文映射）、RiskBadge 风险等级、Level 层级标签
- 超时状态区：剩余时间/已超时标签
- 操作按钮区：通过、驳回按钮（响应 isOperationDisabled）

**Commit:** 2ba9250

## 技术要点

### 来源标签中文映射

```typescript
const sourceLabelMap: Record<string, string> = {
  alert: '告警',
  manual: '手动',
  scheduled: '定时',
  api: 'API',
}
```

### 超时时间计算

```typescript
function getRemainingTime(expiresAt?: string): { text: string; isExpired: boolean } | null {
  if (!expiresAt) return null
  const now = dayjs()
  const expires = dayjs(expiresAt)
  const remainingMinutes = expires.diff(now, 'minute')
  if (remainingMinutes <= 0) return { text: '已超时', isExpired: true }
  // 格式化剩余时间
}
```

### 按钮禁用逻辑

```typescript
const isOperationDisabled = approval.status !== 'pending'
```

## Deviations from Plan

### [Rule 3 - Blocking Issue] 补充缺失的 approval.ts 类型文件

- **发现时间:** Task 1 开始前
- **问题:** 工作树中缺少 approval.ts 类型文件，导致 useApprovals.ts 导入失败
- **原因:** Plan 01 的 b0fe4ef 提交未包含该文件（仅包含 hooks 和 App.tsx）
- **修复:** 创建 approval.ts 和 approval.test.ts 文件，与主仓库内容一致
- **文件:** frontend/src/types/approval.ts, frontend/src/types/approval.test.ts
- **Commit:** 2ba9250（与 Task 1 合并提交）

### [Rule 1 - Bug] 测试适配中文显示

- **发现时间:** Task 1 GREEN 阶段
- **问题:** 测试期望英文显示（alert），但组件使用中文映射（告警）
- **修复:** 修改测试用例使用正则匹配和中文预期值
- **文件:** frontend/src/components/ApprovalCard.test.tsx
- **Commit:** 2ba9250

## 验收标准达成

- [x] frontend/src/components/ApprovalCard.tsx 存在（175 行）
- [x] ApprovalCardProps 包含 approval、onApprove、onReject、onViewDetails
- [x] 卡片包含通过/驳回按钮，disabled=True 当 status !== 'pending'
- [x] 卡片显示 approval_id、task_id、风险等级、来源、超时状态
- [x] 点击卡片触发 onViewDetails 回调
- [x] 使用 RiskBadge 组件
- [x] 组件遵循 Phase 02 TemplateCard 设计风格（hoverable, cursor:pointer）
- [x] 19 个测试全部通过

## Threat Model Consideration

根据计划中的 threat_model：
- T-03-02-01 (Spoofing): 回调由父组件注入，父组件负责权限校验 — 已 accept
- T-03-02-02 (Denial): 单个卡片渲染成本低，无 DoS 风险 — 已 accept

## Next Steps

Plan 03-03 将基于此组件创建：
- ApprovalListPage 页面（列表展示 + L1/L2 Tab）
- 使用 ApprovalCard 作为列表项组件
- 集成 useApprovals hook 获取数据

---

**开始时间:** 2026-04-08T00:49:50Z
**结束时间:** 2026-04-08T00:53:27Z
**持续时间:** 216 秒

## Self-Check: PASSED

- [x] frontend/src/components/ApprovalCard.tsx 存在
- [x] frontend/src/components/ApprovalCard.test.tsx 存在
- [x] frontend/src/types/approval.ts 存在
- [x] Commit 2ba9250 已验证存在
- [x] 19 个测试全部通过