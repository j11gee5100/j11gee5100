---
phase: 02-template-policy
plan: 01
subsystem: frontend
tags: [react, typescript, vite, antd, tanstack-query, react-router]

requires: []
provides:
  - Template/Policy/Governance 类型定义
  - TanStack Query hooks (templates, policies, governance)
  - Ant Design Layout 路由配置
  - PlaceholderPage 帧位组件
affects: [template-center-page, blacklist-page, governance-audit-page]

tech-stack:
  added: []
  patterns: [Type-only imports, TanStack Query mutations, Ant Design Layout routing]

key-files:
  created:
    - frontend/src/types/template.ts
    - frontend/src/types/policy.ts
    - frontend/src/types/governance.ts
    - frontend/src/hooks/useTemplates.ts
    - frontend/src/hooks/usePolicies.ts
    - frontend/src/hooks/useGovernance.ts
    - frontend/src/pages/PlaceholderPage.tsx
  modified:
    - frontend/src/App.tsx

key-decisions:
  - "使用 type-only import 语法适配 TypeScript verbatimModuleSyntax"
  - "Infinite scroll 使用 useInfiniteQuery，默认 20 条/页"
  - "策略评估使用 mutation (手动触发)而非自动查询"
  - "时间范围转换内置在 hooks 中 (1h/24h/7d -> hours)"

patterns-established:
  - "Query key factory pattern: templateKeys, policyKeys, governanceKeys"
  - "TanStack Query v5 API: useQuery({ queryKey, queryFn })"
  - "Ant Design Layout: Sider + Header + Content 结构"
  - "PlaceholderPage 组件作为开发中路由的临时占位"

requirements-completed: [TMPL-01, TMPL-04, POL-04]

duration: 10min
completed: 2026-04-07
---

# Plan 02-01: 类型定义 + TanStack Query hooks + 路由配置

**创建模板中心、策略治理、治理审计所需的类型定义、数据 hooks 和路由配置，为后续页面组件提供数据层基础**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-04-07T04:53:59Z
- **Completed:** 2026-04-07T05:05:00Z
- **Tasks:** 3
- **Files modified:** 8

## Accomplishments
- 创建 Template/BlacklistRule/AuditRecord 类型定义
- 创建 PolicyEvaluationRequest/Response 类型定义
- 创建 TanStack Query hooks: useTemplates, usePolicies, useGovernance
- 配置 Ant Design Layout 导航结构
- 配置路由: /templates/commands, /policies/blacklist, /governance/audits

## Task Commits

每个任务原子提交:

1. **Task 1: 类型定义** - `b75aea7` (feat)
2. **Task 2: TanStack Query hooks** - `27818d5` (feat)
3. **Task 3: 路由配置** - `6c5103f` (feat)

## Files Created/Modified
- `frontend/src/types/template.ts` - Template 类型定义 (Template, TemplateFormData, TemplateListResponse)
- `frontend/src/types/policy.ts` - Policy 类型定义 (BlacklistRule, PolicyEvaluationRequest, PolicyEvaluationResponse)
- `frontend/src/types/governance.ts` - Governance 类型定义 (AuditRecord, AuditFilters, timeRangeToHours)
- `frontend/src/hooks/useTemplates.ts` - Template hooks (useTemplates, useTemplatesInfinite, useCreateTemplate, useUpdateTemplate)
- `frontend/src/hooks/usePolicies.ts` - Policy hooks (useBlacklist, useEvaluatePolicy, useCreateBlacklistRule, useUpdateBlacklistRule)
- `frontend/src/hooks/useGovernance.ts` - Governance hooks (useAuditLogs, useAuditLogsPaginated)
- `frontend/src/pages/PlaceholderPage.tsx` - 帧位页面组件
- `frontend/src/App.tsx` - Ant Design Layout 路由容器

## Decisions Made
- 使用 TanStack Query v5 API (对象参数形式)
- 策略评估使用 mutation 而非自动触发 query
- Query key factory 模式统一管理缓存键
- Ant Design Sider 作为左侧导航，Header 显示标题

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] TypeScript verbatimModuleSyntax 类型导入错误**
- **Found during:** Task 3 (构建验证)
- **Issue:** TypeScript 编译报错 `PaginatedResponse is a type and must be imported using a type-only import`
- **Fix:** 将 `import { PaginatedResponse }` 改为 `import type { PaginatedResponse }`
- **Files modified:** frontend/src/types/template.ts, frontend/src/types/policy.ts, frontend/src/types/governance.ts
- **Verification:** npm run build 成功
- **Committed in:** 6c5103f (Task 3 提交)

**2. [Rule 3 - Blocking] 未使用的类型导入警告**
- **Found during:** Task 3 (构建验证)
- **Issue:** hooks 文件导入未使用的类型 (TemplateFormData, AuditRecord, timeRangeToHours)
- **Fix:** 移除未使用的类型导入
- **Files modified:** frontend/src/hooks/useTemplates.ts, frontend/src/hooks/useGovernance.ts
- **Verification:** npm run build 成功
- **Committed in:** 6c5103f (Task 3 提交)

---

**Total deviations:** 2 auto-fixed (2 blocking)
**Impact on plan:** 修复必要的编译错误，无范围蔓延

## Issues Encountered
None - 所有任务按计划完成

## User Setup Required
- 无需额外操作，前端脚手架已配置完成

## Next Phase Readiness
- 数据层完成，可开始开发 PolicyEvaluationModal (02-02)
- 类型定义可被页面组件直接引用
- hooks 可直接用于页面组件数据获取

## Self-Check: PASSED

- [x] frontend/src/types/template.ts 存在
- [x] frontend/src/types/policy.ts 存在
- [x] frontend/src/types/governance.ts 存在
- [x] frontend/src/hooks/useTemplates.ts 存在
- [x] frontend/src/hooks/usePolicies.ts 存在
- [x] frontend/src/hooks/useGovernance.ts 存在
- [x] frontend/src/pages/PlaceholderPage.tsx 存在
- [x] Commit b75aea7 存在
- [x] Commit 27818d5 存在
- [x] Commit 6c5103f 存在

---

*Phase: 02-template-policy*
*Plan: 02-01*
*Completed: 2026-04-07*