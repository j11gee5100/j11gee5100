# Skill DSL 设计（v0.1）

## 1. 目标

Skill 是可复用运维能力单元，用于约束 Agent 行为，避免自由命令失控。

设计目标：

- 可读：便于运维人员审核
- 可控：可绑定风险等级与策略
- 可执行：可被引擎解析为稳定流程

## 2. DSL 最小结构

建议采用 YAML：

```yaml
id: nginx_service_recovery
name: Nginx Service Recovery
product: nginx
issue_type: service_down
risk_level: safe-write

precheck:
  - check_permission
  - check_asset_online

observe:
  - template: check_nginx_status
  - template: check_nginx_config
  - template: read_nginx_error_log

decisions:
  - when: "config_invalid"
    then: escalate
  - when: "inactive && config_ok"
    then: restart_nginx_safe

actions:
  - id: restart_nginx_safe
    template: restart_nginx

verify:
  - template: verify_nginx_process
  - template: verify_nginx_port
  - template: verify_http_health

escalate:
  - on_unknown_pattern
  - on_repeat_failure
```

## 3. 风险等级建议

- `readonly`：只读命令，不改系统状态
- `safe-write`：低风险可逆动作
- `high-risk`：高风险写操作，必须审批
- `forbidden`：禁止自动执行

## 4. Skill 生命周期

- 草稿：从 SOP/工单经验抽取
- 测试：在非生产环境回放验证
- 发布：版本化上线
- 复盘：依据执行结果迭代

## 5. 与策略引擎协作

Skill 执行前后由策略引擎检查：

- 资产范围是否越界
- 命令模板是否在白名单
- 当前环境是否允许该风险等级
- 是否满足审批条件

