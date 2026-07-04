# OpsPaw Web 联调清单（v0.1）

本文给前端与联调同学直接使用，按页面拆分“要接哪些接口、关键字段、验收标准”。

## 1. 首页看板（Dashboard）

目标：一屏看到健康度、失败分型、修复建议入口。

接口：

- `GET /api/v1/dashboard/overview?hours=24&source=api&top_n=5`

必展示字段：

- `alerts.level`（`ok|warn|critical`）
- `alerts.summary`
- `failure_summary.total_failed`
- `failure_summary.by_failure_code[]`
- `remediation_cards[]`（`failure_code/title/severity/summary/recommended_actions`）

交互：

- 点击失败分型卡片 -> 跳转失败详情页，并携带 `failure_code`

验收：

- 正常时 1s 内渲染（本地缓存 + loading 骨架）
- `critical` 时顶部红色告警条可见

## 2. 失败详情页（Failure Detail）

目标：按失败分型看近期失败任务，并给操作建议。

接口：

- `GET /api/v1/dashboard/failures/{failure_code}/detail?hours=24&source=api&limit=20`

必展示字段：

- `template.title`
- `template.recommended_actions[]`
- `template.verification_steps[]`
- `recent_failed_tasks[]`（`task_id/source/risk_level/target_asset_id/error_message/updated_at`）

交互：

- 支持按 `hours/source` 过滤刷新
- 点击 `task_id` 跳转任务详情页

验收：

- 空数据时显示“最近窗口无同类失败”

## 3. 模板中心（Command Templates）

目标：管理受控命令模板，禁止自由命令直接扩散。

接口：

- `GET /api/v1/templates/commands`
- `POST /api/v1/templates/commands`
- `PATCH /api/v1/templates/commands/{template_id}`

关键字段：

- `template_id/name/description/command/risk_level/enabled`

交互：

- 新建模板时，先调用策略评估（见第 4 节）做预校验
- 支持启停模板（`enabled`）

验收：

- 新建后列表可见
- `enabled=false` 模板不能用于创建任务

## 4. 策略治理页（Policy & Blacklist）

目标：可视化黑名单与风险判级结果，前端提交前即知道是否会被拦截。

接口：

- `GET /api/v1/policies/command-blacklist`
- `POST /api/v1/policies/command-blacklist`
- `PATCH /api/v1/policies/command-blacklist/{rule_id}`
- `POST /api/v1/policies/evaluate`
- `GET /api/v1/governance/audits`

关键字段：

- 黑名单：`pattern/hard_block/enabled`
- 评估：`allowed/block_reason/matched_rules/final_risk_level/approval_required`
- 审计：`entity_type/entity_id/action/operator_id/detail/created_at`

交互：

- 命令输入框实时或提交前触发 `/policies/evaluate`
- 若 `allowed=false`，禁止提交并展示 `block_reason`

验收：

- 命中硬拦截规则时，按钮置灰且错误提示可读

## 5. 审批中心（多级）

目标：支持待审批列表、按层级筛选、手工升级。

接口：

- `GET /api/v1/approvals/pending?current_level=1`
- `GET /api/v1/approvals?status=pending&current_level=2`
- `GET /api/v1/approvals/{approval_id}`
- `POST /api/v1/approvals/{approval_id}/approve`
- `POST /api/v1/approvals/{approval_id}/reject`
- `POST /api/v1/approvals/{approval_id}/escalate`

关键字段：

- `status/current_level/max_level/escalation_count/next_escalate_at/expires_at`
- `actions[]`（审批动作时间线）

交互：

- L1/L2 Tab（按 `current_level` 切换）
- 详情页可做通过/驳回/升级

验收：

- 升级后 `current_level` 立即变化
- 动作时间线出现 `escalated/approved/rejected`

## 6. 任务创建页（模板化 + 风险可解释）

目标：统一模板/自由命令创建入口，但默认引导模板化。

接口：

- `POST /api/v1/tasks`

请求要点：

- 建议传 `command_template_id`，也支持 `command`
- 必填：`target_asset_id/run_as_system_user_id`

响应关键字段：

- `status`
- `approval_required`
- `approval_id`
- `risk_level_final`
- `command_template_id`

验收：

- 高风险任务返回 `approval_pending`
- 命中策略拦截时展示 `POLICY_BLOCKED`

## 7. 联调顺序建议

1. 先接看板 `overview` + 失败详情  
2. 再接模板中心与策略评估  
3. 再接审批多级与升级动作  
4. 最后串任务创建页（模板化 + 审批跳转）  

## 8. 灰度关注项

- 开启自动升级后，关注审批是否出现异常“跳级/重复升级”
- 看板接口优先走预聚合，若回退 raw 需要展示 `data_mode`
- 策略拦截提示要可追溯（展示命中的 pattern）
