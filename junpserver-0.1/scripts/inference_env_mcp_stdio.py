#!/usr/bin/env python3
from __future__ import annotations

import json
import mimetypes
import os
from pathlib import Path
import secrets
import sys
import urllib.error
import urllib.request

BASE_URL = os.environ.get("INFERENCE_ENV_MCP_BASE_URL", "http://127.0.0.1:18080").rstrip("/")
TOKEN = ""
CURRENT_USER: dict | None = None

ENV_PACKAGE_README = """# 推理环境包制作指南（Agent/MCP）

新窗口初次连接后，请先读取 `opspaw://inference-env/readme`。

最小环境包资产只需要两段脚本：

1. `install_script`：安装脚本。
2. `verify_script`：安装后成功检查脚本。

不需要 `check.sh` / `check_script`。

推荐流程：

1. 调用 `mcp_login` 登录。
2. 调用 `resources/read` 读取 `opspaw://inference-env/readme`。
3. 调用 `list_allowed_package_roots` 确认可登记文件根目录。
4. 调用 `list_device_profiles` 选择适配配置。
5. 从实施手册和资源目录识别环境包资产。强关联源码包可以整理成一个组合资产。
6. Agent 必须在本地先生成资产归档 tar.gz。自动安装类环境包归档内建议包含：`README.md`、`install.sh`、`verify.sh`、`payload/`；应用包只作为交付资源携带，可保留原始目录形态，不要求被交付框架自动执行。
7. 调用 `upload_env_package_file` 上传本地 tar.gz 到系统存储，拿到真实 `file_uri/file_name/checksum`。
8. 调用 `register_env_package` 或 `update_env_package` 登记资产，必须使用上传工具返回的 `file_uri/checksum`，禁止编造 `filesystem:///data/...` 路径。
9. 调用 `list_env_packages` 检查资产是否可见；文件型资产必须能在后续审计中通过 payload 检查。
10. 调用 `create_delivery_bundle_draft` / `update_delivery_bundle_composition` 编排交付包。
11. 调用 `audit_delivery_bundle` 审计，出现 `PAYLOAD_FILE_MISSING` 必须回到第 6-8 步补包/上传/更新。
12. 调用 `build_delivery_bundle_artifact` 制作完整包。
13. 调用 `get_delivery_bundle_build_job` 查询后台制作结果。

安装脚本规则：使用 `set -Eeuo pipefail`，从 `${BASH_SOURCE[0]}` 定位小包目录，不假设资源在 `/root`，安装路径优先使用 `THIRDPART_PATH=${THIRDPART_PATH:-/usr/local/Ascend/thirdpart/$(uname -m)}`，多阶段编译应记录状态文件，失败后可重跑跳过已完成阶段。

`.bashrc` 环境变量写入约定：写入 `/root/.bashrc` 必须使用固定标记块，禁止无标记重复追加；每次写入前先删除旧标记块，再写入新标记块；标记块应放在 `.bashrc` 前部，避免被 `[ -z "$PS1" ] && return` 提前跳过；通用 MBAB 包不要内置项目环境变量，项目专用环境变量应放到独立命令步骤包中处理。

推荐写法：

```bash
BASHRC="/root/.bashrc"
TMP="$(mktemp)"

sed '/# >>> OpsPaw MBAB runtime env >>>/,/# <<< OpsPaw MBAB runtime env <<</d' "$BASHRC" > "$TMP"

{
  cat <<'EOF'
# >>> OpsPaw MBAB runtime env >>>
export PATH="/usr/local/python3.8/bin:/usr/local/Ascend/thirdpart/aarch64/bin:${PATH:-/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin}"
export LD_LIBRARY_PATH="/usr/local/python3.8/lib:/usr/local/Ascend/thirdpart/aarch64/lib:/usr/local/Ascend/thirdpart/aarch64/lib64:/usr/local/lib:${LD_LIBRARY_PATH:-}"
export PKG_CONFIG_PATH="/usr/local/lib/pkgconfig:/usr/local/Ascend/thirdpart/aarch64/lib/pkgconfig:/usr/local/Ascend/thirdpart/aarch64/lib64/pkgconfig:${PKG_CONFIG_PATH:-}"
export THIRDPART_PATH="/usr/local/Ascend/thirdpart/aarch64"
# <<< OpsPaw MBAB runtime env <<<

EOF
  cat "$TMP"
} > "$BASHRC"

rm -f "$TMP"
```

验证方式：`/bin/bash -i -l -c 'source /root/.profile; echo "$PATH"; echo "$LD_LIBRARY_PATH"; command -v python3; python3 --version'`。

禁止写法：`echo 'export PATH=...' >> /root/.bashrc`，`echo 'ulimit -SHn 655350' >> /root/.bashrc`。

成功检查脚本规则：检查最终库/命令/文件是否存在，例如 `libopencv_core.so`、`libavcodec.so`、`ffmpeg -version`，不要只 echo。

应用包类型：`package_type=application_package`。应用包用于业务程序、模型服务、前后处理脚本工程等资源。最新规则：应用包只随交付包放入 `application_packages/` 目录，不进入交付包根目录 `install.sh` / `scripts/run_bundle.py` 自动安装链；系统不会自动执行应用包 `install.sh` / `verify.sh`，也不会为应用包写入自动安装 `state.json` 状态。部署方式以交付包中的部署文档为准。

应用包制作原则：尽量保持原始包目录和文件形态，不要拆散、重命名或二次改造成很多小包；可以提供归档根目录 `install.sh` 作为人工部署入口，也可以保留原始安装脚本；如原脚本有交互输入，保留交互，不要擅自静默化，并在 `README.md` 或部署文档说明交互点、默认建议和需要实施人员输入的内容；如有明确自检方式，可以提供 `verify.sh` 供实施人员人工执行，但交付框架不会自动调用。

应用包 Agent 提示词模板：

```text
请把当前目录/资料整理成 OpsPaw 应用包资产。要求：
1. 不要拆散原始应用包，尽量保持原始目录、文件名和资源形态。
2. 应用包只作为交付资源放入 application_packages/，不会被交付包根 install.sh / run_bundle.py 自动执行。
3. 如需统一入口，可将安装入口整理为归档根目录 install.sh；如果存在多个安装脚本，按实施文档顺序整合成一个 install.sh 去调用它们。
4. 如果原脚本存在交互输入，保留交互，不要擅自静默化；在 README.md 或部署文档中记录每个交互点、默认建议和实施人员需要输入的内容。
5. 如有明确自检方式，可编写 verify.sh 供实施人员人工执行；系统不会自动调用应用包 verify.sh。
6. 生成 tar.gz 后调用 upload_env_package_file 上传，再用 register_env_package/update_env_package 登记，package_type 必须为 application_package。
7. 不要为应用包编写 _payload_extract 外层包装脚本；应用包归档内容会被系统直接展开到交付包 application_packages/<序号>-<package_code>/。
```

包装脚本规则：非应用包的文件型环境包外层 `install_script` / `verify_script` 是交付系统生成的步骤脚本，不能在同目录直接执行 `bash install.sh`、`bash ./install.sh`、`bash verify.sh`、`bash ./verify.sh`，否则会递归调用自身。正确做法是先把上传归档解压到 `_payload_extract/<package_code>/`，再调用解压后资产目录里的内层脚本。应用包不使用这套外层包装脚本规则。

推荐外层 install_script 模板：

```bash
#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ARCHIVE="${SCRIPT_DIR}/<file_name>.tar.gz"
EXTRACT_ROOT="${SCRIPT_DIR}/_payload_extract"
ASSET_DIR="${EXTRACT_ROOT}/<package_code>"
rm -rf "${EXTRACT_ROOT}"
mkdir -p "${ASSET_DIR}"
tar -xzf "${ARCHIVE}" -C "${ASSET_DIR}"
exec bash "${ASSET_DIR}/install.sh"
```

推荐外层 verify_script 模板：

```bash
#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ASSET_DIR="${SCRIPT_DIR}/_payload_extract/<package_code>"
exec bash "${ASSET_DIR}/verify.sh"
```

审计规则：`audit_delivery_bundle` 发现外层脚本直接 `bash install.sh` / `bash ./install.sh` / `bash verify.sh` / `bash ./verify.sh` 时会返回 `RECURSIVE_WRAPPER_SCRIPT`，必须修正后才能制作交付包。

关键约束：文件型环境包不是只登记数据库记录。Agent 必须先在本地完成 tar.gz 制作，再通过 `upload_env_package_file` 上传到系统，最后用上传返回值登记；否则交付包会缺 payload。
"""

README_RESOURCE = {"uri": "opspaw://inference-env/readme", "name": "推理环境包制作指南", "description": "Agent 初次连接 MCP 时应先读取的环境包制作上下文", "mimeType": "text/markdown"}

AUTH_TOOLS = [
    {
        "name": "mcp_login",
        "description": "登录推理环境交付系统 MCP，会话内保存 token；业务工具未登录只会返回 AUTH_REQUIRED。",
        "inputSchema": {
            "type": "object",
            "properties": {"username": {"type": "string"}, "password": {"type": "string"}},
            "required": ["username", "password"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    {
        "name": "mcp_logout",
        "description": "清除当前 MCP 适配器会话 token。",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    {
        "name": "mcp_whoami",
        "description": "查看当前 MCP 适配器登录状态；不会返回 token。",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
]


def http_json(path: str, payload: dict, token: str | None = None) -> dict:
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"{BASE_URL}{path}", data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = {"message": body}
        raise RuntimeError(f"HTTP {exc.code}: {parsed}") from exc



def http_upload_file(path: str, token: str) -> dict:
    local_path = Path(path).expanduser().resolve()
    if not local_path.exists() or not local_path.is_file():
        raise RuntimeError(f"local file not found: {local_path}")
    boundary = "----opspaw-mcp-" + secrets.token_hex(12)
    filename = local_path.name
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    file_bytes = local_path.read_bytes()
    head = (
        f"--{boundary}\r\n"
        f"Content-Disposition: form-data; name=\"file\"; filename=\"{filename}\"\r\n"
        f"Content-Type: {content_type}\r\n\r\n"
    ).encode("utf-8")
    tail = f"\r\n--{boundary}--\r\n".encode("utf-8")
    data = head + file_bytes + tail
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Content-Length": str(len(data)),
    }
    req = urllib.request.Request(f"{BASE_URL}/api/v1/environment-packages/uploads", data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = {"message": body}
        raise RuntimeError(f"HTTP {exc.code}: {parsed}") from exc


def upload_env_package_file(path: str) -> dict:
    result = http_upload_file(path, TOKEN)
    item = result.get("item", {})
    file_uri = item.get("file_uri", "")
    if file_uri and not file_uri.startswith("filesystem://"):
        prefix = "" if file_uri.startswith("/") else "/"
        item["file_uri"] = "filesystem://" + prefix + file_uri
    return {"ok": True, "item": item, "message": "upload success; use item.file_uri/file_name/checksum in register_env_package"}


def rpc_result(request_id, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def tool_content(payload: dict) -> dict:
    return {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}], "structuredContent": payload}


def login(username: str, password: str) -> dict:
    global TOKEN, CURRENT_USER
    result = http_json("/api/v1/auth/login", {"username": username, "password": password})
    TOKEN = result["access_token"]
    CURRENT_USER = result["user"]
    return {"ok": True, "user": CURRENT_USER, "message": "login success"}


def logout() -> dict:
    global TOKEN, CURRENT_USER
    TOKEN = ""
    CURRENT_USER = None
    return {"ok": True, "message": "logout success"}


def whoami() -> dict:
    return {"ok": bool(TOKEN), "authenticated": bool(TOKEN), "user": CURRENT_USER}


LOCAL_BUSINESS_TOOLS = [
    {
        "name": "upload_env_package_file",
        "description": "上传 Agent 本地已制作好的环境包 tar.gz 到系统存储，返回 file_uri/file_name/checksum；登记文件型资产前必须先调用。",
        "inputSchema": {"type": "object", "properties": {"path": {"type": "string", "description": "Agent 本地 tar.gz 文件路径"}}, "required": ["path"], "additionalProperties": False},
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
    },
]

FALLBACK_BUSINESS_TOOLS = [
    {
        "name": "list_allowed_package_roots",
        "description": "列出 Agent 可登记文件路径的允许根目录；未登录会返回 AUTH_REQUIRED。",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    {
        "name": "list_device_profiles",
        "description": "列出设备适配配置；未登录会返回 AUTH_REQUIRED。",
        "inputSchema": {
            "type": "object",
            "properties": {"enabled": {"anyOf": [{"type": "boolean"}, {"type": "null"}], "default": True}, "search": {"type": "string", "default": ""}, "limit": {"type": "integer", "default": 100}},
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    {
        "name": "list_env_packages",
        "description": "按适配配置和类型列出环境包资产；未登录会返回 AUTH_REQUIRED。",
        "inputSchema": {
            "type": "object",
            "properties": {"profile_id": {"type": "string", "default": ""}, "package_type": {"type": "string", "default": ""}, "quality_status": {"type": "string", "default": ""}, "include_shared": {"type": "boolean", "default": True}, "limit": {"type": "integer", "default": 100}},
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    {
        "name": "upload_env_package_file",
        "description": "上传 Agent 本地已制作好的环境包 tar.gz 到系统存储，返回 file_uri/file_name/checksum；登记文件型资产前必须先调用。",
        "inputSchema": {"type": "object", "properties": {"path": {"type": "string", "description": "Agent 本地 tar.gz 文件路径"}}, "required": ["path"], "additionalProperties": False},
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
    },
    {"name": "register_env_package", "description": "登记环境包资产；未登录会返回 AUTH_REQUIRED。", "inputSchema": {"type": "object", "additionalProperties": True}, "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}},
    {"name": "update_env_package", "description": "更新环境包资产；未登录会返回 AUTH_REQUIRED。", "inputSchema": {"type": "object", "additionalProperties": True}, "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}},
    {"name": "import_probe_result", "description": "导入离线探测结果 JSON；未登录会返回 AUTH_REQUIRED。", "inputSchema": {"type": "object", "additionalProperties": True}, "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}},
    {"name": "preview_delivery_manifest", "description": "预览交付包 manifest，不保存；未登录会返回 AUTH_REQUIRED。", "inputSchema": {"type": "object", "additionalProperties": True}, "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}},
    {"name": "create_delivery_bundle_draft", "description": "创建交付包草稿；未登录会返回 AUTH_REQUIRED。", "inputSchema": {"type": "object", "additionalProperties": True}, "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}},
    {"name": "update_delivery_bundle_composition", "description": "更新交付包小包编排；未登录会返回 AUTH_REQUIRED。", "inputSchema": {"type": "object", "additionalProperties": True}, "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}},
    {"name": "audit_delivery_bundle", "description": "审查交付包脚本完整性、适配一致性和产物状态；未登录会返回 AUTH_REQUIRED。", "inputSchema": {"type": "object", "additionalProperties": True}, "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}},
    {"name": "build_delivery_bundle_artifact", "description": "制作交付包完整安装包产物 tar.gz，并记录制作任务；未登录会返回 AUTH_REQUIRED。", "inputSchema": {"type": "object", "additionalProperties": True}, "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}},
    {"name": "get_delivery_bundle_build_job", "description": "查询交付包最新制作任务；未登录会返回 AUTH_REQUIRED。", "inputSchema": {"type": "object", "additionalProperties": True}, "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}},
    {"name": "deliver_delivery_bundle", "description": "确认交付交付包并锁定资产；未登录会返回 AUTH_REQUIRED。", "inputSchema": {"type": "object", "additionalProperties": True}, "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}},
    {"name": "delete_delivery_bundle", "description": "删除制作中的交付包；已交付不可删除；未登录会返回 AUTH_REQUIRED。", "inputSchema": {"type": "object", "additionalProperties": True}, "annotations": {"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": False}},
    {"name": "create_delivery_bundle_version", "description": "基于已交付交付包创建新版本；未登录会返回 AUTH_REQUIRED。", "inputSchema": {"type": "object", "additionalProperties": True}, "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}},
]


def local_resources_list() -> dict:
    resources = [README_RESOURCE]
    if TOKEN:
        try:
            msg = {"jsonrpc": "2.0", "id": "resources-list-proxy", "method": "resources/list", "params": {}}
            remote = http_json("/mcp", msg, TOKEN).get("result", {}).get("resources", [])
            seen = {README_RESOURCE["uri"]}
            for item in remote:
                if item.get("uri") not in seen:
                    resources.append(item)
                    seen.add(item.get("uri"))
        except Exception:
            pass
    return {"resources": resources}


def local_resource_read(uri: str, request_id):
    if uri == README_RESOURCE["uri"]:
        return rpc_result(request_id, {"contents": [{"uri": uri, "mimeType": "text/markdown", "text": ENV_PACKAGE_README}]})
    if not TOKEN:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32001, "message": "AUTH_REQUIRED: call mcp_login first"}}
    return http_json("/mcp", {"jsonrpc": "2.0", "id": request_id, "method": "resources/read", "params": {"uri": uri}}, TOKEN)


def _merge_tools(*groups: list[dict]) -> list[dict]:
    merged: list[dict] = []
    seen: set[str] = set()
    for group in groups:
        for tool in group:
            name = tool.get("name", "")
            if not name or name in seen:
                continue
            seen.add(name)
            merged.append(tool)
    return merged


def business_tools_list() -> list[dict]:
    if not TOKEN:
        return _merge_tools(LOCAL_BUSINESS_TOOLS, FALLBACK_BUSINESS_TOOLS)
    msg = {"jsonrpc": "2.0", "id": "tools-list-proxy", "method": "tools/list", "params": {}}
    try:
        result = http_json("/mcp", msg, TOKEN)
        remote_tools = result.get("result", {}).get("tools", FALLBACK_BUSINESS_TOOLS)
        return _merge_tools(LOCAL_BUSINESS_TOOLS, remote_tools)
    except Exception:
        return _merge_tools(LOCAL_BUSINESS_TOOLS, FALLBACK_BUSINESS_TOOLS)


def handle_tools_call(message: dict) -> dict:
    request_id = message.get("id")
    params = message.get("params") or {}
    name = params.get("name", "")
    args = params.get("arguments") or {}
    if name == "mcp_login":
        return rpc_result(request_id, tool_content(login(args.get("username", ""), args.get("password", ""))))
    if name == "mcp_logout":
        return rpc_result(request_id, tool_content(logout()))
    if name == "mcp_whoami":
        return rpc_result(request_id, tool_content(whoami()))
    if not TOKEN:
        payload = {"ok": False, "error": {"code": "AUTH_REQUIRED", "message": "请先调用 mcp_login 登录后再使用业务工具"}}
        return rpc_result(request_id, tool_content(payload))
    if name == "upload_env_package_file":
        return rpc_result(request_id, tool_content(upload_env_package_file(args.get("path", ""))))
    return http_json("/mcp", message, TOKEN)


def forward(message: dict) -> dict | None:
    method = message.get("method")
    request_id = message.get("id")
    is_notification = "id" not in message
    if is_notification and method == "notifications/initialized":
        return None
    if method == "initialize":
        return rpc_result(request_id, {
            "protocolVersion": "2025-06-18",
            "serverInfo": {"name": "inference-env-delivery-mcp-stdio-auth", "version": "0.2.0"},
            "capabilities": {"tools": {}, "resources": {}, "prompts": {}},
        })
    if method == "tools/list":
        return rpc_result(request_id, {"tools": AUTH_TOOLS + business_tools_list()})
    if method == "tools/call":
        return handle_tools_call(message)
    if method == "resources/list":
        return rpc_result(request_id, local_resources_list())
    if method == "resources/read":
        return local_resource_read((message.get("params") or {}).get("uri", ""), request_id)
    if not TOKEN:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32001, "message": "AUTH_REQUIRED: call mcp_login first"}}
    return http_json("/mcp", message, TOKEN)


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
            response = forward(message)
            if response is not None:
                sys.stdout.write(json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n")
                sys.stdout.flush()
        except Exception as exc:
            request_id = None
            try:
                request_id = json.loads(line).get("id")
            except Exception:
                pass
            error = {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32603, "message": str(exc)}}
            sys.stdout.write(json.dumps(error, ensure_ascii=False, separators=(",", ":")) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
