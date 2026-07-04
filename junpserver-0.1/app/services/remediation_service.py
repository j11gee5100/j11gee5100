from __future__ import annotations

from app.core.failure import infer_failure_code


_TEMPLATES: dict[str, dict] = {
    "CONNECTIVITY_ERROR": {
        "title": "目标主机连通性失败",
        "severity": "high",
        "summary": "执行节点无法连通目标资产（超时/拒绝/路由不可达）。",
        "recommended_actions": [
            "检查目标资产 22 端口可达性与安全组/防火墙规则。",
            "确认目标主机 sshd 服务正常且监听地址正确。",
            "确认 JumpServer 到目标网段的路由与 DNS 解析正常。",
        ],
        "verification_steps": [
            "在 JumpServer 节点执行连通性探测（tcp/icmp）。",
            "在 OpsPaw 重新发起只读命令（如 hostname）验证恢复。",
        ],
    },
    "PERMISSION_DENIED": {
        "title": "执行权限不足",
        "severity": "high",
        "summary": "当前账号对资产或命令执行能力无权限。",
        "recommended_actions": [
            "检查 JumpServer 资产授权与系统用户绑定是否完整。",
            "确认命令执行开关开启且命令未命中黑名单。",
            "核对系统用户凭据（密码/密钥）是否正确。",
        ],
        "verification_steps": [
            "使用同一账号在 JumpServer 控制台手工执行最小命令。",
            "确认 API `permission-check` 中 required checks 全部通过。",
        ],
    },
    "ASSET_STALE": {
        "title": "资产快照过期（stale）",
        "severity": "medium",
        "summary": "本地资产投影已陈旧，执行闸门拒绝继续下发。",
        "recommended_actions": [
            "触发单资产刷新，确认资产与系统用户映射最新。",
            "检查同步任务是否延迟或分页中断。",
            "必要时使用批量 refresh-retry（带速率与冷却护栏）。",
        ],
        "verification_steps": [
            "检查 `sync/snapshots` 新鲜度与一致性字段。",
            "观察任务重试审计是否从 `skipped_*` 转为 `queued`。",
        ],
    },
    "ASSET_EXPIRED": {
        "title": "资产快照失效（expired）",
        "severity": "high",
        "summary": "本地资产快照超过失效阈值，需先刷新再执行。",
        "recommended_actions": [
            "立即触发单资产刷新并复查系统用户映射。",
            "检查 JumpServer 增量接口与全量回退策略是否正常。",
            "确认同步调度器运行状态与最近日志无异常。",
        ],
        "verification_steps": [
            "确认资产 freshness 状态变为 active/fresh。",
            "对同一任务执行 refresh-retry 并观察最终状态。",
        ],
    },
    "ASSET_NOT_FOUND": {
        "title": "资产不存在或不可见",
        "severity": "high",
        "summary": "目标资产在本地投影中不存在，或上游不可见。",
        "recommended_actions": [
            "核对资产 ID 是否正确且属于当前环境。",
            "检查 JumpServer 账号是否具备该资产可见权限。",
            "执行一次资产刷新并确认返回 found=true。",
        ],
        "verification_steps": [
            "在 JumpServer 控制台可检索到目标资产。",
            "OpsPaw 资产中心中出现同一 jms_asset_id。",
        ],
    },
    "ASSET_INACTIVE": {
        "title": "资产被标记为 inactive",
        "severity": "medium",
        "summary": "资产投影处于 inactive，执行被闸门阻断。",
        "recommended_actions": [
            "检查最近同步是否命中 inactivation guardrail。",
            "核对资产在 JumpServer 侧状态是否真实下线。",
            "必要时执行单资产刷新恢复 active 状态。",
        ],
        "verification_steps": [
            "确认同步快照中未出现异常大规模 inactivation。",
            "验证该资产恢复为 active 后任务可继续执行。",
        ],
    },
    "EXECUTION_TIMEOUT": {
        "title": "执行超时",
        "severity": "medium",
        "summary": "上游执行未在时限内完成，已被超时机制兜底。",
        "recommended_actions": [
            "检查 JumpServer 最近执行队列积压与 worker 状态。",
            "评估命令本身是否耗时过长或存在阻塞。",
            "根据场景调整执行超时阈值并灰度验证。",
        ],
        "verification_steps": [
            "观察相同任务重试后的平均耗时变化。",
            "确认 P95 执行时延回落到目标范围。",
        ],
    },
    "UPSTREAM_ERROR": {
        "title": "上游接口错误",
        "severity": "high",
        "summary": "调用 JumpServer 接口时返回非预期错误状态。",
        "recommended_actions": [
            "核对上游 API 路由版本与参数兼容性。",
            "检查调用 token 是否过期、权限是否收敛。",
            "排查 JumpServer 服务日志中的对应 trace/window。",
        ],
        "verification_steps": [
            "同请求在 JumpServer OpenAPI 页面可成功复现/恢复。",
            "OpsPaw 接口错误率在观测窗口内回落。",
        ],
    },
    "UPSTREAM_BAD_RESPONSE": {
        "title": "上游响应不完整",
        "severity": "medium",
        "summary": "上游响应字段缺失或不符合契约。",
        "recommended_actions": [
            "记录异常响应样本并与 JumpServer 团队对齐契约。",
            "短期增加回退逻辑（查询补全/重试）防止任务卡死。",
            "在 CI 中补充契约测试防止回归。",
        ],
        "verification_steps": [
            "抽样验证关键字段（execution_id/status）完整率。",
            "确认同类错误在新版本中消失。",
        ],
    },
    "VALIDATION_ERROR": {
        "title": "请求参数校验失败",
        "severity": "low",
        "summary": "任务输入参数不满足接口或策略校验要求。",
        "recommended_actions": [
            "检查任务入参必填项和格式约束。",
            "补充前端/API 请求参数校验提示。",
            "为常见错误输入增加示例模板。",
        ],
        "verification_steps": [
            "复测同类请求返回 2xx 且无校验错误。",
        ],
    },
    "EXECUTION_FAILED": {
        "title": "执行失败（命令已下发）",
        "severity": "medium",
        "summary": "任务已执行但返回失败，需结合 stderr/summary 定位。",
        "recommended_actions": [
            "先检查命令是否可幂等重试并评估风险等级。",
            "提取失败主机明细，区分权限、路径、依赖缺失等类型。",
            "针对高频失败脚本补充前置检查步骤。",
        ],
        "verification_steps": [
            "复测后失败率下降，且失败原因集中度降低。",
        ],
    },
    "INTERNAL_ERROR": {
        "title": "系统内部错误",
        "severity": "high",
        "summary": "OpsPaw 内部处理流程出现异常。",
        "recommended_actions": [
            "按 trace_id 检索 API/worker 日志并定位堆栈。",
            "回滚最近变更或开启降级路径保护执行链路。",
            "补充回归用例覆盖该异常路径。",
        ],
        "verification_steps": [
            "同链路压测与回归测试通过。",
        ],
    },
    "CANCELED": {
        "title": "任务已取消",
        "severity": "low",
        "summary": "任务被主动取消，通常无需自动修复。",
        "recommended_actions": [
            "确认取消原因是否符合变更窗口与审批要求。",
            "必要时以新任务重新提交执行。",
        ],
        "verification_steps": [
            "确保无残留 running execution。",
        ],
    },
    "UNKNOWN": {
        "title": "未知失败类型",
        "severity": "medium",
        "summary": "失败原因暂无法自动分类，建议先做人工分型。",
        "recommended_actions": [
            "收集原始错误信息并补充 failure_code 映射规则。",
            "按连接、权限、参数、上游异常四类先人工归类。",
            "把高频未知错误沉淀为可复用模板。",
        ],
        "verification_steps": [
            "UNKNOWN 占比在后续版本中持续下降。",
        ],
    },
}


def normalize_failure_code(value: str | None) -> str:
    code = (value or "").strip().upper().replace("-", "_")
    if not code:
        return "UNKNOWN"
    return code


def infer_or_normalize_failure_code(value: str | None) -> str:
    normalized = normalize_failure_code(value)
    if normalized != "UNKNOWN":
        return normalized
    inferred = infer_failure_code(value)
    return normalize_failure_code(inferred)


def list_remediation_templates() -> list[dict]:
    items = []
    for code in sorted(_TEMPLATES.keys()):
        payload = {
            "title": _TEMPLATES[code]["title"],
            "severity": _TEMPLATES[code]["severity"],
            "summary": _TEMPLATES[code]["summary"],
            "recommended_actions": list(_TEMPLATES[code].get("recommended_actions", [])),
            "verification_steps": list(_TEMPLATES[code].get("verification_steps", [])),
        }
        payload["failure_code"] = code
        items.append(payload)
    return items


def get_remediation_template(failure_code: str | None) -> tuple[str, bool, dict]:
    normalized = infer_or_normalize_failure_code(failure_code)
    template = _TEMPLATES.get(normalized)
    if template:
        payload = {
            "title": template["title"],
            "severity": template["severity"],
            "summary": template["summary"],
            "recommended_actions": list(template.get("recommended_actions", [])),
            "verification_steps": list(template.get("verification_steps", [])),
        }
        payload["failure_code"] = normalized
        return normalized, True, payload

    fallback = {
        "title": _TEMPLATES["UNKNOWN"]["title"],
        "severity": _TEMPLATES["UNKNOWN"]["severity"],
        "summary": _TEMPLATES["UNKNOWN"]["summary"],
        "recommended_actions": list(_TEMPLATES["UNKNOWN"].get("recommended_actions", [])),
        "verification_steps": list(_TEMPLATES["UNKNOWN"].get("verification_steps", [])),
    }
    fallback["failure_code"] = "UNKNOWN"
    return normalized, False, fallback


def get_contextual_remediation_template(
    *,
    failure_code: str | None,
    source: str | None,
    risk_level: str | None,
    resolved_from: str,
) -> tuple[str, bool, dict]:
    normalized, matched, template = get_remediation_template(failure_code)
    source_key = (source or "").strip().lower()
    risk_key = (risk_level or "").strip().lower()
    context_hints: list[str] = []

    if source_key == "api":
        context_hints.append("API 调用场景：优先检查 idempotency_key 去重与调用方重试策略。")
    elif source_key == "web":
        context_hints.append("Web 自用场景：建议结合审批链路与人工确认记录进行复核。")
    elif source_key:
        context_hints.append(f"来源场景 `{source_key}`：请确认该来源的权限模型与默认模板是否一致。")

    if risk_key == "high-risk":
        context_hints.append("高风险任务：修复动作执行前需再次审批，禁止自动批量重试。")
    elif risk_key == "safe-write":
        context_hints.append("safe-write 任务：建议先在 1 台资产灰度验证，再逐步放量。")
    elif risk_key == "readonly":
        context_hints.append("readonly 任务：优先做无副作用探测，确认根因后再进入写操作。")

    if resolved_from == "execution":
        context_hints.append("建议结合 execution.result_summary 与 JumpServer 原始日志交叉验证。")
    elif resolved_from == "task":
        context_hints.append("建议先核对任务级 reason 与最新执行记录是否一致。")

    if normalized in {"ASSET_STALE", "ASSET_EXPIRED", "ASSET_INACTIVE"}:
        context_hints.append("资产新鲜度相关错误：可先走 refresh-retry 快捷链路，减少人工切换。")

    enriched = dict(template)
    enriched["context_hints"] = context_hints
    return normalized, matched, enriched
