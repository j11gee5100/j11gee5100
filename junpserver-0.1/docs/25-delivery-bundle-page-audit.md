# 交付包页面审计：编辑编排能力缺口

- 日期：2026-06-28
- 结论：审计时发现当前页面缺少编辑编排能力；现已补齐最小编辑编排页和后端 GET/PATCH 接口。

## 1. 当前已经具备

### 前端

文件：`frontend/src/pages/DeliveryBundlesPage.tsx`

已具备：

- 一级菜单 `交付包`。
- 新建交付包草稿弹窗。
- 可选择：交付包名称、编码、版本、目标设备、适配配置、安装项资产。
- 可展示 manifest 预览。
- 列表展示草稿、安装项数量、owner、manifest JSON。

### 后端

文件：`app/api/routes/environment_packages.py`

已具备：

- `GET /api/v1/environment-packages/delivery-bundles`
- `POST /api/v1/environment-packages/delivery-bundles`

数据表：

- `delivery_bundle`
- `delivery_bundle_item`

## 2. 当前缺失

### 2.1 缺少编辑入口

列表中没有：

- 编辑按钮。
- 查看详情按钮。
- 进入编排页面按钮。

用户创建后无法再调整：

- 名称。
- 版本。
- 目标设备。
- 适配配置。
- 安装项列表。
- 安装项顺序。

### 2.2 缺少编辑编排页面

当前新建弹窗不适合承担编排工作，因为交付包编排至少需要同时看：

- 目标设备/画像。
- 已选小包列表。
- 可选小包列表。
- 每个小包的安装顺序、依赖、脚本完整性。
- manifest 预览。

当前页面只有一段 JSON 预览，不够工程人员判断组合是否合理。

### 2.3 缺少更新接口

当前后端只有创建接口：

```text
POST /delivery-bundles
```

缺少：

```text
GET /delivery-bundles/{bundle_id}
PATCH /delivery-bundles/{bundle_id}
```

因此前端无法持久化编辑后的编排结果。

### 2.4 manifest 只在创建时生成

当前 `manifest_json` 创建时生成一次。

问题：

- 如果安装项资产后来更新了脚本/顺序，交付包草稿不会自动刷新。
- 如果用户调整安装项顺序，缺少重新生成 manifest 的入口。

MVP 可以接受“编辑交付包时重新生成 manifest”，不需要自动监听资产变化。

### 2.5 缺少小包状态设计展示

虽然当前不生成真实大包脚本，但编辑编排页需要明确未来执行结构：

```text
大包 install.sh
  -> 读取 state.json
  -> 对每个小包判断 status
  -> success 跳过
  -> 非 success 执行 install_script -> verify_script
```

当前页面没有把这个运行模型表现出来。

## 3. 建议最小改造

### 3.1 保留当前列表页

`/delivery-bundles` 作为列表页，增加操作列：

- 查看/编辑。
- manifest 预览。

### 3.2 新增交付包编辑编排页

建议路由：

```text
/delivery-bundles/:bundleId
```

页面结构：

```text
顶部：交付包基础信息
  - 名称
  - 编码，只读
  - 版本
  - 状态 draft
  - 目标设备
  - 适配配置

左侧：可选安装项资产
  - 按适配配置筛选
  - 显示质量状态
  - 显示 install_order
  - 添加到交付包

中间：已选小包编排列表
  - 小包名称
  - 版本
  - install_order
  - depends_on
  - check/install/verify 是否齐全
  - 上移/下移
  - 移除

右侧/底部：manifest 预览
  - 按当前编排实时生成
  - 保存后写入 delivery_bundle.manifest_json
```

### 3.3 后端补最小接口

新增：

```text
GET /api/v1/environment-packages/delivery-bundles/{bundle_id}
PATCH /api/v1/environment-packages/delivery-bundles/{bundle_id}
```

PATCH 入参可以复用创建结构：

```json
{
  "name": "xxx",
  "version": "1.0.1",
  "target_device_id": "...",
  "target_profile_id": "...",
  "package_ids": ["pkgA", "pkgB", "pkgC"]
}
```

保存逻辑：

1. 校验交付包 owner/admin 权限。
2. 校验目标设备/适配配置存在。
3. 校验小包存在且当前用户可见。
4. 删除旧 `delivery_bundle_item`。
5. 按新的顺序写入 `delivery_bundle_item`。
6. 重新生成 `manifest_json`。

### 3.4 暂不做

- 不做真实打包下载。
- 不做 install.sh 生成。
- 不做 state.json 执行结果回传。
- 不做复杂依赖求解。
- 不做拖拽排序也可以，先用上移/下移或选择顺序。

## 4. 验收标准

最小编辑编排能力完成后，应满足：

1. 用户能从交付包列表进入某个草稿的编辑页。
2. 用户能修改目标设备/适配配置。
3. 用户能添加/移除/调整安装项。
4. 页面能显示每个小包的两段脚本是否齐全。
5. 页面能实时预览 manifest。
6. 保存后再次打开，编排结果仍然存在。

## 5. 落地状态 — 2026-06-28

已完成最小改造：

- 后端新增 `GET /api/v1/environment-packages/delivery-bundles/{bundle_id}`。
- 后端新增 `PATCH /api/v1/environment-packages/delivery-bundles/{bundle_id}`。
- PATCH 保存时会重建 `delivery_bundle_item` 并重新生成 `manifest_json`。
- 前端新增 `/delivery-bundles/:bundleId` 编辑编排页。
- 列表页新增“编辑编排”入口。
- 编辑页支持基础信息、目标设备、适配配置、安装项添加/移除/上移/下移、脚本完整性展示、manifest 实时预览。

仍然延后：真实打包下载、总控 `install.sh` 生成、`state.json` 执行结果回传、复杂依赖求解。
