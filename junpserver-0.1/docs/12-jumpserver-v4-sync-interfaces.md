# JumpServer v4 同步接口映射（OpsPaw）

## 1. 结论

在 `v4.10.16-ce` 上，OpsPaw 同步主数据可用接口存在，但与旧版路径不同。

可用于同步的核心接口：

- 资产列表：
  - `GET /api/v1/assets/assets/`（管理员视角）
  - `GET /api/v1/perms/users/my/assets/`（当前用户可见资产视角）
- 资产账号（等价旧版 system-user）：
  - `GET /api/v1/accounts/accounts/?asset_id=<asset_uuid>&limit=<n>&offset=<m>`

另外，v4 的执行链路与旧版不同：

- 旧版执行接口 `/api/v1/ops/command-executions/` 在 v4 CE 默认不可用
- 可用替代路径：
  - 创建执行：`POST /api/v1/ops/jobs/`（`instant=true`, `type=adhoc`）
  - 状态查询：`GET /api/v1/ops/job-execution/task-detail/{task_id}/`
  - 详情查询：`GET /api/v1/ops/job-executions/{id}/`

注意：需先开启设置项 `SECURITY_COMMAND_EXECUTION=true`，否则会返回 `403 命令执行已禁用`。

## 2. 与旧版接口对照

| 能力 | 旧版（v3 兼容） | 新版（v4.10.16-ce） |
|---|---|---|
| 资产列表 | `/api/v1/perms/users/assets/` | `/api/v1/perms/users/my/assets/` 或 `/api/v1/assets/assets/` |
| 资产系统用户 | `/api/v1/perms/users/assets/{asset_id}/system-users/` | `/api/v1/accounts/accounts/?asset_id={asset_id}` |
| 命令执行 | `/api/v1/ops/command-executions/` | 该路径在 v4 CE 默认不存在（需走新任务模型） |

## 3. 已验证样例（172.24.26.12）

## 3.1 资产接口

```http
GET /api/v1/assets/assets/?limit=5&offset=0
```

返回字段含：`id`, `name`, `address`, `date_created`, `date_updated` 等。

## 3.2 账号接口

```http
GET /api/v1/accounts/accounts/?asset_id=<asset_uuid>&limit=5&offset=0
```

返回字段含：`id`, `name`, `username`, `asset`, `date_created`, `date_updated` 等。

## 4. 增量同步能力说明

当前 v4 CE 接口不提供明确的 `updated_at>=...` 过滤参数（实测传入会被忽略）。

建议增量策略：

1. 按 `ordering=-date_updated` + 分页拉取
2. 在 OpsPaw 侧维护 `last_seen_date_updated + id` 检查点
3. 对命中窗口做 upsert 去重

这属于“近实时增量 + 本地幂等”策略，而非上游严格游标增量。

## 5. OpsPaw 当前适配状态

`app/services/jumpserver/client.py` 已支持自动探测并切换：

- `legacy_v3`：使用旧路径
- `v4`：使用新版资产与账号路径

当前同步链路与执行链路均已具备 v3/v4 兼容能力：

- 同步：资产与账号映射自动切换到 v4 端点
- 执行：创建任务使用 `POST /api/v1/ops/jobs/`，状态查询使用 `task-detail`/`job-executions`

另外，`/api/v1/integrations/jumpserver/capabilities` 可直接输出 `api_mode`、`SECURITY_COMMAND_EXECUTION` 与执行查询可达性，便于定位“配置开关”与“账号权限”问题。
