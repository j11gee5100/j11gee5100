# Phase 1: Dashboard 看板与失败详情 - Context

**Gathered:** 2026-04-06 (assumptions mode)
**Status:** Ready for planning

<domain>
## Phase Boundary

实现 Dashboard 看板和失败详情页，展示系统健康度、失败分型、修复建议入口。不包含任务创建、审批操作功能。

**需求追溯:**
- DASH-01 ~ DASH-05 (看板展示)
- FAIL-01 ~ FAIL-05 (失败详情)

</domain>

<decisions>
## Implementation Decisions

### 布局风格
- **D-01:** 卡片式布局，非列表或时间线
- **D-02:** 告警条采用三色方案：红色 (critical) / 黄色 (warn) / 绿色 (ok)
- **D-03:** 卡片具有微阴影、圆角 — 现代简洁风格

### 数据刷新策略
- **D-04:** 看板默认 60 秒自动刷新
- **D-05:** 始终显示手动刷新按钮
- **D-06:** 失败详情页默认显示最近 24 小时数据，支持切换 12h/48h

### 信息密度
- **D-07:** 失败分型榜单默认显示 Top 5
- **D-08:** 失败样本表格每页显示 20 行
- **D-09:** 表格支持分页，每页可切换 20/50/100

### 空状态处理
- **D-10:** 无失败时显示"✅ 系统健康，最近 N 小时无失败任务"
- **D-11:** 空状态包含友好图示和刷新按钮

### 错误处理
- **D-12:** 接口失败时显示重试按钮和 trace_id
- **D-13:** Loading 状态使用骨架屏 (Skeleton)

### Claude's Discretion
- 精确的间距和排版数值
- 加载骨架屏的具体样式
- 图表具体颜色值（遵循 Ant Design 默认色板）

</decisions>

<canonical_refs>
## Canonical References

### 看板接口
- `docs/05-interface-spec.md` — 8.5~8.5.7 看板聚合接口定义、响应结构
- `docs/16-web-integration-checklist.md` — 第 1-2 节 Dashboard 和失败详情联调清单
- `docs/17-frontend-page-design-spec.md` — 第 4.1~4.2 节页面规格

### 技术栈
- `docs/adr/ADR-0004-frontend-react-typescript.md` — 前端技术选型决策

</canonical_refs>

<code_context>
## Existing Code Insights

### 后端接口已就绪
- `GET /api/v1/dashboard/overview` — 预聚合告警 + 失败分型 + 修复建议
- `GET /api/v1/dashboard/failures/{failure_code}/detail` — 失败详情 + 样本
- `GET /api/v1/metrics/failures/remediation-template` — 修复建议模板

### 无前端代码
- 当前项目无前端代码，需从零搭建
- 后端接口已完成，可直接联调

### 集成点
- 前端需配置代理转发 `/api/v1/*` 到后端服务

</code_context>

<specifics>
## Specific Ideas

- 参考 Linear 的卡片风格 — 干净、不杂乱
- 告警条固定在顶部，类似 Grafana 告警展示方式
- 失败分型按 count 降序排列，点击跳转详情页

</specifics>

<deferred>
## Deferred Ideas

- 任务创建页跳转逻辑 — Phase 4
- 审批中心页面 — Phase 3
- 模板中心页面 — Phase 2
- 响应式移动端适配 — v2 增强

---
*Phase: 01-dashboard*
*Context gathered: 2026-04-06*
