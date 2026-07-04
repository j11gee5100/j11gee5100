# AI 推理环境安装包编排平台接口与开放集成设计

## 1. 设计目标

当前 API 优先支撑环境安装包编排 MVP：

- 安装包管理。
- 适配规则管理。
- 依赖/冲突关系管理。
- 目标环境筛包。
- recipe 组合方案管理。
- bundle 出包。
- manifest 和 install.sh 获取。

设备实施、测试回写、总装交接暂不作为当前 API 主线。

## 2. API 前缀

建议统一前缀：

```text
/api/v1/environment-packages
```

说明：旧名称 `inference-environments` 容易被理解为设备环境台账；当前 MVP 更准确的领域名是 `environment-packages`。

## 3. 通用响应格式

列表响应：

```json
{
  "items": [],
  "total": 0,
  "limit": 50,
  "offset": 0,
  "trace_id": "trace-id"
}
```

创建/更新响应：

```json
{
  "status": "ok",
  "item": {},
  "trace_id": "trace-id"
}
```

错误响应：

```json
{
  "code": "NOT_FOUND",
  "message": "package not found: pkg-id",
  "trace_id": "trace-id"
}
```

## 4. 安装包接口

### 4.1 查询安装包

```http
GET /api/v1/environment-packages/packages
```

查询参数：

- `package_type`
- `status`
- `search`
- `limit`
- `offset`

### 4.2 创建安装包

```http
POST /api/v1/environment-packages/packages
```

示例：

```json
{
  "package_code": "nvidia-driver",
  "name": "NVIDIA Driver",
  "package_type": "driver",
  "version": "535.183",
  "file_uri": "s3://env-packages/nvidia/535.183/driver.run",
  "file_name": "NVIDIA-Linux-x86_64-535.183.run",
  "checksum_type": "sha256",
  "checksum": "...",
  "install_script": "bash ./NVIDIA-Linux-x86_64-535.183.run --silent",
  "verify_script": "nvidia-smi",
  "requires_root": true,
  "requires_reboot": true,
  "offline_supported": true,
  "status": "active"
}
```

### 4.3 更新安装包

```http
PATCH /api/v1/environment-packages/packages/{package_id}
```

### 4.4 获取安装包详情

```http
GET /api/v1/environment-packages/packages/{package_id}
```

详情应包含：

- 包基础信息。
- 适配规则列表。
- 依赖/冲突关系列表。

## 5. 适配规则接口

### 5.1 查询包适配规则

```http
GET /api/v1/environment-packages/packages/{package_id}/compatibilities
```

### 5.2 创建适配规则

```http
POST /api/v1/environment-packages/packages/{package_id}/compatibilities
```

示例：

```json
{
  "hardware_vendor": "Dell",
  "cpu_arch": "x86_64",
  "os_type": "ubuntu",
  "os_version": "22.04",
  "accelerator_vendor": "NVIDIA",
  "accelerator_model": "A10",
  "driver_version_min": "535.0",
  "runtime_name": "CUDA",
  "runtime_version_min": "12.0",
  "runtime_version_max": "12.4",
  "match_mode": "compatible",
  "description": "A10 Ubuntu 22.04 CUDA 12.x"
}
```

### 5.3 更新适配规则

```http
PATCH /api/v1/environment-packages/compatibilities/{compatibility_id}
```

## 6. 包关系接口

### 6.1 查询包关系

```http
GET /api/v1/environment-packages/package-relations
```

查询参数：

- `package_id`
- `relation_type`

### 6.2 创建包关系

```http
POST /api/v1/environment-packages/package-relations
```

示例：

```json
{
  "source_package_id": "pkg-tensorrt-id",
  "target_package_id": "pkg-cuda-id",
  "relation_type": "requires",
  "description": "TensorRT requires CUDA first"
}
```

关系类型：

- `requires`
- `conflicts`
- `recommends`
- `replaces`

## 7. 目标环境筛包接口

### 7.1 筛选可用安装包

```http
POST /api/v1/environment-packages/match
```

请求示例：

```json
{
  "hardware_vendor": "Dell",
  "cpu_arch": "x86_64",
  "os_type": "ubuntu",
  "os_version": "22.04",
  "accelerator_vendor": "NVIDIA",
  "accelerator_model": "A10",
  "runtime_name": "CUDA",
  "runtime_version": "12.4",
  "package_types": ["driver", "runtime", "framework", "inference_server"]
}
```

响应示例：

```json
{
  "items": [
    {
      "package_id": "pkg-id",
      "package_code": "cuda",
      "name": "CUDA Toolkit",
      "package_type": "runtime",
      "version": "12.4",
      "matched": true,
      "match_reasons": ["cpu_arch matched", "os_type matched", "accelerator_vendor matched"]
    }
  ],
  "total": 1,
  "trace_id": "trace-id"
}
```

一期匹配语义：

- 规则字段为空表示不限。
- 请求字段为空表示不参与该维度筛选。
- 非空规则字段必须和请求字段一致。
- 版本范围字段先保留，可后续启用严格比较。

## 8. Recipe 接口

### 8.1 查询 recipe

```http
GET /api/v1/environment-packages/recipes
```

查询参数：

- `status`
- `search`
- `limit`
- `offset`

### 8.2 创建 recipe

```http
POST /api/v1/environment-packages/recipes
```

示例：

```json
{
  "recipe_code": "recipe-yolo-a10-ubuntu2204-v1",
  "name": "YOLO A10 Ubuntu 22.04 环境",
  "version": "1.0",
  "target_cpu_arch": "x86_64",
  "target_os_type": "ubuntu",
  "target_os_version": "22.04",
  "target_accelerator_vendor": "NVIDIA",
  "target_accelerator_model": "A10",
  "target_runtime_name": "CUDA",
  "target_runtime_version": "12.4",
  "items": [
    {
      "package_id": "pkg-driver-id",
      "install_order": 10
    },
    {
      "package_id": "pkg-cuda-id",
      "install_order": 20
    },
    {
      "package_id": "pkg-tensorrt-id",
      "install_order": 30
    }
  ]
}
```

### 8.3 更新 recipe

```http
PATCH /api/v1/environment-packages/recipes/{recipe_id}
```

### 8.4 校验 recipe

```http
POST /api/v1/environment-packages/recipes/{recipe_id}/validate
```

校验内容：

- requires 是否都已选择。
- requires 的目标包是否排在源包前面。
- conflicts 是否同时出现。
- 是否存在重复安装顺序。

响应示例：

```json
{
  "valid": false,
  "errors": [
    {
      "code": "MISSING_REQUIRED_PACKAGE",
      "message": "TensorRT requires CUDA"
    }
  ],
  "warnings": []
}
```

## 9. Bundle 出包接口

### 9.1 查询 bundle

```http
GET /api/v1/environment-packages/bundles
```

查询参数：

- `status`
- `recipe_id`
- `limit`
- `offset`

### 9.2 创建 bundle 构建

```http
POST /api/v1/environment-packages/bundles
```

示例：

```json
{
  "bundle_code": "bundle-yolo-a10-ubuntu2204-v1",
  "recipe_id": "recipe-id",
  "name": "YOLO A10 Ubuntu 22.04 Environment Bundle",
  "version": "1.0"
}
```

一期行为：

- 读取 recipe 和安装包清单。
- 生成 manifest JSON。
- 生成 install.sh。
- 写入 bundle 记录。
- 如果对象存储已配置，后续可写入 MinIO。

### 9.3 获取 bundle manifest

```http
GET /api/v1/environment-packages/bundles/{bundle_id}/manifest
```

### 9.4 获取 bundle 总安装脚本

```http
GET /api/v1/environment-packages/bundles/{bundle_id}/install-script
```

### 9.5 下载大包

```http
GET /api/v1/environment-packages/bundles/{bundle_id}/download
```

一期如果尚未实现真实压缩包，可返回 `bundle_uri` 或 `501 NOT_IMPLEMENTED`。

## 10. 对接模型平台

当前模型平台不是阻塞项。

后续对接方式：

- 模型平台记录推荐 `recipe_code` 或 `bundle_code`。
- 模型平台查询可用 bundle。
- 模型平台将模型版本和环境 bundle 关联。

建议后续字段：

- `model_id`
- `model_version`
- `recommended_recipe_code`
- `recommended_bundle_code`

## 11. 对接测试平台

当前测试平台不是阻塞项。

后续对接方式：

- 测试平台拉取 bundle。
- 测试完成后回写 bundle 测试状态。

建议后续接口：

```http
POST /api/v1/environment-packages/bundles/{bundle_id}/test-result
```

## 12. 对接总装交付

当前总装交付不是阻塞项。

后续对接方式：

- 总装下载测试通过的 bundle。
- 查看 manifest 和 install.sh。
- 标记接收状态。

## 13. 安全建议

- 安装脚本创建和更新记录审计。
- 高风险脚本后续进入审批。
- 包文件必须有 checksum。
- bundle 应支持签名，后续增强。
- 生产安装不由本平台直接执行，应交给受控执行系统。
