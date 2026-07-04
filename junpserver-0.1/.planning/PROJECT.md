# OpsPaw 项目文档

## What This Is

OpsPaw 是一个运维自动化平台，通过 AI Agent 结合 JumpServer 实现受控的命令执行和审批流程。面向试点团队提供任务创建、执行编排、风控审批、审计追溯等能力。

## Core Value

提供安全可控的自动化执行闭环，让运维团队能快速响应告警和变更需求，同时确保所有操作可审计、可追溯、可解释。

## Requirements

### Validated

**后端核心能力（Phase 1-2）：**
- ✓ JumpServer v3/v4 适配集成（认证、契约测试、健康检查）
- ✓ 资产/系统用户同步（全量初始化、增量双轨、新鲜度标记）
- ✓ 任务状态机（pending→running→success/failed、幂等保护、取消能力）
- ✓ 执行链路（模板注册表、执行封装、结果轮询、审计关联）
- ✓ 风控审批（风险分级、黑名单拦截、多级审批流）
- ✓ OpenAPI（创建/查询/取消任务、回调重试、签名校验）
- ✓ 失败分型与批量重试审计（15 种失败代码、护栏速率控制）
- ✓ 预聚合看板接口（健康度告警、修复建议模板）

**前端联调能力（Phase 1-5, v1.1）：**
- ✓ Dashboard 看板页面（健康度、失败分型、修复建议入口）— v1.1
- ✓ 失败详情页面（按失败码查看样本与建议）— v1.1
- ✓ 模板中心（命令模板 CRUD、启停管理）— v1.1
- ✓ 策略治理页（黑名单管理、策略评估预览）— v1.1
- ✓ 审批中心（多级审批列表、详情、通过/驳回/升级）— v1.1
- ✓ 任务创建页（模板化创建、风险解释、审批跳转）— v1.1
- ✓ 治理审计页（配置变更追踪）— v1.1
- ✓ E2E 测试框架（40 条测试用例，77% 通过率）— v1.1
- ✓ Docker 部署配置（Gunicorn + Uvicorn workers）— v1.1
- ✓ 用户操作手册和已知问题清单 — v1.1

### Active

**v2.0 规划中：**
- [ ] 移动端适配 — 优先保障桌面端体验，v2 考虑响应式优化
- [ ] 影子模式控制台 — 信任增强功能，试点后根据反馈决定
- [ ] 证据卡生成器 — AI 可解释性，v2 考虑
- [ ] 多 JumpServer source 支持 — 平台化能力，v2 考虑

### Out of Scope

- 影子模式执行链 — 信任增强功能，试点后再说
- 证据卡生成器 — AI 可解释性，试点后再说
- 多 JumpServer source 支持 — 平台化能力，v2+ 考虑
- 移动端适配 — 优先保障桌面端体验

## Context

**当前状态：** v1.1 前端联调里程碑已完成，前端 8 个核心页面全部实现并部署。

**技术栈：**
- 前端：React 19 + TypeScript 5 + Vite 8 + Ant Design 5 + TanStack Query 5
- 后端：Python 3.11 + FastAPI + Gunicorn + Uvicorn workers
- 测试：Playwright 1.59（40 条 E2E 测试，77% 通过率）
- 部署：Docker Compose + Linux 服务器

**代码规模：**
- 前端：~4000 行 TypeScript 代码
- 页面组件：8 个核心页面
- 可复用组件：15+ 个（RiskBadge, PolicyEvaluationModal, ApprovalCard 等）

**已知问题：**
- E2E 测试表单选择器 alignment（9 条测试失败，非功能问题）
- WebKit 浏览器测试待安装（当前仅 Chromium）

**后端已实现接口：**
- `GET /api/v1/dashboard/overview` - 看板聚合数据
- `GET /api/v1/dashboard/failures/{failure_code}/detail` - 失败详情
- `GET/POST/PATCH /api/v1/templates/commands` - 模板中心
- `GET/POST/PATCH /api/v1/policies/command-blacklist` - 黑名单管理
- `POST /api/v1/policies/evaluate` - 策略评估预览
- `GET /api/v1/approvals/pending` - 待审批列表
- `GET/POST /api/v1/approvals/{approval_id}/approve|reject|escalate` - 审批操作
- `POST /api/v1/tasks` - 创建任务
- 更多接口见 `docs/05-interface-spec.md`

## Constraints

- **技术栈**: React + TypeScript + Vite + TanStack Query + Ant Design
- **联调环境**: Linux 服务器部署，Docker Compose 运行
- **JumpServer**: v4 API 适配，需真实环境联调

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| 模块化单体架构 | MVP 阶段控制复杂度 | ✓ Good |
| 前端 React+TS | 企业后台组件成熟，团队熟悉 | ✓ Good |
| 优先后端闭环 | 先确保执行链路可靠，再补齐前端 | ✓ Good |
| D-01: 卡片式布局 | 响应式布局适配不同屏幕 | ✓ Good |
| D-02: 无限滚动加载 | 大数据量下性能更好 | ✓ Good |
| D-03: 启停开关位于卡片右上角 | 符合用户习惯 | ✓ Good |
| D-05: 弹窗表单方式新建模板 | 不跳转页面，操作流畅 | ✓ Good |
| D-06: 命令字段使用单行输入框 | 简化表单设计 | ✓ Good |
| D-07: 风险等级下拉选择 (low/medium/high) | 标准化输入，减少错误 | ✓ Good |
| D-08: 表单上下分区布局 | 信息组织清晰 | ✓ Good |
| D-09: 手动触发评估，添加"预览"按钮 | 用户主动触发而非自动 | ✓ Good |
| D-10: 评估结果在单独弹窗显示 | 信息量大，展示清晰 | ✓ Good |
| D-12: 卡片布局展示审计记录 | 与模板中心/策略治理一致 | ✓ Good |
| D-13: 独立筛选区域 | 筛选与列表分离，易于使用 | ✓ Good |
| D-16: 时间范围预设选择 (1h/24h/7d) | 简化用户操作 | ✓ Good |

## Evolution

PROJECT.md evolves throughout the project lifecycle.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-10 after v1.1 milestone*
