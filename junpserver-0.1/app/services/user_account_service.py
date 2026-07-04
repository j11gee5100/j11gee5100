from __future__ import annotations

from datetime import datetime
from typing import Iterable

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import UserAccount
from app.services.auth_service import default_password_for, ensure_password, hash_password


def format_dt(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def set_if_present(item, payload: BaseModel, fields: Iterable[str]) -> None:
    for field in fields:
        value = getattr(payload, field)
        if value is not None:
            setattr(item, field, value)


def build_user_account_response(item: UserAccount) -> dict:
    return {
        "user_id": item.id,
        "username": item.username,
        "display_name": item.display_name,
        "role": item.role,
        "password_configured": bool(item.password_hash),
        "last_login_at": format_dt(item.last_login_at),
        "password_changed_at": format_dt(item.password_changed_at),
        "enabled": item.enabled,
        "created_at": format_dt(item.created_at),
        "updated_at": format_dt(item.updated_at),
    }


def ensure_default_users(session: Session) -> None:
    defaults = [
        {"username": "admin", "display_name": "系统管理员", "role": "admin", "enabled": True},
        {"username": "zhangsan", "display_name": "张三", "role": "user", "enabled": True},
        {"username": "lisi", "display_name": "李四", "role": "user", "enabled": True},
    ]
    for data in defaults:
        exists = session.scalar(select(UserAccount).where(UserAccount.username == data["username"]))
        if not exists:
            item = UserAccount(**data)
            item.password_hash = hash_password(default_password_for(item.username))
            session.add(item)
        else:
            ensure_password(exists)
    session.flush()


def list_users(session: Session, limit: int, offset: int) -> tuple[list[UserAccount], int]:
    ensure_default_users(session)
    total = int(session.scalar(select(func.count()).select_from(UserAccount)) or 0)
    items = list(session.scalars(select(UserAccount).order_by(UserAccount.username.asc()).offset(offset).limit(limit)))
    return items, total


def get_user(session: Session, user_id: str) -> UserAccount | None:
    return session.get(UserAccount, user_id) or session.scalar(select(UserAccount).where(UserAccount.username == user_id))
