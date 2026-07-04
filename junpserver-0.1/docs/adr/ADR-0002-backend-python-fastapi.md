# ADR-0002: 后端采用 Python + FastAPI + SQLAlchemy

- 状态：Accepted
- 日期：2026-04-02

## 背景

OpsPaw 后端需要同时处理：

- JumpServer API 集成
- 异步任务与同步链路
- 任务状态机与策略引擎
- OpenAPI 与 Web API
- AI 上下文构造与证据卡逻辑

## 决策

后端技术栈采用：

- `Python 3.12`
- `FastAPI`
- `Pydantic v2`
- `SQLAlchemy 2`
- `Alembic`
- `httpx`

## 备选方案

- Go + Gin/Fiber
- Java + Spring Boot
- Node.js + NestJS

## 选择理由

- Python 对运维自动化、HTTP 集成、AI 集成都更贴近现阶段需求
- FastAPI 适合快速构建清晰的 OpenAPI 和内部接口
- SQLAlchemy 与 PostgreSQL 的组合足够成熟
- 团队在 MVP 阶段更需要交付速度和适中复杂度

## 结果

优点：

- 开发效率高
- 运维和 AI 场景适配度高
- 生态成熟

代价：

- 需要对异步和类型建模保持纪律
- 高并发极限能力不如部分编译型语言栈

