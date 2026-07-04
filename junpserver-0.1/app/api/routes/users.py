from __future__ import annotations

from fastapi import APIRouter, Query, Request

from app.api.dependencies import conflict_response, current_operator, is_admin_role, missing_response, permission_denied
from app.core.trace import get_trace_id
from app.db.session import session_scope
from app.models import UserAccount
from app.schemas.user_account import CreateUserAccountRequest, UpdateUserAccountRequest
from app.services.auth_service import hash_password
from app.services.user_account_service import build_user_account_response, get_user, list_users, set_if_present

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.get("")
def list_user_accounts(request: Request, limit: int = Query(default=100, ge=1, le=500), offset: int = Query(default=0, ge=0)):
    _username, role = current_operator(request)
    if not is_admin_role(role):
        return permission_denied()
    with session_scope() as session:
        items, total = list_users(session, limit=limit, offset=offset)
        return {"items": [build_user_account_response(item) for item in items], "total": total, "limit": limit, "offset": offset, "trace_id": get_trace_id()}


@router.get("/login-options")
def list_login_user_options():
    with session_scope() as session:
        items, total = list_users(session, limit=500, offset=0)
        return {"items": [build_user_account_response(item) for item in items if item.enabled], "total": total, "limit": 500, "offset": 0, "trace_id": get_trace_id()}


@router.post("")
def create_user_account(payload: CreateUserAccountRequest, request: Request):
    _username, role = current_operator(request)
    if not is_admin_role(role):
        return permission_denied()
    with session_scope() as session:
        existing = get_user(session, payload.username)
        if existing:
            return conflict_response(f"user exists: {payload.username}")
        data = payload.model_dump(exclude={"password"})
        item = UserAccount(**data)
        item.password_hash = hash_password(payload.password)
        session.add(item)
        session.flush()
        return {"status": "ok", "item": build_user_account_response(item), "trace_id": get_trace_id()}


@router.patch("/{user_id}")
def update_user_account(user_id: str, payload: UpdateUserAccountRequest, request: Request):
    _username, role = current_operator(request)
    if not is_admin_role(role):
        return permission_denied()
    with session_scope() as session:
        item = get_user(session, user_id)
        if not item:
            return missing_response(f"user not found: {user_id}")
        fields = [field for field in UpdateUserAccountRequest.model_fields.keys() if field != "password"]
        set_if_present(item, payload, fields)
        if payload.password:
            item.password_hash = hash_password(payload.password)
        session.flush()
        return {"status": "ok", "item": build_user_account_response(item), "trace_id": get_trace_id()}
