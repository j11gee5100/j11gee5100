# Phase 03: 审批中心（多级） - Context

**Gathered:** 2026-04-07
**Status:** Ready for planning

<domain>
## Phase Boundary

按层级查看待审批任务，完成通过/驳回/升级操作。包含待审批列表、审批详情、时间线展示、审批动作执行。

**不包含:** 任务创建页（Phase 4）、模板中心（Phase 2）、Dashboard 看板（Phase 1）

**需求追溯:**
- APP-01 ~ APP-07 (审批中心)

</domain>

<decisions>
## Implementation Decisions

### 审批列表布局
- **D-01:** 卡片式布局，延续 Phase 01/02 设计风格
- **D-02:** L1/L2/... Tab 切换，按 current_level 筛选显示
- **D-03:** 卡片底部显示通过/驳回按钮（快速操作入口）
- **D-04:** 卡片显示超时状态（剩余时间/已超时标签）

### 审批详情展示
- **D-05:** 右侧抽屉/弹窗展示详情，不跳转独立页面
- **D-06:** 抽屉内包含基础信息卡、决策区、时间线
- **D-07:** 时间线内嵌于详情区块，使用 Ant Design Timeline 组件

### 审批操作交互
- **D-08:** 驳回操作必填原因，通过和升级可选
- **D-09:** 原因通过 TextArea 输入，限制 500 字符
- **D-10:** 409 冲突时显示 Toast 提示并自动刷新列表

### 操作约束
- **D-11:** 已 approved/rejected/expired 状态禁用操作按钮
- **D-12:** current_level = max_level 时禁用升级按钮
- **D-13:** 超时项目标记为 expired，卡片显示超时标签

### Claude's Discretion
- 卡片具体间距和排版数值
- 超时标签颜色和图标选择
- 升级确认弹窗样式
- 时间线节点颜色（按操作类型区分）

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 审批接口定义
- `docs/05-interface-spec.md` §8.5.7 — 高风险任务审批流、审批查询接口、审批动作接口
- `docs/17-frontend-page-design-spec.md` §4.4/4.5 — 审批列表和详情页设计规格
- `docs/16-web-integration-checklist.md` §审批中心 — 联调清单

### 前端技术栈
- `docs/adr/ADR-0004-frontend-react-typescript.md` — 前端技术选型决策

### Phase 02 设计延续
- `.planning/phases/02-template-policy/02-CONTEXT.md` — 卡片式布局、弹窗交互模式

</canonical_refs>

<code_context>
## Existing Code Insights

### 可复用组件模式
- `frontend/src/components/TemplateCard.tsx` — 卡片布局参考（hoverable、cursor:pointer、操作按钮位置）
- `frontend/src/components/RiskBadge.tsx` — 风险等级标签，可直接复用
- `frontend/src/App.tsx` — 已有路由配置，需添加审批中心路由

### 可复用 Hooks 模式
- `frontend/src/hooks/useTemplates.ts` — TanStack Query hooks 参考模式
- `frontend/src/hooks/useGovernance.ts` — 审计日志 hooks，可参考分页查询模式

### 可复用类型
- `frontend/src/types/api.ts` — PaginatedResponse、PaginationParams
- `frontend/src/types/policy.ts` — PolicyEvaluationResponse 包含 approval_required 字段

### 集成点
- 路由: `/approvals` — 审批列表页
- L1/L2 Tab: 通过 `current_level` 查询参数调用 `GET /api/v1/approvals/pending?current_level={n}`
- 抽屉组件: Ant Design Drawer，宽度 520px
- Toast: Ant Design message.success() / message.error()

### 后端接口已就绪
- `GET /api/v1/approvals/pending?current_level={n}` — 待审批列表
- `GET /api/v1/approvals/{approval_id}` — 审批详情（含 actions 时间线）
- `POST /api/v1/approvals/{approval_id}/approve` — 通过
- `POST /api/v1/approvals/{approval_id}/reject` — 驳回
- `POST /api/v1/approvals/{approval_id}/escalate` — 升级

</code_context>

<specifics>
## Specific Ideas

- 参考 Linear 的审批列表设计：卡片紧凑、操作便捷
- Tab 切换类似 GitHub PR 的 review 状态过滤
- 抽屉参考 Ant Design Pro 的详情抽屉样式

</specifics>

<deferred>
## Deferred Ideas

- 批量审批操作（批量通过/驳回） — v2 增强
- 审批代理授权（休假期间代理审批） — v2 增强
- 审批提醒通知（邮件/企微推送） — v2 增强

</deferred>

---

*Phase: 03-approval-center*
*Context gathered: 2026-04-07*