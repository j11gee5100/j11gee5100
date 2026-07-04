# OpsPaw 技术选型 ADR 集（v0.1）

## 1. 说明

`09-tech-selection.md` 不再维护为单篇技术选型说明，而是作为 ADR 集入口页。

目的：

- 把“技术选型”拆成可独立演进的决策文档
- 让未来替换某一项技术时，只变更对应 ADR
- 让架构、研发、运维、评审都能清楚看到每个决策的上下文、取舍和影响

## 2. ADR 清单

- [ADR-0000](F:\junpserver\docs\adr\ADR-0000-record-architecture-decisions.md)：采用 ADR 机制管理关键技术决策
- [ADR-0001](F:\junpserver\docs\adr\ADR-0001-mvp-architecture-modular-monolith.md)：MVP 采用模块化单体 + 独立 Worker
- [ADR-0002](F:\junpserver\docs\adr\ADR-0002-backend-python-fastapi.md)：后端采用 Python + FastAPI + SQLAlchemy
- [ADR-0003](F:\junpserver\docs\adr\ADR-0003-postgresql-redis-celery.md)：主库、缓存与任务执行采用 PostgreSQL + Redis + Celery
- [ADR-0004](F:\junpserver\docs\adr\ADR-0004-frontend-react-typescript.md)：前端采用 React + TypeScript + Vite
- [ADR-0005](F:\junpserver\docs\adr\ADR-0005-observability-stack.md)：观测采用 OpenTelemetry + Prometheus + Grafana + Loki
- [ADR-0006](F:\junpserver\docs\adr\ADR-0006-deployment-model.md)：部署采用 Compose for dev，Kubernetes for test/prod
- [ADR-0007](F:\junpserver\docs\adr\ADR-0007-auth-secrets-and-llm-abstraction.md)：认证、密钥与 LLM 集成采用统一抽象层
- [ADR-0008](F:\junpserver\docs\adr\ADR-0008-linux-server-deployment-baseline.md)：Linux 服务器环境下的 MVP 部署基线

## 3. 当前核心结论

当前阶段已经明确的主决策：

- 架构：先做模块化单体，不做重微服务
- 后端：`Python + FastAPI + SQLAlchemy`
- 数据与队列：`PostgreSQL + Redis + Celery`
- 前端：`React + TypeScript + Vite + Ant Design + TanStack Query`
- 观测：`OpenTelemetry + Prometheus + Grafana + Loki`
- 部署：`Docker Compose` 本地开发，Linux 服务器上优先 `Docker Compose + systemd + Nginx`，`Kubernetes` 仅在已有平台或规模化后再启用
- 集成：JumpServer 凭据进入密钥管理系统，LLM 通过统一 provider 抽象接入

## 4. 维护方式

- 新决策：新增 ADR，不修改历史 ADR 的决策结论
- 决策变更：新增一条 ADR 说明“替代/废弃/升级”关系
- 实施前发生重大变化时，同步更新相关 ADR 的状态

## 5. 推荐下一步

在进入开发前，建议优先基于 ADR 跑 5 个 Spike：

- JumpServer 契约 Spike
- 同步性能 Spike
- 状态机与回调竞态 Spike
- Prompt Injection 防护 Spike
- UI 骨架 Spike
