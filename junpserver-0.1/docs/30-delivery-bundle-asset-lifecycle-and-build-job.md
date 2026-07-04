# 交付包资产生命周期与后台制作任务设计

## 已实现范围

1. 交付包列表页不展示 Manifest 预览，只展示资产摘要。
2. 交付包新增资产生命周期 `lifecycle_status`：`making` 制作中、`delivered` 已交付。
3. 新增后台制作任务表 `delivery_bundle_build_job`。
4. “制作安装包”改为提交后台 job，接口立即返回 queued。
5. 前端编辑页轮询 latest job，并显示进度、当前步骤、消息、日志。
6. 已交付交付包不可编辑、不可删除、不可重新制作。
7. 制作中交付包可删除；正在制作中不可删除/修改。
8. 已交付交付包可创建新版本，新版本复制编排但清空产物，回到制作中。

## 状态模型

### 资产生命周期

| 状态 | 含义 | 规则 |
| --- | --- | --- |
| `making` | 制作中资产 | 可编辑、可删除、可制作安装包 |
| `delivered` | 已交付资产 | 只读、可下载、可创建新版本，不可删除 |

### 制作任务状态

| 状态 | 含义 |
| --- | --- |
| `queued` | 已进入后台制作队列 |
| `running` | 正在制作 |
| `success` | 制作成功 |
| `failed` | 制作失败 |

## 接口

- `POST /api/v1/environment-packages/delivery-bundles/{bundle_id}/build-jobs`
- `GET /api/v1/environment-packages/delivery-bundles/{bundle_id}/build-jobs/latest`
- `POST /api/v1/environment-packages/delivery-bundles/{bundle_id}/deliver`
- `DELETE /api/v1/environment-packages/delivery-bundles/{bundle_id}`
- `POST /api/v1/environment-packages/delivery-bundles/{bundle_id}/new-version`

旧的制作接口 `/build` 保留为兼容别名。

## 前端页面

### 交付包列表页

展示：交付包名称、版本、交付类型、资产状态、制作状态、安装项数量、产物、Owner、操作。

不再展示 Manifest 大 JSON。

### 交付包编辑页

展示：基础信息、编排、Manifest 实时预览、后台制作任务面板、下载、确认交付、创建新版本。

已交付后页面只读。

## 制作过程中环境包变化的规则

当前制作任务在开始执行时会读取交付包编排中的环境包资产，并把当时读取到的脚本、文件引用、checksum、依赖等写入最终产物的 `manifest.json` 和 `packages/` 目录。

因此：

1. **已生成的交付包产物不受后续环境包资产编辑影响**：产物里已经有 manifest、脚本和已复制的本地文件。
2. **制作任务运行中不允许修改交付包编排**：接口会拒绝 queued/running 状态下的交付包编辑和删除。
3. **如果环境包资产本身在制作任务运行中被修改，可能造成不一致风险**：例如前几步读取的是旧脚本，后几步读取的是新文件引用。当前第一阶段建议通过流程约束避免：制作任务开始后不要修改参与本次交付的环境包资产。
4. **正式交付后不可修改交付包资产**：如需变更，创建新版本重新制作。

后续建议增强为“环境包资产版本快照”：制作任务创建时把每个小包的脚本、文件 URI、checksum、版本号完整快照到 `delivery_bundle_build_job` 或独立快照表中，构建只读取快照，彻底隔离环境包资产的后续变化。

## MCP 一致性

MCP 已补齐交付包资产生命周期能力：

- `build_delivery_bundle_artifact`：制作完整包并记录制作任务。
- `get_delivery_bundle_build_job`：查询最新制作任务。
- `deliver_delivery_bundle`：确认交付并锁定资产。
- `delete_delivery_bundle`：删除制作中的交付包，已交付不可删除。
- `create_delivery_bundle_version`：基于已交付包创建新版本。

MCP 仍要求先登录，后续业务工具都会校验 bearer token。
