# Phase 4: 任务创建与审计闭环 - Context

**Gathered:** 2026-04-07
**Status:** Ready for planning

<domain>
## Phase Boundary

完成任务创建页，串联模板/审批/审计，形成操作闭环。包含任务创建表单、策略评估集成、审批跳转、审计列表展示。

**不包含:** 审批中心（Phase 3）、模板中心（Phase 2）、Dashboard 看板（Phase 1）

**需求追溯:**
- TSK-01 ~ TSK-05 (任务创建)
- AUD-01 ~ AUD-03 (治理审计)

**注意:** AUD-01~03 审计列表已在 Phase 02 的 GovernanceAuditPage 实现，本 Phase 重点是任务创建页串联审批跳转闭环。

</domain>

<decisions>
## Implementation Decisions

### 任务创建入口
- **D-01:** 支持两种入口：选择现有模板 或 输入自定义命令
- **D-02:** 模板选择使用 SearchSelect 下拉组件，支持搜索过滤
- **D-03:** 选择模板后自动填充 command 字段（只读），选择自定义则手动输入

### 资产与系统用户选择
- **D-04:** 资产选择使用 SearchSelect 组件（资产数量多需搜索）
- **D-05:** 系统用户选择使用 SearchSelect 组件
- **D-06:** 必填字段标记红色星号，校验失败显示错误提示

### 策略评估集成
- **D-07:** 手动触发评估，添加"策略预览"按钮（延续 Phase 02 D-09）
- **D-08:** 评估结果显示在 PolicyEvaluationModal 复用
- **D-09:** 命中策略拦截时禁用提交按钮，显示 block_reason

### 提交后跳转逻辑
- **D-10:** approval_required=true 时跳转审批详情页 `/approvals/{approval_id}`
- **D-11:** approval_required=false 时跳转任务详情页（或显示成功 Toast）
- **D-12:** 高风险任务在提交前显示风险确认弹窗

### 审计列表复用
- **D-13:** AUD-01~03 已在 Phase 02 GovernanceAuditPage 实现
- **D-14:** 本 Phase 验证审计列表完整功能，确保 entity_type=task 筛选正常

### Claude's Discretion
- 表单具体布局和间距
- 风险确认弹窗样式
- 提交成功后的 Toast 提示文案
- 空状态处理（无模板可选时）

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 任务创建接口
- `docs/05-interface-spec.md` §8.5 — 任务创建接口定义
- `docs/17-frontend-page-design-spec.md` §4.3 — 任务创建页设计规格
- `docs/16-web-integration-checklist.md` §任务创建 — 联调清单

### 策略评估
- `docs/05-interface-spec.md` — POST /api/v1/policies/evaluate 接口
- `.planning/phases/02-template-policy/02-CONTEXT.md` D-09~D-11 — 策略评估预览决策

### 审批跳转
- `docs/17-frontend-page-design-spec.md` §4.4/4.5 — 审批详情页设计
- `.planning/phases/03-approval-center/03-CONTEXT.md` — 审批中心设计决策

</canonical_refs>

<code_context>
## Existing Code Insights

### 可复用组件
- `frontend/src/components/PolicyEvaluationModal.tsx` — 策略评估弹窗，直接复用
- `frontend/src/components/RiskBadge.tsx` — 风险等级标签
- `frontend/src/pages/GovernanceAuditPage.tsx` — 审计列表页（AUD-01~03 已实现）

### 可复用 Hooks 模式
- `frontend/src/hooks/useTemplates.ts` — 模板列表查询
- `frontend/src/hooks/usePolicies.ts` — 策略评估 hooks（含 useEvaluatePolicy）

### 可复用类型
- `frontend/src/types/policy.ts` — PolicyEvaluationResponse 包含 approval_required 字段
- `frontend/src/types/template.ts` — CommandTemplate 类型
- `frontend/src/types/api.ts` — PaginatedResponse、ApiError

### 集成点
- 路由: `/tasks/new` — 任务创建页（目前是 PlaceholderPage）
- POST /api/v1/tasks — 创建任务接口
- POST /api/v1/policies/evaluate — 策略评估接口
- GET /api/v1/approvals/{approval_id} — 审批详情接口（跳转目标）

### 后端接口已就绪
- `POST /api/v1/tasks` — 创建任务（返回 task_id + approval_id 若需审批）
- `GET /api/v1/templates/commands` — 模板列表（用于下拉选择）
- `GET /api/v1/assets` — 资产列表（用于资产选择）
- `GET /api/v1/assets/{asset_id}/system-users` — 系统用户列表

</code_context>

<specifics>
## Specific Ideas

- 表单布局参考 Phase 02 的 TemplateFormModal：上分区基础信息，下分区命令/配置
- 提交按钮文案根据风险级别变化："创建任务" / "提交审批"
- 选择模板时显示风险等级标签，帮助用户理解风险

</specifics>

<deferred>
## Deferred Ideas

- 任务详情页（执行状态、日志查看） — v2 增强
- 批量任务创建 — v2 增强
- 任务模板变量替换预览 — v2 增强
- 任务执行历史记录页 — v2 增强

</deferred>

---
*Phase: 04-task-audit*
*Context gathered: 2026-04-07*