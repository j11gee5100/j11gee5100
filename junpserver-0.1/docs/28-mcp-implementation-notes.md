# MCP 服务第一版实现说明

- 日期：2026-06-28
- 设计依据：`docs/27-mcp-design-audit-and-detailed-design.md`
- 状态：MVP Implemented

## 1. 已实现范围

当前已在现有 FastAPI 应用中挂载轻量 MCP JSON-RPC 入口：

```text
GET  /mcp
POST /mcp
```

`POST /mcp` 必须使用登录后的 Bearer Token；MCP 不再接受默认用户或 `x-operator-id` 伪登录。未登录时返回：

```json
{"code":"AUTH_REQUIRED","message":"MCP requires login bearer token"}
```

服务信息：

```json
{
  "name": "inference-env-delivery-mcp",
  "protocolVersion": "2025-06-18",
  "transport": "streamable-http-jsonrpc"
}
```

支持 MCP 基础方法：

```text
initialize
notifications/initialized
tools/list
tools/call
resources/list
resources/read
prompts/list
```

## 2. 已实现 Toolsets

配置项：

```text
mcp_enabled
mcp_read_only
mcp_toolsets
mcp_allowed_package_roots
```

默认 toolsets：

```text
profiles
packages_read
bundles_read
audit
packages_write
probe
bundles_write
```

`mcp_read_only=true` 时只暴露：

```text
profiles
packages_read
bundles_read
audit
```

## 3. 已实现 Tools

```text
list_allowed_package_roots
list_device_profiles
list_env_packages
register_env_package
update_env_package
import_probe_result
preview_delivery_manifest
create_delivery_bundle_draft
update_delivery_bundle_composition
audit_delivery_bundle
```

其中写工具会记录 `mcp_tool_call_audit`。

## 4. 已实现 Resources

```text
opspaw://inference-env/device-profiles
opspaw://inference-env/packages
opspaw://inference-env/delivery-bundles
opspaw://inference-env/allowed-package-roots
```

## 5. 已实现 Prompts 列表

当前先实现 prompt listing，未实现 prompts/get：

```text
compose_bundle_for_profile
register_package_from_manual
```

## 6. 文件路径安全

`register_env_package` 支持：

```text
storage_type=local_upload
storage_type=filesystem_path
```

当 `storage_type=filesystem_path` 时，`file_uri` 必须以 `filesystem://` 开头，并且路径必须位于 `mcp_allowed_package_roots` 配置的根目录内。

默认允许根：

```text
/mnt/env-packages
/nas/inference-packages
/data/env-packages
```

## 7. 审计

新增模型和表：

```text
mcp_tool_call_audit
```

记录字段包括：

```text
mcp_call_id
session_id
client_name
operator_id
operator_role
tool_name
toolset
risk_level
read_only
arguments_hash
status
error_code
trace_id
started_at
finished_at
details_json
```

## 8. 验证

已新增测试：

```text
tests/test_mcp_api.py
```

覆盖：

- initialize
- tools/list
- resources/read
- read-only 模式隐藏写工具
- list_env_packages 按 profile/type 过滤
- register_env_package allowed roots 校验
- preview_delivery_manifest
- create_delivery_bundle_draft
- update_delivery_bundle_composition
- audit_delivery_bundle

验证命令：

```bash
python3 -m pytest -q tests/test_environment_packages_api.py tests/test_mcp_api.py
cd frontend && node node_modules/typescript/bin/tsc -b && node node_modules/vite/bin/vite.js build
```

当前结果：

```text
20 passed
frontend tsc passed
vite build passed
```

## 9. 当前边界

第一版是轻量 MCP JSON-RPC 兼容入口，不依赖外部 MCP SDK。

已实现核心语义：

- tools/list
- tools/call
- resources/list
- resources/read
- prompts/list
- tool annotations
- structuredContent

后续建议：

- 接入官方 Python MCP SDK 或 FastMCP。
- 实现 prompts/get。
- 实现 package_upload_session。
- 后端 packages API 增加 profile_id/package_type 原生过滤。
- 完善 OAuth/token scope。
- 扩展真实 Streamable HTTP 会话语义。

## 10. 登录与上传验证 — 2026-06-28

已验证：

- 未登录调用 `POST /mcp` 返回 401。
- 登录 `zhangsan/user123` 获取 Bearer Token 后可调用 `tools/list`。
- 使用登录 Token 上传模拟 `ffmpeg-4.3-linux-x86_64.tar.gz`。
- 创建环境包资产 `FFmpeg 4.3` 成功。
- 资产字段包含：文件 URI、checksum、安装脚本、成功检查脚本、安装顺序、适配配置，质量状态为 `ok`。

## 11. Codex MCP 接入 — 2026-06-28

已新增 stdio 适配器：

```text
scripts/inference_env_mcp_stdio.py
```

当前安全模型已调整为 **显式登录 + 每次请求校验 token**：

- Codex 启动适配器后不会自动使用任何默认业务账号。
- 适配器不再读取 `INFERENCE_ENV_MCP_TOKEN/USERNAME/PASSWORD` 等预置身份环境变量。
- 工具列表静态暴露认证工具和业务工具，避免 Codex/MCP 客户端缓存初始工具列表后登录仍看不到业务工具。
- 未登录调用任何业务工具都会返回 `AUTH_REQUIRED`，不会转发到后端业务接口。
- 调用 `mcp_login` 成功后，适配器只在当前 stdio 进程内存中保存 token；`mcp_whoami` 不返回 token。
- 后续业务工具调用都会携带该 token 转发到后端 `/mcp`。
- 调用 `mcp_logout` 后清除内存 token，业务工具再次返回 `AUTH_REQUIRED`。

后端 `/mcp` 强制 Bearer Token，不接受默认用户或 `x-operator-id` 伪登录；每次 MCP 请求都会校验 token 签名、过期时间、用户是否存在且启用、角色是否与 token 一致。

已注册到 Codex：

```text
name: inference-env-delivery
transport: stdio
command: python3
args: /mnt/f/jingying/junpserver/junpserver/scripts/inference_env_mcp_stdio.py
```

环境变量只保留后端地址，不再保存用户名/密码：

```text
INFERENCE_ENV_MCP_BASE_URL=http://127.0.0.1:18080
```

当前注册命令：

```bash
codex mcp add inference-env-delivery \
  --env INFERENCE_ENV_MCP_BASE_URL=http://127.0.0.1:18080 \
  -- python3 /mnt/f/jingying/junpserver/junpserver/scripts/inference_env_mcp_stdio.py
```

验证：

- 未登录 `tools/list` 返回认证工具 + 业务工具名称，便于 Codex 缓存；但业务工具调用返回 `AUTH_REQUIRED`。
- 未登录调用 `list_device_profiles` 返回 `AUTH_REQUIRED`。
- 调用 `mcp_login(username=zhangsan,password=user123)` 后，`tools/list` 返回认证工具 + 业务工具。
- 登录后调用 `list_device_profiles` 成功。
- 调用 `mcp_logout` 后业务工具再次返回 `AUTH_REQUIRED`。
- `codex mcp get inference-env-delivery` 显示 enabled。

注意：当前 Codex 会话通常不会热注入新 MCP 工具；需要在另一个 Codex 窗口启动，或重载 MCP/重开会话后才能看到工具命名空间。

## 12. 交付包制作安装包闭环 — 2026-06-28

已实现保存编排后的完整包制作闭环：

- 前端交付包编辑页新增：`制作安装包`、`下载完整包`、构建状态/产物/校验/日志展示。
- 后端新增：
  - `POST /api/v1/environment-packages/delivery-bundles/{bundle_id}/build`
  - `GET /api/v1/environment-packages/delivery-bundles/{bundle_id}/artifact`
- 交付包构建会输出 `tar.gz`，默认产物根目录由 `DELIVERY_BUNDLE_ARTIFACT_ROOT` 配置，默认 `/tmp/opspaw-delivery-bundles`。
- 归档结构包含：
  - `manifest.json`
  - `install.sh`
  - `state.template.json`
  - `scripts/run_bundle.py`
  - `README.md`
  - `packages/NNN-package-code/install.sh|verify.sh`
  - 若小包 `file_uri=filesystem://...` 且文件存在，则复制小包文件；其它 URI 记录在 `package_references` 中。
- 总控安装逻辑：读取/初始化 `state.json`；已 `success` 小包跳过；非 success 小包按 `install.sh -> verify.sh` 执行；任一阶段失败会记录状态和日志并中断，重新执行从失败小包继续。
- 数据库 `delivery_bundle` 增加构建产物字段：`build_status`、`artifact_uri`、`artifact_name`、`artifact_size`、`artifact_checksum`、`build_log`、`built_at`。
- MCP 新增工具：`build_delivery_bundle_artifact`，Agent 可直接触发交付包完整安装包制作；`audit_delivery_bundle` 会返回产物状态。

当前实现是同步构建，适合 MVP/架子阶段；后续如包体很大，可迁移为异步任务队列并保留同一 API 语义。
