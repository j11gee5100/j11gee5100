from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.trace import get_trace_id
from app.services.auth_service import parse_token


def current_operator(request: Request) -> tuple[str, str]:
    auth = (request.headers.get("authorization") or "").strip()
    if auth.lower().startswith("bearer "):
        parsed = parse_token(auth.split(" ", 1)[1].strip())
        if parsed:
            return parsed
    username = (request.headers.get("x-operator-id") or "zhangsan").strip()[:64] or "zhangsan"
    role = (request.headers.get("x-operator-role") or "user").strip().lower()[:32] or "user"
    if username == "admin":
        role = "admin"
    return username, role


def is_admin_role(role: str) -> bool:
    return role.lower() == "admin"


def permission_denied(message: str = "admin role required") -> JSONResponse:
    return JSONResponse(status_code=403, content={"code": "PERMISSION_DENIED", "message": message, "trace_id": get_trace_id()})


def missing_response(message: str) -> JSONResponse:
    return JSONResponse(status_code=404, content={"code": "NOT_FOUND", "message": message, "trace_id": get_trace_id()})


def conflict_response(message: str) -> JSONResponse:
    return JSONResponse(status_code=409, content={"code": "CONFLICT", "message": message, "trace_id": get_trace_id()})


def invalid_request_response(code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=400, content={"code": code, "message": message, "trace_id": get_trace_id()})
