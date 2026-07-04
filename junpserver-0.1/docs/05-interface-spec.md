# OpsPaw 接口文档（v0.1）

## 1. 文档范围

本文件基于历史会话已确认方案整理，覆盖两类接口：

- JumpServer 北向 REST API（由 `jms-adapter` 调用）
- OpsPaw Adapter 对 Agent/编排层暴露的内部接口

说明：

- 生产执行链路以 `ops/command-executions` 为主
- `connection-token` 仅用于人工接管或跳转类场景

## 2. 接口总览

### 2.1 JumpServer 侧接口

- `GET /api/v1/perms/users/assets/`
- `GET /api/v1/perms/users/assets/{asset_id}/system-users/`
- `POST /api/v1/ops/command-executions/`
- `GET /api/v1/ops/command-executions/{id}/`
- `GET /api/v1/ops/celery/task/{id}/log/`
- `GET /api/v1/ops/celery/task/{id}/result/`
- `GET /api/v1/ops/ansible/task/{id}/log/`
- `GET /api/v1/audits/command-executions-hosts-relations/`
- `GET /api/v1/terminal/commands/`
- `POST /api/v1/authentication/connection-token/`
- `POST /api/v1/authentication/connection-token/client-url/`
- `POST /api/v1/authentication/connection-token/rdp/file/`

### 2.2 OpsPaw Adapter 侧接口

- `POST /internal/v1/assets/search`
- `GET /internal/v1/assets/{asset_id}/system-users`
- `POST /internal/v1/executions`
- `GET /internal/v1/executions/{execution_id}`
- `GET /internal/v1/executions/{execution_id}/log`
- `GET /internal/v1/executions/{execution_id}/audit`
- `POST /internal/v1/review-tickets`

## 3. JumpServer 接口定义

### 3.1 查询可访问资产

- 方法：`GET`
- 路径：`/api/v1/perms/users/assets/`
- 用途：获取当前服务账号可访问资产清单
- 关键查询参数：`search`、`id`、`limit`、`offset`

### 3.2 查询资产可用系统用户

- 方法：`GET`
- 路径：`/api/v1/perms/users/assets/{asset_id}/system-users/`
- 用途：为执行动作选择 `run_as`

### 3.3 发起命令执行

- 方法：`POST`
- 路径：`/api/v1/ops/command-executions/`
- 用途：由 JumpServer 代连并执行远程命令
- 请求体核心字段：`command`、`run_as`、`hosts`

请求示例：

```json
{
  "command": "bash -lc 'systemctl is-active nginx && nginx -t'",
  "run_as": "system_user_uuid",
  "hosts": ["asset_uuid_1"]
}
```

### 3.4 查询执行详情

- 方法：`GET`
- 路径：`/api/v1/ops/command-executions/{id}/`
- 用途：轮询执行状态
- 关注字段：`is_finished`、`result`、`log_url`、`date_finished`

### 3.5 查询任务日志/结果

- 方法：`GET`
- 路径：
  - `/api/v1/ops/celery/task/{id}/log/`
  - `/api/v1/ops/celery/task/{id}/result/`
  - `/api/v1/ops/ansible/task/{id}/log/`
- 用途：长任务跟踪与结果归档

### 3.6 查询审计关联

- 方法：`GET`
- 路径：`/api/v1/audits/command-executions-hosts-relations/`
- 用途：把任务与审计记录关联到主机维度

### 3.7 人工接管相关（可选）

- `POST /api/v1/authentication/connection-token/`
- `POST /api/v1/authentication/connection-token/client-url/`
- `POST /api/v1/authentication/connection-token/rdp/file/`

用途：

- 人工接管时下发连接凭据或跳转 URL
- 不作为无人值守自动执行主路径

## 4. Adapter 内部接口定义

### 4.1 POST /internal/v1/assets/search

用途：按标签、环境、关键词筛选资产。

请求示例：

```json
{
  "env": "prod",
  "tags": ["nginx"],
  "keyword": "web"
}
```

响应示例：

```json
{
  "items": [
    {
      "asset_id": "asset_uuid_1",
      "hostname": "web-01",
      "ip": "10.0.0.11",
      "env": "prod"
    }
  ],
  "total": 1
}
```

### 4.2 GET /internal/v1/assets/{asset_id}/system-users

用途：获取资产可执行系统用户候选列表。

响应示例：

```json
{
  "asset_id": "asset_uuid_1",
  "system_users": [
    {"id": "su_uuid_1", "name": "appops"},
    {"id": "su_uuid_2", "name": "root"}
  ]
}
```

### 4.3 POST /internal/v1/executions

用途：执行受控命令模板，不接受自由命令明文。

请求示例：

```json
{
  "task_id": "task_20260402_001",
  "command_id": "check_nginx_status",
  "asset_ids": ["asset_uuid_1"],
  "run_as_id": "su_uuid_1",
  "reason": "alert: nginx_down"
}
```

响应示例：

```json
{
  "execution_id": "exec_20260402_001",
  "jms_execution_id": "jms_exec_uuid",
  "status": "running"
}
```

### 4.4 GET /internal/v1/executions/{execution_id}

用途：查询执行状态摘要。

响应示例：

```json
{
  "execution_id": "exec_20260402_001",
  "status": "success",
  "finished": true,
  "result_summary": "nginx active"
}
```

### 4.5 GET /internal/v1/executions/{execution_id}/log

用途：返回脱敏后的执行日志片段，供 Agent 复盘。

### 4.6 GET /internal/v1/executions/{execution_id}/audit

用途：返回审计关联字段。

响应示例：

```json
{
  "execution_id": "exec_20260402_001",
  "jms_execution_id": "jms_exec_uuid",
  "jms_audit_relation_ids": ["audit_rel_1"],
  "trace_id": "trace_abc_001"
}
```

### 4.7 POST /internal/v1/review-tickets

用途：高风险动作触发人工审批。

请求示例：

```json
{
  "task_id": "task_20260402_001",
  "risk_level": "high-risk",
  "plan": "restart service on 3 hosts",
  "impact_scope": "prod-web"
}
```

## 5. 通用约束

### 5.1 认证与鉴权

- Adapter 调用 JumpServer 使用服务账号 Token/Access Key
- Adapter 对内部接口使用服务间鉴权（如 JWT/mTLS）
- 每个请求必须携带 `trace_id`

### 5.2 幂等与重试

- `POST /internal/v1/executions` 建议支持 `idempotency_key`
- 查询类接口可安全重试
- 执行类接口重试需先判断上次请求是否已落地

### 5.3 脱敏与审计

- 日志返回前做密钥、口令、令牌脱敏
- 全链路记录：`task_id`、`execution_id`、`jms_execution_id`、`trace_id`

## 6. 错误码约定（Adapter）

- `400 INVALID_ARGUMENT`：参数错误
- `401 UNAUTHORIZED`：认证失败
- `403 FORBIDDEN`：权限不足或策略拦截
- `404 NOT_FOUND`：资产/执行记录不存在
- `409 CONFLICT`：幂等冲突或状态冲突
- `429 RATE_LIMITED`：触发限流
- `502 JMS_UPSTREAM_ERROR`：JumpServer 上游错误
- `504 EXECUTION_TIMEOUT`：执行超时

错误响应示例：

```json
{
  "code": "FORBIDDEN",
  "message": "policy denied for high-risk command",
  "trace_id": "trace_abc_001"
}
```

## 7. 最小联调顺序

1. 打通资产查询：`assets/search` -> `perms/users/assets`
2. 打通系统用户查询：`system-users`
3. 打通执行链路：`executions` -> `ops/command-executions`
4. 打通状态/日志轮询：`command-executions/{id}` + `celery log/result`
5. 打通审计关联：`audits/command-executions-hosts-relations`
6. 最后接入审批票据接口与策略拦截

## 8. 当前已实现接口（代码对齐）

以下接口已在 `app/api/main.py` 实现，可直接用于 Web 看板与外部调用。

### 8.0 资产投影查询（含新鲜度）

- 方法：`GET`
- 路径：`/api/v1/assets`
- 查询参数：
  - `status`：可选（如 `active` / `inactive`）
  - `freshness_status`：可选（`fresh` / `stale` / `expired`）
  - `search`：可选，按 `hostname/ip/jms_asset_id` 模糊匹配
  - `limit`：默认 50，最大 500
  - `offset`：默认 0

响应示例：

```json
{
  "items": [
    {
      "asset_id": "local_asset_uuid",
      "jms_asset_id": "jms_asset_uuid",
      "hostname": "web-01",
      "ip": "10.0.0.11",
      "status": "active",
      "freshness_status": "fresh",
      "sync_at": "2026-04-02T15:45:00+00:00",
      "created_at": "2026-04-02T10:00:00+00:00",
      "updated_at": "2026-04-02T15:45:00+00:00"
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0,
  "status_filter": "active",
  "freshness_status_filter": "fresh",
  "search_filter": null,
  "trace_id": "trace_uuid"
}
```

### 8.1 查询任务详情

- 方法：`GET`
- 路径：`/api/v1/tasks/{task_id}`
- 关键返回：`status`、`failure_code`、`reason`、`trace_id`

当 `status=failed` 时：

- `failure_code` 透出标准失败码（如 `UPSTREAM_ERROR`、`EXECUTION_TIMEOUT`）
- `reason` 返回去前缀后的可读错误信息

### 8.1.1 取消任务（未执行）

- 方法：`POST`
- 路径：`/api/v1/tasks/{task_id}/cancel`
- 请求体（可选）：
  - `reason`：取消原因（默认 `canceled by user`）

取消规则：

- 仅 `pending` / `planning` 状态可取消
- `executing` / `success` / `failed` 返回 `409 TASK_NOT_CANCELABLE`
- 已取消任务重复调用返回 `200` 且 `already_canceled=true`

响应示例：

```json
{
  "task_id": "task_uuid",
  "status": "canceled",
  "already_canceled": false,
  "reason": "manual cancel",
  "trace_id": "trace_uuid"
}
```

### 8.1.2 回调注册与投递查询

任务创建接口 `POST /api/v1/tasks` 支持可选字段：

- `callback_url`：任务终态回调地址（需 `http://` 或 `https://`）
- `callback_secret`：可选签名密钥（用于 `X-OpsPaw-Signature`）

安全约束（新增）：

- `callback_url` 不允许携带 URL 凭据（`user:pass@host`）
- 默认启用私网/保留网段拦截（anti-SSRF），例如 `localhost`、`127.0.0.1`、内网地址会被拒绝
- 可通过白名单放行（`CALLBACK_ALLOWED_HOSTS` / `CALLBACK_ALLOWED_DOMAIN_SUFFIXES` / `CALLBACK_ALLOWED_CIDRS`）
- 若被拦截，创建任务返回 `400 CALLBACK_URL_BLOCKED`

任务创建响应新增：

- `callback_registered`：是否注册成功

查询任务回调状态：

- 方法：`GET`
- 路径：`/api/v1/tasks/{task_id}/callbacks`

返回：

- `hook`：回调配置
- `deliveries`：投递记录（状态、重试次数、下次重试时间、最近错误）

签名头（新增，便于调用方防重放）：

- `X-OpsPaw-Signature`: `sha256=<hmac_hex>`
- `X-OpsPaw-Signature-Timestamp`: Unix 秒级时间戳
- `X-OpsPaw-Signature-Nonce`: 每次投递唯一 nonce

签名原文：`{timestamp}.{nonce}.{raw_json_body}`

### 8.2 查询任务下执行记录

- 方法：`GET`
- 路径：`/api/v1/tasks/{task_id}/executions`
- 查询参数：`limit`（默认 20，最大 200）

响应示例：

```json
{
  "task_id": "task_uuid",
  "items": [
    {
      "execution_id": "exec_uuid",
      "task_id": "task_uuid",
      "jms_execution_id": "jms_exec_uuid",
      "status": "failed",
      "result_summary": "[EXECUTION_TIMEOUT] jumpserver execution timeout",
      "failure_code": "EXECUTION_TIMEOUT",
      "error_message": "jumpserver execution timeout",
      "trace_id": "trace_uuid",
      "started_at": "2026-04-02T09:03:24+00:00",
      "finished_at": "2026-04-02T09:13:24+00:00",
      "created_at": "2026-04-02T09:03:24+00:00",
      "updated_at": "2026-04-02T09:13:24+00:00",
      "audit_relation_ids": ["audit_rel_uuid"]
    }
  ],
  "trace_id": "trace_uuid"
}
```

### 8.3 查询单条执行记录

- 方法：`GET`
- 路径：`/api/v1/executions/{execution_id}`
- 说明：
  - 优先按本地 `execution.id` 查询
  - 若未命中，自动回退按 `jms_execution_id` 查询

该接口返回结构与 `8.2` 的 `items[]` 单项一致，适合外部系统按 JumpServer 执行 ID 直接反查结果与错误。

### 8.4 查询全局执行记录（看板/排障）

- 方法：`GET`
- 路径：`/api/v1/executions`
- 查询参数：
  - `limit`：分页大小（默认 20，最大 200）
  - `offset`：分页偏移（默认 0）
  - `status`：可选执行状态过滤（如 `running`、`failed`、`success`）
  - `source`：可选任务来源过滤（如 `api`、`web`）
  - `risk_level`：可选风险等级过滤
  - `task_id`：可选按任务 ID 过滤
  - `hours`：可选时间窗口过滤（最近 N 小时）

响应示例：

```json
{
  "items": [
    {
      "execution_id": "exec_uuid",
      "task_id": "task_uuid",
      "jms_execution_id": "jms_exec_uuid",
      "status": "failed",
      "result_summary": "[PERMISSION_DENIED] You do not have access rights",
      "failure_code": "PERMISSION_DENIED",
      "error_message": "You do not have access rights",
      "trace_id": "trace_uuid",
      "started_at": "2026-04-02T09:03:24+00:00",
      "finished_at": "2026-04-02T09:13:24+00:00",
      "created_at": "2026-04-02T09:03:24+00:00",
      "updated_at": "2026-04-02T09:13:24+00:00",
      "audit_relation_ids": ["audit_rel_uuid"]
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0,
  "status_filter": "failed",
  "source_filter": "api",
  "risk_level_filter": null,
  "task_id_filter": null,
  "hours_filter": null,
  "trace_id": "trace_uuid"
}
```

### 8.5 失败分型聚合统计（看板直连）

- 方法：`GET`
- 路径：`/api/v1/metrics/failures/summary`
- 查询参数：
  - `hours`：统计窗口小时数（默认 24，最大 720）
  - `source`：可选调用来源过滤（如 `api`、`web`）
  - `prefer_preaggregated`：优先读取预聚合桶（默认 `true`）

响应示例：

```json
{
  "window_hours": 24,
  "to": "2026-04-02T10:00:00+00:00",
  "since": "2026-04-01T10:00:00+00:00",
  "source_filter": null,
  "total_failed": 5,
  "by_failure_code": [
    {"failure_code": "UPSTREAM_ERROR", "count": 2},
    {"failure_code": "EXECUTION_TIMEOUT", "count": 1},
    {"failure_code": "UNKNOWN", "count": 2}
  ],
  "by_source": [
    {"source": "api", "count": 4},
    {"source": "web", "count": 1}
  ],
  "by_risk_level": [
    {"risk_level": "readonly", "count": 3},
    {"risk_level": "safe-write", "count": 2}
  ],
  "unknown_reason_samples": [
    {"reason": "external smoke", "count": 1}
  ],
  "data_mode": "preaggregated_hour",
  "trace_id": "trace_uuid"
}
```

### 8.5.1 任务重试审计聚合统计（看板直连）

- 方法：`GET`
- 路径：`/api/v1/metrics/task-retry/summary`
- 查询参数：
  - `hours`：统计窗口小时数（默认 24，最大 720）
  - `source`：可选任务来源过滤（如 `api`、`web`）
  - `operator_id`：可选操作人过滤
  - `include_dry_run`：是否包含 dry-run 审计（默认 `true`）
  - `prefer_preaggregated`：优先读取预聚合桶（默认 `true`）

响应示例：

```json
{
  "window_hours": 24,
  "to": "2026-04-03T01:00:00+00:00",
  "since": "2026-04-02T01:00:00+00:00",
  "source_filter": "api",
  "operator_id_filter": null,
  "include_dry_run": false,
  "audit_total": 4,
  "item_total": 12,
  "audit_by_hour": [
    {"hour": "2026-04-03T00:00:00+00:00", "count": 2}
  ],
  "by_hour": [
    {
      "hour": "2026-04-03T00:00:00+00:00",
      "total": 5,
      "by_action": [
        {"action": "queued", "count": 3},
        {"action": "skipped_task_cooldown", "count": 2}
      ]
    }
  ],
  "by_action": [
    {"action": "queued", "count": 7},
    {"action": "skipped_task_cooldown", "count": 3}
  ],
  "by_failure_code": [
    {"failure_code": "ASSET_STALE", "count": 6},
    {"failure_code": "ASSET_EXPIRED", "count": 4}
  ],
  "by_source": [
    {"source": "api", "count": 10}
  ],
  "data_mode": "preaggregated_hour",
  "trace_id": "trace_uuid"
}
```

### 8.5.2 失败分型修复建议模板（看板点开即用）

- 方法：`GET`
- 路径：
  - `/api/v1/metrics/failures/remediation-template`
  - `/api/v1/metrics/failures/remediation-templates`
- 说明：
  - `remediation-template` 适合按 `failure_code` 单点查询
  - `remediation-templates` 返回全量模板，可用于前端本地缓存

单个模板查询参数：

- `failure_code`（可选，不传时返回 `UNKNOWN` 模板）
- `source`（可选，用于生成来源场景提示）
- `risk_level`（可选，用于生成风险级别提示）

单个模板响应示例：

```json
{
  "requested_failure_code": "CONNECTIVITY_ERROR",
  "matched": true,
  "template": {
    "failure_code": "CONNECTIVITY_ERROR",
    "title": "目标主机连通性失败",
    "severity": "high",
    "summary": "执行节点无法连通目标资产（超时/拒绝/路由不可达）。",
    "recommended_actions": [
      "检查目标资产 22 端口可达性与安全组/防火墙规则。"
    ],
    "verification_steps": [
      "在 OpsPaw 重新发起只读命令（如 hostname）验证恢复。"
    ],
    "context_hints": [
      "API 调用场景：优先检查 idempotency_key 去重与调用方重试策略。"
    ]
  },
  "trace_id": "trace_uuid"
}
```

### 8.5.3 失败修复建议（带任务/执行上下文）

- 方法：`GET`
- 路径：`/api/v1/metrics/failures/remediation`
- 查询参数（至少提供一个）：
  - `task_id`
  - `execution_id`（支持本地 `execution_id` 或 `jms_execution_id`）
  - `failure_code`

响应示例：

```json
{
  "resolved_from": "execution",
  "requested_failure_code": "ASSET_EXPIRED",
  "inferred_failure_code": "ASSET_EXPIRED",
  "matched": true,
  "failure_code_override": false,
  "context": {
    "task_id": "task_uuid",
    "execution_id": "exec_uuid",
    "jms_execution_id": "jms_exec_uuid",
    "task_status": "failed",
    "execution_status": "failed",
    "source": "api",
    "risk_level": "readonly",
    "error_message": "refresh required"
  },
  "template": {
    "failure_code": "ASSET_EXPIRED",
    "title": "资产快照失效（expired）"
  },
  "trace_id": "trace_uuid"
}
```

### 8.5.4 预聚合健康状态

- 方法：`GET`
- 路径：`/api/v1/metrics/preaggregation/status`
- 查询参数：
  - `granularity`：`hour|day`（默认 `hour`）

返回：

- 三类聚合桶最新时间（失败分型、重试明细、重试审计计数）
- `run_lag_minutes`、`bucket_lag_minutes` 与 `healthy` 判定
- `max_allowed_lag_minutes` 阈值

### 8.5.5 预聚合告警级别（看板红黄绿灯）

- 方法：`GET`
- 路径：`/api/v1/metrics/preaggregation/alerts`
- 查询参数：
  - `granularity`：`hour|day`（默认 `hour`）

响应包含：

- `level`：`ok|warn|critical`
- `summary`：告警摘要
- `suggested_actions`：建议动作
- `status`：内嵌 `preaggregation/status` 原始结果

### 8.5.6 审计摘要聚合（时间/资产/调用方）

- 方法：`GET`
- 路径：`/api/v1/audits/summary`
- 查询参数：
  - `hours`：窗口小时（默认 24）
  - `source`：可选来源过滤（可作为调用方维度）
  - `asset_id`：可选资产过滤
  - `top_assets`：返回资产 TopN（默认 10）

响应包含：

- 总量：`task_total/execution_total/audit_link_total/failed_task_total`
- 分布：`by_source/by_asset/by_task_status/by_execution_status/by_failure_code`
- 趋势：`by_hour`（每小时 task/execution/audit_link 数）

### 8.5.7 高风险任务审批流（MVP）

- 触发条件：
  - `POST /api/v1/tasks` 且 `risk_level=high-risk`
- 行为：
  - 任务初始状态为 `approval_pending`（不进入执行）
  - 自动创建审批单并返回 `approval_id`
  - 通过审批后任务转为 `pending`，由 orchestrator 正常拉起执行
  - 驳回/超时后任务标记失败并写入标准失败码

任务创建响应补充字段：

- `approval_required`：是否需要审批
- `approval_id`：审批单 ID（仅高风险任务）
- `approval_status`：`pending|approved|rejected|expired`

审批查询接口：

- `GET /api/v1/tasks/{task_id}/approval`：按任务查询审批详情 + 审批动作流水
- `GET /api/v1/approvals`：审批单列表（支持 `status/source/risk_level` 过滤）
- `GET /api/v1/approvals/pending`：待审批列表快捷入口
- `GET /api/v1/approvals/{approval_id}`：审批详情 + 审批动作分页

审批动作接口：

- `POST /api/v1/approvals/{approval_id}/approve`
- `POST /api/v1/approvals/{approval_id}/reject`

失败码约定：

- `APPROVAL_REJECTED`：人工驳回
- `APPROVAL_TIMEOUT`：审批超时自动过期

审批超时后台处理：

- scheduler 周期调用审批过期检查，将逾期 `pending` 审批单置为 `expired`
- 对应任务（`approval_pending/pending/planning`）统一置为 `failed`

审批升级能力（新增）：

- 自动升级：当 `APPROVAL_ESCALATION_ENABLED=true` 且审批未决时，scheduler 会在 `APPROVAL_ESCALATION_AFTER_MINUTES` 后自动提升一级审批层级
- 多级上限：`APPROVAL_MAX_LEVELS`（例如 2 或 3）
- 到达最高级后仍未处理：按 `APPROVAL_TIMEOUT` 过期失败
- 手工升级接口：`POST /api/v1/approvals/{approval_id}/escalate`
- 列表筛选支持层级：`GET /api/v1/approvals?current_level=2`、`GET /api/v1/approvals/pending?current_level=2`

### 8.5.8 模板中心与策略治理（B4-01 / B5-01 / B5-02）

命令模板中心：

- `GET /api/v1/templates/commands`
- `POST /api/v1/templates/commands`
- `PATCH /api/v1/templates/commands/{template_id}`

命令黑名单治理：

- `GET /api/v1/policies/command-blacklist`
- `POST /api/v1/policies/command-blacklist`
- `PATCH /api/v1/policies/command-blacklist/{rule_id}`

策略评估（前端提交前预判）：

- `POST /api/v1/policies/evaluate`
- 输入：`command` 或 `command_template_id` + `requested_risk_level`
- 输出：`allowed/block_reason/matched_rules/final_risk_level/approval_required`

治理审计：

- `GET /api/v1/governance/audits`
- 记录模板/黑名单变更动作（谁、何时、改了什么）

任务创建策略升级：

- `POST /api/v1/tasks` 支持 `command_template_id`
- 当传模板时，后端自动加载模板命令并执行策略评估
- 风险级别由三者合并取高：`requested_risk_level`、模板风险、命令推断风险
- 命中硬黑名单直接阻断：返回 `POLICY_BLOCKED`

### 8.5.9 看板聚合接口（预聚合告警 + 修复建议详情）

- `GET /api/v1/dashboard/overview`
  - 聚合返回：预聚合告警状态 + 失败分型概览 + TopN 修复建议卡片
- `GET /api/v1/dashboard/failures/{failure_code}/detail`
  - 返回：该失败分型的修复模板 + 最近失败任务样本（用于看板点开详情）

### 8.6 JumpServer 能力探针（权限与开关诊断）

- 方法：`GET`
- 路径：`/api/v1/integrations/jumpserver/capabilities`

用途：

- 直接返回 `api_mode`（`legacy_v3`/`v4`）
- 返回 `SECURITY_COMMAND_EXECUTION` 开关状态
- 返回命令黑名单数量与示例
- 探测执行结果查询接口是否可访问（识别权限不足场景）

### 8.6.1 JumpServer 权限自检（服务账号就绪检查）

- 方法：`GET`
- 路径：`/api/v1/integrations/jumpserver/permission-check`

用途：

- 检查当前 OpsPaw 配置的 JumpServer 服务账号是否具备关键权限：
  - `list_assets`（资产可见）
  - `list_asset_system_users`（系统用户映射可读）
  - `list_command_executions`（执行状态可查询）
- 返回 `overall_required_ok`，用于上线前快速验收

返回示例（权限不全时）：

```json
{
  "status": "degraded",
  "overall_required_ok": false,
  "required_checks": 3,
  "required_checks_ok": 2,
  "checks": [
    {"name": "list_assets", "required": true, "ok": true, "skipped": false, "detail": "assets_visible=1", "error": null},
    {"name": "list_asset_system_users", "required": true, "ok": false, "skipped": false, "detail": null, "error": "jumpserver ... status=403"},
    {"name": "list_command_executions", "required": true, "ok": true, "skipped": false, "detail": "count=3", "error": null}
  ],
  "recommendation": "grant missing JumpServer API permissions for list_assets, asset system user mapping, and execution listing",
  "trace_id": "trace_uuid"
}
```

### 8.6.2 同步快照查询（初始化/增量一致性）

- 方法：`GET`
- 路径：
  - `/api/v1/sync/snapshots/latest`
  - `/api/v1/sync/snapshots`

用途：

- 查询最近一次同步快照（offset、next_offset、checksum）
- 查看一致性状态（`ok/warning/error/skipped/unknown`）
- 支持看板展示“同步是否健康”

补充说明（增量双轨）：

- `SYNC_INCREMENTAL_STRATEGY=auto|timestamp|full_compare`
- 当 `timestamp` 策略生效时，快照的 `consistency_status` 可能为 `skipped`（因为只同步变更集，不做全量计数比对）
- 当上游不支持更新时间过滤参数时，`auto` 会自动回退到 `full_compare`
- 当 `timestamp` 多次命中“上游资产缺少 `updated_at`”时，会触发保护：
  - 累计计数达到 `SYNC_TIMESTAMP_INEFFECTIVE_THRESHOLD`
  - 自动写入强制窗口 `SYNC_TIMESTAMP_FORCE_FULL_MINUTES`
  - 窗口内 `auto` 会临时改走 `full_compare`
- `full_compare` 的资产失效标记受护栏限制：
  - `SYNC_INACTIVATION_GUARDRAIL_RATIO`
  - `SYNC_INACTIVATION_GUARDRAIL_MAX`
  - 命中护栏时会阻断批量 `inactive` 变更，防止权限收敛导致误失效

示例响应（latest）：

```json
{
  "item": {
    "snapshot_id": "snapshot_uuid",
    "source": "jumpserver",
    "snapshot_type": "sync_tick",
    "offset": 100,
    "next_offset": 0,
    "page_size": 50,
    "fetched_assets": 20,
    "fetched_system_users": 35,
    "fetched_relations": 35,
    "upstream_total_assets": 120,
    "local_total_assets": 120,
    "local_total_system_users": 240,
    "local_total_relations": 240,
    "consistency_status": "ok",
    "consistency_delta_assets": 0,
    "checksum": "sha256_hex",
    "detail": "local assets count is consistent with upstream total",
    "created_at": "2026-04-02T14:30:00+00:00"
  },
  "trace_id": "trace_uuid"
}
```

### 8.6.2.0 手工触发预聚合任务（调试）

- 方法：`POST`
- 路径：`/api/v1/admin/metrics/preaggregation/run`
- 说明：
  - 仅在 `APP_ALLOW_ADMIN_DEBUG_ENDPOINTS=true` 时可用
  - 立即重建最近窗口内的失败分型与任务重试聚合桶
  - 常用于首次部署后预热看板数据

### 8.6.2.1 单资产精准刷新（调试）

- 方法：`POST`
- 路径：`/api/v1/admin/sync/assets/{jms_asset_id}/refresh`
- 说明：
  - 仅在 `APP_ALLOW_ADMIN_DEBUG_ENDPOINTS=true` 时可用
  - 用于 stale/expired 资产执行前快速刷新，不必触发全量同步
  - 步骤：按 `jms_asset_id` 查上游资产 -> 刷新资产投影 -> 同步系统用户映射 -> 失效已解除绑定关系

成功响应示例：

```json
{
  "status": "ok",
  "result": {
    "found": true,
    "asset_id": "local_asset_uuid",
    "jms_asset_id": "jms_asset_uuid",
    "users": 2,
    "relations_active": 2,
    "relations_inactivated": 1,
    "scan_pages": 1,
    "fresh_assets": 3,
    "stale_assets": 0,
    "expired_assets": 4727
  },
  "trace_id": "trace_uuid"
}
```

未命中响应示例：

```json
{
  "code": "ASSET_NOT_FOUND",
  "message": "asset not found on jumpserver: jms_asset_uuid",
  "trace_id": "trace_uuid"
}
```

执行闸门自动刷新（可选）：

- `EXECUTION_GATE_AUTO_REFRESH_ENABLED=true` 时，orchestrator 在 `ASSET_STALE/ASSET_EXPIRED` 命中后会先尝试一次精准刷新，再重试闸门
- 若刷新后资产变为 `fresh`，则继续执行；否则按最终闸门失败码失败
- 默认关闭，避免在高并发下引入额外上游查询压力
- 刷新查找策略：先按 `search` 查询，未命中时按分页做有界扫描（`EXECUTION_GATE_REFRESH_SCAN_PAGES`）

### 8.6.2.2 按任务刷新并重试（调试）

- 方法：`POST`
- 路径：`/api/v1/admin/tasks/{task_id}/refresh-retry`
- 说明：
  - 仅在 `APP_ALLOW_ADMIN_DEBUG_ENDPOINTS=true` 时可用
  - 仅支持 `status=failed` 且失败码属于：
    - `ASSET_STALE`
    - `ASSET_EXPIRED`
    - `ASSET_NOT_FOUND`
    - `ASSET_INACTIVE`
  - 执行动作：
    1. 按 `task.target_asset_id` 做一次单资产精准刷新
    2. 将任务重置为 `pending`
    3. 立即触发一次 orchestrator tick 尝试重跑

成功响应示例：

```json
{
  "status": "ok",
  "task_id": "task_uuid",
  "previous_failure_code": "ASSET_EXPIRED",
  "refresh_result": {
    "found": true,
    "jms_asset_id": "jms_asset_uuid",
    "users": 2
  },
  "orchestrator_result": {
    "created_executions": 1,
    "finished_executions": 0,
    "created_audit_links": 0
  },
  "task": {
    "task_id": "task_uuid",
    "status": "executing",
    "failure_code": null,
    "reason": "retry requested after asset refresh"
  },
  "trace_id": "trace_uuid"
}
```

### 8.6.2.3 批量按任务刷新并重试（调试）

- 方法：`POST`
- 路径：`/api/v1/admin/tasks/refresh-retry/batch`
- 说明：
  - 仅在 `APP_ALLOW_ADMIN_DEBUG_ENDPOINTS=true` 时可用
  - 支持两种筛选方式：
    - 指定 `task_ids`
    - 按最近 `hours` + 可选 `source` + `failure_codes` 筛选
- 仅处理 `status=failed` 任务
- 默认可重试失败码：`ASSET_STALE/ASSET_EXPIRED/ASSET_NOT_FOUND/ASSET_INACTIVE`
- `dry_run=true` 时仅返回“将要重试”的评估结果，不改数据
- 护栏与速率控制：
  - `hours` 会被 `TASK_REFRESH_RETRY_MAX_HOURS` 上限约束
  - 同一资产最近窗口内最多重试 `TASK_REFRESH_RETRY_SAME_ASSET_MAX_RETRIES` 次
  - 同一任务在冷却窗口内最多触发一次（`TASK_REFRESH_RETRY_TASK_COOLDOWN_MINUTES`）
  - 单次请求最多执行 `window_size * max_windows` 条（默认受 `TASK_REFRESH_RETRY_WINDOW_SIZE` 与 `TASK_REFRESH_RETRY_MAX_WINDOWS_PER_REQUEST` 约束）

请求体示例：

```json
{
  "hours": 24,
  "source": "api",
  "failure_codes": ["ASSET_STALE", "ASSET_EXPIRED"],
  "limit": 100,
  "window_size": 5,
  "max_windows": 2,
  "same_asset_max_retries": 2,
  "task_cooldown_minutes": 30,
  "dry_run": true
}
```

响应示例：

```json
{
  "status": "ok",
  "audit_id": "audit_uuid",
  "dry_run": false,
  "filters": {
    "hours": 24,
    "source": "api",
    "failure_codes": ["ASSET_EXPIRED", "ASSET_STALE"],
    "limit": 100,
    "window_size": 5,
    "max_windows": 2,
    "same_asset_max_retries": 2,
    "task_cooldown_minutes": 30
  },
  "summary": {
    "requested": 12,
    "missing_tasks": 0,
    "matched_by_failure": 8,
    "queued": 5,
    "skipped_non_retryable": 4,
    "skipped_in_progress": 1,
    "skipped_asset_not_found": 2,
    "skipped_rate_limited": 3,
    "skipped_asset_guardrail": 1,
    "skipped_task_cooldown": 1
  },
  "orchestrator_result": {
    "runs": 2,
    "created_executions": 5,
    "finished_executions": 0,
    "created_audit_links": 0,
    "window_size": 5
  },
  "items": [
    {
      "task_id": "task_uuid",
      "action": "queued",
      "final_status": "executing"
    }
  ],
  "trace_id": "trace_uuid"
}
```

### 8.6.2.4 批量重试审计查询（调试）

- 方法：`GET`
- 路径：
  - `/api/v1/admin/tasks/refresh-retry/audits`
  - `/api/v1/admin/tasks/refresh-retry/audits/{audit_id}`
  - `/api/v1/admin/tasks/refresh-retry/audits/{audit_id}/export?format=csv|json`
- 说明：
  - 仅在 `APP_ALLOW_ADMIN_DEBUG_ENDPOINTS=true` 时可用
  - 记录“谁在何时重试了哪些 task，结果如何”
- 审计主表包含：operator/source_ip/filter/summary/guardrail 结果
- 审计明细包含：每个 task 的 action（`queued/would_retry/skipped_*`）与最终状态

### 8.6.2.5 调度器自动批量重试（后台）

- 执行入口：`opspaw-scheduler.service`（非 HTTP 调试接口）
- 使用同一套批量重试逻辑与护栏，并写入 `task_retry_audit/task_retry_audit_item`
- 关键配置：
  - `TASK_REFRESH_RETRY_TASK_COOLDOWN_MINUTES`
  - `TASK_REFRESH_RETRY_SCHEDULER_ENABLED`
  - `TASK_REFRESH_RETRY_SCHEDULER_INTERVAL_SEC`
  - `TASK_REFRESH_RETRY_SCHEDULER_HOURS`
  - `TASK_REFRESH_RETRY_SCHEDULER_SOURCE`
  - `TASK_REFRESH_RETRY_SCHEDULER_FAILURE_CODES`
  - `TASK_REFRESH_RETRY_SCHEDULER_LIMIT`
  - `TASK_REFRESH_RETRY_SCHEDULER_WINDOW_SIZE`
  - `TASK_REFRESH_RETRY_SCHEDULER_MAX_WINDOWS`
  - `APPROVAL_TIMEOUT_HOURS`
  - `APPROVAL_EXPIRE_CHECK_INTERVAL_SEC`
  - `APPROVAL_EXPIRE_BATCH_SIZE`
  - `APPROVAL_ESCALATION_ENABLED`
  - `APPROVAL_ESCALATION_AFTER_MINUTES`
  - `APPROVAL_MAX_LEVELS`
  - `POLICY_BUILTIN_BLACKLIST`
  - `METRICS_PREAGGREGATION_SCHEDULER_ENABLED`
  - `METRICS_PREAGGREGATION_INTERVAL_SEC`
  - `METRICS_PREAGGREGATION_HOURLY_LOOKBACK_HOURS`
  - `METRICS_PREAGGREGATION_DAILY_LOOKBACK_DAYS`
- 批量重试调度默认关闭；建议先通过 `dry_run` API 观察审计结果，再开启自动模式
- 预聚合调度默认开启，用于降低看板实时聚合压力

列表查询参数（可选）：

- `operator_id`
- `task_id`
- `action`
- `limit/offset`

### 8.6.3 回调投递手动推进（调试）

- 方法：`POST`
- 路径：`/api/v1/admin/callback/tick`
- 说明：
  - 仅在 `APP_ALLOW_ADMIN_DEBUG_ENDPOINTS=true` 时可用
  - 触发一次回调投递扫描与重试（便于联调）

### 8.6.4 回调死信重放（调试）

- 方法：`POST`
- 路径：`/api/v1/admin/callback/deliveries/{delivery_id}/replay`
- 说明：
  - 仅在 `APP_ALLOW_ADMIN_DEBUG_ENDPOINTS=true` 时可用
  - 把死信/失败投递重置为 `pending` 并立即进入下一轮重试
  - `status=success` 的投递不允许重放（返回 `409 DELIVERY_NOT_REPLAYABLE`）

请求体（可选）：

```json
{
  "reset_attempts": true
}
```

响应示例：

```json
{
  "status": "ok",
  "item": {
    "delivery_id": "delivery_uuid",
    "status": "pending",
    "attempts": 0,
    "max_attempts": 8,
    "next_retry_at": "2026-04-02T15:10:00+00:00",
    "last_http_status": null,
    "last_error": ""
  },
  "trace_id": "trace_uuid"
}
```

### 8.6.5 回调投递查询（调试）

- 方法：`GET`
- 路径：`/api/v1/admin/callback/deliveries`
- 说明：
  - 仅在 `APP_ALLOW_ADMIN_DEBUG_ENDPOINTS=true` 时可用
  - 支持按 `status/task_id/error_contains` 查询
  - 支持 `limit/offset` 分页

示例：

```http
GET /api/v1/admin/callback/deliveries?status=dead&error_contains=timeout&limit=50&offset=0
```

### 8.6.6 回调批量重放（调试）

- 方法：`POST`
- 路径：`/api/v1/admin/callback/deliveries/replay`
- 说明：
  - 仅在 `APP_ALLOW_ADMIN_DEBUG_ENDPOINTS=true` 时可用
  - 可按 `delivery_ids` 精确重放，或按 `status/task_id/error_contains` 条件重放
  - 支持 `dry_run=true` 先查看命中与跳过数量，不写库
  - `status=success` 的投递会自动跳过
  - 受护栏限制：`replayable` 数超过 `CALLBACK_REPLAY_MAX_APPLY` 时返回 `400 CALLBACK_REPLAY_LIMIT_EXCEEDED`
  - 建议调用方传 `X-Operator-Id` 记录操作者（用于审计）

请求体示例：

```json
{
  "status": "dead",
  "task_id": "",
  "error_contains": "timeout",
  "limit": 100,
  "reset_attempts": true,
  "dry_run": false
}
```

响应示例：

```json
{
  "status": "ok",
  "audit_id": "audit_uuid",
  "dry_run": false,
  "matched": 12,
  "replayed": 10,
  "skipped_non_replayable": 2,
  "filters": {
    "delivery_ids": [],
    "status": "dead",
    "task_id": null,
    "error_contains": "timeout",
    "limit": 100
  },
  "items": [
    {
      "delivery_id": "delivery_uuid",
      "status": "pending",
      "attempts": 0
    }
  ],
  "skipped_items": [],
  "trace_id": "trace_uuid"
}
```

### 8.6.7 回调重放审计查询（调试）

- 方法：`GET`
- 路径：`/api/v1/admin/callback/replay-audits`
- 查询参数：
  - `operator_id`：可选，按操作者过滤
  - `limit` / `offset`：分页
- 说明：
  - 单条重放与批量重放都会落审计
  - 审计包含：操作者、来源 IP、是否 dry-run、命中/重放数量、是否被护栏拦截

### 8.7 当前失败码集合

- `UPSTREAM_ERROR`
- `PERMISSION_DENIED`
- `CONNECTIVITY_ERROR`
- `UPSTREAM_BAD_RESPONSE`
- `VALIDATION_ERROR`
- `ASSET_NOT_FOUND`（执行前未找到资产投影）
- `ASSET_INACTIVE`（执行前资产状态为 inactive）
- `ASSET_STALE`（执行前资产新鲜度为 stale，当前默认拦截）
- `ASSET_EXPIRED`（执行前资产新鲜度为 expired，默认拦截）
- `EXECUTION_TIMEOUT`
- `EXECUTION_FAILED`
- `INTERNAL_ERROR`
- `CANCELED`（任务取消状态码）

兼容旧数据：若历史 `reason` 没有失败码前缀，系统会按关键字进行推断归类，无法识别时归为 `UNKNOWN`。
