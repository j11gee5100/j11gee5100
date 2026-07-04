# API 与数据设计（v0.1）

## 1. JumpServer 侧关键 API

最小可用接口集：

- `GET /api/v1/perms/users/assets/`
- `GET /api/v1/perms/users/assets/{asset_id}/system-users/`
- `POST /api/v1/ops/command-executions/`
- `GET /api/v1/ops/command-executions/{id}/`
- `GET /api/v1/ops/celery/task/{id}/log/`
- `GET /api/v1/audits/command-executions-hosts-relations/`

## 2. Agent Adapter 对外工具接口

建议仅暴露以下受控工具：

- `list_assets(filters)`
- `list_system_users(asset_id)`
- `execute_runbook(command_id, asset_ids, run_as_id)`
- `get_execution(execution_id)`
- `get_execution_log(task_id)`

说明：

- 大模型不直接调用 JumpServer 原始 API
- 工具层做参数校验、权限检查、脱敏与审计关联

## 3. 执行请求样例

```json
{
  "command": "bash -lc 'systemctl is-active nginx && nginx -t'",
  "run_as": "system_user_uuid",
  "hosts": ["asset_uuid_1"]
}
```

## 4. 核心数据表建议

`task`

- `task_id`
- `source`
- `type`
- `status`
- `env`
- `skill_id`
- `risk_level`
- `created_at`
- `finished_at`

`execution`

- `execution_id`
- `task_id`
- `asset_id`
- `system_user_id`
- `command_template_id`
- `jms_execution_id`
- `status`
- `result_summary`
- `started_at`
- `finished_at`

`audit_link`

- `id`
- `task_id`
- `execution_id`
- `approver`
- `jms_audit_id`
- `trace_id`
- `created_at`

## 5. 任务与审计关联

每次执行建议至少记录：

- 发起来源与请求上下文
- Agent 输出计划摘要
- 审批信息（如有）
- JumpServer execution_id / task_id / audit_id
- 验证结果与最终结论

这样可以完成“计划 -> 审批 -> 执行 -> 验证 -> 审计”的端到端追踪。

