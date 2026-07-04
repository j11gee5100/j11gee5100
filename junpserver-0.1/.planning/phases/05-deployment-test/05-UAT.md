---
status: partial
phase: 05-deployment-test
source: [05-01-SUMMARY.md, 05-02-SUMMARY.md, 05-03-SUMMARY.md, 05-04-SUMMARY.md, 05-05-SUMMARY.md, 05-06-SUMMARY.md]
started: "2026-04-09T00:00:00Z"
updated: "2026-04-10T16:00:00Z"
---

## Current Test

[testing paused - 需要进一步修复测试选择器]

## Tests

### 1. 冷启动烟雾测试
expected: 停止现有服务，清理临态，从头启动应用。服务器无错误启动，数据库迁移/种子执行完成，健康检查端点返回成功。
result: pass

### 2. E2E 测试基础设施验证
expected: npx playwright --version 返回版本号，playwright.config.ts 存在，e2e/specs/、e2e/fixtures/、e2e/utils/ 目录存在
result: pass

### 3. Dashboard 看板 E2E 测试执行
expected: npx playwright test e2e/specs/01-dashboard.spec.ts 执行通过
result: pass
notes: 4 passed, 1 skipped

### 4. 失败详情页 E2E 测试执行
expected: npx playwright test e2e/specs/02-failure-detail.spec.ts 执行通过
result: pass
notes: 5 passed

### 5. 模板中心 E2E 测试执行
expected: npx playwright test e2e/specs/03-template-center.spec.ts 执行通过（5 条通过）
result: issue
reported: "TMPL-01 通过，但 TMPL-02~05 失败。原因是表单字段选择器与实际 Modal 组件不匹配（name='template_id' 等选择器找不到元素）"
severity: minor
notes: 1/5 passed - 路由问题已修复，表单选择器需要调整

### 6. 策略治理 E2E 测试执行
expected: npx playwright test e2e/specs/04-policy-governance.spec.ts 执行通过（6 条通过）
result: issue
reported: "POL-01 通过，但 POL-02~06 失败。类似模板中心问题，表单选择器和弹窗交互需要调整"
severity: minor
notes: 1/6 passed - 路由问题已修复，表单选择器需要调整

### 7. 审批中心 E2E 测试执行
expected: npx playwright test e2e/specs/05-approval-center.spec.ts 执行通过（11 条通过）
result: pass
notes: 11 passed

### 8. 任务创建 E2E 测试执行
expected: npx playwright test e2e/specs/06-task-create.spec.ts 执行通过（5 条通过）
result: pass
notes: 5 passed

### 9. 治理审计 E2E 测试执行
expected: npx playwright test e2e/specs/07-audit.spec.ts 执行通过（3 条通过）
result: pass
notes: 3 passed

### 10. Docker 部署配置验证
expected: Dockerfile 包含 HEALTHCHECK 和使用 gunicorn，docker-compose.yml 包含 db-migrate 服务，deploy-prod.sh 语法正确
result: pass

### 11. 文档完整性验证
expected: docs/USER-MANUAL.md 包含完整章节结构，docs/KNOWN-ISSUES.md 格式正确
result: pass

## Summary

total: 11
passed: 8
issues: 2 (部分通过)
pending: 0
skipped: 0
blocked: 0

## E2E 测试详细统计

| 测试文件 | 通过 | 失败 | 跳过 | 通过率 |
|---------|------|------|------|--------|
| 01-dashboard.spec.ts | 4 | 0 | 1 | 100% |
| 02-failure-detail.spec.ts | 5 | 0 | 0 | 100% |
| 03-template-center.spec.ts | 1 | 4 | 0 | 20% |
| 04-policy-governance.spec.ts | 1 | 5 | 0 | 17% |
| 05-approval-center.spec.ts | 11 | 0 | 0 | 100% |
| 06-task-create.spec.ts | 5 | 0 | 0 | 100% |
| 07-audit.spec.ts | 3 | 0 | 0 | 100% |
| **总计** | **30** | **9** | **1** | **77%** |

## Gaps

- truth: "模板中心 E2E 测试 5 条全部通过"
  status: partially_failed
  reason: "TMPL-01 通过，TMPL-02~05 失败。表单字段选择器 (name='template_id') 与实际 Modal 组件不匹配"
  severity: minor
  test: 5
  root_cause: "E2E 测试表单选择器与实际 UI 组件字段不一致"
  missing:
    - "更新 TMPL-02~05 的表单选择器以匹配 TemplateFormModal 组件"

- truth: "策略治理 E2E 测试 6 条全部通过"
  status: partially_failed
  reason: "POL-01 通过，POL-02~06 失败。表单选择器和弹窗交互测试需要调整"
  severity: minor
  test: 6
  root_cause: "E2E 测试表单选择器与实际 UI 组件字段不一致"
  missing:
    - "更新 POL-02~06 的表单选择器以匹配 BlacklistFormModal 组件"

## 已完成的修复

1. **deploy-prod.sh Git 权限** ✅
2. **前端组件同步** ✅
3. **Playwright 端口配置** ✅
4. **login fixture 兼容** ✅
5. **路由路径修正** ✅
   - 03-template-center: `/templates` → `/templates/commands`
   - 04-policy-governance: `/governance/blacklist` → `/policies/blacklist`

## 待修复项目

1. 模板中心测试 TMPL-02~05 的表单选择器
2. 策略治理测试 POL-02~06 的表单选择器

