# Phase 04 UAT 问题汇总报告

**测试时间:** 2026-04-08  
**测试范围:** Phase 04 全部功能  
**远程服务:** http://172.24.26.12:3000  
**后端 API:** http://172.24.26.12:18080

---

## 问题汇总

### 问题 1: Vite 代理配置错误 ✅ 已修复

**问题描述:** Vite 代理配置为 `http://localhost:8000`，但远程后端 API 实际运行在 `http://172.24.26.12:18080`

**影响:** 前端无法获取后端 API 数据，所有页面功能失效

**修复:** 更新 `vite.config.ts` 代理配置为正确的后端地址

**状态:** 已修复并部署

---

### 问题 2: matched_rules 渲染崩溃 ✅ 已修复

**问题描述:** `PolicyEvaluationModal.tsx` 和 `TaskCreatePage.tsx` 中 matched_rules 对象被直接渲染为 React 子元素

**错误信息:** `Objects are not valid as a React child (found: object with keys {source, rule_id, pattern, hard_block, description})`

**修复:** 
1. 更新类型定义 `PolicyEvaluationResponse.matched_rules: MatchedRule[]`
2. 修改渲染逻辑使用结构化展示

**状态:** 已修复并部署

---

### 问题 3: 模板创建无策略拦截 ✅ 已修复

**问题描述:** `TemplateFormModal.tsx` 提交时没有检查策略评估结果

**影响:** 可以创建被策略拦截的命令模板

**修复:** 
1. 添加 `evalResult` 状态保存评估结果
2. 当命令被拦截时禁用提交按钮
3. 显示警告信息

**状态:** 已修复并部署

---

## 待测试项目

### Test 1: 任务创建页 UI 完整性验证
- [ ] 选择模板或自定义命令两种入口存在
- [ ] 模板选择使用 SearchSelect 组件
- [ ] 资产/系统用户选择联动查询
- [ ] 必填字段红色星号标记
- [ ] 表单上下分区布局

### Test 2: 策略预览按钮交互验证
- [ ] 策略预览按钮存在
- [ ] 点击打开 PolicyEvaluationModal
- [ ] 评估结果显示风险等级、审批需求、matched_rules
- [ ] 命中策略时显示 block_reason 警告

### Test 3: 高风险任务跳转验证
- [ ] RiskConfirmModal 确认弹窗显示
- [ ] 确认后跳转到 /approvals/:approvalId 页面
- [ ] approval_required=true 时按钮文案为"提交审批"

### Test 4: 策略拦截按钮禁用验证
- [ ] 评估结果显示红色 Alert（命令被策略拦截）
- [ ] 提交按钮 disabled 状态
- [ ] 显示 block_reason 和 matched_rules

### Test 5: 审计列表筛选验证
- [ ] entity_type 下拉包含"任务"选项
- [ ] action 下拉包含 create/update/delete/enable/disable
- [ ] 时间范围预设选择（1h/24h/7d）
- [ ] 筛选组合正常工作

### Test 6: 任务创建到审计记录闭环验证
- [ ] 选择 entity_type="任务" 筛选
- [ ] 能看到刚创建的任务记录
- [ ] 点击卡片展开 detail JSON
- [ ] 包含 task_id、command 等信息

---

## 下一步

1. ✅ 后端 API 地址修复完成
2. ✅ 等待服务重启完成
3. ⏳ 执行完整 UAT 测试流程
4. ⏳ 记录测试结果

---

*创建时间：2026-04-08*
*最后更新：2026-04-08*