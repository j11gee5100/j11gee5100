# Design

## Source of truth
- Status: Active draft
- Last refreshed: 2026-06-28
- Primary product surfaces: AI 推理环境安装项资产、设备探测与画像、交付包组合生成、Admin 管理
- Evidence reviewed:
  - `docs/18-ai-inference-env-requirements.md`
  - `docs/19-ai-inference-env-product-design.md`
  - `docs/20-ai-inference-env-architecture.md`
  - `docs/21-ai-inference-env-database-design.md`
  - `docs/22-ai-inference-env-api-integration.md`
  - `docs/23-delivery-package-workflow-design.md`
  - `docs/24-mvp-skeleton-module-audit.md`
  - `docs/17-frontend-page-design-spec.md`
  - `frontend/src/App.tsx`
  - `frontend/src/pages/TemplateCenterPage.tsx`

## Brand
- Personality: 企业级、可靠、工程化、资产可追溯。
- Trust signals: 清晰归属、版本、校验状态、适配状态、审计信息。
- Avoid: 炫技式大屏、过度渐变、把组合出包/交接/测试全部堆在首屏。

## Confirmed direction update — 2026-06-28
- Atlas300Ipro 手册只是一个设备类型样例，系统设计必须保持通用。
- 系统不做在线远程实施任务调度；远程设备往往无法被平台直连。
- 平台管理探测脚本和探测结果导入，导入后生成设备画像。
- 安装项资产保持通用粒度，但必须补齐安装脚本、检查脚本、验证脚本、依赖关系、安装顺序。
- 平台核心交付物是离线交付包：多个小包 + manifest + 总控 install.sh + state.json。
- 小包只提供前置检查、安装、验证三段脚本；断点续装由大包总控脚本读取 state.json 后按小包状态处理。

## MVP skeleton scope — 2026-06-28
- 当前先做架子，不做完整交付包执行引擎；详见 `docs/24-mvp-skeleton-module-audit.md`。
- 架子版只验证：登录与权限、安装项资产、设备适配配置、交付包草稿、manifest 预览。
- 一级菜单先收敛为：环境包资产、设备管理、探测结果、交付包、Admin 管理。
- 安装项资产的适配条件必须来自设备管理中的适配配置选择框，不允许在包表单中自由填写硬件/系统/架构/显卡型号。
- 探测结果先只做 JSON 导入占位；探测脚本库、多厂商 schema、自动画像生成延后。
- 交付包先只做草稿和 manifest 预览；真正压缩包、install.sh、state.json 断点续装、执行日志回传延后。

## Product goals
- Current skeleton goals:
  - 先让用户能管理最小安装包资产：显卡驱动、Python 环境、FFmpeg、OpenCV 等。
  - 每个用户只管理自己的资产。
  - Admin 管理用户、查看全局资产。
  - 每个包能清楚表达文件、版本、适配条件、脚本槽位、安装顺序。
  - 能把多个安装项保存为交付包草稿并预览 manifest。
- Later goals:
  - 生成可断点续装的离线交付包。
  - 管理探测脚本并导入探测结果形成设备画像。
  - 对接测试平台和模型管理平台。
- Non-goals for current skeleton:
  - 不做平台直连远程设备的在线实施任务调度。
  - 不把 Atlas300Ipro 固化为唯一设备模型。
  - 不做真实压缩包、总控 install.sh、state.json 断点续装。
  - 不做复杂 recipe、依赖求解、测试平台和总装交接。
- Success signals:
  - 用户一眼知道“我有哪些包、哪些可用、哪些缺适配/脚本”。
  - 用户能理解新增包要填哪些最小信息。
  - 安装项适配条件来自设备管理中的选择框。
  - Admin 权限和普通用户权限边界明确。

## Personas and jobs
- Primary personas:
  - 普通环境包维护人员：上传/登记/编辑自己负责的包。
  - Admin：管理用户和资产归属，查看全局资产质量。
- User jobs:
  - 维护显卡驱动、Python 环境、FFmpeg、OpenCV 等基础包。
  - 补齐适配条件。
  - 补齐安装/验证脚本。
  - 确认 checksum 和资产状态。
- Key contexts of use:
  - 内网企业后台。
  - 工程人员桌面端使用为主。
  - 数据表格密度可偏高，但关键状态必须醒目。

## Information architecture
- Primary navigation for current skeleton:
  - 环境包资产
  - 设备管理
  - 探测结果
  - 交付包
  - Admin 管理
- Core routes/screens for current skeleton:
  - 登录页
  - 环境包资产列表/新增编辑
  - 设备管理/适配配置
  - 探测结果导入列表
  - 交付包草稿/manifest 预览
  - Admin 用户管理
  - 新增/编辑包表单
  - Admin 用户与资产归属管理
- Content hierarchy:
  1. 当前用户和权限范围
  2. 资产质量概览
  3. 我的包资产列表
  4. 选中包详情与可操作项
  5. Admin 管理入口

## Design principles
- Principle 1: 先资产，后编排。原型只把最小包资产管清楚。
- Principle 2: 归属优先。所有列表和操作都明确 owner，普通用户默认只能看自己的。
- Principle 3: 状态可见。缺适配、缺脚本、校验失败、草稿等必须显著标识。
- Tradeoffs: 相比视觉炫酷，优先信息清晰、字段完整、可开发落地。

## Visual language
- Color: Ant Design 蓝为主色；绿色表示可用/通过；橙色表示待补/草稿；红色表示异常/危险；紫色表示 Admin/共享。
- Typography: 企业后台默认无衬线字体；标题 22-28px；正文 13-14px；表格紧凑但保持可读。
- Spacing/layout rhythm: 24px 页面内边距，16px 卡片间距，8-12px 控件间距。
- Shape/radius/elevation: 8-12px 圆角，轻阴影，避免过度玻璃拟态。
- Motion: 原型不要求动效；实现时只使用 AntD 默认过渡。
- Imagery/iconography: 使用简单类型徽标，不使用装饰性插画。

## Components
- Existing components to reuse:
  - Ant Design Layout/Menu/Typography/Button/Table/Card/Form/Drawer/Tag/Tabs/Upload/Descriptions/Alert。
- New/changed components:
  - PackageQualityCards
  - PackageTable
  - PackageDetailDrawer
  - PackageEditForm
  - OwnershipScopeBar
  - AdminUserAssetPanel
- Variants and states:
  - package status: draft/active/inactive/deprecated
  - quality status: ok/missing_compatibility/missing_script/checksum_failed
  - visibility: private/shared/admin_only
- Token/component ownership: Prefer repo-native AntD usage; no new design system layer for MVP.

## Accessibility
- Target standard: WCAG 2.1 AA where practical.
- Keyboard/focus behavior: Forms, tabs, drawer actions must be keyboard reachable.
- Contrast/readability: Status tags must not rely on color alone; include text labels.
- Screen-reader semantics: Tables use real table structure; form labels explicit.
- Reduced motion and sensory considerations: No required motion.

## Responsive behavior
- Supported breakpoints/devices: Desktop first; tablet acceptable; mobile not primary for MVP.
- Layout adaptations: On narrow screens, right detail panel stacks below table.
- Touch/hover differences: Row click should also have explicit “查看/编辑” action.

## Interaction states
- Loading: Table skeleton or AntD loading state.
- Empty: Prompt “暂无安装包，上传第一个基础包”。
- Error: Show trace_id and retry action.
- Success: Message toast + row status refresh.
- Disabled: Non-owner edit/delete disabled with tooltip.
- Offline/slow network: Upload shows progress and retry.

## Content voice
- Tone: 工程化、明确、少营销词。
- Terminology:
  - 安装包：最小可复用环境资产。
  - 适配条件：硬件/系统/架构/显卡等匹配规则。
  - 资产归属：owner，决定普通用户可见和可编辑范围。
  - 共享资产：Admin 或 owner 发布给其他人组合使用的包。
- Microcopy rules: 操作按钮使用动词 + 对象，如“上传安装包”“补齐适配”“校验文件”。

## Implementation constraints
- Framework/styling system: React + TypeScript + Ant Design。
- Design-token constraints: 沿用 AntD 默认 token，可少量局部 CSS。
- Performance constraints: 包列表分页；避免一次加载全局资产。
- Compatibility constraints: 内网 Chrome/Edge 桌面端优先。
- Test/screenshot expectations: 原型需能直接打开；后续实现需可用 Playwright 截图回归。

## Open questions
- [ ] 是否需要“共享资产”审批？owner / 产品负责人 / 影响：决定权限模型复杂度。
- [ ] 安装包文件是否必须上传到平台 MinIO，还是可仅登记外部 URI？owner / 平台负责人 / 影响：上传表单和校验流程。
- [ ] 普通用户是否允许删除自己的 active 包？owner / 管理员 / 影响：审计和可追溯。
