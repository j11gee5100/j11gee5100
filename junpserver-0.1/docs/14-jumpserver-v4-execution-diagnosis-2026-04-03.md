# JumpServer v4 执行诊断报告（2026-04-03）

## 1. 诊断目标

确认当前环境是否仍存在“上游 celery `PENDING` 长时间卡死”问题，并定位最近执行失败的主因。

## 2. 诊断环境

- OpsPaw API: `http://172.24.26.12:18080`
- JumpServer: `http://127.0.0.1`（OpsPaw 服务器本机）
- 探针脚本：`python scripts/probe_jumpserver.py --pending-diagnosis`
- 诊断时间：`2026-04-03 09:55 ~ 10:05 CST`

## 3. 关键证据

### 3.1 平台健康

- `GET /api/v1/health/` 返回：`status=true, db_status=true, redis_status=true`

结论：JumpServer 基础依赖健康。

### 3.2 执行链路状态（v4）

- `Detected API mode: v4`
- `command_executions_brief.unfinished = 0`
- `pending_diagnosis.running_items = 0`

结论：当前没有“任务长期未结束”的现象，不符合旧版 celery `PENDING` 卡死特征。

### 3.3 最近失败分型（来自 `v4_execution_probe_rows`）

- SSH 认证失败（密码不正确）：
  - 典型错误：`Invalid/incorrect password ... Permission denied`
- 目标主机不可达（网络超时）：
  - 典型错误：`connect to host ... port 22: Connection timed out`

结论：当前失败主要是“目标连接/凭证问题”，不是 JumpServer 队列未推进。

## 4. 根因判断

在 `2026-04-03` 这次 v4 环境验证中：

- 高概率根因：`AUTH_FAILED` + `CONNECT_TIMEOUT`
- 低概率根因：celery worker/broker/result backend 异常（本次未命中）

## 5. 立即修复建议

1. 修复资产登录凭据（系统用户密码/密钥），优先处理 `Permission denied` 资产。
2. 对失败资产执行网络可达性检查（22 端口、路由、防火墙、sshd）。
3. 修复后用同一命令进行回放验证，确认 `is_finished=true` 且 `is_success=true`。
4. 继续保留 OpsPaw 执行超时兜底，防止单任务长时间占用。

## 6. 持续验证建议

- 每次变更后执行：
  - `python scripts/probe_jumpserver.py --pending-diagnosis`
- 重点观察：
  - `pending_diagnosis.running_items`
  - `v4_root_cause_hints.reason_counts`
  - `v4_root_cause_hints.likely_root_cause`

若后续出现 `running_items` 持续 > 0，再按 `docs/10-jumpserver-pending-runbook.md` 进入 worker/queue 层排查。
