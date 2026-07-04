---
phase: 05
slug: deployment-test
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-08
---

# Phase 05 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Playwright (E2E) + Vitest (单元) + pytest (后端) |
| **Config file** | `e2e/playwright.config.ts`, `frontend/vitest.config.ts`, `pytest.ini` |
| **Quick run command** | `npx playwright test --grep @smoke` |
| **Full suite command** | `npm run test:run && pytest && npx playwright test` |
| **Estimated runtime** | ~30 分钟 (全量 E2E) |

---

## Sampling Rate

- **After every task commit:** Run `npx playwright test --grep @smoke` (针对相关 spec 文件)
- **After every plan wave:** Run `npx playwright test` (该 wave 覆盖的 spec 文件)
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~5 分钟 (smoke 测试), ~30 分钟 (全量)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------------|-----------|-------------------|-------------|--------|
| 05-01-01 | 01 | 1 | D-02 | Playwright 安装 | infra | `npm ls @playwright/test` | ❌ W0 | ⬜ |
| 05-01-02 | 01 | 1 | D-02 | playwright.config.ts 配置 | unit | `test -f e2e/playwright.config.ts` | ❌ W0 | ⬜ |
| 05-01-03 | 01 | 1 | D-08 | test-fixtures.ts 基础 fixture | unit | `test -f e2e/fixtures/test-fixtures.ts` | ❌ W0 | ⬜ |
| 05-02-01 | 05-02 | 2 | DASH-01~05 | Dashboard E2E 测试 | E2E | `npx playwright test 01-dashboard.spec.ts` | ❌ W0 | ⬜ |
| 05-02-02 | 05-02 | 2 | FAIL-01~05 | FailureDetail E2E 测试 | E2E | `npx playwright test 02-failure-detail.spec.ts` | ❌ W0 | ⬜ |
| 05-03-01 | 05-03 | 2 | TMPL-01~05 | TemplateCenter E2E 测试 | E2E | `npx playwright test 03-template-center.spec.ts` | ❌ W0 | ⬜ |
| 05-03-02 | 05-03 | 2 | POL-01~06 | PolicyGovernance E2E 测试 | E2E | `npx playwright test 04-policy-governance.spec.ts` | ❌ W0 | ⬜ |
| 05-04-01 | 05-04 | 3 | APP-01~07 | ApprovalCenter E2E 测试 | E2E | `npx playwright test 05-approval-center.spec.ts` | ❌ W0 | ⬜ |
| 05-05-01 | 05-05 | 3 | TSK-01~05 | TaskCreate E2E 测试 | E2E | `npx playwright test 06-task-create.spec.ts` | ❌ W0 | ⬜ |
| 05-05-02 | 05-05 | 3 | AUD-01~03 | Audit E2E 测试 | E2E | `npx playwright test 07-audit.spec.ts` | ❌ W0 | ⬜ |
| 05-06-01 | 05-06 | 4 | D-03, D-04 | Dockerfile Gunicorn 改造 | infra | `grep gunicorn Dockerfile` | ✅ | ⬜ |
| 05-06-02 | 05-06 | 4 | D-03 | docker-compose.yml 迁移服务 | infra | `grep db-migrate docker-compose.yml` | ✅ | ⬜ |
| 05-06-03 | 05-06 | 4 | D-04 | deploy-prod.sh 部署脚本 | infra | `test -f scripts/deploy-prod.sh` | ❌ W0 | ⬜ |
| 05-06-04 | 05-06 | 4 | D-06 | USER-MANUAL.md 用户手册 | docs | `test -f docs/USER-MANUAL.md` | ❌ W0 | ⬜ |
| 05-06-05 | 05-06 | 4 | D-07 | KNOWN-ISSUES.md 问题清单 | docs | `test -f docs/KNOWN-ISSUES.md` | ❌ W0 | ⬜ |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `e2e/playwright.config.ts` — Playwright 配置
- [ ] `e2e/fixtures/test-fixtures.ts` — 共享 fixtures (登录/权限)
- [ ] `e2e/specs/01-dashboard.spec.ts` — DASH-01~05 覆盖
- [ ] `e2e/specs/02-failure-detail.spec.ts` — FAIL-01~05 覆盖
- [ ] `e2e/specs/03-template-center.spec.ts` — TMPL-01~05 覆盖
- [ ] `e2e/specs/04-policy-governance.spec.ts` — POL-01~06 覆盖
- [ ] `e2e/specs/05-approval-center.spec.ts` — APP-01~07 覆盖
- [ ] `e2e/specs/06-task-create.spec.ts` — TSK-01~05 覆盖
- [ ] `e2e/specs/07-audit.spec.ts` — AUD-01~03 覆盖
- [ ] Playwright 安装：`npm install -D @playwright/test`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| 试点环境部署成功 | D-04 | 需要真实产线环境 | 1. 执行 deploy-prod.sh 2. 访问前端页面 3. 调用健康检查接口 |
| 用户操作手册完整性 | D-06 | 文档质量需人工审核 | 1. 检查章节覆盖所有核心功能 2. 图文匹配 3. 步骤可执行 |
| 已知问题清单准确性 | D-07 | 问题定级需人工判断 | 1. 确认问题可复现 2. 严重等级评估 3. 状态追踪 |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 300s (smoke), < 1800s (full)
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
