from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CommandBlacklistRule, CommandTemplate, GovernanceAudit


RISK_SEVERITY = {
    "readonly": 1,
    "safe-write": 2,
    "high-risk": 3,
}

READONLY_PREFIXES = (
    "cat ",
    "ls",
    "pwd",
    "whoami",
    "hostname",
    "uptime",
    "df ",
    "free ",
    "ps ",
    "top ",
    "grep ",
    "find ",
    "echo ",
    "id",
    "uname",
)

SAFE_WRITE_KEYWORDS = (
    "systemctl restart",
    "systemctl reload",
    "systemctl start",
    "systemctl stop",
    "service ",
)

HIGH_RISK_KEYWORDS = (
    "rm -rf",
    "mkfs",
    "dd if=",
    "shutdown",
    "reboot",
    "poweroff",
    "useradd",
    "usermod",
    "userdel",
    "passwd",
    "chmod ",
    "chown ",
    "iptables",
    "firewall-cmd",
    "sudo ",
    "crontab ",
)

DEFAULT_BUILTIN_BLACKLIST = (
    "rm -rf /",
    "mkfs",
    "shutdown -h",
    "reboot",
    "poweroff",
    ":(){:|:&};:",
)


def normalize_risk_level(value: str | None) -> str:
    text = (value or "").strip().lower()
    if text in RISK_SEVERITY:
        return text
    return "readonly"


def merge_risk_level(*levels: str | None) -> str:
    candidate = "readonly"
    for level in levels:
        normalized = normalize_risk_level(level)
        if RISK_SEVERITY[normalized] > RISK_SEVERITY[candidate]:
            candidate = normalized
    return candidate


def infer_risk_level_from_command(command: str) -> str:
    text = (command or "").strip().lower()
    if not text:
        return "readonly"
    if any(keyword in text for keyword in HIGH_RISK_KEYWORDS):
        return "high-risk"
    if any(keyword in text for keyword in SAFE_WRITE_KEYWORDS):
        return "safe-write"
    if text.startswith(READONLY_PREFIXES):
        return "readonly"
    return "safe-write"


def parse_builtin_blacklist(raw: str | None) -> list[str]:
    values: list[str] = []
    for part in (raw or "").split(","):
        pattern = part.strip()
        if not pattern:
            continue
        if pattern not in values:
            values.append(pattern)
    return values


def list_enabled_blacklist_rules(session: Session) -> list[CommandBlacklistRule]:
    stmt = (
        select(CommandBlacklistRule)
        .where(CommandBlacklistRule.enabled.is_(True))
        .order_by(CommandBlacklistRule.created_at.asc(), CommandBlacklistRule.id.asc())
    )
    return list(session.scalars(stmt))


def _match_rule(command: str, pattern: str) -> bool:
    if not pattern:
        return False
    return pattern.lower() in command.lower()


def evaluate_command_policy(
    *,
    session: Session,
    command: str,
    builtin_blacklist_raw: str | None,
    requested_risk_level: str | None,
    template_risk_level: str | None,
) -> dict:
    builtins = parse_builtin_blacklist(builtin_blacklist_raw)
    if not builtins:
        builtins = list(DEFAULT_BUILTIN_BLACKLIST)

    matched_patterns: list[dict] = []
    for pattern in builtins:
        if _match_rule(command, pattern):
            matched_patterns.append(
                {
                    "source": "builtin",
                    "rule_id": "",
                    "pattern": pattern,
                    "hard_block": True,
                    "description": "builtin hard block",
                }
            )

    for rule in list_enabled_blacklist_rules(session):
        if _match_rule(command, rule.pattern):
            matched_patterns.append(
                {
                    "source": "db",
                    "rule_id": rule.id,
                    "pattern": rule.pattern,
                    "hard_block": bool(rule.hard_block),
                    "description": rule.description,
                }
            )

    inferred_risk = infer_risk_level_from_command(command)
    final_risk = merge_risk_level(requested_risk_level, template_risk_level, inferred_risk)
    hard_block_match = next((item for item in matched_patterns if item["hard_block"]), None)

    return {
        "allowed": hard_block_match is None,
        "matched": matched_patterns,
        "block_reason": (
            f"command matched hard blacklist pattern: {hard_block_match['pattern']}" if hard_block_match else ""
        ),
        "inferred_risk_level": inferred_risk,
        "final_risk_level": final_risk,
        "approval_required": final_risk == "high-risk",
    }


def record_governance_audit(
    *,
    session: Session,
    entity_type: str,
    entity_id: str,
    action: str,
    operator_id: str,
    source_ip: str,
    detail: dict,
) -> GovernanceAudit:
    payload = json.dumps(detail, ensure_ascii=True, separators=(",", ":"))
    item = GovernanceAudit(
        entity_type=(entity_type or "")[:32],
        entity_id=(entity_id or "")[:64],
        action=(action or "")[:32],
        operator_id=(operator_id or "unknown")[:64],
        source_ip=(source_ip or "unknown")[:64],
        detail_json=payload[:4096],
    )
    session.add(item)
    session.flush()
    return item


def create_command_template(
    *,
    session: Session,
    template_id: str,
    name: str,
    description: str,
    command: str,
    risk_level: str,
    enabled: bool,
    operator_id: str,
) -> CommandTemplate:
    item = CommandTemplate(
        template_id=template_id[:64],
        name=name[:128],
        description=description[:1024],
        command=command[:2048],
        risk_level=normalize_risk_level(risk_level),
        enabled=enabled,
        created_by=(operator_id or "unknown")[:64],
        updated_by=(operator_id or "unknown")[:64],
    )
    session.add(item)
    session.flush()
    return item


def get_template_by_template_id(session: Session, template_id: str) -> CommandTemplate | None:
    return session.scalar(select(CommandTemplate).where(CommandTemplate.template_id == template_id))


def update_command_template(
    *,
    template: CommandTemplate,
    name: str | None,
    description: str | None,
    command: str | None,
    risk_level: str | None,
    enabled: bool | None,
    operator_id: str,
) -> CommandTemplate:
    if name is not None:
        template.name = name[:128]
    if description is not None:
        template.description = description[:1024]
    if command is not None:
        template.command = command[:2048]
    if risk_level is not None:
        template.risk_level = normalize_risk_level(risk_level)
    if enabled is not None:
        template.enabled = enabled
    template.updated_by = (operator_id or "unknown")[:64]
    return template


def create_blacklist_rule(
    *,
    session: Session,
    pattern: str,
    description: str,
    hard_block: bool,
    enabled: bool,
    operator_id: str,
) -> CommandBlacklistRule:
    item = CommandBlacklistRule(
        pattern=pattern[:255],
        description=description[:1024],
        hard_block=hard_block,
        enabled=enabled,
        created_by=(operator_id or "unknown")[:64],
        updated_by=(operator_id or "unknown")[:64],
    )
    session.add(item)
    session.flush()
    return item


def update_blacklist_rule(
    *,
    rule: CommandBlacklistRule,
    pattern: str | None,
    description: str | None,
    hard_block: bool | None,
    enabled: bool | None,
    operator_id: str,
) -> CommandBlacklistRule:
    if pattern is not None:
        rule.pattern = pattern[:255]
    if description is not None:
        rule.description = description[:1024]
    if hard_block is not None:
        rule.hard_block = hard_block
    if enabled is not None:
        rule.enabled = enabled
    rule.updated_by = (operator_id or "unknown")[:64]
    return rule


def calculate_next_escalate_at(*, now_utc: datetime, escalate_after_minutes: int) -> datetime | None:
    if escalate_after_minutes <= 0:
        return None
    return now_utc + timedelta(minutes=max(1, escalate_after_minutes))
