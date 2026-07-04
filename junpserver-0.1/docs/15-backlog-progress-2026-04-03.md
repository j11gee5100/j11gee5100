# OpsPaw Backlog 进度快照（2026-04-03）

本清单基于 `docs/07-backlog-roadmap.md` 的 ID 做当前实现状态盘点。

状态定义：

- `done`：代码与接口已可验证
- `partial`：已落地部分能力，仍有缺口
- `todo`：尚未开始或未达到可用标准

## 1. P0/P1 核心项快照

| ID | 状态 | 备注 |
|---|---|---|
| B1-01 Adapter 认证客户端 | done | JumpServer v3/v4 适配、token 调用已联通 |
| B1-02 契约测试与 Mock | done | JumpServer v3/v4 关键接口契约测试已覆盖（模式探测、分页、字段归一化、回退链路、增量参数失败路径） |
| B1-03 上游健康检查与降级判断 | done | `check/capabilities/permission-check` 已上线 |
| B2-01 资产全量初始化同步 | done | 初始化入库、分页同步、快照已可用 |
| B2-02 系统用户同步与映射 | done | 映射入库与关系同步已实现 |
| B2-03 初始化快照与一致性校验 | done | snapshot + checksum + consistency 字段可查询 |
| B2-04 增量同步双轨 | done | timestamp/full_compare 双轨与回退已实现 |
| B2-05 新鲜度与失效标记 | done | `freshness_status` + gate 已上线 |
| B3-01 任务模型与状态机 | done | 任务生命周期、执行与失败分类可运行 |
| B3-02 幂等与状态迁移保护 | done | `idempotency_key` 去重可用 |
| B3-03 场景路由规则引擎 | partial | 模板化执行有基础，规则引擎能力仍需增强 |
| B3-05 任务取消 | done | 取消接口已上线并有状态保护 |
| B4-01 模板注册表 | done | 命令模板中心接口（列表/创建/更新）与任务创建模板化执行已上线 |
| B4-02 JumpServer 执行封装 | done | 执行发起、查询、超时兜底已实现 |
| B4-03 执行结果轮询与聚合 | done | execution 查询与错误分型已可用 |
| B4-04 审计关联落库 | done | `task/execution/jms/audit_link` 链路可查询 |
| B5-01 风险分级引擎 | done | 请求风险+模板风险+命令推断风险三者合并取高，统一触发审批门禁 |
| B5-02 黑名单硬拦截 | done | 内建+可配置黑名单规则生效，命中即 `POLICY_BLOCKED` 拦截 |
| B5-03 审批流与升级 | done | 高风险任务 `approval_pending`、审批查询/决策接口、超时自动过期与审计动作已实现 |
| B6-01 创建任务接口 | done | `/api/v1/tasks` 已可用 |
| B6-02 查询任务/执行接口 | done | task/execution/failure summary 已可用 |
| B6-03 取消任务接口 | done | `/api/v1/tasks/{id}/cancel` 已可用 |
| B6-04 回调重试/死信 | done | callback 重试、重放、审计已实现 |
| B6-05 审计摘要接口 | done | `/api/v1/audits/summary` 已新增 |
| B6-06 回调白名单与签名 | done | 回调安全策略与签名校验已实现 |

## 2. 新增（超出原清单的近期增强）

- 任务失败分型看板接口（含预聚合读取）
- 任务重试看板接口（含预聚合读取）
- 预聚合调度、手工触发、健康状态与告警级别接口
- 失败分型修复建议模板（含上下文增强与场景提示）
- 批量 refresh-retry 护栏（速率窗口、同资产上限、任务冷却）
- 批量重试审计查询与 JSON/CSV 导出
- 看板聚合接口：`/api/v1/dashboard/overview`、`/api/v1/dashboard/failures/{failure_code}/detail`
- 治理审计查询：`/api/v1/governance/audits`
- 审批升级策略：自动/手工升级（多级审批链）

## 3. 下一阶段建议优先级

1. Web 页面联调（模板中心、策略评估、看板详情、审批分级视图）  
2. 模板发布流程增强（版本冻结、灰度发布、回滚）  
3. 审批链路增强（审批人路由策略、自动转交通知）  
4. 故障演练自动化（JumpServer 超时/403/接口漂移）  
