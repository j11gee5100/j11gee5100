---
name: OpsPaw 项目
description: AI Agent + JumpServer 自动化运维平台
type: project
---

**项目定位：** OpsPaw = AI 决策能力 + JumpServer 受控执行能力 + 策略/审计闭环能力

**当前阶段：** MVP Phase 1-2（核心后端功能已完成）

**核心能力：**
- JumpServer v3/v4 适配集成（资产/系统用户同步、命令执行、权限检查）
- 任务状态机（pending→running→success/failed）
- 风控审批（风险分级、黑名单拦截、多级审批）
- OpenAPI（任务创建/查询/取消/回调）
- 失败分型与重试机制（15 种失败代码、批量重试审计）

**技术栈：** FastAPI + PostgreSQL + Redis + Celery + Docker Compose

**待完成重点：**
1. Web 前端页面联调（B7 系列）
2. 模板发布流程增强
3. 审批链路完善（转交通知）
4. 故障演练自动化

**Why：** 当前已完成后端核心闭环，需补齐前端界面和增强能力以支持试点

**How to apply：** 后续 GSD 规划应优先推进 Web 联调和试点准备相关工作
