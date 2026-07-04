# AI 推理环境交付包工作流设计

- 状态：Active Draft
- 日期：2026-06-28
- 背景输入：`F:\workspace\yolocpp\实施手册-Atlas300Ipro环境配置V1.1.3.md` 仅作为一种推理设备实施样例，不作为系统专用模型。

## 1. 设计结论

系统目标从“在线实施任务平台”收敛为：

> 面向多种推理设备的通用环境交付包管理与生成平台。

核心能力：

1. 管理通用安装项资产。
2. 管理设备探测脚本与导入的探测结果，形成设备画像。
3. 基于设备画像筛选可用安装项。
4. 组合多个安装项生成离线交付包。
5. 小包本身不负责断点续装；每个小包只提供前置检查脚本、安装脚本、验证脚本。
6. 交付包内置总控安装脚本，按顺序调度小包，并在大包级状态文件中记录每个小包状态。
7. 任一小包失败即中断并记录状态；重新执行大包脚本时，从失败/未成功的小包继续。

## 2. 非目标

- 不以 Atlas300Ipro 为唯一模型；Atlas 文档只是样例。
- 不要求系统直接连接远程实施设备。
- 不做在线实施任务调度、远程执行、远程实时日志采集。
- 不把一次安装过程作为平台内必须在线跟踪的“实施任务”。

## 3. 核心用户流程

### 3.1 设备画像流程

```text
Admin/工程人员维护探测脚本
        ↓
实施人员在远程设备执行探测脚本
        ↓
得到探测结果 JSON / 日志包
        ↓
在系统导入探测结果
        ↓
系统形成或更新设备画像
        ↓
后续用于筛选安装项和生成交付包
```

设备往往无法被平台直接连接，因此“探测脚本执行”发生在现场或远程设备侧，平台只管理脚本与结果导入。

### 3.2 交付包生成流程

```text
选择设备画像 / 手工选择适配条件
        ↓
系统筛选可用安装项资产
        ↓
用户选择多个安装项
        ↓
系统根据依赖关系和安装顺序排序
        ↓
生成交付包：packages/ + manifest.json + install.sh + state.json
        ↓
实施人员拷贝到目标设备执行 install.sh
        ↓
总控脚本逐个执行小包：前置检查 → 安装 → 验证
        ↓
每个小包结果写入大包状态文件
        ↓
失败则中断；再次执行大包脚本时从失败/未成功小包继续
```

## 4. 模块设计

### 4.1 用户与权限

- 登录后才能进入系统。
- 普通用户：维护自己的安装项资产，查看设备/画像/模板，生成交付包。
- Admin：管理用户、全局资产、设备探测脚本、设备画像、全局交付包配置。

### 4.2 设备探测脚本

用于维护通用或设备类型专用的探测脚本。

字段建议：

```text
probe_script
- id
- script_code
- name
- version
- target_vendor        # NVIDIA / Ascend / 寒武纪 / 通用
- target_arch          # x86_64 / aarch64 / 通用
- script_type          # shell/python
- content              # 脚本内容
- output_schema        # 期望输出 JSON schema
- enabled
- created_by
- updated_by
```

### 4.3 设备画像

设备画像来自探测结果导入，也允许手工补充。

字段建议：

```text
device_profile_snapshot
- id
- device_id
- source               # imported/manual
- os_type
- os_version
- kernel_version
- cpu_arch
- accelerator_vendor
- accelerator_model
- accelerator_count
- driver_version
- firmware_version
- cann_version / cuda_version / runtime_version
- detected_libraries   # JSON: opencv/ffmpeg/protobuf/libyuv 等
- raw_result_uri
- imported_by
- imported_at
```

现有 `EnvDeviceProfile` 可继续作为“适配条件选项”，但应逐步从手工配置升级为由“设备画像”生成或关联。

### 4.4 通用安装项资产

不需要按业务过细分类，但必须表达安装、检查、验证、依赖和顺序。

字段建议：

```text
env_package
- package_code
- name
- package_type         # driver/runtime/library/tool/business/custom
- version
- file_uri
- checksum
- owner_id
- status
- visibility
- install_script
- check_script         # 安装前/安装后检查是否已存在或是否满足条件
- verify_script        # 安装成功判定
- uninstall_script
- depends_on           # 依赖安装项 code/version 范围
- conflicts_with
- install_order        # 默认顺序权重
- requires_root
- requires_reboot
- offline_supported
```

关键要求：

- 安装项必须能声明依赖关系。
- 安装项必须能声明安装顺序。
- 安装项必须有检查脚本和验证脚本。
- 验证脚本失败时，交付包总控脚本必须中断。

### 4.5 交付包定义

平台生成交付包，不负责在线执行。

```text
delivery_bundle
- bundle_id
- bundle_code
- name
- version
- target_profile_id / snapshot_id
- selected_package_ids
- package_order
- status              # draft/built/archived
- artifact_uri
- manifest_uri
- created_by
- created_at
```

交付包内容建议：

```text
bundle/
  manifest.json
  install.sh
  state.json
  logs/
  packages/
    001-system-deps/
    002-driver/
    003-cann/
    004-opencv-ffmpeg/
```

### 4.6 交付包本地执行状态

状态不一定实时回传平台，但必须在 **大包目录** 内记录。这里的状态粒度是“小包级”，不是小包内部步骤级。

小包不需要自己实现断点续装；小包只负责提供两段脚本：

```text
install_script  # 安装脚本
verify_script   # 安装后成功检查脚本
```

大包总控脚本负责维护 `state.json`：

```json
{
  "bundle_id": "...",
  "current_package": "003-cann",
  "packages": [
    {
      "package_code": "001-system-deps",
      "status": "success",
      "started_at": "...",
      "finished_at": "...",
      "exit_code": 0
    },
    {
      "package_code": "003-cann",
      "status": "failed",
      "phase": "verify_script",
      "error": "verify_script failed",
      "log_file": "logs/003-cann.log"
    }
  ]
}
```

重新执行大包 `install.sh` 时：

1. 读取大包目录下的 `state.json`。
2. 按 `manifest.steps` 顺序遍历每个小包。
3. 如果 A/B 小包状态是 `success`，直接跳过。
4. 如果执行到 C 小包，先检查 C 在状态文件中的状态：
   - C 是 `success`：跳过 C，继续 D。
   - C 不是 `success`，或没有状态：重新执行 C 的 `install_script -> verify_script`。
5. C 验证成功后，把 C 标记为 `success`，再继续 D。
6. C 任一阶段失败，把 C 标记为 `failed`，记录失败阶段和日志，然后中断整个大包安装。

## 5. 交付包总控脚本行为

伪流程：

```bash
load_manifest
load_state_or_init

for pkg in manifest.packages:
  status = state[pkg.code].status

  if status == "success":
    echo "skip ${pkg.code}, already success"
    continue

  mark_running(pkg.code, phase="check_script")
  run pkg.check_script
  if failed:
    mark_failed(pkg.code, phase="check_script")
    exit 1

  mark_running(pkg.code, phase="install_script")
  run pkg.install_script
  if failed:
    mark_failed(pkg.code, phase="install_script")
    exit 1

  mark_running(pkg.code, phase="verify_script")
  run pkg.verify_script
  if failed:
    mark_failed(pkg.code, phase="verify_script")
    exit 1

  mark_success(pkg.code)

echo "bundle install success"
```

关键约束：

- 断点续装只发生在 **大包总控脚本层**。
- 小包内部不拆步骤、不维护自己的断点状态。
- 大包状态文件只判断“小包是否成功”。
- 如果 C 小包失败，重新执行大包脚本时，从 C 小包重新跑完整的 `前置检查 -> 安装 -> 验证`，而不是从 C 内部某一行继续。
- 只有验证脚本成功，才能把小包标记为 `success`。

## 6. 信息架构调整

一级菜单建议：

- 环境包资产
  - 我的安装项资产
- 设备管理
  - 推理设备台账
  - 设备画像
- 探测脚本
  - 探测脚本库
  - 探测结果导入
- 交付包
  - 新建交付包
  - 交付包列表
  - 下载交付包
- Admin 管理
  - 用户管理
  - 全局资产管理

## 7. 下一步落地建议

优先级从高到低：

1. 给安装项资产补齐 `install_script`、`verify_script`、`depends_on`、`install_order` 字段。
2. 新增“探测脚本”与“探测结果导入”模块。
3. 新增“交付包”模块，先做 manifest 生成，不急于做复杂 UI。
4. 生成可运行的 `install.sh`，支持断点续装和每步验证。
5. 交付包执行日志支持压缩回传/导入，作为交付验收材料。
