# Phase 2: 模板中心与策略治理 - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-07
**Phase:** 02-template-policy
**Areas discussed:** 模板列表布局, 模板创建流程, 策略评估预览, 审计日志展示

---

## 模板列表布局

| Option | Description | Selected |
|--------|-------------|----------|
| 表格布局 | 更适合管理类数据，支持排序筛选，与 Ant Design Table 组件一致 | |
| 卡片布局 | 延续 Phase 1 卡片风格，每个模板一张卡片 | ✓ |
| 列表紧凑模式 | 每行一条，左边模板名称+风险标签，右边启停+操作按钮 | |

**User's choice:** 卡片布局
**Notes:** 延续 Phase 1 设计风格，启停开关在卡片右上角

### 分页方式

| Option | Description | Selected |
|--------|-------------|----------|
| 传统分页 | 适合管理后台，用户可以跳转指定页 | |
| 无限滚动 | 滚动加载更多，延续 Phase 1 看板风格 | ✓ |

**User's choice:** 无限滚动

### 启停位置

| Option | Description | Selected |
|--------|-------------|----------|
| 卡片右上角 | 操作直观，类似 Linear issue cards | ✓ |
| 卡片右侧边缘 | 与卡片内容对齐，信息层级更关联 | |

**User's choice:** 卡片右上角

---

## 模板创建流程

### 创建入口

| Option | Description | Selected |
|--------|-------------|----------|
| 弹窗表单 | 弹窗表单，不需要跳转页面 | ✓ |
| 独立页面 | 单独页面，更复杂表单的考虑 | |

**User's choice:** 弹窗表单

### 命令输入

| Option | Description | Selected |
|--------|-------------|----------|
| 文本框 (Textarea) | 适合多行命令，脚本片段 | |
| 单行输入框 | 适合单行命令，紧凑简洁 | ✓ |

**User's choice:** 单行输入框

### 风险等级

| Option | Description | Selected |
|--------|-------------|----------|
| 下拉选择 (low/medium/high) | 直观明确，规范选项 | ✓ |
| 自由输入 | 更灵活，但可能不规范 | |

**User's choice:** 下拉选择

### 表单布局

| Option | Description | Selected |
|--------|-------------|----------|
| 上下分区 | 左列基础信息，右列命令区域 | ✓ |
| 单列依次排列 | 全部字段依次排列，更简单 | |

**User's choice:** 上下分区

---

## 策略评估预览

### 触发时机

| Option | Description | Selected |
|--------|-------------|----------|
| 实时触发 | 每次输入后触发，用户体验更好 | |
| 手动触发 | 添加"预览"按钮，调用量可控 | ✓ |
| 防抖触发 | 停顿一定时间后自动触发 | |

**User's choice:** 手动触发

### 预览结果

| Option | Description | Selected |
|--------|-------------|----------|
| 输入框下方实时显示 | 命令输入框下方显示预警色 | |
| 右侧侧边栏显示 | 右侧固定区域显示评估结果 | |
| 单独弹窗 (Modal) | 弹窗显示完整评估结果 | ✓ |

**User's choice:** 单独弹窗

---

## 审计日志展示

### 日志布局

| Option | Description | Selected |
|--------|-------------|----------|
| 表格布局 | 适合审计数据，有 trace_id/action/operator_id/timestamp | |
| 卡片布局 | 视觉效果更现代 | ✓ |
| 时间线 (Timeline) | 时间线形式展示，适合浏览型阅读 | |

**User's choice:** 卡片布局

### 筛选位置

| Option | Description | Selected |
|--------|-------------|----------|
| 表格顶部筛选栏 | 筛选器占据一行 | |
| 独立筛选区域 | 筛选器单独区域，与表格分离 | ✓ |

**User's choice:** 独立筛选区域

### JSON 详情

| Option | Description | Selected |
|--------|-------------|----------|
| 卡片内展开 | 卡片内有"查看详情"按钮，点击展开 | |
| 弹窗查看详情 | 点击卡片后弹窗显示完整 JSON | ✓ |
| 行内格式化显示 | 类似代码块展示，key-value 高亮 | |

**User's choice:** 弹窗查看详情

### 时间范围

| Option | Description | Selected |
|--------|-------------|----------|
| 预设范围选择 (1h/24h/7d) | 内置选项，快速切换 | ✓ |
| 日期范围选择器 | 更精确控制 | |

**User's choice:** 预设范围选择

---

## Claude's Discretion

- 卡片精确间距和排版数值
- 风险等级标签颜色（延续 Phase 1 三色方案）
- 骨架屏具体样式
- 空状态友好提示文案

## Deferred Ideas

- 批量模板操作 — v2 增强
- 模板版本管理 — v2 增强
- 任务创建页跳转审批详情 — Phase 4
- 审批中心页面 — Phase 3