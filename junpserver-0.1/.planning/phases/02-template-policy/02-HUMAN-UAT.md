---
status: partial
phase: 02-template-policy
source: [02-VERIFICATION.md]
started: 2026-04-07T20:35:00Z
updated: 2026-04-07T20:35:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. UI视觉验证 - 模板中心卡片布局
expected: 卡片显示 template_id/name/risk_level(en标签颜色)/enabled状态，启停开关位于右上角
result: [pending]

### 2. UI交互验证 - 模板表单预览按钮
expected: 点击预览按钮打开策略评估弹窗，显示 allowed/block_reason/matched_rules
result: [pending]

### 3. UI视觉验证 - 黑名单卡片标签
expected: 硬拦截显示红色标签，软拦截显示蓝色标签
result: [pending]

### 4. UI交互验证 - 筛选区域功能
expected: entity_type/action/operator_id/time_range 四个筛选字段正常工作，切换后刷新列表
result: [pending]

### 5. UI交互验证 - 详情弹窗JSON展示
expected: 点击卡片打开详情弹窗，JSON 使用格式化显示
result: [pending]

## Summary

total: 5
passed: 0
issues: 0
pending: 5
skipped: 0
blocked: 0

## Gaps