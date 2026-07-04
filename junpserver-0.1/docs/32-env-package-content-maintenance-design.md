# 32 环境包资产独立编辑工作台设计

## 目标

环境包资产的复杂编辑不再放在列表页抽屉/弹框中，改为独立编辑工作台。工作台参考 JupyterLab：左侧文件树，中间文件编辑器，右侧属性/保存策略，底部说明/输出。文件增删改查后端采用 Jupyter Server Contents API 风格的受控工作区服务。

## 页面设计

列表页职责收敛为：
- 上传/创建环境包资产。
- 查看环境包基础信息与脚本预览。
- 下载环境包。
- 点击“编辑”新开页面进入独立工作台：`/environment-packages/{package_id}/editor`。

独立编辑页职责：
- 信息编辑：包名称、类型、版本、适配配置、状态、可见性等资产元数据。
- 文件编辑：工作区文件树、文本文件编辑、新增文件、新增目录、重命名/移动、删除。
- 提交策略：原地修改 / 另存新版本。
- 提交工作区：把工作区重新打包成环境包归档，重新计算 checksum，并写入修改记录。

## 后端工作区模型

后端不直接在 tar.gz/zip 中原地改文件，而是：

1. 创建工作区。
2. 解包到受控目录。
3. 所有文件 CRUD 都作用于工作区。
4. 用户提交后重新打包。
5. 根据保存策略更新当前资产或创建新版本资产。

工作区根目录：

```text
{delivery_bundle_artifact_root 的父目录}/package-workspaces/{package_id}/{workspace_id}/files
```

## Jupyter Contents 风格 API

新增接口：

```text
POST   /api/v1/environment-packages/packages/{id}/workspaces
GET    /api/v1/environment-packages/packages/{id}/workspaces/{workspace_id}/contents/{path}
POST   /api/v1/environment-packages/packages/{id}/workspaces/{workspace_id}/contents/{path}
PUT    /api/v1/environment-packages/packages/{id}/workspaces/{workspace_id}/contents/{path}
PATCH  /api/v1/environment-packages/packages/{id}/workspaces/{workspace_id}/contents/{path}
DELETE /api/v1/environment-packages/packages/{id}/workspaces/{workspace_id}/contents/{path}
POST   /api/v1/environment-packages/packages/{id}/workspaces/{workspace_id}/commit
DELETE /api/v1/environment-packages/packages/{id}/workspaces/{workspace_id}
```

Contents 返回模型接近 Jupyter：

```json
{
  "name": "install.sh",
  "path": "install.sh",
  "type": "file",
  "writable": true,
  "content": "...",
  "format": "text"
}
```

目录返回 `content` 子项列表；二进制文件返回 `format=base64`。

## 权限与安全

- owner 和 admin 可创建/编辑/提交工作区。
- shared 资产只可见，不代表可编辑。
- 仅 `filesystem://` 归档资产可创建工作区。
- 支持 tar/tar.gz/tgz/zip 解包。
- 禁止绝对路径、`../`、路径穿越。
- 提交时重新生成 tar.gz 并计算 sha256。
- 另存新版本会复制元数据和适配配置；若版本号已存在，拒绝提交。

## 边界

- 当前实现是“受控 Jupyter Contents 风格服务”，不是直接启动完整 JupyterLab/Jupyter Server 进程。
- 前端采用 JupyterLab 工作台交互范式。
- 后续如要接入真实 Jupyter Server，可用当前 Contents API 作为替换边界。
