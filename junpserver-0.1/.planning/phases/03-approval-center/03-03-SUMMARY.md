---
phase: 03-approval-center
plan: 03
subsystem: frontend/pages-components
tags: [approval, list-page, drawer, timeline, tdd, react, ant-design]
requires:
  - 03-01 (Approval types and hooks)
  - 03-02 (ApprovalCard component)
provides:
  - ApprovalListPage with L1/L2 tab switching
  - ApprovalDrawer for approval details and actions
  - ApprovalTimeline for action history
  - Route connection to /approvals
affects:
  - /approvals route
tech-stack:
  added:
    - ApprovalListPage with Tabs component
    - ApprovalDrawer with Drawer, Descriptions, TextArea
    - ApprovalTimeline with Timeline component
  patterns:
    - TDD approach for all components
    - 409 conflict handling with auto-refresh
    - Mutation with callbacks and invalidate
key-files:
  created:
    - frontend/src/pages/ApprovalListPage.tsx
    - frontend/src/pages/ApprovalListPage.test.tsx
    - frontend/src/components/ApprovalDrawer.tsx
    - frontend/src/components/ApprovalDrawer.test.tsx
    - frontend/src/components/ApprovalTimeline.tsx
    - frontend/src/components/ApprovalTimeline.test.tsx
  modified:
    - frontend/src/App.tsx
decisions:
  - 使用 TDD 方法实现所有组件（39 个测试）
  - 驳回操作必须填写原因
  - 升级按钮在 current_level >= max_level 时禁用
  - approved/rejected/expired 状态禁用所有操作按钮
  - 409 冲突时自动刷新列表
metrics:
  duration: ~25 minutes
  tasks_completed: 4
  files_created: 6
  files_modified: 1
  tests_added: 39
completed_at: 2026-04-08T09:21:00Z
---

# Phase 03 Plan 03: 审批列表页面与详情抽屉

## 一句话总结

创建审批列表页面、详情抽屉和时间线组件，实现完整的审批工作流交互，支持 L1/L2 Tab 切换、通过/驳回/升级操作，以及 409 冲突自动处理。

## 完成的任务

### Task 1: 实现 ApprovalListPage 审批列表页面

创建 `frontend/src/pages/ApprovalListPage.tsx`，实现 D-02/D-10：
- L1/L2 Tab 切换按层级筛选
- Grid 响应式布局展示审批卡片
- 通过/驳回快速操作按钮
- 点击卡片打开详情抽屉
- 409 冲突 Toast 提示自动刷新
- Loading/Empty/Error 状态处理

**Commit:** 5dca8e3

### Task 2: 实现 ApprovalDrawer 审批详情抽屉

创建 `frontend/src/components/ApprovalDrawer.tsx`，实现 D-05/D-06/D-07/D-08/D-09/D-11/D-12：
- 抽屉宽度 520px
- 基础信息卡（Descriptions）
- 决策区（通过/驳回/升级按钮 + 原因输入）
- TextArea maxLength=500 showCount
- 驳回必填原因验证
- 升级按钮在 max_level 时禁用
- approved/rejected/expired 状态禁用操作
- 嵌套 ApprovalTimeline 组件

**Commit:** ee3812f

### Task 3: 实现 ApprovalTimeline 审批动作时间线

创建 `frontend/src/components/ApprovalTimeline.tsx`，实现 D-07：
- 时间线组件渲染 actions 数组
- 显示动作类型、操作者、时间、备注
- 颜色区分动作类型（green/red/gold/blue）
- 空状态友好提示

**Commit:** 8d9a397

### Task 4: 更新路由配置连接 ApprovalListPage

更新 `frontend/src/App.tsx`：
- 导入 ApprovalListPage 组件
- /approvals 路由使用 ApprovalListPage 元素
- 保留 /approvals/:approvalId 占位符（详情在抽屉中展示）

**Commit:** 1510296

## 技术要点

### L1/L2 Tab 切换

```typescript
const tabItems = [
  { key: '1', label: `L1 审批 (${currentLevel === 1 ? approvals?.length ?? 0 : 0})` },
  { key: '2', label: `L2 审批 (${currentLevel === 2 ? approvals?.length ?? 0 : 0})` },
]
```

### 按钮禁用逻辑

```typescript
const isOperationDisabled = currentApproval?.status !== 'pending'
const cannotEscalate = (currentApproval?.current_level ?? 0) >= (currentApproval?.max_level ?? 0) || isOperationDisabled
```

### 409 冲突处理

```typescript
onError: (err: any) => {
  if (err?.response?.status === 409) {
    message.warning('审批状态已变更')
    refetch()
  }
}
```

### 时间线颜色映射

```typescript
const colorMap: Record<ApprovalActionType, string> = {
  approved: 'green',
  rejected: 'red',
  escalated: 'gold',
  created: 'blue',
}
```

## Deviations from Plan

### [Rule 1 - Bug] 测试适配 Ant Design 中文字符空格

- **发现时间:** Task 1, Task 2 绿色阶段
- **问题:** Ant Design 渲染中文按钮名称时在字符间插入空格（"通 过" 而非 "通过"）
- **修复:** 修改测试使用正则匹配 `/\s*` 适应空格
- **文件:** ApprovalListPage.test.tsx, ApprovalDrawer.test.tsx
- **Commit:** 包含在相应任务提交中

### [Rule 1 - Bug] Mutation mock 缺少 isPending 属性

- **发现时间:** Task 2 绿色阶段
- **问题:** 测试 mock 的 mutation 对象缺少 isPending 属性导致渲染失败
- **修复:** 在测试的 beforeEach 中添加完整的 mutation mock
- **文件:** ApprovalDrawer.test.tsx
- **Commit:** ee3812f

### [Rule 3 - Blocking Issue] 组件依赖占位符

- **发现时间:** Task 1, Task 2 开始时
- **问题:** ApprovalDrawer 和 ApprovalTimeline 尚未实现导致导入失败
- **修复:** 先创建 placeholder 组件以通过依赖解析，然后在相应任务中完整实现
- **文件:** ApprovalDrawer.tsx, ApprovalTimeline.tsx
- **Commit:** 包含在相应任务提交中

## 验收标准达成

- [x] frontend/src/pages/ApprovalListPage.tsx 存在且导出 ApprovalListPage 函数
- [x] frontend/src/components/ApprovalDrawer.tsx 存在且导出 ApprovalDrawer 函数
- [x] frontend/src/components/ApprovalTimeline.tsx 存在且导出 ApprovalTimeline 函数
- [x] L1/L2 Tab 切换实现（14 个测试通过）
- [x] 详情抽屉包含基础信息、决策区、时间线（15 个测试通过）
- [x] 驳回必填原因，其他可选
- [x] 原因最长 500 字符
- [x] 升级按钮在 max_level 时禁用
- [x] approved/rejected/expired 状态禁用操作
- [x] 409 冲突 Toast 提示 + 刷新
- [x] 路由 /approvals 连接 ApprovalListPage
- [x] 所有 163 个测试通过
- [x] 构建成功

## Threat Model Consideration

根据计划中的 threat_model：
- T-03-03-01 (Information Disclosure): 原因文本传输到后端，后端负责存储和访问控制 — 已 accept
- T-03-03-02 (Elevation of Privilege): 升级按钮在 max_level 时禁用，防止无限升级 — 已 mitigate
- T-03-03-03 (Spoofing): 409 响应时刷新列表，防止基于过期数据操作 — 已 mitigate

## Next Steps

Plan 03-04 和后续计划将基于此组件创建：
- 任务创建页（模板化创建 + 审批跳转）
- 任务详情页
- Dashboard 看板页面

---

**开始时间:** 2026-04-08T08:57:00Z
**结束时间:** 2026-04-08T09:21:00Z
**持续时间:** ~24 分钟

## Self-Check: PASSED

- [x] frontend/src/pages/ApprovalListPage.tsx 存在（179 行）
- [x] frontend/src/components/ApprovalDrawer.tsx 存在（221 行）
- [x] frontend/src/components/ApprovalTimeline.tsx 存在（78 行）
- [x] Commits 5dca8e3, ee3812f, 8d9a397, 1510296 已验证存在
- [x] 所有 163 个测试通过
- [x] 构建成功