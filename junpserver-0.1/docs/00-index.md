# OpsPaw 文档索引

本目录用于沉淀 `AI Agent + JumpServer` 自动化运维方案，面向立项评审与实施落地。

## 文档清单

- `01-prd.md`：产品目标、范围、角色、验收标准（v1.2 深化版）
- `02-architecture.md`：系统架构、模块职责、执行链路、部署建议
- `03-skill-dsl.md`：Skill 规范、DSL 结构、示例、发布流程
- `04-api-data-design.md`：核心 API 与数据模型设计
- `05-interface-spec.md`：项目接口文档（JumpServer 接口 + Adapter 接口）
- `06-product-optimization.md`：创意点、隐性需求、风险点与优化建议
- `07-backlog-roadmap.md`：研发 backlog、优先级与阶段路线图
- `08-detailed-architecture.md`：详细架构设计（模块边界、链路、状态机、降级）
- `09-tech-selection.md`：技术选型 ADR 集入口页
- `10-jumpserver-pending-runbook.md`：JumpServer celery `PENDING` 根因排障手册
- `11-jumpserver-pending-diagnosis-2026-04-02.md`：本轮联调诊断报告（含权限排除证据）
- `12-jumpserver-v4-sync-interfaces.md`：JumpServer v4 同步接口映射与增量策略说明
- `13-jumpserver-v4-execution-diagnosis-2026-04-02.md`：新版 v4 执行诊断（权限与连通性结论）
- `14-jumpserver-v4-execution-diagnosis-2026-04-03.md`：新版 v4 执行诊断（`PENDING` 复检与失败分型）
- `15-backlog-progress-2026-04-03.md`：backlog 任务清单进度快照（done/partial/todo）
- `16-web-integration-checklist.md`：Web 联调清单（看板/模板/策略/审批多级）
- `17-frontend-page-design-spec.md`：前端页面设计规格（路由、页面布局、组件、交互、验收）
- `18-ai-inference-env-requirements.md`：AI 推理环境安装包编排平台用户需求文档
- `19-ai-inference-env-product-design.md`：AI 推理环境安装包编排平台产品设计文档
- `20-ai-inference-env-architecture.md`：AI 推理环境安装包编排平台架构设计文档
- `21-ai-inference-env-database-design.md`：AI 推理环境安装包编排平台数据库设计文档
- `22-ai-inference-env-api-integration.md`：AI 推理环境安装包编排平台接口与开放集成设计
- `23-delivery-package-workflow-design.md`：离线交付包现场工作流设计
- `24-mvp-skeleton-module-audit.md`：MVP 架子版模块设计审计与最小开发顺序
- `25-delivery-bundle-page-audit.md`：交付包编辑编排页面审计与最小改造方案
- `26-mcp-service-design.md`：面向 Agent 调用的 MCP 服务设计（环境包上传、资产登记、交付包编排）
- `27-mcp-design-audit-and-detailed-design.md`：MCP 服务设计审计与详细设计（借鉴开源 MCP Server）
- `28-mcp-implementation-notes.md`：MCP 服务第一版实现说明与验证记录

## 原型

- `prototypes/environment-package-prototype.html`：AI 推理环境安装包编排平台静态原型
- `prototypes/environment-package-asset-prototype.html`：AI 推理环境最小安装包资产管理静态原型
- `prototypes/package-asset-ant-prototype.html`：按 DESIGN.md 重做的基础安装包资产管理原型
- `prototypes/package-assets/README.md`：基础安装包资产管理 4 张拆分原型说明

## 版本信息

- 当前版本：`v0.1`
- 更新日期：`2026-06-27`
- 状态：可用于方案评审与 PoC 启动

## 一句话定位

`OpsPaw = AI 决策能力 + JumpServer 受控执行能力 + 策略/审计闭环能力`
