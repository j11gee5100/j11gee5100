# ADR-0008: Linux 服务器环境下的 MVP 部署基线

- 状态：Accepted
- 日期：2026-04-02
- Supersedes：ADR-0006

## 背景

现在已经明确，OpsPaw 的实际运行环境是 Linux 服务器。

这意味着部署决策需要优先考虑：

- 单机或少量 Linux 服务器快速落地
- 运维团队对 `systemd`、`Nginx`、`Docker Compose` 的熟悉度
- 试点阶段的交付速度与可维护性

如果在这一前提下仍默认采用 Kubernetes，会带来额外复杂度：

- 容器平台维护成本
- 发布与配置管理复杂度
- 调试与故障定位路径更长

## 决策

在 Linux 服务器环境下，OpsPaw 的 MVP/试点阶段采用：

- 本地开发：`Docker Compose`
- Linux 测试/生产：`Nginx + Docker Compose + systemd`

部署建议：

- `Nginx`：统一入口，处理 HTTPS、静态文件、反向代理
- `Docker Compose`：编排 `ops-api`、workers、PostgreSQL、Redis、MinIO（可选）
- `systemd`：负责主 stack 的开机自启、故障拉起、日志集成

## 备选方案

- Linux 服务器直接跑裸进程
- 测试/生产直接上 Kubernetes
- 本地与线上完全不同部署方式

## 选择理由

相比裸进程：

- Compose 更容易统一依赖和环境
- 服务依赖关系更清晰
- 本地与线上更接近

相比 Kubernetes：

- 更适合当前明确的 Linux 服务器场景
- 上手与交付更快
- 运维复杂度显著更低

## 推荐拓扑

- `nginx`
- `ops-api`
- `orchestrator-worker`
- `sync-worker`
- `callback-worker`
- `scheduler`
- `postgresql`
- `redis`
- `minio`（按需）

## 结果

优点：

- 更贴近当前运行环境
- MVP 落地更快
- 运维和排障路径更短

代价：

- 多机弹性能力有限
- 高可用和滚动升级能力不如成熟 Kubernetes 平台

## 何时重评估

满足以下条件之一时，再评估切换到 Kubernetes 或统一 PaaS：

- 已有成熟容器平台可直接复用
- 需要多节点水平扩缩容
- 需要更复杂的灰度发布或多环境统一治理
- Worker 与任务规模超出单机/少量 Linux 服务器承载范围

