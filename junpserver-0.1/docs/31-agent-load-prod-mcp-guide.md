# Agent 加载 12 生产 MCP 教程：`inference-env-prod-12`

更新时间：2026-06-30

## 1. 目标

让新开的 Codex/Agent 窗口能够连接 12 服务器生产环境 MCP，并按标准流程读取上下文、登录、查看设备配置、登记环境包、编排交付包。

生产 MCP 名称：`inference-env-prod-12`

生产 MCP 后端地址：

```text
http://172.24.26.12:18080/mcp
```

本机 Codex MCP 适配器：

```text
/mnt/f/jingying/junpserver/junpserver/scripts/inference_env_mcp_stdio.py
```

## 2. MCP 官方如何解释 Server 能力

MCP 官方规范把 MCP 定义为让 LLM 应用和外部数据源/工具集成的开放协议。对 Agent 使用本系统时，最重要的是三个 Server 能力：

1. **Tools**：服务端暴露可由模型调用的工具。工具有唯一名称、描述和输入 schema，适合执行动作，比如登记环境包、创建交付包草稿、制作交付包。
2. **Resources**：服务端暴露上下文数据，每个资源由 URI 唯一标识，适合给模型读取系统说明、设备配置、资产列表等上下文。
3. **Prompts**：服务端暴露可复用提示模板，适合把常见工作流封装成可发现、可参数化的操作入口。

官方文档：

- Specification：https://modelcontextprotocol.io/specification/2025-06-18
- Tools：https://modelcontextprotocol.io/specification/2025-06-18/server/tools
- Resources：https://modelcontextprotocol.io/specification/2025-06-18/server/resources
- Prompts：https://modelcontextprotocol.io/specification/2025-06-18/server/prompts

本系统的设计对应关系：

| MCP 能力 | OpsPaw 用法 |
|---|---|
| Tools | 登录、列设备配置、登记环境包、创建/更新交付包、审计、制作产物 |
| Resources | `opspaw://inference-env/readme`、设备配置、环境包资产、交付包草稿、允许包目录 |
| Prompts | 后续可用于“从实施手册登记资产”“按设备配置生成交付包草稿”等 Agent 工作流 |

## 3. Codex 配置位置

配置文件：

```text
/root/.codex/config.toml
```

已经新增：

```toml
[mcp_servers.inference-env-prod-12]
command = "python3"
args = ["/mnt/f/jingying/junpserver/junpserver/scripts/inference_env_mcp_stdio.py"]
startup_timeout_sec = 20.0

[mcp_servers.inference-env-prod-12.env]
INFERENCE_ENV_MCP_BASE_URL = "http://172.24.26.12:18080"
```

同时保留开发环境别名：

```toml
[mcp_servers.inference-env-dev]
command = "python3"
args = ["/mnt/f/jingying/junpserver/junpserver/scripts/inference_env_mcp_stdio.py"]
startup_timeout_sec = 20.0

[mcp_servers.inference-env-dev.env]
INFERENCE_ENV_MCP_BASE_URL = "http://127.0.0.1:18080"
```

说明：修改 `/root/.codex/config.toml` 后，通常需要新开 Codex 窗口/会话才会加载新的 MCP server。

## 4. 新窗口 Agent 首次加载步骤

### 4.1 确认 MCP 已出现

新窗口中应能看到 MCP server：

```text
inference-env-prod-12
```

如果没有出现：

1. 确认新窗口使用的是同一个 `/root/.codex/config.toml`。
2. 确认配置 TOML 无语法错误。
3. 重新打开 Codex 会话。

### 4.2 读取 README Resource

新窗口初次连接后，先读：

```text
opspaw://inference-env/readme
```

这个资源会告诉 Agent：

- 环境包资产最小结构；
- install_script / verify_script 规则；
- 强关联包怎么组合；
- 交付包如何编排、审计和制作。

### 4.3 登录

先调用工具：

```text
mcp_login
```

输入：

```json
{
  "username": "admin",
  "password": "admin123"
}
```

登录后当前 MCP stdio 适配器会在该会话内保存 token。后续业务工具会自动带 token 调生产 HTTP MCP。

> 注意：不要把密码写入最终交付包脚本或文档。这里是系统登录凭据，仅用于 MCP 操作。

### 4.4 检查登录状态

调用：

```text
mcp_whoami
```

期望：

```json
{
  "ok": true,
  "authenticated": true,
  "user": {"username": "admin", ...}
}
```

### 4.5 查看设备适配配置

调用：

```text
list_device_profiles
```

示例参数：

```json
{
  "enabled": true,
  "limit": 200
}
```

五舟当前适配配置：

```text
dev-a10-01-x86-64-ubuntu-22-04-atlas-300ipro
```

标签：

```text
五舟300ipro / arm64 / Ubuntu 22.04 / Atlas 300ipro
```

### 4.6 查看当前环境包资产

调用：

```text
list_env_packages
```

示例：

```json
{
  "include_shared": true,
  "limit": 500
}
```

按五舟适配过滤时，使用 `profile_id` 或 `profile_code`。

### 4.7 创建或更新交付包草稿

推荐流程：

1. `preview_delivery_manifest`：预览，不保存。
2. `create_delivery_bundle_draft`：创建草稿。
3. `update_delivery_bundle_composition`：调整编排。
4. `audit_delivery_bundle`：审计脚本完整性、适配一致性、产物状态。
5. 确认后再调用 `build_delivery_bundle_artifact` 制作完整包。

## 5. 当前 12 生产 MCP 常用工具

| 工具 | 用途 | 风险 |
|---|---|---|
| `mcp_login` | 登录 MCP 会话 | 低 |
| `mcp_logout` | 清除 MCP 会话 token | 低 |
| `mcp_whoami` | 查看登录状态 | 低 |
| `list_allowed_package_roots` | 查看允许登记文件根目录 | 低 |
| `list_device_profiles` | 查看设备适配配置 | 低 |
| `list_env_packages` | 查看环境包资产 | 低 |
| `register_env_package` | 登记环境包资产 | 中 |
| `update_env_package` | 更新环境包资产 | 中 |
| `import_probe_result` | 导入设备探测结果 | 中 |
| `preview_delivery_manifest` | 预览交付包 manifest | 低 |
| `create_delivery_bundle_draft` | 创建交付包草稿 | 中 |
| `update_delivery_bundle_composition` | 更新交付包编排 | 中 |
| `audit_delivery_bundle` | 审计交付包 | 低 |
| `build_delivery_bundle_artifact` | 制作完整交付包产物 | 中高 |
| `get_delivery_bundle_build_job` | 查询制作任务 | 低 |
| `deliver_delivery_bundle` | 标记已交付并锁定 | 中高 |
| `delete_delivery_bundle` | 删除制作中交付包 | 高 |
| `create_delivery_bundle_version` | 基于已交付包创建新版本 | 中 |

## 6. Agent 操作原则

1. **先读 README Resource，再调用写工具。**
2. **所有生产登记必须走 MCP，不直接写生产数据库。**
3. **新需求代码开发仍在本地环境；生产只登记资产或在明确上线时更新程序。**
4. **制作交付包前必须先审计。**
5. **已交付交付包不可删除；需要修改时创建新版本。**
6. **纯命令包 `command_step` 当前生产质量状态可能显示 `missing_checksum`，这是生产代码尚未优化的已知规则缺口。**

## 7. 标准 Agent 提示词

新窗口可以直接给 Agent 这段任务：

```text
请使用 MCP server `inference-env-prod-12`。
先读取 resource `opspaw://inference-env/readme`，再调用 `mcp_login` 登录生产环境。
登录后调用 `mcp_whoami` 确认身份，然后列出设备适配配置和当前环境包资产。
所有生产资产登记、交付包编排都必须通过 MCP 工具完成，不允许直接写数据库。
如涉及制作交付包，先调用 `preview_delivery_manifest` 和 `audit_delivery_bundle`，再根据明确指令调用 `build_delivery_bundle_artifact`。
```

## 8. 快速验收

新窗口能完成以下动作即表示加载成功：

1. `tools/list` 中能看到 `mcp_login`。
2. `resources/list` 中能看到 `opspaw://inference-env/readme`。
3. `mcp_login` 成功。
4. `mcp_whoami` 显示 `admin`。
5. `list_device_profiles` 能看到五舟适配配置。
6. `list_env_packages` 能看到当前生产环境包资产。

## 9. MCP 客户端安装包怎么安装

这里要区分两个东西：

1. **生产 MCP HTTP 服务端**：运行在 12 服务器 OpsPaw 后端里，地址是 `http://172.24.26.12:18080/mcp`。
2. **Agent 本机 MCP stdio 适配器**：运行在 Codex 所在机器上，把 Codex 的 stdio MCP 调用转发到生产 HTTP MCP，并在本会话内保存登录 token。

当前 `inference-env-prod-12` 使用的是第 2 种适配器：

```text
scripts/inference_env_mcp_stdio.py
```

它是一个单文件 Python 脚本，只使用 Python 标准库：

- `json`
- `os`
- `sys`
- `urllib`

因此不需要额外 pip 安装第三方包。

### 9.1 推荐安装目录

推荐把 MCP 客户端适配器作为独立安装包放到：

```text
/opt/opspaw-mcp-clients/inference-env/
```

目录结构：

```text
/opt/opspaw-mcp-clients/inference-env/
  inference_env_mcp_stdio.py
  README.md
```

### 9.2 从当前项目安装

在 Codex 所在机器执行：

```bash
sudo mkdir -p /opt/opspaw-mcp-clients/inference-env
sudo cp /mnt/f/jingying/junpserver/junpserver/scripts/inference_env_mcp_stdio.py \
  /opt/opspaw-mcp-clients/inference-env/inference_env_mcp_launcher.py
sudo chmod +x /opt/opspaw-mcp-clients/inference-env/inference_env_mcp_launcher.py
```

验证脚本可执行：

```bash
INFERENCE_ENV_MCP_BASE_URL=http://172.24.26.12:18080 \
  /opt/opspaw-mcp-clients/inference-env/inference_env_mcp_launcher.py
```

该命令会等待 stdio 输入，按 `Ctrl+C` 退出即可。

### 9.3 一次性初始化验证

执行：

```bash
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' \
  '{"jsonrpc":"2.0","id":3,"method":"resources/list","params":{}}' \
| INFERENCE_ENV_MCP_BASE_URL=http://172.24.26.12:18080 \
  /opt/opspaw-mcp-clients/inference-env/inference_env_mcp_launcher.py
```

期望看到：

- `serverInfo.name = inference-env-delivery-mcp-stdio-auth`
- `tools` 中包含 `mcp_login`
- `resources` 中包含 `opspaw://inference-env/readme`

### 9.4 Codex 配置方式

编辑：

```text
/root/.codex/config.toml
```

推荐使用独立安装路径：

```toml
[mcp_servers.inference-env-prod-12]
command = "python3"
args = ["/opt/opspaw-mcp-clients/inference-env/inference_env_mcp_launcher.py"]
startup_timeout_sec = 20.0

[mcp_servers.inference-env-prod-12.env]
INFERENCE_ENV_MCP_BASE_URL = "http://172.24.26.12:18080"
```

如果不想复制安装，也可以直接引用项目路径：

```toml
[mcp_servers.inference-env-prod-12]
command = "python3"
args = ["/mnt/f/jingying/junpserver/junpserver/scripts/inference_env_mcp_stdio.py"]
startup_timeout_sec = 20.0

[mcp_servers.inference-env-prod-12.env]
INFERENCE_ENV_MCP_BASE_URL = "http://172.24.26.12:18080"
```

### 9.5 同时配置开发和生产

```toml
[mcp_servers.inference-env-dev]
command = "python3"
args = ["/opt/opspaw-mcp-clients/inference-env/inference_env_mcp_launcher.py"]
startup_timeout_sec = 20.0

[mcp_servers.inference-env-dev.env]
INFERENCE_ENV_MCP_BASE_URL = "http://127.0.0.1:18080"

[mcp_servers.inference-env-prod-12]
command = "python3"
args = ["/opt/opspaw-mcp-clients/inference-env/inference_env_mcp_launcher.py"]
startup_timeout_sec = 20.0

[mcp_servers.inference-env-prod-12.env]
INFERENCE_ENV_MCP_BASE_URL = "http://172.24.26.12:18080"
```

这样新窗口 Agent 可以明确选择：

- `inference-env-dev`：本地开发环境；
- `inference-env-prod-12`：12 生产环境。

### 9.6 其他 MCP 客户端如何配置

只要客户端支持 stdio MCP，原则上都可以这样配置：

```json
{
  "mcpServers": {
    "inference-env-prod-12": {
      "command": "python3",
      "args": ["/opt/opspaw-mcp-clients/inference-env/inference_env_mcp_launcher.py"],
      "env": {
        "INFERENCE_ENV_MCP_BASE_URL": "http://172.24.26.12:18080"
      }
    }
  }
}
```

不同客户端配置文件位置不同，但核心都是：

- command：`python3`
- args：stdio 适配器脚本路径
- env：`INFERENCE_ENV_MCP_BASE_URL`

### 9.7 生产 HTTP MCP 连通性检查

安装前先确认 12 服务可访问：

```bash
curl -s http://172.24.26.12:18080/mcp | jq .
```

期望：

```json
{
  "name": "inference-env-delivery-mcp",
  "protocolVersion": "2025-06-18",
  "enabled": true,
  "transport": "streamable-http-jsonrpc"
}
```

如果无法访问，先检查：

1. 12 服务器网络是否可达；
2. `opspaw-api` 容器是否运行；
3. 18080 端口是否开放；
4. 本机是否在同一局域网或 VPN 内。

### 9.8 登录与安全说明

- MCP 适配器不保存永久账号密码。
- 每个新 Agent 会话需要调用一次 `mcp_login`。
- 登录成功后 token 只保存在该 Python 进程内存里。
- 调用 `mcp_logout` 或结束 Agent 会话后 token 消失。
- 不建议把生产密码写入 Codex 配置文件。

## 10. 可选：制作一个 tar.gz 安装包

如果要把 MCP 客户端发给其他 Agent 机器，可以打成 tar.gz：

```bash
mkdir -p /tmp/opspaw-inference-env-mcp-client
cp /mnt/f/jingying/junpserver/junpserver/scripts/inference_env_mcp_stdio.py \
  /tmp/opspaw-inference-env-mcp-client/inference_env_mcp_stdio.py
cat > /tmp/opspaw-inference-env-mcp-client/README.md <<'README'
# OpsPaw Inference Env MCP Client

安装：

```bash
sudo mkdir -p /opt/opspaw-mcp-clients/inference-env
sudo cp inference_env_mcp_stdio.py /opt/opspaw-mcp-clients/inference-env/
sudo chmod +x /opt/opspaw-mcp-clients/inference-env/inference_env_mcp_launcher.py
```

Codex 配置：

```toml
[mcp_servers.inference-env-prod-12]
command = "python3"
args = ["/opt/opspaw-mcp-clients/inference-env/inference_env_mcp_launcher.py"]
startup_timeout_sec = 20.0

[mcp_servers.inference-env-prod-12.env]
INFERENCE_ENV_MCP_BASE_URL = "http://172.24.26.12:18080"
```
README
cd /tmp
 tar -czf opspaw-inference-env-mcp-client.tar.gz opspaw-inference-env-mcp-client
sha256sum opspaw-inference-env-mcp-client.tar.gz
```

安装包内容：

```text
opspaw-inference-env-mcp-client/
  inference_env_mcp_stdio.py
  README.md
```

## 11. 通用 MCP 客户端下载地址

生产环境已提供通用 MCP 客户端包下载：

```text
http://172.24.26.12:18081/downloads/opspaw-inference-env-mcp-client.tar.gz
```

校验和：

```text
http://172.24.26.12:18081/downloads/opspaw-inference-env-mcp-client.tar.gz.sha256
```

当前 sha256：

```text
65a715328ce0e94cbdefff1609064182bb091959b5e84c6a5b434f8c9246e31b
```

包内结构：

```text
opspaw-inference-env-mcp-client/
  install.sh
  bin/inference_env_mcp_stdio.py
  examples/codex-config-prod.toml
  examples/mcp-config-generic.json
  README.md
  AGENT_PROMPT.md
```

## 12. 给新 Agent 的一段提示词

把下面整段发给新 Agent 即可：

```text
你需要安装并使用 OpsPaw 推理环境交付系统 MCP。

请下载 MCP 客户端包：
http://172.24.26.12:18081/downloads/opspaw-inference-env-mcp-client.tar.gz

校验文件：
http://172.24.26.12:18081/downloads/opspaw-inference-env-mcp-client.tar.gz.sha256

下载后请解压，先阅读包内 README.md 和 AGENT_PROMPT.md。
然后执行包内 install.sh，把 MCP stdio 适配器安装到：
/opt/opspaw-mcp-clients/inference-env/inference_env_mcp_launcher.py

如果你是 Codex，请把包内 examples/codex-config-prod.toml 的内容加入 /root/.codex/config.toml。
最终需要新增 MCP server：inference-env-prod-12。
其配置应为：

[mcp_servers.inference-env-prod-12]
command = "python3"
args = ["/opt/opspaw-mcp-clients/inference-env/inference_env_mcp_launcher.py"]
startup_timeout_sec = 20.0

[mcp_servers.inference-env-prod-12.env]
INFERENCE_ENV_MCP_BASE_URL = "http://172.24.26.12:18080"

配置完成后新开 Agent/Codex 会话。
首次连接后，先读取 resource：opspaw://inference-env/readme。
然后调用 mcp_login 登录，再调用 mcp_whoami 确认身份。
之后使用 list_device_profiles、list_env_packages、register_env_package、preview_delivery_manifest、create_delivery_bundle_draft、audit_delivery_bundle、build_delivery_bundle_artifact 等工具完成环境包和交付包工作。

生产资产登记、交付包编排和制作必须走 MCP；不要直接写生产数据库。
制作交付包前必须先 preview 和 audit。
```

## 13. 重要修正：环境包文件必须先上传再登记

文件型环境包的正确 MCP 工作流是：

```text
本地读取原始资料 -> 本地整理/制作环境包 tar.gz -> upload_env_package_file -> register_env_package/update_env_package -> audit_delivery_bundle
```

禁止只在 `register_env_package` 中手写类似下面的路径：

```text
filesystem:///data/env-packages/<user>/<dir>/<package>.tar.gz
```

因为这只是数据库引用，不代表文件已经存在。Agent 必须先调用：

```text
upload_env_package_file
```

输入：

```json
{
  "path": "/本地/已制作好的/package.tar.gz"
}
```

返回示例：

```json
{
  "ok": true,
  "item": {
    "file_uri": "filesystem:///data/env-packages/lisi/package.tar.gz",
    "file_name": "package.tar.gz",
    "checksum_type": "sha256",
    "checksum": "..."
  }
}
```

然后把返回的 `file_uri/file_name/checksum_type/checksum` 原样传给 `register_env_package` 或 `update_env_package`。

如果 `audit_delivery_bundle` 返回：

```text
PAYLOAD_FILE_MISSING
```

说明资产只登记了引用或文件丢失，必须重新本地制包、上传、更新资产后再制作交付包。

## 14. 应用包类型：作为交付资源携带，不进入自动安装链

`package_type=application_package` 用于业务程序、模型服务、前后处理脚本工程等应用形态资源。最新规则：

- 应用包只随交付包放入 `application_packages/` 目录，不进入交付包根目录 `install.sh` / `scripts/run_bundle.py` 自动安装链。
- 系统不会自动执行应用包 `install.sh` / `verify.sh`，也不会为应用包写入自动安装 `state.json` 状态。
- 应用包部署方式以交付包中的部署文档为准；如果当前资料里已有部署文档，应在 README 中引用并说明关键部署入口。
- 尽量保持原始包目录和文件形态，不要拆散、重命名或二次改造成很多小包。
- 可以提供归档根目录 `install.sh` 作为人工部署入口，也可以保留原始安装脚本。
- 如果原脚本存在交互输入，保留交互，不要擅自静默化；在 README.md 或部署文档中记录每个交互点、默认建议和实施人员需要输入的内容。
- 如有明确自检方式，可编写 `verify.sh` 供实施人员人工执行；系统不会自动调用应用包 `verify.sh`。

应用包 Agent 提示词：

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

## 15. 防递归自调用：非应用包外层脚本必须解压到子目录再调用内层脚本

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

## 16. MCP 客户端自动更新机制

MCP 分两层：

1. 服务端 MCP：随 OpsPaw 后端上线自动更新。
2. Agent 本地 stdio 客户端：需要通过 launcher 自动拉取最新脚本。

以后 Codex/Agent 配置应固定指向：

```text
/opt/opspaw-mcp-clients/inference-env/inference_env_mcp_launcher.py
```

launcher 每次启动会读取：

```text
{BASE_URL}/mcp/client/manifest
```

然后按 manifest 下载最新：

```text
{BASE_URL}/mcp/client/inference_env_mcp_stdio.py
```

下载后校验 sha256，缓存到：

```text
~/.cache/opspaw/inference-env-mcp/
```

校验通过才执行；下载失败时回退到同目录的本地 `inference_env_mcp_stdio.py`。

可选环境变量：

- `INFERENCE_ENV_MCP_AUTO_UPDATE=0`：关闭自动更新。
- `INFERENCE_ENV_MCP_CLIENT_CACHE=/path/to/cache`：修改缓存目录。
- `INFERENCE_ENV_MCP_UPDATE_TIMEOUT_SEC=10`：修改更新请求超时。

因此以后服务端上线后，新开 Agent 会话会自动拿到最新 MCP stdio 客户端；已运行中的 Agent 会话不会热更新，需要重开窗口/会话。
