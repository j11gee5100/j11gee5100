from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import UserAccount

PBKDF2_ITERATIONS = 210_000
TOKEN_PREFIX = "opspaw-dev-token"
TOKEN_VERSION = "opspaw-v1"


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("ascii"))


def _token_secret() -> bytes:
    # Development default keeps local setup simple; deployments should set
    # APP_TOKEN_SECRET/OPSPAW_TOKEN_SECRET through environment management.
    secret = getattr(settings, "auth_token_secret", "") or getattr(settings, "app_token_secret", "") or "opspaw-dev-secret-change-me"
    return secret.encode("utf-8")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def hash_password(password: str, salt: str | None = None) -> str:
    salt_bytes = base64.b64decode(salt) if salt else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt_bytes, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${base64.b64encode(salt_bytes).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, stored_hash: str) -> bool:
    if not stored_hash or not stored_hash.startswith("pbkdf2_sha256$"):
        return False
    try:
        _algo, iterations, salt, digest = stored_hash.split("$", 3)
        computed = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), base64.b64decode(salt), int(iterations))
        return hmac.compare_digest(base64.b64encode(computed).decode(), digest)
    except Exception:
        return False


def default_password_for(username: str) -> str:
    return "admin123" if username == "admin" else "user123"


def ensure_password(item: UserAccount) -> None:
    if not item.password_hash:
        item.password_hash = hash_password(default_password_for(item.username))
        item.password_changed_at = _utc_now()


def make_token(item: UserAccount) -> str:
    now = _utc_now()
    ttl_hours = int(getattr(settings, "auth_token_ttl_hours", 12) or 12)
    payload: dict[str, Any] = {
        "sub": item.id,
        "username": item.username,
        "role": item.role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=ttl_hours)).timestamp()),
        "nonce": secrets.token_urlsafe(12),
    }
    payload_part = _b64url_encode(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(_token_secret(), f"{TOKEN_VERSION}.{payload_part}".encode("ascii"), hashlib.sha256).digest()
    return f"{TOKEN_VERSION}.{payload_part}.{_b64url_encode(signature)}"


def _parse_signed_token(token: str) -> dict[str, Any] | None:
    try:
        version, payload_part, signature_part = token.split(".", 2)
        if version != TOKEN_VERSION:
            return None
        expected = hmac.new(_token_secret(), f"{version}.{payload_part}".encode("ascii"), hashlib.sha256).digest()
        supplied = _b64url_decode(signature_part)
        if not hmac.compare_digest(expected, supplied):
            return None
        payload = json.loads(_b64url_decode(payload_part).decode("utf-8"))
        if int(payload.get("exp", 0)) < int(_utc_now().timestamp()):
            return None
        if not payload.get("sub") or not payload.get("username") or not payload.get("role"):
            return None
        return payload
    except Exception:
        return None


def parse_token(token: str) -> tuple[str, str] | None:
    """Return lightweight identity claims after signature/expiry verification.

    DB-backed checks such as account existence/enabled status are intentionally
    handled by validate_token_user() for endpoints that need strict auth.
    """
    payload = _parse_signed_token(token)
    if not payload:
        return None
    return str(payload["username"]), str(payload["role"])


def validate_token_user(session: Session, token: str) -> tuple[UserAccount | None, str]:
    payload = _parse_signed_token(token)
    if not payload:
        return None, "INVALID_TOKEN"
    item = session.get(UserAccount, str(payload["sub"]))
    if not item or item.username != payload.get("username"):
        return None, "USER_NOT_FOUND"
    if not item.enabled:
        return None, "USER_DISABLED"
    if item.role != payload.get("role"):
        return None, "TOKEN_STALE"
    return item, ""


def authenticate(session: Session, username: str, password: str) -> tuple[UserAccount | None, str]:
    item = session.scalar(select(UserAccount).where(UserAccount.username == username))
    if not item:
        return None, "INVALID_CREDENTIALS"
    ensure_password(item)
    if not item.enabled:
        return None, "USER_DISABLED"
    if not verify_password(password, item.password_hash):
        return None, "INVALID_CREDENTIALS"
    item.last_login_at = _utc_now()
    session.flush()
    return item, ""


def _format_dt(value):
    return value.isoformat() if value else None


def build_auth_user_response(item: UserAccount) -> dict:
    return {
        "user_id": item.id,
        "username": item.username,
        "display_name": item.display_name,
        "role": item.role,
        "enabled": item.enabled,
        "last_login_at": _format_dt(item.last_login_at),
        "password_changed_at": _format_dt(item.password_changed_at),
    }


def build_login_response(item: UserAccount) -> dict:
    return {"access_token": make_token(item), "token_type": "bearer", "user": build_auth_user_response(item)}
