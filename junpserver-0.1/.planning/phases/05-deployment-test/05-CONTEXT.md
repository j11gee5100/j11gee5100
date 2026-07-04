# Phase 05: 联调测试与试点部署 - Context

**Gathered:** 2026-04-08
**Status:** Ready for planning

<domain>
## Phase Boundary

完成端到端测试，部署试点环境，实现 v1.1 里程碑闭环。

**范围内：**
- 33 条 v1 需求验证通过
- 关键路径 E2E 测试通过（创建→审批→执行→审计）
- 试点环境部署成功（Linux + Docker Compose）
- 用户操作手册编写完成
- 已知问题清单整理完毕

**范围外：**
- 影子模式、证据卡生成器等 v2 能力
- 移动端适配
- 多 JumpServer source 支持

</domain>

<decisions>
## Implementation Decisions

### 测试范围
- **D-01:** 全需求覆盖测试 — 33 条 v1 需求每条都有对应用例，确保无遗漏
- **D-02:** E2E 测试采用自动化测试脚本（Playwright/Cypress）

### 部署策略
- **D-03:** 容器化交付 — 提供完整 Docker 镜像，包含所有依赖
- **D-04:** 部署到真实产线环境（Linux 服务器）
- **D-05:** 零阻塞性问题 — 所有阻塞性 bug 修复，轻微问题可延后

### 交付物
- **D-06:** 用户培训采用文档自学形式 — 提供图文操作手册
- **D-07:** 已知问题清单使用 Markdown 清单记录（问题/严重等级/状态）

### 测试数据
- **D-08:** 使用现有 mock 数据 — 后端已有的 mock/tripp 数据，无需额外准备

### 成功指标
- **D-09:** 需求 100% 通过 — 所有 33 条 v1 需求验证通过，无 P0/P1 bug

### Claude's Discretion
- 自动化测试框架具体选型（Playwright vs Cypress）
- Docker 镜像构建细节（基础镜像、层优化）
- 操作手册具体章节结构
- Markdown 问题清单的具体模板格式

</decisions>

<canonical_refs>
## Canonical References

### 需求定义
- `.planning/REQUIREMENTS.md` — 33 条 v1 需求详细定义，验收标准
- `.planning/ROADMAP.md` — Phase 05 目标、Success Criteria

### 接口规范
- `docs/05-interface-spec.md` — 后端 OpenAPI 接口文档

### 部署配置
- `docker-compose.yml` — Docker Compose 编排配置
- `Dockerfile` — 镜像构建配置
- `scripts/` — 部署脚本目录

</canonical_refs>

<code_context>
## Existing Code Insights

### 可复用资产
- 后端已完成：JumpServer 适配、任务状态机、风控审批、OpenAPI 全套接口
- 前端已完成：Phase 01-04 的 8 个核心页面（Dashboard、失败详情、模板中心、策略治理、审批中心、任务创建、治理审计）

### 既定模式
- 前端技术栈：React + TypeScript + Vite + TanStack Query + Ant Design
- 后端技术栈：Python FastAPI + JumpServer v4 API

### 集成点
- 前端通过 TanStack Query 调用后端 OpenAPI
- 后端通过 JumpServer API 执行任务
- Docker Compose 编排前端（Vite dev server / nginx）+ 后端（FastAPI）+ JumpServer

</code_context>

<specifics>
## Specific Ideas

- "33 条 v1 需求每条都要验证通过" — 用户强调全覆盖
- "零阻塞性问题" — 阻塞性 bug 必须修复，轻微问题可延后
- "文档自学" — 用户偏向文档化交付，而非现场培训

</specifics>

<deferred>
## Deferred Ideas

### v2 能力（试点后再说）
- 影子模式控制台（可视化模拟执行结果）
- 证据卡生成器（AI 可解释性）
- 多 JumpServer source 支持（平台化能力）
- 移动端适配（优先保障桌面端体验）
- 自动复盘报告（规模化能力）

### Reviewed Todos (not folded)
- 无 — 讨论均聚焦 Phase 05 范围内

</deferred>

---

*Phase: 05-deployment-test*
*Context gathered: 2026-04-08*
