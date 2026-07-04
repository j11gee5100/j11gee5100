# MCP 服务设计审计与详细设计文档

- 日期：2026-06-28
- 状态：Detailed Draft
- 关联文档：`docs/26-mcp-service-design.md`
- 目标：审计上一版 MCP 设计，吸收开源 MCP Server 的成熟设计思路，形成一套适合本系统长期演进的 MCP 服务详细设计。

## 1. 结论摘要

上一版 `26-mcp-service-design.md` 的方向是正确的：它已经把本系统的核心对象抽象成 Agent 可调用能力，包括环境包资产、设备适配配置、探测结果、交付包草稿和 manifest。

但上一版还偏“业务能力清单”，缺少 MCP Server 工程化细节。要适合未来 Agent 稳定调用，需要补齐以下设计：

1. **Toolset 分组与动态暴露**：避免一次暴露过多工具，让 Agent 混乱。
2. **Read-only / write / admin 模式**：区分只读查询、普通写操作、高风险管理操作。
3. **Tool Annotations 风险标注**：标明工具是否只读、是否幂等、是否破坏性、是否访问外部世界。
4. **文件存储安全边界**：借鉴 filesystem MCP 的 allowed directories / roots 思路，限制 Agent 可登记或上传的路径。
5. **大文件上传会话**：MCP 不承载大文件，只创建上传会话或登记文件 URI。
6. **资源模板 Resource Templates**：把设备、包、交付包 manifest 做成稳定 URI，便于 Agent 获取上下文。
7. **结构化输出 Schema**：Tools 必须返回可机器解析的 JSON，而不是只返回文本。
8. **幂等性和 trace_id**：写操作需要 request_id / idempotency_key，便于 Agent 重试。
9. **权限与审计**：MCP 调用必须映射到系统用户，并记录工具调用审计。
10. **提示词 Prompts 工作流**：把常见 Agent 工作流沉淀成 prompt，而不是完全依赖自由对话。

最终建议：本系统 MCP Server 不应只是 REST API 的薄包装，而应成为一个 **Agent Orchestration Facade**：

```text
MCP Host / Agent
        ↓ MCP
Inference Env Delivery MCP Server
        ↓ 调用现有服务层/API
环境包资产 / 设备适配 / 探测结果 / 交付包编排 / 文件存储
```

## 2. 参考开源/官方设计思路

### 2.1 官方 MCP 规范

官方规范明确 MCP 用于：

- 分享上下文信息。
- 暴露工具和能力。
- 构建可组合集成与工作流。

协议基于 JSON-RPC 2.0，并区分 Host、Client、Server。MCP Server 的能力重点包括 Resources、Tools、Prompts。

对本系统的启发：

- 设备适配配置、环境包资产、交付包 manifest 应优先做成 Resources。
- 登记资产、导入探测结果、更新编排是 Tools。
- “根据设备画像生成交付包草稿”应做成 Prompt 工作流。

### 2.2 Transport 设计

官方传输机制重点是：

- `stdio`：适合本地开发、CLI、桌面 Agent。
- `Streamable HTTP`：适合远程部署、多客户端、企业集成。

对本系统的启发：

- 开发期支持 stdio，便于 Claude Desktop / Cursor / Codex 类工具调试。
- 企业部署优先 Streamable HTTP，放在内网服务后面。
- HTTP 模式必须做 Origin 校验、认证和会话管理。

### 2.3 GitHub MCP Server

GitHub MCP Server 的可借鉴点：

- 支持 **read-only mode**，只暴露只读工具。
- 支持 **toolsets**，按任务域启用工具。
- read-only 优先级高于显式工具选择，避免误开放写工具。
- 工具重命名时保留别名，保证兼容。

对本系统的启发：

- 本系统应有 `read_only`、`asset_write`、`bundle_write`、`admin` 等模式。
- 工具按 toolset 暴露：`profiles`、`packages`、`bundles`、`probe`、`audit`、`admin`。
- 默认只开只读和草稿能力，不默认开放删除、转移、共享、真实打包。

### 2.4 Filesystem MCP Server

Filesystem MCP Server 的可借鉴点：

- 对文件操作设置 allowed directories。
- 可通过 MCP Roots 动态更新允许访问目录。
- 所有文件操作限制在允许目录内。
- 提供 `list_allowed_directories` 让 Agent 知道边界。
- 对工具标注 readOnly / idempotent / destructive hints。

对本系统的启发：

- `filesystem_path` 类型不能任意登记 `/root/xxx` 或系统路径。
- 应有 `allowed_package_roots`，例如：

```text
/mnt/env-packages
/nas/inference-packages
/data/env-packages
```

- MCP 工具 `register_env_package` 必须校验 file_uri 是否在 allowed roots 内。
- 提供 `list_allowed_package_roots` 工具。
- 上传包和登记包都要有风险标注。

### 2.5 Python SDK / FastMCP

Python SDK 和 FastMCP 的可借鉴点：

- 用 Python 函数声明 Tools，自动生成 schema 和文档。
- 支持 Resources、Prompts、Tools。
- 支持 Streamable HTTP。
- 结构化输出让 Agent 更稳定解析。

对本系统的启发：

- 本系统后端是 FastAPI/Python，MCP Server 第一版可以用官方 Python SDK 或 FastMCP 快速落地。
- 业务逻辑复用现有 service 层，不另写一套数据库逻辑。
- 每个 Tool 都定义 Pydantic 输入/输出模型。

## 3. 对上一版设计的审计

### 3.1 做得对的地方

| 项目 | 审计结论 |
| --- | --- |
| 业务对象抽象 | 正确。围绕设备适配、环境包资产、探测结果、交付包编排。 |
| 不直接执行现场安装 | 正确。Agent 不应连接现场设备执行脚本。 |
| MCP 不传大文件 | 正确。大文件走 HTTP/NAS/对象存储，MCP 只传 URI 和元数据。 |
| 首批工具集 | 基本合理。覆盖查询、登记、导入、编排。 |
| 权限审计意识 | 有，但需要更细化。 |

### 3.2 主要缺口

| 缺口 | 影响 | 建议 |
| --- | --- | --- |
| 没有 toolset 分层 | 工具数量增长后 Agent 选择混乱 | 按 profiles/packages/bundles/probe/audit/admin 分组 |
| 没有 read-only 模式 | Agent 容易误调用写工具 | 默认只读，写工具需显式启用 |
| 没有 tool annotations | MCP Host 不知道工具风险 | 每个工具标注 readOnlyHint/destructiveHint/idempotentHint/openWorldHint |
| 文件路径无边界 | Agent 可登记危险路径 | 增加 allowed_package_roots |
| 上传会话不完整 | 大文件上传不可审计/不可恢复 | 增加 upload_session 状态模型 |
| 没有 idempotency_key | Agent 重试可能重复创建 | 写工具支持幂等键 |
| 没有结构化错误码 | Agent 难以恢复 | 统一 error.code / trace_id / retryable |
| 没有 prompt 工作流细化 | Agent 每次都要自由推理 | 固化常用流程 prompt |
| 没有审计表设计 | 难追踪 Agent 操作 | 增加 mcp_tool_call_audit |
| 没有生产部署边界 | stdio/http/auth/网关未明确 | 分开发/生产两种部署模式 |

## 4. 设计目标

### 4.1 功能目标

本系统 MCP Server 必须支持：

1. Agent 查询设备适配配置。
2. Agent 按适配配置和类型筛选环境包资产。
3. Agent 登记或更新环境包资产。
4. Agent 导入探测结果。
5. Agent 创建交付包草稿。
6. Agent 编辑交付包编排。
7. Agent 预览 manifest。
8. Agent 审查交付包脚本完整性和适配一致性。

### 4.2 非目标

MCP Server 不做：

- 不执行现场安装。
- 不连接远程推理设备。
- 不执行小包安装脚本。
- 不直接生成生产可下载包，除非后续用户显式确认。
- 不开放删除、资产转移、全局共享等高风险工具作为第一版能力。

## 5. 总体架构

```text
+-------------------------+
| MCP Host / Agent        |
| Claude / Cursor / Codex |
+-----------+-------------+
            |
            | MCP stdio / Streamable HTTP
            v
+-------------------------+
| Inference Env MCP Server|
| - Resources             |
| - Tools                 |
| - Prompts               |
| - Auth/Audit            |
+-----------+-------------+
            |
            | internal service calls
            v
+-------------------------+
| Existing FastAPI App    |
| Services / DB / Uploads |
+-----------+-------------+
            |
            v
+-------------------------+
| DB + Package Storage    |
| SQLite/Postgres + FS/NAS|
+-------------------------+
```

### 5.1 推荐进程形态

第一阶段可以同仓库独立进程：

```text
python -m app.mcp.server --transport stdio
python -m app.mcp.server --transport streamable-http --host 127.0.0.1 --port 18090
```

后续企业部署：

```text
/mcp/inference-env    Streamable HTTP endpoint
```

可由 API Gateway / Nginx / 内网认证代理保护。

## 6. Toolset 设计

借鉴 GitHub MCP Server 的 toolset 思路，本系统按业务域分组。

### 6.1 Toolsets

| Toolset | 默认 | 说明 |
| --- | --- | --- |
| `profiles` | 开启 | 设备适配配置查询 |
| `packages_read` | 开启 | 环境包资产查询 |
| `packages_write` | 关闭 | 环境包登记/更新 |
| `probe` | 关闭 | 探测结果导入/查询 |
| `bundles_read` | 开启 | 交付包读取/manifest 读取 |
| `bundles_write` | 关闭 | 创建/更新交付包编排 |
| `audit` | 开启 | 脚本和交付包审计 |
| `admin` | 关闭 | 用户、全局资产、共享、转移等高风险操作 |

### 6.2 运行模式

```text
read_only      只暴露 profiles/packages_read/bundles_read/audit
asset_author   允许 packages_write/probe
bundle_author  允许 bundles_write
admin          允许 admin toolset，但第一版不建议开放
```

优先级规则：

```text
read_only 模式优先级最高。
即使配置了 packages_write，只要 read_only=true，写工具也不暴露。
```

## 7. Resources 详细设计

资源 URI 统一前缀：

```text
opspaw://inference-env
```

### 7.1 Resource 列表

| Resource URI | 说明 |
| --- | --- |
| `opspaw://inference-env/device-profiles` | 设备适配配置列表 |
| `opspaw://inference-env/device-profiles/{profile_id}` | 单个适配配置 |
| `opspaw://inference-env/packages` | 当前用户可见环境包资产 |
| `opspaw://inference-env/packages/{package_id}` | 单个环境包资产详情 |
| `opspaw://inference-env/packages/by-profile/{profile_id}` | 某适配配置可用安装项 |
| `opspaw://inference-env/delivery-bundles` | 交付包草稿列表 |
| `opspaw://inference-env/delivery-bundles/{bundle_id}` | 交付包详情 |
| `opspaw://inference-env/delivery-bundles/{bundle_id}/manifest` | manifest JSON |
| `opspaw://inference-env/probe-results/{result_id}` | 探测结果 |
| `opspaw://inference-env/allowed-package-roots` | 允许登记的文件根目录 |

### 7.2 Resource Template 参数

`packages/by-profile/{profile_id}` 支持 query 参数：

```text
?package_type=runtime&quality_status=ok&include_shared=true
```

Agent 使用模式：

```text
1. 读取 device-profiles
2. 选择 profile_id
3. 读取 packages/by-profile/{profile_id}?package_type=runtime
4. 组合交付包
```

## 8. Tools 详细设计

### 8.1 Tool Annotation 规范

每个工具必须声明：

```json
{
  "readOnlyHint": true,
  "destructiveHint": false,
  "idempotentHint": true,
  "openWorldHint": false
}
```

含义：

- `readOnlyHint`：是否只读。
- `destructiveHint`：是否可能破坏性修改。
- `idempotentHint`：同参数重复调用是否无额外影响。
- `openWorldHint`：是否访问外部世界。

本系统大部分工具是闭域工具：只访问本系统数据库和配置，不访问公网。

### 8.2 Tool 清单

#### 8.2.1 `list_allowed_package_roots`

Toolset：`packages_read`

用途：列出 Agent 可登记文件路径的根目录。

输入：无。

输出：

```json
{
  "items": [
    {
      "root_uri": "filesystem:///mnt/env-packages",
      "writable": false,
      "description": "NAS mounted package repository"
    }
  ]
}
```

Annotations：

```json
{
  "readOnlyHint": true,
  "destructiveHint": false,
  "idempotentHint": true,
  "openWorldHint": false
}
```

#### 8.2.2 `list_device_profiles`

Toolset：`profiles`

输入：

```json
{
  "enabled": true,
  "search": "A10",
  "limit": 100
}
```

输出：设备适配配置列表。

Annotations：只读、幂等、非破坏、闭域。

#### 8.2.3 `list_env_packages`

Toolset：`packages_read`

输入：

```json
{
  "profile_id": "...",
  "package_type": "runtime",
  "quality_status": "ok",
  "include_shared": true,
  "limit": 100
}
```

行为：

- `profile_id` 非空时，只返回绑定该适配配置的包。
- `package_type` 非空时，继续按类型过滤。
- `quality_status=ok` 时只返回脚本、checksum、适配配置完整的包。

输出：

```json
{
  "items": [
    {
      "package_id": "...",
      "package_code": "libyuv",
      "package_type": "system_dependency",
      "version": "refs_heads_main",
      "install_order": 40,
      "depends_on": "[\"cmake\",\"gcc\"]",
      "quality_status": "ok"
    }
  ]
}
```

#### 8.2.4 `create_package_upload_session`

Toolset：`packages_write`

用途：准备上传大文件。MCP 不传文件正文。

输入：

```json
{
  "filename": "libyuv.tar",
  "size": 12345678,
  "checksum_type": "sha256",
  "checksum": "...",
  "storage_type": "local_upload",
  "idempotency_key": "uuid"
}
```

输出：

```json
{
  "upload_id": "...",
  "upload_url": "http://127.0.0.1:18080/api/v1/environment-packages/uploads",
  "method": "POST",
  "content_type": "multipart/form-data",
  "expires_at": "2026-06-28T12:00:00Z"
}
```

Annotations：

```json
{
  "readOnlyHint": false,
  "destructiveHint": false,
  "idempotentHint": true,
  "openWorldHint": false
}
```

#### 8.2.5 `register_env_package`

Toolset：`packages_write`

用途：登记一个小包资产。

输入：

```json
{
  "package_code": "libyuv",
  "name": "libyuv",
  "package_type": "system_dependency",
  "version": "refs_heads_main",
  "storage_type": "filesystem_path",
  "file_uri": "filesystem:///mnt/env-packages/libyuv.tar",
  "checksum_type": "sha256",
  "checksum": "...",
  "check_script": "command -v cmake && command -v make",
  "install_script": "cd /root && mkdir -p libyuv && tar -xvf libyuv.tar -C ./libyuv && cd libyuv && mkdir -p build && cd build && cmake .. && make -j$(nproc) && make install",
  "verify_script": "test -f /usr/local/include/libyuv.h",
  "depends_on": "[\"cmake\",\"gcc\",\"make\"]",
  "install_order": 40,
  "device_profile_ids": ["..."],
  "idempotency_key": "uuid"
}
```

校验：

1. `storage_type=filesystem_path` 时，`file_uri` 必须在 allowed roots 内。
2. `device_profile_ids` 必须存在且启用。
3. 普通用户只能创建自己的资产。
4. 同 owner 下 `package_code + version` 幂等处理：
   - 如果 `idempotency_key` 相同，返回已有结果。
   - 如果无幂等键且已存在，返回 `PACKAGE_EXISTS`。

Annotations：写、非破坏、幂等（有 idempotency_key）、闭域。

#### 8.2.6 `update_env_package`

Toolset：`packages_write`

用途：更新小包脚本、顺序、依赖、适配配置。

输入：

```json
{
  "package_id": "...",
  "check_script": "...",
  "install_script": "...",
  "verify_script": "...",
  "depends_on": "...",
  "install_order": 50,
  "device_profile_ids": ["..."]
}
```

Annotations：写、非破坏、非完全幂等或按相同参数幂等、闭域。

#### 8.2.7 `import_probe_result`

Toolset：`probe`

输入：

```json
{
  "result_code": "probe-a10-001",
  "name": "A10 探测结果",
  "device_id": "...",
  "raw_json": "{...}",
  "idempotency_key": "uuid"
}
```

输出：

```json
{
  "result_id": "...",
  "os_type": "Ubuntu",
  "os_version": "22.04",
  "cpu_arch": "x86_64",
  "accelerator_vendor": "NVIDIA",
  "accelerator_model": "A10",
  "driver_version": "535.183"
}
```

Annotations：写、非破坏、幂等、闭域。

#### 8.2.8 `preview_delivery_manifest`

Toolset：`bundles_read` 或 `audit`

用途：根据当前选择预览 manifest，不保存。

输入：

```json
{
  "target_device_id": "...",
  "target_profile_id": "...",
  "package_ids": ["pkg1", "pkg2"]
}
```

输出：manifest。

Annotations：只读、幂等、非破坏、闭域。

#### 8.2.9 `create_delivery_bundle_draft`

Toolset：`bundles_write`

输入：

```json
{
  "bundle_code": "a10-yolo-runtime-20260628",
  "name": "A10 YOLO 推理环境交付包",
  "version": "1.0.0",
  "target_device_id": "...",
  "target_profile_id": "...",
  "package_ids": ["pkg-system", "pkg-driver", "pkg-runtime"],
  "idempotency_key": "uuid"
}
```

行为：创建草稿并生成 manifest。

Annotations：写、非破坏、幂等、闭域。

#### 8.2.10 `update_delivery_bundle_composition`

Toolset：`bundles_write`

输入：

```json
{
  "bundle_id": "...",
  "name": "A10 YOLO 推理环境交付包",
  "version": "1.0.1",
  "target_device_id": "...",
  "target_profile_id": "...",
  "package_ids": ["pkg-driver", "pkg-runtime", "pkg-python"]
}
```

行为：

1. 校验权限。
2. 校验适配配置。
3. 校验小包可见且匹配适配配置。
4. 重建交付包小包列表。
5. 重新生成 manifest。

Annotations：写、非破坏、按相同参数幂等、闭域。

#### 8.2.11 `audit_delivery_bundle`

Toolset：`audit`

输入：

```json
{
  "bundle_id": "..."
}
```

输出：

```json
{
  "status": "warning",
  "findings": [
    {
      "level": "warning",
      "code": "MISSING_VERIFY_SCRIPT",
      "package_code": "libyuv",
      "message": "缺少验证脚本"
    }
  ],
  "suggestions": []
}
```

检查项：

- 小包是否匹配目标适配配置。
- 安装脚本和成功检查脚本是否齐全。
- 是否缺 checksum。
- install_order 是否明显倒置。
- depends_on 文本是否引用不存在的小包。

Annotations：只读、幂等、非破坏、闭域。

## 9. Prompts 详细设计

### 9.1 `compose_bundle_for_profile`

用途：根据适配配置生成交付包建议。

输入：

```json
{
  "profile_id": "...",
  "goal": "部署 YOLO 推理服务运行环境"
}
```

流程：

1. 读取适配配置。
2. 查询匹配小包。
3. 按类型分组：
   - system_dependency
   - driver
   - runtime
   - python_runtime
   - python_dependency
   - inference_server
4. 按 install_order 排序。
5. 调用 `preview_delivery_manifest`。
6. 输出草稿建议，等待用户确认。

### 9.2 `register_package_from_manual`

用途：从实施手册片段中提取小包资产。

输入：

```json
{
  "manual_text": "## 安装libyuv ...",
  "profile_id": "...",
  "file_uri": "filesystem:///mnt/env-packages/libyuv.tar"
}
```

输出：

- 建议 package_code/name/package_type。
- 生成 check_script/install_script/verify_script 初稿。
- 给出 depends_on 和 install_order 建议。
- 用户确认后调用 `register_env_package`。

### 9.3 `audit_package_script_quality`

用途：审查一个小包脚本是否适合离线交付。

检查：

- 是否依赖公网。
- 是否缺少失败退出。
- 是否有硬编码危险路径。
- 验证脚本是否足够证明安装成功。

## 10. 文件上传与存储详细设计

### 10.1 存储类型

| storage_type | 含义 | 第一版支持 |
| --- | --- | --- |
| `local_upload` | 上传到平台本地目录 | 是 |
| `filesystem_path` | NAS/服务器/共享目录路径 | 是 |
| `http_url` | 内网 HTTP 下载地址 | 后续 |
| `object_storage` | MinIO/S3 | 后续 |
| `artifact_repo` | 制品库 | 后续 |

### 10.2 allowed roots

配置：

```env
MCP_ALLOWED_PACKAGE_ROOTS=/mnt/env-packages,/nas/inference-packages,/data/env-packages
```

校验规则：

```text
filesystem:///mnt/env-packages/a.tar        允许
filesystem:///etc/passwd                    拒绝
file:///root/.ssh/id_rsa                    拒绝
../../secret.tar                            拒绝
```

### 10.3 上传会话状态

后续建议新增表：`package_upload_session`

字段：

```text
id
upload_id
filename
storage_type
expected_size
expected_checksum
status: created/uploaded/registered/expired/failed
file_uri
owner_id
expires_at
created_at
updated_at
```

MCP 流程：

```text
create_package_upload_session
  -> Agent/Host 用 HTTP 上传文件
  -> upload endpoint 计算 checksum
  -> register_env_package 引用 upload_id 或 file_uri
```

## 11. 认证、授权、审计

### 11.1 开发期认证

开发期可以使用：

```text
OPSPAW_MCP_OPERATOR=zhangsan
OPSPAW_MCP_ROLE=user
```

或 MCP tool 参数隐式注入 operator。

### 11.2 生产认证

生产 Streamable HTTP 模式建议：

- 使用 OAuth 2.1 / 企业 IdP。
- MCP Server 作为 Resource Server。
- Access token 映射到系统用户。
- Toolset 权限来自用户角色和 token scope。

建议 scope：

```text
mcp:read
mcp:package:write
mcp:bundle:write
mcp:probe:write
mcp:admin
```

### 11.3 权限矩阵

| 角色 | profiles | packages_read | packages_write | probe | bundles_read | bundles_write | admin |
| --- | --- | --- | --- | --- | --- | --- | --- |
| user | 是 | 自己/共享 | 自己 | 自己 | 自己 | 自己 | 否 |
| admin | 是 | 全部 | 全部 | 全部 | 全部 | 全部 | 是 |
| read_only_agent | 是 | 授权范围 | 否 | 否 | 授权范围 | 否 | 否 |

### 11.4 审计表

建议新增：`mcp_tool_call_audit`

字段：

```text
id
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
object_type
object_id
status
error_code
trace_id
started_at
finished_at
```

写工具额外记录：

```text
before_snapshot_hash
after_snapshot_hash
idempotency_key
```

## 12. 错误模型

所有 Tool 失败都返回结构化错误：

```json
{
  "ok": false,
  "error": {
    "code": "PACKAGE_NOT_FOUND",
    "message": "package not found: ...",
    "retryable": false,
    "trace_id": "..."
  }
}
```

常见错误码：

```text
PERMISSION_DENIED
INVALID_ARGUMENT
DEVICE_PROFILE_NOT_FOUND
PACKAGE_NOT_FOUND
PACKAGE_NOT_VISIBLE
PACKAGE_EXISTS
BUNDLE_NOT_FOUND
INVALID_FILE_URI
FILE_OUTSIDE_ALLOWED_ROOTS
CHECKSUM_MISMATCH
UPLOAD_SESSION_EXPIRED
EMPTY_DELIVERY_BUNDLE
```

## 13. 与当前系统接口映射

| MCP 能力 | 当前系统状态 | 需补充 |
| --- | --- | --- |
| list_device_profiles | 已有 API | 包装成 Resource/Tool |
| list_env_packages | 已有 API，前端已有过滤 | 建议后端加 profile_id/package_type 过滤 |
| register_env_package | 已有 POST packages | 补 storage_type、allowed root 校验、idempotency |
| update_env_package | 已有 PATCH packages | 补 storage_type、审计 |
| import_probe_result | 已有 POST probe-results | 补 idempotency |
| create_delivery_bundle_draft | 已有 POST delivery-bundles | 补 idempotency |
| update_delivery_bundle_composition | 已有 PATCH delivery-bundles/{id} | 补适配一致性强校验 |
| preview_delivery_manifest | 服务函数已有 | 需暴露只读 Tool |
| audit_delivery_bundle | 未有 | 新增服务 |
| list_allowed_package_roots | 未有 | 新增配置和 Tool |

## 14. MCP Server 代码结构建议

```text
app/mcp/
  __init__.py
  server.py                  # FastMCP / MCP SDK 入口
  context.py                 # operator/session/auth context
  toolsets.py                # toolset 开关、read_only 过滤
  annotations.py             # tool annotation 常量
  resources.py               # MCP resources
  prompts.py                 # MCP prompts
  tools/
    profiles.py
    packages.py
    probe.py
    bundles.py
    audit.py
  schemas/
    common.py
    packages.py
    bundles.py
    probe.py
  services/
    package_uri_guard.py     # allowed roots 校验
    manifest_preview.py
    mcp_audit.py
```

原则：

- MCP 层不直接写 SQL。
- MCP 层调用现有 service 或 API 内部函数。
- MCP 层负责协议、鉴权、审计、参数模型、工具风险标注。

## 15. 分阶段落地路线

### Phase 0：设计冻结

- 审核本文档。
- 确认第一版 toolset。
- 确认存储类型：`local_upload`、`filesystem_path`。

### Phase 1：只读 MCP Server

目标：安全上线，Agent 可读上下文。

交付：

- MCP Server 骨架。
- Resources：device_profiles、packages、delivery_bundles、manifest。
- Tools：list_device_profiles、list_env_packages、preview_delivery_manifest、audit_delivery_bundle 初版。
- read_only 模式。

### Phase 2：资产登记

交付：

- storage_type 字段。
- allowed_package_roots 配置。
- list_allowed_package_roots。
- register_env_package。
- update_env_package。
- MCP tool call audit。

### Phase 3：交付包编排

交付：

- create_delivery_bundle_draft。
- update_delivery_bundle_composition。
- compose_bundle_for_profile prompt。
- register_package_from_manual prompt。

### Phase 4：上传会话

交付：

- package_upload_session 表。
- create_package_upload_session。
- 上传状态、checksum 校验、过期处理。

### Phase 5：企业化

交付：

- Streamable HTTP endpoint。
- OAuth / token scope。
- Toolset 动态启用。
- 更完整审计和指标。

## 16. 第一版验收标准

1. Agent 能列出设备适配配置。
2. Agent 能按适配配置和类型列出安装项资产。
3. Agent 能读取交付包 manifest。
4. Agent 能预览交付包 manifest，不落库。
5. Agent 能登记一个 `filesystem_path` 环境包资产，并被 allowed roots 限制。
6. Agent 能创建和更新交付包草稿。
7. 所有写工具都有审计记录。
8. read_only 模式下不暴露任何写工具。
9. 工具都带 annotations。
10. 所有错误都返回结构化错误和 trace_id。

## 17. 参考资料

- MCP 官方规范：`https://modelcontextprotocol.io/specification/2025-06-18`
- MCP Streamable HTTP / stdio Transport：`https://modelcontextprotocol.io/specification/2025-11-25/basic/transports`
- MCP Authorization：`https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization`
- MCP Python SDK：`https://github.com/modelcontextprotocol/python-sdk`
- MCP Reference Servers：`https://github.com/modelcontextprotocol/servers`
- Filesystem MCP Server：`https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem`
- GitHub MCP Server：`https://github.com/github/github-mcp-server`
- FastMCP：`https://github.com/PrefectHQ/fastmcp`
