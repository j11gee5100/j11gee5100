from __future__ import annotations

from typing import Any
import hashlib
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from app.core.config import settings
from app.db.session import session_scope
from app.mcp.service import MCP_PROTOCOL_VERSION, McpError, ToolContext, call_tool, mcp_tools_list, prompts_list, read_resource, resources_list
from app.services.auth_service import validate_token_user

router = APIRouter(prefix="/mcp", tags=["mcp"])


def _client_script_path() -> Path:
    mounted_app_root = Path(__file__).resolve().parents[2]
    candidates = [
        # Production containers mount current/app -> /app/app, but do not mount current/scripts.
        # Prefer this app-local copy so MCP launcher auto-update sees the latest client sha.
        mounted_app_root / "mcp" / "inference_env_mcp_stdio.py",
        Path(__file__).resolve().parents[3] / "scripts" / "inference_env_mcp_stdio.py",
        Path.cwd() / "scripts" / "inference_env_mcp_stdio.py",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def _client_script_bytes() -> bytes:
    path = _client_script_path()
    if not path.exists():
        raise McpError("MCP_CLIENT_NOT_FOUND", f"MCP stdio client not found: {path}")
    return path.read_bytes()


def _client_version(data: bytes) -> str:
    digest = hashlib.sha256(data).hexdigest()
    return f"{settings.app_version}-{digest[:12]}"


def _external_base_url(request: Request) -> str:
    configured = getattr(settings, "mcp_client_public_base_url", "") or ""
    if configured.strip():
        return configured.strip().rstrip("/")
    return str(request.base_url).rstrip("/")


def _rpc_result(request_id: Any, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _rpc_error(request_id: Any, code: int, message: str, data: dict | None = None) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message, "data": data or {}}}


def _ctx(request: Request) -> ToolContext:
    auth = (request.headers.get("authorization") or "").strip()
    if not auth.lower().startswith("bearer "):
        raise McpError("AUTH_REQUIRED", "MCP requires login bearer token")
    token = auth.split(" ", 1)[1].strip()
    with session_scope() as session:
        user, error = validate_token_user(session, token)
        if not user:
            message_by_error = {
                "INVALID_TOKEN": "invalid or expired bearer token",
                "USER_NOT_FOUND": "token user no longer exists",
                "USER_DISABLED": "token user is disabled",
                "TOKEN_STALE": "token role is stale; please login again",
            }
            raise McpError(error or "INVALID_TOKEN", message_by_error.get(error, "invalid bearer token"))
        return ToolContext(
            operator_id=user.username,
            operator_role=user.role,
            session_id=request.headers.get("mcp-session-id", ""),
            client_name=request.headers.get("x-mcp-client", request.headers.get("user-agent", "mcp-client"))[:128],
        )


@router.get("")
def mcp_info():
    return {
        "name": "inference-env-delivery-mcp",
        "protocolVersion": MCP_PROTOCOL_VERSION,
        "enabled": settings.mcp_enabled,
        "transport": "streamable-http-jsonrpc",
    }




@router.get("/client/manifest")
def mcp_client_manifest(request: Request):
    data = _client_script_bytes()
    digest = hashlib.sha256(data).hexdigest()
    base_url = _external_base_url(request)
    return {
        "name": "opspaw-inference-env-mcp-stdio",
        "version": _client_version(data),
        "sha256": digest,
        "download_url": f"{base_url}/mcp/client/inference_env_mcp_stdio.py",
        "launcher_url": f"{base_url}/mcp/client/inference_env_mcp_launcher.py",
        "base_url": base_url,
        "auto_update": True,
    }


@router.get("/client/inference_env_mcp_stdio.py", response_class=PlainTextResponse)
def download_mcp_stdio_client():
    return PlainTextResponse(_client_script_bytes().decode("utf-8"), media_type="text/x-python; charset=utf-8")


@router.get("/client/inference_env_mcp_launcher.py", response_class=PlainTextResponse)
def download_mcp_launcher_client():
    path = _client_script_path().with_name("inference_env_mcp_launcher.py")
    if not path.exists():
        raise McpError("MCP_LAUNCHER_NOT_FOUND", f"MCP launcher not found: {path}")
    return PlainTextResponse(path.read_text(encoding="utf-8"), media_type="text/x-python; charset=utf-8")


@router.post("")
async def mcp_jsonrpc(request: Request):
    if not settings.mcp_enabled:
        return JSONResponse(status_code=404, content={"code": "MCP_DISABLED", "message": "MCP endpoint disabled"})
    try:
        _ctx(request)
    except McpError as exc:
        return JSONResponse(status_code=401, content={"code": exc.code, "message": exc.message})
    body = await request.json()
    if isinstance(body, list):
        return [await _handle_rpc(item, request) for item in body]
    return await _handle_rpc(body, request)


async def _handle_rpc(body: dict, request: Request):
    request_id = body.get("id")
    method = body.get("method")
    params = body.get("params") or {}
    ctx = _ctx(request)
    try:
        if method == "initialize":
            return _rpc_result(request_id, {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "serverInfo": {"name": "inference-env-delivery-mcp", "version": "0.1.0"},
                "capabilities": {"tools": {}, "resources": {}, "prompts": {}},
            })
        if method == "tools/list":
            return _rpc_result(request_id, mcp_tools_list())
        if method == "tools/call":
            name = params.get("name", "")
            arguments = params.get("arguments") or {}
            result = call_tool(name, arguments, ctx)
            return _rpc_result(request_id, {"content": [{"type": "text", "text": __import__("json").dumps(result, ensure_ascii=False)}], "structuredContent": result})
        if method == "resources/list":
            return _rpc_result(request_id, resources_list())
        if method == "resources/read":
            return _rpc_result(request_id, read_resource(params.get("uri", ""), ctx))
        if method == "prompts/list":
            return _rpc_result(request_id, prompts_list())
        if method == "notifications/initialized":
            return _rpc_result(request_id, {})
        return _rpc_error(request_id, -32601, f"method not found: {method}")
    except McpError as exc:
        return _rpc_error(request_id, -32000, exc.message, {"code": exc.code, "retryable": exc.retryable})
    except Exception as exc:
        return _rpc_error(request_id, -32603, str(exc))
