# Phase 05: 联调测试与试点部署 - Research

**Researched:** 2026-04-08
**Domain:** E2E 测试框架选型、Docker 生产部署、试点环境交付
**Confidence:** HIGH

## Summary

本阶段研究聚焦三个核心领域：(1) E2E 测试框架选型与测试架构设计，(2) Docker 生产部署方案优化，(3) 试点环境交付物规范。基于项目技术栈（React + TypeScript + Vite + TanStack Query + Ant Design + FastAPI）和现有基础设施分析，形成明确的实施路径。

**Primary recommendation:** 采用 Playwright 进行 E2E 测试（优于 Cypress 的复杂 UI 处理能力），优化现有 Dockerfile 使用 Gunicorn+Uvicorn 工作模式，编写标准化用户操作手册和部署检查清单。

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** 全需求覆盖测试 — 33 条 v1 需求每条都有对应用例，确保无遗漏
- **D-02:** E2E 测试采用自动化测试脚本（Playwright/Cypress）
- **D-03:** 容器化交付 — 提供完整 Docker 镜像，包含所有依赖
- **D-04:** 部署到真实产线环境（Linux 服务器）
- **D-05:** 零阻塞性问题 — 所有阻塞性 bug 修复，轻微问题可延后
- **D-06:** 用户培训采用文档自学形式 — 提供图文操作手册
- **D-07:** 已知问题清单使用 Markdown 清单记录（问题/严重等级/状态）
- **D-08:** 使用现有 mock 数据 — 后端已有的 mock/tripp 数据，无需额外准备
- **D-09:** 需求 100% 通过 — 所有 33 条 v1 需求验证通过，无 P0/P1 bug

### Claude's Discretion
- 自动化测试框架具体选型（Playwright vs Cypress）
- Docker 镜像构建细节（基础镜像、层优化）
- 操作手册具体章节结构
- Markdown 问题清单的具体模板格式

### Deferred Ideas (OUT OF SCOPE)
- 影子模式控制台（可视化模拟执行结果）
- 证据卡生成器（AI 可解释性）
- 多 JumpServer source 支持（平台化能力）
- 移动端适配（优先保障桌面端体验）
- 自动复盘报告（规模化能力）

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DASH-01~05 | Dashboard 看板需求 | E2E 测试覆盖页面加载、告警条、失败榜单、跳转、修复建议 |
| FAIL-01~05 | 失败详情页需求 | E2E 测试覆盖详情页加载、修复步骤、样本表格、筛选 |
| TMPL-01~05 | 模板中心需求 | E2E 测试覆盖列表、新建、启停、表单、策略评估 |
| POL-01~06 | 策略治理需求 | E2E 测试覆盖黑名单、规则管理、实时评估、审计 |
| APP-01~07 | 审批中心需求 | E2E 测试覆盖待审批列表、L1/L2 切换、详情、通过/驳回/升级 |
| TSK-01~05 | 任务创建需求 | E2E 测试覆盖模板选择、命令输入、策略预览、审批跳转 |
| AUD-01~03 | 治理审计需求 | E2E 测试覆盖审计列表、筛选、JSON 详情 |

## Standard Stack

### E2E 测试框架

| 框架 | 版本 | 目的 | 为什么选择 |
|------|------|------|-----------|
| [Playwright](https://playwright.dev) | ^1.52.0 (2026 最新) | E2E 端到端测试 | 对 Ant Design 复杂 DOM 结构支持更好、原生并行执行、跨浏览器（包括 Safari/WebKit）、速度比 Cypress 快 2x [VERIFIED: npm trends & Geekflare 2026 对比] |
| @playwright/test | ^1.52.0 | 测试运行器 | 内置 assertion、并行、HTML 报告、trace viewer |
| dotenv | ^16.4.0 | 环境变量管理 | 测试环境配置隔离 |

### 单元测试框架（现有）

| 框架 | 版本 | 目的 | 为什么继续用 |
|------|------|------|-----------|
| Vitest | ^4.1.2 | 单元/组件测试 | 项目已配置，与 Vite 原生集成，速度快 [VERIFIED: frontend/package.json] |
| @testing-library/react | ^16.3.2 | React 组件测试 | 业界标准，支持 React 19 [VERIFIED: frontend/package.json] |
| @testing-library/jest-dom | ^6.9.1 | DOM assertion | 提供语义化断言匹配器 |

### 后端测试框架（现有）

| 框架 | 版本 | 目的 | 为什么继续用 |
|------|------|------|-----------|
| pytest | 8.4.1 | Python 单元测试 | 项目已配置，fixtures 完善 [VERIFIED: requirements.txt] |
| sqlalchemy | 2.0.43 | 数据库测试 | 测试使用 SQLite 内存数据库 [VERIFIED: tests/conftest.py] |

### Docker 部署栈

| 组件 | 版本 | 目的 | 配置说明 |
|------|------|------|---------|
| Gunicorn | ^23.0.0 | 进程管理器 | 管理 Uvicorn workers，生产环境必备 [CITED: FastAPI 官方部署指南] |
| Uvicorn | 0.35.0 | ASGI 服务器 | 已有，作为 Gunicorn worker |
| Nginx | 1.27-alpine | 反向代理 | 已有，配置需优化超时和缓冲 |
| PostgreSQL | 16-alpine | 数据库 | 已有，数据持久化 |
| Redis | 7-alpine | 缓存/队列 | 已有，任务队列后端 |
| MinIO | RELEASE.2025-07-23 | 对象存储 | 已有，用于回调/日志存储 |

### 安装命令

```bash
# 前端 E2E 测试框架
cd frontend
npm install -D @playwright/test
npx playwright install --with-deps chromium  # CI 环境只装 Chromium 即可

# 后端 Gunicorn（添加到 requirements.txt）
echo "gunicorn>=23.0.0" >> requirements.txt
pip install gunicorn
```

## Architecture Patterns

### 测试架构设计

采用测试金字塔模型：

```
        ┌───────────────┐
        │   E2E Tests   │  ← Playwright (关键用户旅程，~10-15 个场景)
        │  (Happy Path) │
       ─┼───────────────┼─
        │ Integration   │  ← API 测试 + 服务层测试 (~30-50 个用例)
        │    Tests      │
       ─┼───────────────┼─
        │   Unit Tests  │  ← Vitest (组件/钩子) + pytest (服务层) (~100+ 用例)
        │  (Full Cover) │
       ─┴───────────────┴─
```

### 推荐的 E2E 测试目录结构

```
frontend/
├── e2e/
│   ├── fixtures/
│   │   └── test-fixtures.ts    # Playwright fixtures（登录、权限）
│   ├── specs/
│   │   ├── 01-dashboard.spec.ts    # DASH-01~05
│   │   ├── 02-failure-detail.spec.ts # FAIL-01~05
│   │   ├── 03-template-center.spec.ts # TMPL-01~05
│   │   ├── 04-policy-governance.spec.ts # POL-01~06
│   │   ├── 05-approval-center.spec.ts # APP-01~07
│   │   ├── 06-task-create.spec.ts # TSK-01~05
│   │   └── 07-audit.spec.ts     # AUD-01~03
│   ├── utils/
│   │   └── test-data.ts        # 测试数据生成
│   └── playwright.config.ts    # Playwright 配置
├── src/
│   └── ... (现有组件测试)
```

### 关键路径测试设计

```typescript
// e2e/specs/06-task-create.spec.ts 示例
import { test, expect } from '@playwright/test'

test.describe('任务创建→审批→执行→审计 闭环', () => {
  test('完整流程：创建高风险任务→L1 审批→L2 审批→执行→审计可查', async ({ page }) => {
    // 1. 登录（使用 fixture）
    await loginAsOperator(page)
    
    // 2. 创建任务（选择高风险模板）
    await page.goto('/tasks/create')
    await page.selectOption('[data-testid="template-select"]', 'high-risk-template')
    await page.fill('[data-testid="target-asset"]', 'asset-001')
    await page.click('[data-testid="policy-preview"]')
    await expect(page.locator('[data-testid="approval-required-badge"]')).toBeVisible()
    await page.click('[data-testid="submit-task"]')
    
    // 3. 验证跳转到审批详情页
    await expect(page).toHaveURL(/\/approvals\/.+/)
    
    // 4. L1 审批通过
    await page.click('[data-testid="approve-btn"]')
    await page.fill('[data-testid="approval-comment"]', 'L1 approved')
    await page.click('[data-testid="confirm-approve"]')
    
    // 5. 验证状态更新（轮询或使用 waitFor）
    await page.waitForSelector('[data-testid="approval-status-approved"]')
    
    // 6. 切换到审计列表验证记录存在
    await page.goto('/audits')
    await page.fill('[data-testid="entity-type-filter"]', 'task')
    await expect(page.locator('[data-testid="audit-list"]')).toContainText('task-create')
  })
})
```

### TanStack Query 测试注意事项

**陷阱:** React Query 默认 3 次重试 + 指数退避会导致测试超时。

**解决方案:**
```typescript
// e2e/fixtures/test-fixtures.ts
import { test as base } from '@playwright/test'

export const test = base.extend<{
  pageWithQuerySettings: Page
}>({
  pageWithQuerySettings: async ({ page }, use) => {
    // 禁用 React Query 重试和缓存
    await page.addInitScript(() => {
      window.__REACT_QUERY_CONFIG__ = {
        queries: {
          retry: false,
          cacheTime: 0,
        },
      }
    })
    await use(page)
  },
})
```

### Ant Design 组件选择器最佳实践

```typescript
// 推荐：使用 data-testid 属性
await page.click('[data-testid="template-select"]')
await page.fill('[data-testid="command-input"]', 'systemctl status nginx')

// 避免：使用动态生成的类名
// ❌ await page.click('.ant-select-selector')
// ❌ await page.click('.css-dev-kq4j2a')

// Ant Design Modal 确认操作
await page.click('.ant-btn-primary:has-text("确认")')
await page.click('.ant-btn-default:has-text("取消")')

// Ant Design Table 行操作
const targetRow = page.locator('tr:has-text("asset-001")')
await targetRow.locator('button:has-text("编辑")').click()
```

## Don't Hand-Roll

| 问题 | 不要构建 | 使用现成方案 | 原因 |
|------|----------|--------------|------|
| E2E 测试框架 | 自己写 Selenium 脚本 | Playwright | 内置 auto-wait、trace viewer、并行执行、AI 生成测试 [VERIFIED: Playwright 官方文档] |
| 测试数据管理 | 手动插入数据库 | Playwright fixtures + 后端 API | 可复用、可追踪、与生产数据一致 |
| Docker 进程管理 | 直接用 Uvicorn | Gunicorn + Uvicorn workers | 生产级进程管理、优雅关闭、多 worker 并发 [CITED: FastAPI 官方] |
| 反向代理 | 自己写 Python HTTP 服务 | Nginx | SSL 终止、负载均衡、静态资源、安全头 [CITED: 业界标准] |
| 测试报告 | 自己解析日志 | Playwright HTML Report | 内置截图、录屏、trace、时间线 |

**关键洞察:** 生产环境直接使用 Uvicorn 是常见反模式。Uvicorn 设计为开发/单进程服务器，缺乏健壮的过程管理。Gunicorn 提供 worker 管理、优雅重启、信号处理等生产必需能力。

## Common Pitfalls

### 陷阱 1: E2E 测试过度依赖 CSS 选择器
**问题:** Ant Design 的类名是动态生成的（如 `.css-dev-kq4j2a`），测试会频繁失败。
**原因:** Ant Design 使用 CSS-in-JS，类名随版本/配置变化。
**避免策略:** 始终使用 `data-testid` 属性标识关键元素。
**警告信号:** 测试失败信息显示元素找不到，但手动操作正常。

### 陷阱 2: TanStack Query 重试导致测试超时
**问题:** 测试中 API 调用失败时，React Query 默认重试 3 次，每次指数退避。
**原因:** 测试环境未覆盖 QueryClient 配置。
**避免策略:** 在测试初始化脚本中禁用重试：`retry: false`。

### 陷阱 3: Docker 镜像缺少 SOPS 密钥
**问题:** 部署到产线后无法连接 JumpServer（SOPS 密钥在本地，未打包进镜像）。
**原因:** SOPS 密钥通过 `.sops.yaml` 配置，但密钥文件本身不加进 git。
**避免策略:** 部署前确认：(1) SOPS 密钥已导入产线密钥管理系统，(2) 部署脚本包含密钥注入步骤。

### 陷阱 4: Nginx 配置未处理大请求体
**问题:** 上传大模板或长命令时返回 413 Entity Too Large。
**原因:** Nginx 默认 `client_max_body_size` 为 1MB。
**避免策略:** 已在 `docker/nginx/nginx.conf` 配置 `client_max_body_size 20m` — 验证此配置在生产环境生效。

### 陷阱 5: 数据库迁移未执行
**问题:** 容器启动后表不存在，API 返回 500。
**原因:** Dockerfile 未包含 alembic upgrade 步骤。
**避免策略:** docker-compose.yml 中添加 init 容器或 entrypoint 脚本执行迁移。

## Code Examples

### Playwright 配置 (playwright.config.ts)

```typescript
// Source: [Playwright 官方文档 https://playwright.dev/docs/test-configuration]
import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e/specs',
  fullyParallel: true,  // 并行执行
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',
  use: {
    baseURL: 'http://localhost:3000',  // Vite dev server
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    // 可选：Safari 测试 (WebKit)
    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
    },
  ],
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:3000',
    reuseExistingServer: !process.env.CI,
  },
})
```

### 优化后的 Dockerfile (生产环境)

```dockerfile
# Source: [FastAPI 官方部署指南]
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app /app/app

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health')"

EXPOSE 8000

# 使用 Gunicorn + Uvicorn workers
# workers = (CPU_CORES * 2) + 1，这里假设 4 核 = 9 workers
CMD ["gunicorn", "app.api.main:app", \
     "--workers", "4", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", \
     "--timeout", "120", \
     "--graceful-timeout", "30", \
     "--keep-alive", "5"]
```

### docker-compose.yml 补充数据库迁移

```yaml
# 添加到现有 docker-compose.yml
services:
  db-migrate:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: opspaw-db-migrate
    env_file:
      - .env
    command: alembic upgrade head
    depends_on:
      - postgres
    restart: "no"  # 迁移完成后退出

  api:
    # ... 现有配置
    depends_on:
      - postgres
      - redis
      - db-migrate  # 确保迁移先执行
```

### 33 条需求测试映射表

```markdown
| 需求 ID | 测试文件 | 测试场景 | 优先级 |
|---------|----------|----------|--------|
| DASH-01 | 01-dashboard.spec.ts | 页面加载调用 overview 接口 | P0 |
| DASH-02 | 01-dashboard.spec.ts | 告警条显示 ok/warn/critical | P0 |
| DASH-03 | 01-dashboard.spec.ts | 失败榜单按 count 降序 | P0 |
| DASH-04 | 01-dashboard.spec.ts | 点击卡片跳转到 failure_code 详情 | P1 |
| DASH-05 | 01-dashboard.spec.ts | 修复建议卡片内容渲染 | P1 |
| FAIL-01 | 02-failure-detail.spec.ts | 调用 detail 接口加载数据 | P0 |
| FAIL-02 | 02-failure-detail.spec.ts | 显示标题/严重级别/摘要 | P0 |
| FAIL-03 | 02-failure-detail.spec.ts | 推荐修复步骤和验证步骤 | P1 |
| FAIL-04 | 02-failure-detail.spec.ts | 底部显示近期失败样本表格 | P1 |
| FAIL-05 | 02-failure-detail.spec.ts | hours/source 筛选刷新 | P2 |
| TMPL-01 | 03-template-center.spec.ts | 调用 GET /templates/commands 列表 | P0 |
| TMPL-02 | 03-template-center.spec.ts | 弹窗新建模板 POST | P0 |
| TMPL-03 | 03-template-center.spec.ts | 启停模板 PATCH enabled | P0 |
| TMPL-04 | 03-template-center.spec.ts | 表单字段完整 (id/name/desc/cmd/risk) | P1 |
| TMPL-05 | 03-template-center.spec.ts | 新建前策略评估预览 | P1 |
| POL-01 | 04-policy-governance.spec.ts | 调用 GET /policies/command-blacklist | P0 |
| POL-02 | 04-policy-governance.spec.ts | 新增黑名单规则 POST | P0 |
| POL-03 | 04-policy-governance.spec.ts | 修改规则 PATCH | P0 |
| POL-04 | 04-policy-governance.spec.ts | 命令输入实时评估 | P1 |
| POL-05 | 04-policy-governance.spec.ts | 拦截时显示 block_reason/matched_rules | P0 |
| POL-06 | 04-policy-governance.spec.ts | 治理审计列表 | P1 |
| APP-01 | 05-approval-center.spec.ts | 待审批列表 current_level 筛选 | P0 |
| APP-02 | 05-approval-center.spec.ts | L1/L2 Tab 切换 | P0 |
| APP-03 | 05-approval-center.spec.ts | 详情页基础信息/决策区/时间线 | P1 |
| APP-04 | 05-approval-center.spec.ts | 通过操作 POST /approve | P0 |
| APP-05 | 05-approval-center.spec.ts | 驳回操作 POST /reject | P0 |
| APP-06 | 05-approval-center.spec.ts | 升级操作 POST /escalate (max_level 限制) | P1 |
| APP-07 | 05-approval-center.spec.ts | 超时状态禁用操作按钮 | P1 |
| TSK-01 | 06-task-create.spec.ts | 选择模板或输入命令 | P0 |
| TSK-02 | 06-task-create.spec.ts | 必填 target_asset_id/run_as_system_user_id | P0 |
| TSK-03 | 06-task-create.spec.ts | 提交前策略评估 | P0 |
| TSK-04 | 06-task-create.spec.ts | approval_required 跳转审批页 | P1 |
| TSK-05 | 06-task-create.spec.ts | 命中拦截禁用提交 | P0 |
| AUD-01 | 07-audit.spec.ts | 审计列表 | P0 |
| AUD-02 | 07-audit.spec.ts | entity_type/action/operator_id 筛选 | P1 |
| AUD-03 | 07-audit.spec.ts | 展开 JSON 详情 | P1 |
```

## State of the Art

| 旧方案 | 当前方案 | 变化时间 | 影响 |
|--------|----------|----------|------|
| Cypress E2E 测试 | Playwright E2E 测试 | 2024-2025 | Cypress  downloads 被 Playwright 超越，Playwright 成为 React 生态首选 [VERIFIED: npm trends] |
| Uvicorn 直接运行 | Gunicorn + Uvicorn workers | 2023+ | 生产环境标准配置，支持多 worker 并发 |
| 手动测试 | 自动化 E2E 测试 | 2026 | 减少人工回归成本，CI 集成自动验证 |

**已废弃/过时:**
- 直接使用 Uvicorn 生产部署：缺少进程管理，不推荐用于生产环境 [CITED: FastAPI 官方]
- Selenium E2E 测试：配置复杂、跨浏览器支持差、速度慢

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | 产线环境 Linux 服务器已安装 Docker 20.x+ | 部署方案 | 需额外安装步骤 |
| A2 | 产线环境可访问 JumpServer API | 部署方案 | 网络隔离导致执行失败 |
| A3 | SOPS 密钥管理机制已就绪 | 部署方案 | 无法解密敏感配置 |
| A4 | 前端 Vite dev server 仅用于测试，生产用 Nginx 静态文件 | 部署方案 | 配置错误导致性能问题 |
| A5 | PostgreSQL 16 和 Redis 7 兼容现有代码 | 部署方案 | 数据库驱动不兼容 |

## Open Questions

1. **产线环境具体网络配置？**
   - 已知：需要访问 JumpServer API
   - 待确认：是否需要出网访问（npm/pip 安装）
   - 建议：提前准备离线依赖包或使用国内镜像

2. **SOPS 密钥如何注入生产环境？**
   - 已知：项目使用 SOPS 加密敏感配置
   - 待确认：密钥存储位置（Vault/AWS Secrets Manager/本地文件）
   - 建议：部署脚本前添加密钥获取步骤

3. **试点环境用户账号如何创建？**
   - 已知：需要审批人/操作员角色
   - 待确认：是否从 JumpServer 同步用户
   - 建议：准备用户初始化脚本

## Environment Availability

| 依赖 | 被需要 | 可用性 | 版本 | 备选方案 |
|------|--------|--------|------|----------|
| Docker | 容器化部署 | ✓ (假设) | — | — |
| Docker Compose | 多服务编排 | ✓ (假设) | — | Kubernetes (过度) |
| Node.js 18+ | 前端构建 | ✓ (现有) | — | — |
| Python 3.12 | 后端运行 | ✓ (现有) | 3.12 | — |
| PostgreSQL | 数据持久化 | ✓ (docker-compose) | 16-alpine | — |
| Redis | 任务队列 | ✓ (docker-compose) | 7-alpine | — |
| MinIO | 对象存储 | ✓ (docker-compose) | RELEASE.2025-07-23 | AWS S3 |
| Playwright | E2E 测试 | 需安装 | ^1.52.0 | Cypress (备选) |
| Gunicorn | 生产部署 | 需安装 | ^23.0.0 | Uvicorn standalone (不推荐) |

**需提前准备:**
1. Playwright: `npm install -D @playwright/test && npx playwright install`
2. Gunicorn: 添加到 requirements.txt 并重新构建镜像

## Validation Architecture

### 测试框架 (现有 + 新增)

| 属性 | 值 |
|------|-----|
| 单元测试框架 | Vitest ^4.1.2 (前端) + pytest 8.4.1 (后端) |
| E2E 测试框架 | Playwright ^1.52.0 (新增) |
| 配置文件 | frontend/vitest.config.ts, pytest.ini, e2e/playwright.config.ts |
| 快速运行命令 | `npm run test:run` (前端单元) / `pytest -x` (后端单元) |
| E2E 运行命令 | `npx playwright test` (前端 E2E) |
| 全量测试命令 | `npm run test:run && pytest && npx playwright test` |

### Phase 33 条需求 → 测试映射

| 需求 ID | 行为 | 测试类型 | 自动化命令 | 文件存在? |
|---------|------|----------|------------|-----------|
| DASH-01~05 | Dashboard 看板 | E2E | `playwright test 01-dashboard.spec.ts` | ❌ Wave 0 |
| FAIL-01~05 | 失败详情页 | E2E | `playwright test 02-failure-detail.spec.ts` | ❌ Wave 0 |
| TMPL-01~05 | 模板中心 | E2E | `playwright test 03-template-center.spec.ts` | ❌ Wave 0(已有组件测试) |
| POL-01~06 | 策略治理 | E2E | `playwright test 04-policy-governance.spec.ts` | ❌ Wave 0(已有组件测试) |
| APP-01~07 | 审批中心 | E2E | `playwright test 05-approval-center.spec.ts` | ❌ Wave 0(已有组件测试) |
| TSK-01~05 | 任务创建 | E2E | `playwright test 06-task-create.spec.ts` | ❌ Wave 0 |
| AUD-01~03 | 治理审计 | E2E | `playwright test 07-audit.spec.ts` | ❌ Wave 0(已有组件测试) |

### 每任务提交采样

- **快速验证:** `npx playwright test --grep @smoke` (~5 分钟)
- **全量 E2E:** `npx playwright test` (~30 分钟)
- **阶段门:** 全量 E2E 绿色 + 无 P0/P1 bug

### Wave 0 差距

- [ ] `e2e/playwright.config.ts` — Playwright 配置
- [ ] `e2e/fixtures/test-fixtures.ts` — 共享 fixtures(登录/权限)
- [ ] `e2e/specs/01-dashboard.spec.ts` — DASH-01~05 覆盖
- [ ] `e2e/specs/02-failure-detail.spec.ts` — FAIL-01~05 覆盖
- [ ] `e2e/specs/03-template-center.spec.ts` — TMPL-01~05 覆盖
- [ ] `e2e/specs/04-policy-governance.spec.ts` — POL-01~06 覆盖
- [ ] `e2e/specs/05-approval-center.spec.ts` — APP-01~07 覆盖
- [ ] `e2e/specs/06-task-create.spec.ts` — TSK-01~05 覆盖
- [ ] `e2e/specs/07-audit.spec.ts` — AUD-01~03 覆盖
- [ ] Playwright 安装：`npm install -D @playwright/test`

## Security Domain

### 适用的 ASVS 类别

| ASVS 类别 | 适用 | 标准控制 |
|-----------|------|----------|
| V2 认证 | yes | JumpServer 统一认证，OpsPaw 不存储用户凭证 |
| V3 会话管理 | yes | 后端服务间 JWT 鉴权 |
| V4 访问控制 | yes | 审批层级 (L1/L2)、任务风险等级控制 |
| V5 输入验证 | yes | 命令黑名单策略评估、zod 前端校验 |
| V6 加密 | yes | SOPS 管理敏感配置、HTTPS 传输层加密 |

### 已知威胁模式

| 模式 | STRIDE | 标准缓解 |
|------|--------|----------|
| SSRF 攻击回调 URL | Tampering | 回调 URL 白名单/保留网段拦截 [VERIFIED: docs/05-interface-spec.md] |
| 命令注入 | Tampering | 命令黑名单硬拦截、风险评估 |
| 未授权审批 | Elevation of Privilege | 审批层级校验 max_level、操作审计 |
| 重放攻击 | Spoofing | 签名时间戳 + nonce、X-OpsPaw-Signature 校验 |

## Sources

### Primary (HIGH confidence)
- [Playwright 官方文档](https://playwright.dev) — E2E 测试配置和最佳实践
- [FastAPI 官方部署指南](https://fastapi.tiangolo.com/deployment/) — Docker/Gunicorn 部署
- [TanStack Query 测试指南](https://tanstack.com/query/v4/docs/react/guides/testing) — 测试配置
- [项目现有配置] — frontend/package.json, docker-compose.yml, requirements.txt

### Secondary (MEDIUM confidence)
- [Geekflare Playwright vs Cypress 2026 对比](https://geekflare.com/dev/playwright-vs-cypress/) — 框架选型依据
- [Better Stack FastAPI Docker 最佳实践](https://betterstack.com/community/guides/scaling-python/fastapi-docker-best-practices/) — Dockerfile 优化
- [npm trends](https://npmtrends.com/playwright-vs-cypress) — 下载量数据

### Tertiary (LOW confidence)
- [腾讯云前端测试策略](https://cloud.tencent.com/developer/article/2636345) — 中文社区实践（需验证）
- [CSDN Uvicorn 部署文章](https://blog.csdn.net/flower/article/details/149793474) — 中文教程（需验证）

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — 基于官方文档和现有项目配置
- Architecture: HIGH — 测试金字塔模型为业界标准
- Pitfalls: MEDIUM — 基于框架特性和常见问题总结

**Research date:** 2026-04-08
**Valid until:** 90 days (测试框架和部署方案相对稳定)
