# JumpServer Celery PENDING 排障 Runbook（v0.1）

## 1. 已确认现象（2026-04-02）

通过 OpsPaw 与 JumpServer 联调，已确认：

- `GET /api/v1/ops/command-executions/` 返回的执行记录长期 `is_finished=false`
- 对真实 `execution_id` 查询：
  - `GET /api/v1/ops/celery/task/{id}/result/` -> `state=PENDING`
  - `GET /api/v1/ops/celery/task/{id}/log/` -> `等待任务开始`
- 对随机 UUID 查询，返回与真实 ID 一致（同样 `PENDING + 等待任务开始`）

这通常意味着：任务未被 worker 消费或结果后端未推进（而不是单条任务参数错误）。

## 2. 快速结论边界

- OpsPaw 侧已加超时兜底，任务不会无限卡住
- 当前阻塞点在 JumpServer 上游异步执行链路（Celery/Broker/Result Backend）
- 优先排查顺序：`worker 存活 -> broker 可消费 -> result backend 可写`

## 3. 10 分钟快速排查

## 3.1 API 健康检查

在可访问 JumpServer 的机器执行：

```bash
curl -sS http://<jumpserver>/api/v1/health/
```

期望：

- `status=true`
- `db_status=true`
- `redis_status=true`

如果这里就异常，先修复基础依赖。

## 3.2 复现实验（真实 ID vs 随机 ID）

```bash
curl -sS -H "Authorization: Bearer <token>" \
  "http://<jumpserver>/api/v1/ops/command-executions/?limit=3&offset=0"

# 对一个真实 execution_id
curl -sS -H "Authorization: Bearer <token>" \
  "http://<jumpserver>/api/v1/ops/celery/task/<real_id>/result/"
curl -sS -H "Authorization: Bearer <token>" \
  "http://<jumpserver>/api/v1/ops/celery/task/<real_id>/log/"

# 对随机 UUID
curl -sS -H "Authorization: Bearer <token>" \
  "http://<jumpserver>/api/v1/ops/celery/task/<random_uuid>/result/"
curl -sS -H "Authorization: Bearer <token>" \
  "http://<jumpserver>/api/v1/ops/celery/task/<random_uuid>/log/"
```

若两者返回一致，几乎可判定是队列/worker链路问题。

## 4. JumpServer 主机侧排查（优先执行）

## 4.1 识别部署形态

```bash
# 容器化部署
docker ps --format '{{.Names}}\t{{.Status}}' | grep -Ei 'jumpserver|jms|core|celery|redis|rabbit'

# systemd 部署
systemctl list-units --type=service | grep -Ei 'jumpserver|jms|celery|redis|rabbit|mq'
```

## 4.2 检查 worker 是否存活

```bash
# 容器日志（按实际容器名替换）
docker logs --tail=200 <core_or_worker_container> | grep -Ei 'celery|worker|ready|error|traceback'

# 进程视角
ps -ef | grep -Ei 'celery.*worker' | grep -v grep
```

判定：

- 没有 celery worker 进程 -> 直接修复 worker 启动
- 有 worker 但持续报 broker 连接失败 -> 转 4.3
- 有 worker 且无消费日志 -> 转 4.3/4.4

## 4.3 检查 broker（Redis/RabbitMQ）

```bash
# Redis 可达性
redis-cli -h <redis_host> -p <redis_port> ping

# RabbitMQ 可达性（若使用 RabbitMQ）
rabbitmqctl list_queues name messages consumers
```

判定：

- 队列消息积压且 consumers=0 -> worker 未消费
- queue 正常但 worker 无法 ack -> worker/broker 鉴权或网络问题

## 4.4 检查 result backend

```bash
# 从 JumpServer 运行节点测试结果后端连通
redis-cli -h <result_backend_host> -p <port> ping
```

如果 worker 执行了但 result backend 不可写，API 常表现为长期 `PENDING`。

## 4.5 核对时钟与时区

```bash
date
timedatectl status
```

严重时钟偏差会导致任务状态更新异常或延迟。

## 4.6 查看 JumpServer 核心错误日志

```bash
# 容器化
docker logs --tail=500 <jumpserver_core_container>

# systemd
journalctl -u <jumpserver_core_service> -n 500 --no-pager
```

重点检索：

- `broker connection refused`
- `authentication failed`
- `result backend timeout`
- `task revoked`
- `traceback`

## 5. 修复后回归验证

1. 发起一条最小命令（如 `hostname`）
2. 观测 60 秒内状态变化：
   - `command-executions/{id}` 从 `is_finished=false` -> `true`
   - `celery/task/{id}/result` 从 `PENDING` -> `SUCCESS/FAILURE`
3. 在 OpsPaw 侧验证：
   - `GET /api/v1/tasks/{task_id}/executions` 能拿到最终状态
   - `GET /api/v1/executions/{execution_id}` 能拿到 `failure_code` 或成功结果

## 6. 给 JumpServer 团队的最小信息包

建议一次性提供以下信息，减少来回沟通：

- 出问题时间窗口（精确到分钟）
- 3 个真实 `execution_id`
- 1 个随机 UUID 对照结果
- `/api/v1/health/` 返回值
- worker/broker/result backend 的关键日志片段
- 是否容器化部署、版本号、最近变更（升级/重启/配置改动）

## 7. OpsPaw 当前临时兜底策略

- 已启用执行超时失败（`EXECUTION_TIMEOUT`）
- 任务不会永久卡死
- 仍建议尽快修复上游异步链路，否则成功执行率会持续受影响
