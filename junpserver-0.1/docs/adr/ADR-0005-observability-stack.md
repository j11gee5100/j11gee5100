# ADR-0005: 观测采用 OpenTelemetry + Prometheus + Grafana + Loki

- 状态：Accepted
- 日期：2026-04-02

## 背景

OpsPaw 不是普通 CRUD 系统，核心风险来自：

- 上游 JumpServer 波动
- 状态机竞态
- 回调失败
- 同步不一致
- 审计链断裂

没有统一观测，问题会很难排查。

## 决策

采用：

- `OpenTelemetry` 统一 trace
- `Prometheus` 采集指标
- `Grafana` 展示仪表盘
- `Loki` 存储与查询日志

## 备选方案

- 仅记录应用日志
- 引入更重的商业 APM 作为起点

## 选择理由

- 这套组合足够成熟，且与云原生生态兼容
- 可以打通日志、指标、trace
- 能支持任务链路、同步链路、JumpServer 调用链路的可观测

## 结果

优点：

- 问题定位能力强
- 成本可控
- 便于后续扩展

代价：

- 需要在代码里认真埋点和统一字段规范

