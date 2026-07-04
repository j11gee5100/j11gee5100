# Phase 05: 联调测试与试点部署 - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-08
**Phase:** 05-deployment-test
**Areas discussed:** 测试范围，部署方式，验收标准，部署目标，用户培训，问题管理，E2E 测试，测试数据，成功指标

---

## 测试范围

| Option | Description | Selected |
|--------|-------------|----------|
| 仅核心路径 E2E | 聚焦 3-5 条最关键路径，快速验证闭环 | |
| 全需求覆盖测试 | 33 条 v1 需求每条都有对应用例，确保无遗漏 | ✓ |
| 分层测试策略 | 核心路径 E2E + 关键功能冒烟 + UI 探索性测试组合 | |

**User's choice:** 全需求覆盖测试

---

## 部署方式

| Option | Description | Selected |
|--------|-------------|----------|
| 手动部署 | 文档化部署步骤，手动执行，灵活性高 | |
| 脚本自动化 | 编写部署脚本（shell/docker-compose），一键部署 | |
| 容器化交付 | 提供完整 Docker 镜像，包含所有依赖 | ✓ |

**User's choice:** 容器化交付

---

## 验收标准

| Option | Description | Selected |
|--------|-------------|----------|
| 功能可用即可 | 核心功能能跑通，允许已知小问题存在 | |
| 零阻塞性问题 | 所有阻塞性 bug 修复，轻微问题可延后 | ✓ |
| 用户签字确认 | 试点团队实际操作并签字确认验收 | |

**User's choice:** 零阻塞性问题

---

## 部署目标

| Option | Description | Selected |
|--------|-------------|----------|
| 本地测试环境 | 在本地/开发环境完成部署验证 | |
| 真实产线环境 | 部署到真实的 Linux 服务器（用户实际使用环境） | ✓ |
| 云端测试环境 | 使用云服务器（如阿里云/腾讯云）模拟产线环境 | |

**User's choice:** 真实产线环境

---

## 用户培训

| Option | Description | Selected |
|--------|-------------|----------|
| 文档自学 | 提供图文操作手册，用户自学 | ✓ |
| 现场培训会 | 1-2 小时集中演示 + 答疑 + 实操指导 | |
| 视频 + 文档 | 录制操作视频 + 文档，用户随时查阅 | |

**User's choice:** 文档自学

---

## 问题管理

| Option | Description | Selected |
|--------|-------------|----------|
| Markdown 清单 | 简单的 Markdown 清单，记录问题/严重等级/状态 | ✓ |
| Issue 跟踪系统 | 使用 GitHub Issues 或 Linear 跟踪问题 | |
| 在线协作文档 | 使用语雀/飞书等在线协作文档记录问题 | |

**User's choice:** Markdown 清单

---

## E2E 测试

| Option | Description | Selected |
|--------|-------------|----------|
| 自动化测试脚本 | 使用 Playwright/Cypress 编写自动化 E2E 脚本 | ✓ |
| 人工手动测试 | 人工按测试用例手动执行，记录结果 | |
| 混合测试策略 | 核心路径自动化 + 边缘场景人工测试 | |

**User's choice:** 自动化测试脚本

---

## 测试数据

| Option | Description | Selected |
|--------|-------------|----------|
| 使用现有 mock 数据 | 使用后端已有的 mock/tripp 数据，无需额外准备 | ✓ |
| 准备专用测试数据 | 准备专门的测试数据集（资产、用户、模板） | |
| 连接真实环境数据 | 连接真实 JumpServer 环境使用真实数据 | |

**User's choice:** 使用现有 mock 数据

---

## 成功指标

| Option | Description | Selected |
|--------|-------------|----------|
| 需求 100% 通过 | 所有 33 条 v1 需求验证通过，无 P0/P1 bug | ✓ |
| 性能指标达标 | 看板 1s 加载、列表分页流畅等性能达标 | |
| 用户能独立使用 | 试点团队能独立完成任务创建到执行的全流程 | |

**User's choice:** 需求 100% 通过

---

## Claude's Discretion

以下领域用户表示"生成 CONTEXT.md"即可，具体实现细节由 Claude 决定：
- 自动化测试框架具体选型（Playwright vs Cypress）
- Docker 镜像构建细节（基础镜像、层优化）
- 操作手册具体章节结构
- Markdown 问题清单的具体模板格式

---

*Discussion completed: 2026-04-08*
