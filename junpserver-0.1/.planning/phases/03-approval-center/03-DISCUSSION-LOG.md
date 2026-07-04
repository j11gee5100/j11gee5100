# Phase 03: 审批中心（多级） - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-07
**Phase:** 03-approval-center
**Areas discussed:** 列表布局, 详情展示, 操作交互, Tab切换, 状态冲突, 超时显示, 操作区

---

## 审批列表布局

| Option | Description | Selected |
|--------|-------------|----------|
| 表格列表 | 紧凑单行展示，适合批量处理 | |
| 卡片列表 | 延续模板中心风格，信息更丰富 | ✓ |

**User's choice:** 卡片列表 — 延续 Phase 01/02 设计风格
**Notes:** 保持设计一致性

---

## 审批详情展示

| Option | Description | Selected |
|--------|-------------|----------|
| 独立详情页 | 跳转新页面，完整展示 | |
| 右侧抽屉/弹窗 | 在列表页内完成操作 | ✓ |
| 双轨 | 列表行内+详情页 | |

**User's choice:** 右侧抽屉/弹窗 — 操作便捷，无需页面跳转

---

## 原因输入

| Option | Description | Selected |
|--------|-------------|----------|
| 驳回必填 | 通过/升级可选，驳回必填 | ✓ |
| 全部必填 | 三操作都需填写原因 | |
| 全部可选 | 所有操作原因都可选 | |

**User's choice:** 驳回必填 — 确保审计记录完整

---

## 时间线展示

| Option | Description | Selected |
|--------|-------------|----------|
| 独立时间线组件 | Timeline 组件垂直布局 | |
| 详情页内嵌区块 | 时间线嵌入详情页底部 | ✓ |
| 可折叠区块 | 点击展开查看 | |

**User's choice:** 详情页内嵌区块 — 无需滚动即可看到完整历史

---

## Tab切换

| Option | Description | Selected |
|--------|-------------|----------|
| Tab 切换 | L1/L2 Tab 点击切换 | ✓ |
| 无 Tab，统一列表+筛选 | 列表上方筛选 | |

**User's choice:** Tab 切换 — 按 current_level 筛选显示

---

## 状态冲突

| Option | Description | Selected |
|--------|-------------|----------|
| Toast 提示+自动刷新 | 其他审批人已处理时提示并刷新 | ✓ |
| 确认弹窗 | 弹窗展示冲突详情 | |

**User's choice:** Toast 提示+自动刷新 — 快速响应冲突

---

## 超时显示

| Option | Description | Selected |
|--------|-------------|----------|
| 卡片显示超时状态 | 显示超时图标和剩余时间 | ✓ |
| 不显示，自动过滤 | 超时项目自动消失 | |
| 可筛选查看 | 需从筛选条件排除 | |

**User's choice:** 卡片显示超时状态 — 用户可见超时状态

---

## 操作按钮位置

| Option | Description | Selected |
|--------|-------------|----------|
| 卡片底部操作按钮 | 快捷操作入口 | ✓ |
| 详情抽屉内操作 | 仅抽屉内显示按钮 | |

**User's choice:** 卡片底部操作按钮 — 快速操作入口

---

## Claude's Discretion

- 卡片具体间距和排版数值
- 超时标签颜色和图标选择
- 升级确认弹窗样式
- 时间线节点颜色（按操作类型区分）

## Deferred Ideas

- 批量审批操作（批量通过/驳回） — v2 增强
- 审批代理授权（休假期间代理审批） — v2 增强
- 审批提醒通知（邮件/企微推送） — v2 增强