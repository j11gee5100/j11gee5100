# Phase 2: 模板中心与策略治理 - Context

**Gathered:** 2026-04-07
**Status:** Ready for planning

<domain>
## Phase Boundary

管理命令模板和黑名单规则，提交前可预览策略评估结果。包含模板 CRUD、启停操作、黑名单管理、策略评估预览、审计日志查询。

**不包含:** 任务创建页（Phase 4）、审批中心（Phase 3）、Dashboard 看板（Phase 1）

**需求追溯:**
- TMPL-01 ~ TMPL-05 (模板中心)
- POL-01 ~ POL-06 (策略治理)

</domain>

<decisions>
## Implementation Decisions

### 模板列表布局
- **D-01:** 卡片式布局，延续 Phase 1 设计风格
- **D-02:** 无限滚动加载（而非传统分页）
- **D-03:** 启停开关位于卡片右上角，操作直观
- **D-04:** 每张卡片展示 template_id/name/risk_level/enabled 四个核心字段

### 模板创建流程
- **D-05:** 弹窗表单方式新建模板，不跳转独立页面
- **D-06:** 命令字段使用单行输入框（Input）
- **D-07:** 风险等级使用下拉选择 (low/medium/high)
- **D-08:** 表单采用上下分区布局：上半区基础信息（id/name/risk_level），下半区命令区域

### 策略评估预览
- **D-09:** 手动触发评估，添加"预览"按钮而非实时触发
- **D-10:** 评估结果在单独弹窗显示，不占用主界面空间
- **D-11:** 被拦截时在弹窗内显示 block_reason 和 matched_rules

### 审计日志展示
- **D-12:** 卡片布局展示审计记录
- **D-13:** 独立筛选区域，与卡片列表分离
- **D-14:** 支持 entity_type/action/operator_id/time_range 筛选
- **D-15:** JSON 详情通过弹窗查看，不卡片内展开
- **D-16:** 时间范围使用预设选择 (1h/24h/7d)

### Claude's Discretion
- 卡片精确间距和排版数值
- 风险等级标签颜色（建议延续 Phase 1 三色方案：low=绿、medium=黄、high=红）
- 骨架屏具体样式
- 空状态友好提示文案

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 后端接口定义
- `docs/05-interface-spec.md` — 模板中心、策略治理、审计接口定义
- `docs/16-web-integration-checklist.md` — 联调清单模板中心与策略治理章节
- `docs/17-frontend-page-design-spec.md` — 页面规格模板中心与策略治理章节

### 前端技术栈
- `docs/adr/ADR-0004-frontend-react-typescript.md` — 前端技术选型决策

### Phase 1 设计延续
- `.planning/phases/01-dashboard/01-CONTEXT.md` — 卡片式布局、骨架屏、空状态处理决策

</canonical_refs>

<code_context>
## Existing Code Insights

### 前端基础设施
- `frontend/src/api/client.ts` — axios client，baseURL = '/api/v1'
- `frontend/src/types/api.ts` — ApiError/PaginationParams/PaginatedResponse 通用类型
- `frontend/src/utils/formatters.ts` — dayjs 时间格式化函数

### 空目录待填充
- `frontend/src/components/` — 待创建 TemplateCard/PolicyCard/AuditCard 等
- `frontend/src/pages/` — 待创建模板中心、策略治理页面
- `frontend/src/hooks/` — 待创建 TanStack Query hooks

### 后端接口已就绪
- `GET/POST/PATCH /api/v1/templates/commands` — 模板 CRUD
- `GET/POST/PATCH /api/v1/policies/command-blacklist` — 黑名单管理
- `POST /api/v1/policies/evaluate` — 策略评估预览
- `GET /api/v1/governance/audits` — 审计日志查询

</code_context>

<specifics>
## Specific Ideas

- 延续 Phase 1 的卡片风格（参考 Linear 的 issue cards）
- 启停开关在卡片右上角，类似 Linear issue cards 的操作按钮布局
- 策略预览弹窗内清晰显示匹配规则列表

</specifics>

<deferred>
## Deferred Ideas

- 任务创建页跳转审批详情 — Phase 4
- 审批中心页面 — Phase 3
- 批量模板操作（批量启用/停用） — v2 增强
- 模板版本管理 — v2 增强

</deferred>

---
*Phase: 02-template-policy*
*Context gathered: 2026-04-07*