# AI 推理环境平台 MCP 服务设计

- 日期：2026-06-28
- 状态：Draft
- 目标：让本系统天然适合 Agent 调用，尤其是环境包资产上传/登记、适配筛选、交付包编排、manifest 预览与保存。

## 1. 背景与设计依据

MCP（Model Context Protocol）用于让 AI 应用通过标准协议连接外部系统。本系统未来不应只提供人用 Web 页面，还要提供 Agent 可发现、可调用、可审计的能力。

结合 MCP 官方规范，本系统 MCP Server 应提供三类能力：

- **Resources**：给 Agent 读取上下文，例如设备适配配置、安装项资产、交付包 manifest、脚本模板。
- **Tools**：给 Agent 执行动作，例如登记环境包、导入探测结果、创建/更新交付包编排。
- **Prompts**：给 Agent 固化工作流，例如“根据设备画像生成交付包草稿”“审查交付包脚本完整性”。

重要原则：

- Tools 是有副作用的，必须做权限、确认、审计。
- 大文件不建议直接塞进 MCP JSON-RPC；MCP 负责登记、生成上传会话、引用文件 URI，真正文件传输可走 HTTP 上传或共享文件系统。
- Agent 不直接执行现场安装；只生成/维护交付资产和交付包定义。

## 2. MCP Server 定位

服务名建议：

```text
inference-env-delivery-mcp
```

一句话定位：

> 面向 AI Agent 的推理环境资产与交付包编排 MCP 服务。

它不是新的业务系统，而是现有 FastAPI 平台上的 Agent 接入层。

推荐部署形态：

```text
Agent / MCP Host
        ↓ MCP(JSON-RPC)
inference-env-delivery-mcp
        ↓ 内部调用
现有 FastAPI Service / Database / 文件存储
```

MCP Server 不直接绕过业务 API 写库，优先复用现有服务层和权限逻辑。

## 3. 适合 Agent 的核心场景

### 3.1 上传/登记环境包资产

Agent 需要支持：

1. 读取当前设备适配配置。
2. 判断一个安装包适合哪些设备画像。
3. 根据用户提供的文件路径/上传地址登记环境包资产。
4. 写入两段脚本：`install_script`、`verify_script`。
5. 设置 `depends_on`、`install_order`、`package_type`。

### 3.2 交付包编排

Agent 需要支持：

1. 根据目标适配配置筛选可用安装项。
2. 按类型筛选，例如 driver/runtime/python_dependency/system_dependency。
3. 选择小包并排序。
4. 生成 manifest 预览。
5. 保存交付包草稿。
6. 后续更新已有交付包编排。

### 3.3 交付包审查

Agent 需要支持：

1. 检查每个小包是否有安装脚本和成功检查脚本。
2. 检查小包是否匹配目标适配配置。
3. 检查 install_order 和 depends_on 是否明显冲突。
4. 输出修改建议或直接调用更新工具调整编排。

## 4. 资源 Resources 设计

URI 命名统一使用：

```text
opspaw://inference-env/...
```

### 4.1 设备适配配置列表

```text
opspaw://inference-env/device-profiles
```

返回：

```json
{
  "items": [
    {
      "profile_id": "...",
      "profile_code": "a10-ubuntu2204",
      "label": "A10 / Ubuntu 22.04 / x86_64",
      "os_type": "Ubuntu",
      "os_version": "22.04",
      "cpu_arch": "x86_64",
      "accelerator_vendor": "NVIDIA",
      "accelerator_model": "A10",
      "driver_version": "535.183"
    }
  ]
}
```

用途：Agent 先读这个资源，再决定环境包适配条件。

### 4.2 环境包资产列表

```text
opspaw://inference-env/packages?profile_id={profile_id}&package_type={type}
```

返回按适配配置和类型过滤后的安装项资产。

必须包含：

```json
{
  "package_id": "...",
  "package_code": "libyuv",
  "name": "libyuv",
  "package_type": "system_dependency",
  "version": "refs_heads_main",
  "file_uri": "filesystem:///mnt/packages/libyuv.tar",
  "check_script": "...",
  "install_script": "...",
  "verify_script": "...",
  "depends_on": "[\"cmake\",\"gcc\"]",
  "install_order": 40,
  "quality_status": "ok",
  "device_profiles": []
}
```

### 4.3 单个环境包资产

```text
opspaw://inference-env/packages/{package_id}
```

用于 Agent 查看脚本详情、文件位置、checksum、适配配置。

### 4.4 交付包列表

```text
opspaw://inference-env/delivery-bundles
```

返回当前用户可见的交付包草稿。

### 4.5 交付包 manifest

```text
opspaw://inference-env/delivery-bundles/{bundle_id}/manifest
```

返回保存后的 `manifest_json`。

### 4.6 探测结果

```text
opspaw://inference-env/probe-results/{result_id}
```

用于 Agent 基于导入的设备探测结果建议适配配置或小包组合。

## 5. Tools 设计

工具命名采用动宾结构，避免歧义。

### 5.1 `list_device_profiles`

只读工具，也可由 Resource 覆盖。

输入：

```json
{
  "enabled": true,
  "search": "A10"
}
```

输出：设备适配配置列表。

### 5.2 `list_env_packages`

用于 Agent 按适配配置和类型筛选可用小包。

输入：

```json
{
  "profile_id": "...",
  "package_type": "runtime",
  "quality_status": "ok",
  "include_shared": true
}
```

输出：安装项资产列表。

约束：

- 如果传了 `profile_id`，只返回绑定该适配配置的小包。
- 如果传了 `package_type`，再按类型过滤。

### 5.3 `create_package_upload_session`

用于大文件上传前准备。MCP 不直接承载大文件内容，而是生成 HTTP 上传会话或返回建议存放路径。

输入：

```json
{
  "filename": "libyuv-refs_heads_main.tar",
  "size": 12345678,
  "checksum_type": "sha256",
  "checksum": "...",
  "storage_type": "local_upload"
}
```

输出：

```json
{
  "upload_id": "...",
  "upload_url": "http://.../api/v1/environment-packages/uploads?...",
  "expires_at": "...",
  "storage_type": "local_upload"
}
```

第一阶段可简化为返回现有上传接口说明；真正文件仍走 HTTP multipart。

### 5.4 `register_env_package`

登记环境包资产。适合两类文件来源：

- `local_upload`：先上传，拿到 `file_uri`。
- `filesystem_path`：文件已在 NAS/共享目录/服务器目录，Agent 只登记路径。

输入：

```json
{
  "package_code": "libyuv",
  "name": "libyuv",
  "package_type": "system_dependency",
  "version": "refs_heads_main",
  "storage_type": "filesystem_path",
  "file_uri": "filesystem:///mnt/packages/libyuv-refs_heads_main.tar",
  "checksum_type": "sha256",
  "checksum": "...",
  "check_script": "command -v cmake && command -v make",
  "install_script": "cd /root && mkdir -p libyuv && tar -xvf libyuv-refs_heads_main.tar -C ./libyuv && cd libyuv && mkdir -p build && cd build && cmake .. && make -j$(nproc) && make install",
  "verify_script": "test -f /usr/local/include/libyuv.h",
  "depends_on": "[\"cmake\",\"gcc\",\"make\"]",
  "install_order": 40,
  "device_profile_ids": ["..."]
}
```

输出：创建后的环境包资产。

权限：普通用户只能创建自己的资产；Admin 可创建全局或指定 owner（后续）。

### 5.5 `update_env_package`

更新脚本、依赖、顺序、适配配置。

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

### 5.6 `create_delivery_bundle_draft`

创建交付包草稿。

输入：

```json
{
  "bundle_code": "atlas-a10-runtime-20260628",
  "name": "A10 推理环境交付包",
  "version": "1.0.0",
  "target_device_id": "...",
  "target_profile_id": "...",
  "package_ids": ["pkg1", "pkg2", "pkg3"]
}
```

输出：交付包草稿和 manifest。

### 5.7 `update_delivery_bundle_composition`

更新交付包编排。

输入：

```json
{
  "bundle_id": "...",
  "name": "A10 推理环境交付包",
  "version": "1.0.1",
  "target_device_id": "...",
  "target_profile_id": "...",
  "package_ids": ["pkg-driver", "pkg-runtime", "pkg-python", "pkg-opencv"]
}
```

行为：

1. 校验交付包 owner/admin 权限。
2. 校验目标设备/适配配置存在。
3. 校验所有小包存在且对当前用户可见。
4. 重建 `delivery_bundle_item`。
5. 重新生成 `manifest_json`。

### 5.8 `preview_delivery_manifest`

不保存，只预览 manifest。适合 Agent 在修改前让用户确认。

输入：

```json
{
  "target_profile_id": "...",
  "package_ids": ["pkg1", "pkg2"]
}
```

输出：manifest JSON。

### 5.9 `audit_delivery_bundle`

审查交付包草稿。

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
      "package_code": "libyuv",
      "message": "缺少 verify_script 或 verify_script 过弱"
    }
  ],
  "suggestions": []
}
```

### 5.10 `import_probe_result`

导入探测 JSON。

输入：

```json
{
  "result_code": "probe-a10-001",
  "name": "A10 探测结果",
  "device_id": "...",
  "raw_json": "{...}"
}
```

输出：解析出的核心字段。

## 6. Prompts 设计

### 6.1 `compose_delivery_bundle_for_profile`

用途：给定适配配置，让 Agent 生成交付包草稿建议。

参数：

```json
{
  "profile_id": "...",
  "goal": "部署 YOLO 推理服务运行环境"
}
```

Prompt 行为：

1. 读取 `device-profile`。
2. 调用/读取匹配环境包资产。
3. 按类型建议顺序：system_dependency -> driver -> runtime -> python_runtime -> python_dependency -> inference_server。
4. 生成 package_ids 顺序。
5. 调用 `preview_delivery_manifest`。
6. 请求用户确认后再调用 `create_delivery_bundle_draft`。

### 6.2 `audit_package_scripts`

用途：检查一个环境包的安装脚本和成功检查脚本是否足够。

参数：

```json
{
  "package_id": "..."
}
```

输出：检查脚本、安装脚本、验证脚本的风险建议。

### 6.3 `register_package_from_install_doc`

用途：从实施手册片段中提取一个环境包资产。

参数：

```json
{
  "doc_text": "## 安装libyuv ...",
  "profile_id": "..."
}
```

输出建议：

- package_code
- package_type
- check_script
- install_script
- verify_script
- depends_on
- install_order

确认后调用 `register_env_package`。

## 7. 存储设计：MCP 下的包上传/存放

### 7.1 不建议 MCP 直接传大文件

原因：

- MCP 是 JSON-RPC 消息协议，适合结构化调用，不适合传几百 MB/GB 的离线包。
- Agent Host、本系统服务、文件实际所在机器可能不在同一环境。
- 大文件传输需要断点、校验、权限、过期 URL 等能力。

### 7.2 推荐存储类型

第一阶段支持：

```text
local_upload       上传到平台本地 data/env-packages/{owner}/
filesystem_path    已存在于服务器/NAS/共享目录，平台只登记 URI
```

后续扩展：

```text
http_url           内网 HTTP 文件地址
object_storage     S3/MinIO 等对象存储
artifact_repo      制品库/Nexus/自研制品平台
```

### 7.3 MCP 工具和存储类型关系

```text
Agent 有本地文件
  -> create_package_upload_session
  -> HTTP multipart 上传
  -> register_env_package(file_uri=上传结果)

文件已在 NAS/服务器目录
  -> register_env_package(storage_type=filesystem_path, file_uri=filesystem:///mnt/packages/xxx.tar)

文件在内网下载地址
  -> register_env_package(storage_type=http_url, file_uri=http://...)
```

当前系统可以先落地 `local_upload` 和 `filesystem_path`。

## 8. 权限与审计

### 8.1 MCP 身份

MCP 调用必须映射到系统用户。

建议：

- MCP Server 启动时配置 service token。
- 每次工具调用必须携带 `operator`。
- 或者通过 MCP Host 的 OAuth/Token 映射到系统账号。

最小方案：

```json
{
  "operator_id": "zhangsan",
  "operator_role": "user"
}
```

生产方案应改为 Bearer Token / OAuth，不允许 Agent 任意伪造用户头。

### 8.2 工具风险分级

| 风险等级 | 工具 | 策略 |
| --- | --- | --- |
| 只读 | list/read/preview/audit | 可直接调用，记录日志 |
| 低风险写 | create draft / import probe | 需要用户确认或 MCP Host 授权 |
| 中风险写 | register/update package | 需要确认，记录完整 before/after |
| 高风险 | delete / transfer / share / generate downloadable package | 当前不开放 MCP，后续单独审批 |

### 8.3 审计字段

每次 MCP tool call 记录：

```text
mcp_call_id
operator_id
client_name
tool_name
arguments_hash
result_status
object_type
object_id
trace_id
created_at
```

敏感字段如脚本全文可记录摘要和版本，不一定全文入审计表。

## 9. 与当前 API 的映射

| MCP Tool | 当前 API/服务 | 状态 |
| --- | --- | --- |
| list_device_profiles | GET `/device-profiles` | 已有 |
| list_env_packages | GET `/packages` + 前端过滤 | API 可用，后续可加后端 profile 过滤 |
| register_env_package | POST `/packages` | 已有主体，需补 storage_type |
| update_env_package | PATCH `/packages/{id}` | 已有主体，需补 storage_type |
| create_delivery_bundle_draft | POST `/delivery-bundles` | 已有 |
| update_delivery_bundle_composition | PATCH `/delivery-bundles/{id}` | 已有 |
| preview_delivery_manifest | 服务函数 `build_delivery_manifest` | 需暴露 API/MCP tool |
| import_probe_result | POST `/probe-results` | 已有 |
| audit_delivery_bundle | 新增服务 | 待做 |

## 10. 分阶段落地计划

### Phase 1：MCP 设计与只读资源

- 建立 MCP Server 骨架。
- 暴露 Resources：device_profiles、packages、delivery_bundles、manifest。
- 暴露只读 Tools：list_device_profiles、list_env_packages、audit_delivery_bundle 初版。

### Phase 2：资产登记与探测导入

- `register_env_package`
- `update_env_package`
- `import_probe_result`
- 补 `storage_type` 字段和页面选型。

### Phase 3：交付包编排

- `preview_delivery_manifest`
- `create_delivery_bundle_draft`
- `update_delivery_bundle_composition`
- 支持 Agent 根据适配配置自动筛选小包并生成草稿。

### Phase 4：真实交付包生成前置

- 不让 MCP 直接执行现场安装。
- 只允许生成离线交付包构建任务或草稿。
- 真正下载包、总控脚本生成、state.json 模板作为独立能力，并要求用户确认。

## 11. 推荐最小 MCP Tool Set

第一版不要太多，建议只做 8 个：

```text
list_device_profiles
list_env_packages
register_env_package
update_env_package
import_probe_result
preview_delivery_manifest
create_delivery_bundle_draft
update_delivery_bundle_composition
```

这 8 个就能覆盖：

```text
Agent 上传/登记小包
Agent 根据适配配置筛选小包
Agent 编排交付包
Agent 保存 manifest
```

## 12. 关键约束

- Agent 不直接连接实施设备。
- Agent 不直接执行安装脚本。
- Agent 不直接删除资产。
- Agent 不直接把大文件塞进 MCP tool 参数。
- Agent 写操作必须绑定系统用户、权限和审计。
- 交付包断点续装逻辑仍属于未来大包 `install.sh`，不是 MCP Server 职责。
