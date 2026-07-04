# JumpServer PENDING 诊断报告（2026-04-02）

## 1. 诊断目标

确认当前 `command-execution` 长时间 `PENDING` 的主因是否来自：

- OpsPaw 调用错误
- 账号权限不足
- JumpServer 上游异步链路（celery/queue/result backend）

## 2. 诊断环境

- OpsPaw API：`172.24.26.12:18080`
- JumpServer：`http://172.24.26.12`
- 使用账号：`wanger/ghyghy`（通过 token 调用）
- 诊断时间：`2026-04-02 18:00 ~ 18:40 CST`

## 3. 关键证据

## 3.1 权限核验结果：通过

- `GET /api/v1/users/profile/` -> `200`
- `GET /api/v1/perms/users/assets/?limit=3` -> `200`，可见资产总数 `4727`
- `GET /api/v1/perms/users/assets/{asset_id}/system-users/` -> `200`，可见系统用户 `7`
- `POST /api/v1/ops/command-executions/` -> `201`（可成功创建执行）

结论：不是“无权限导致无法创建执行”问题。

## 3.2 新建执行后状态

示例执行 ID：

- `c2a4c44a-19fd-4d1c-b557-0ea2c19e9f84`
- `2e50d53d-d44b-45b9-bf95-2a2f3998a277`

观测结果：

- `GET /api/v1/ops/command-executions/{id}/` -> `is_finished=false`
- `GET /api/v1/ops/celery/task/{id}/result/` -> `state=PENDING`
- `GET /api/v1/ops/celery/task/{id}/log/` -> `等待任务开始`
- `GET /api/v1/ops/ansible/task/{id}/log/` -> `等待任务开始`

## 3.3 真实 ID 与随机 ID 对照

对随机 UUID 访问：

- `GET /ops/celery/task/{random_uuid}/result/` -> `PENDING`
- `GET /ops/celery/task/{random_uuid}/log/` -> `等待任务开始`

对真实 execution id 访问，返回与随机 UUID 同形态。

这说明：任务状态未进入有效执行推进阶段。

## 3.4 OpenAPI 路由能力确认

从 `GET /api/docs/openapi.json` 解析路径：

- 共 `201` 个 path
- 与 celery 相关仅公开：
  - `/ops/celery/task/{id}/log/`
  - `/ops/celery/task/{id}/result/`
- 未发现可直接查看 worker/queue 的公开 API（如 workers/queues/inspect 类端点）

结论：需进入 JumpServer 主机层排查 worker/broker/result backend。

## 4. 排除项与结论

已排除：

- OpsPaw 调用参数格式错误（可 201 创建）
- 账号基础权限缺失（profile/assets/system-users 均正常）

高概率根因：

- JumpServer 上游 celery 异步链路未推进（worker 未消费、broker 阻塞、或 result backend 异常）

## 5. 对 JumpServer 团队的直接请求

请在 JumpServer 运行节点执行以下核查：

1. celery worker 进程是否存活，是否持续消费队列  
2. broker（Redis/RabbitMQ）队列是否积压、是否有 consumer  
3. result backend 是否可写、是否超时  
4. core/worker 日志是否存在连接失败、鉴权失败、traceback  
5. 最近是否有升级、配置变更、重启导致 worker 未恢复

详细命令见：

- `docs/10-jumpserver-pending-runbook.md`

## 6. OpsPaw 侧当前保护

- 已启用执行超时兜底，避免任务永久卡死
- 失败会被归类并可被失败分型看板统计
- 但在上游恢复前，真实执行成功率会持续受影响
