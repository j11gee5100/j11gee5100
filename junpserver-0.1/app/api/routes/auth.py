from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.core.trace import get_trace_id
from app.db.session import session_scope
from app.schemas.user_account import LoginRequest
from app.services.auth_service import authenticate, build_auth_user_response, build_login_response, validate_token_user
from app.services.user_account_service import ensure_default_users

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login")
def login(payload: LoginRequest):
    with session_scope() as session:
        ensure_default_users(session)
        item, error = authenticate(session, payload.username, payload.password)
        if error == "USER_DISABLED":
            return JSONResponse(status_code=403, content={"code": "USER_DISABLED", "message": "user disabled", "trace_id": get_trace_id()})
        if not item:
            return JSONResponse(status_code=401, content={"code": "INVALID_CREDENTIALS", "message": "invalid username or password", "trace_id": get_trace_id()})
        return {**build_login_response(item), "trace_id": get_trace_id()}


@router.get("/me")
def me(request: Request):
    auth = (request.headers.get("authorization") or "").strip()
    if not auth.lower().startswith("bearer "):
        return JSONResponse(status_code=401, content={"code": "AUTH_REQUIRED", "message": "login bearer token required", "trace_id": get_trace_id()})
    with session_scope() as session:
        item, error = validate_token_user(session, auth.split(" ", 1)[1].strip())
        if not item:
            status = 403 if error == "USER_DISABLED" else 401
            return JSONResponse(status_code=status, content={"code": error or "INVALID_TOKEN", "message": "invalid or expired bearer token", "trace_id": get_trace_id()})
        return {"user": build_auth_user_response(item), "trace_id": get_trace_id()}
