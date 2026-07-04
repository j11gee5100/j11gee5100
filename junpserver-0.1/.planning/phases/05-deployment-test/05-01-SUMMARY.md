---
phase: 05-deployment-test
plan: 01
type: execute
wave: 1
subsystem: E2E 测试基础设施
tags: [playwright, e2e, testing, infrastructure]
dependency graph:
  requires: []
  provides:
    - E2E 测试框架
    - Playwright 配置
    - 共享测试 fixtures
  affects:
    - frontend/package.json
    - frontend/playwright.config.ts
    - frontend/e2e/
tech-stack:
  added:
    - '@playwright/test@^1.52.0'
    - dotenv@^16.4.0
  patterns:
    - 测试金字塔模型
    - Fixture 模式
    - Page Object 模式（预备）
key-files:
  created:
    - path: frontend/playwright.config.ts
      purpose: Playwright E2E 测试配置
    - path: frontend/e2e/fixtures/test-fixtures.ts
      purpose: 共享测试 fixtures（登录/权限）
    - path: frontend/e2e/global.d.ts
      purpose: E2E 全局类型声明
    - path: frontend/tsconfig.e2e.json
      purpose: E2E 测试 TypeScript 配置
    - path: frontend/e2e/specs/
      purpose: E2E 测试用例目录
    - path: frontend/e2e/utils/
      purpose: E2E 测试工具函数目录
  modified:
    - path: frontend/package.json
      change: 添加 Playwright 依赖和测试脚本
decisions:
  - 选择 Playwright 而非 Cypress：更好的 Ant Design 支持、原生并行执行、跨浏览器测试
  - 配置双浏览器项目（chromium + webkit）：确保 Safari 兼容性
  - fixtures 包含 React Query 配置：禁用测试环境重试和缓存
metrics:
  started_at: "2026-04-08T23:52:00Z"
  completed_at: "2026-04-08T23:57:00Z"
  duration_minutes: 5
  tasks_completed: 3
  files_created: 6
  files_modified: 1
---

# Phase 05 Plan 01: E2E 测试基础设施搭建 Summary

## 一句话说清楚

搭建 Playwright E2E 测试框架，包含依赖安装、配置文件、目录结构和共享 fixtures（登录/权限功能）。

## 完成的工作

### Task 1: 安装 Playwright 依赖

**文件：** `frontend/package.json`

- 添加 `@playwright/test@^1.52.0` 到 devDependencies
- 添加 `dotenv@^16.4.0` 到 devDependencies
- 添加 npm 脚本：
  - `test:e2e`: `playwright test`
  - `test:e2e:ui`: `playwright test --ui`
  - `test:e2e:report`: `playwright show-report`

**提交：** `4e4cae3`

### Task 2: 创建 Playwright 配置和目录结构

**文件：** `frontend/playwright.config.ts`

配置要点：
- `testDir: './e2e/specs'`
- `fullyParallel: true` 并行执行
- `retries: process.env.CI ? 2 : 0`
- `reporter: 'html'`
- `baseURL: 'http://localhost:3000'`
- 双浏览器项目：chromium（Desktop Chrome）+ webkit（Desktop Safari）
- `webServer` 配置：自动启动 Vite dev server

**目录结构：**
```
frontend/e2e/
├── fixtures/     # 共享 fixtures
├── specs/        # 测试用例
└── utils/        # 工具函数
```

**提交：** `0f98247`

### Task 3: 创建测试 fixtures

**文件：** `frontend/e2e/fixtures/test-fixtures.ts`

实现功能：
1. 扩展 Playwright test，添加自定义 fixtures：
   - `authenticatedPage`: 已登录的 Page 实例
   - `testUserData`: 测试数据工厂
2. `loginAsOperator(page)` 函数：
   - 访问 /login 页面
   - 填充用户名和密码
   - 点击登录按钮
   - 等待跳转到 dashboard
3. React Query 配置脚本（禁用重试和缓存）

**导出：**
- `test` 和 `expect` 供其他测试文件使用
- `loginAsOperator`、`loginAsApprover`、`logout` 工具函数

**类型定义：** `frontend/e2e/global.d.ts`
- 定义 `Window.__REACT_QUERY_CONFIG__` 类型

**提交：** `0c9aab8`

## 验证结果

| 标准 | 状态 |
|------|------|
| `npx playwright --version` 返回版本号 | ✅ Version 1.59.1 |
| Playwright 配置存在 | ✅ playwright.config.ts |
| e2e/specs/ 目录存在 | ✅ |
| e2e/fixtures/ 目录存在 | ✅ |
| e2e/utils/ 目录存在 | ✅ |
| test-fixtures.ts 包含 loginAsOperator | ✅ |
| TypeScript 类型检查通过 | ✅ |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - 阻塞问题] 添加 E2E 专用的 TypeScript 配置**

- **发现于：** Task 3
- **问题：** 使用项目默认 tsconfig 进行类型检查时，zod 模块导入报错（esModuleInterop 问题），且 Window 类型未定义 `__REACT_QUERY_CONFIG__`
- **修复：**
  - 创建 `tsconfig.e2e.json` 专门用于 E2E 测试，配置 `esModuleInterop: true` 和 `skipLibCheck: true`
  - 创建 `e2e/global.d.ts` 定义全局类型
- **文件新增：** `frontend/tsconfig.e2e.json`, `frontend/e2e/global.d.ts`

## 威胁标记扫描

本计划未引入新的威胁面：
- E2E 测试目录完全隔离在 `frontend/e2e/`
- 使用独立测试账号（fixture 中定义）
- 配置中已限制测试仅限本地/dev 环境

## 下一步

Wave 0 待创建的测试文件（05-RESEARCH.md 规划）：

| 文件 | 覆盖需求 |
|------|---------|
| `e2e/specs/01-dashboard.spec.ts` | DASH-01~05 |
| `e2e/specs/02-failure-detail.spec.ts` | FAIL-01~05 |
| `e2e/specs/03-template-center.spec.ts` | TMPL-01~05 |
| `e2e/specs/04-policy-governance.spec.ts` | POL-01~06 |
| `e2e/specs/05-approval-center.spec.ts` | APP-01~07 |
| `e2e/specs/06-task-create.spec.ts` | TSK-01~05 |
| `e2e/specs/07-audit.spec.ts` | AUD-01~03 |

## 提交记录

| 提交哈希 | 描述 |
|---------|------|
| 4e4cae3 | feat(05-01): 安装 Playwright E2E 测试依赖 |
| 0f98247 | feat(05-01): 创建 Playwright 配置和 E2E 目录结构 |
| 0c9aab8 | feat(05-01): 创建测试 fixtures 和 E2E 类型配置 |
