# ADR-0004: 前端采用 React + TypeScript + Vite

- 状态：Accepted
- 日期：2026-04-02

## 背景

OpsPaw 的前端主要是企业后台控制台场景：

- 资产中心
- 任务中心
- 审批中心
- 配置中心
- 执行详情与日志
- 看板与证据卡

## 决策

前端采用：

- `React`
- `TypeScript`
- `Vite`
- `TanStack Query`
- `React Router`
- `Ant Design` 或组织现有设计系统
- `ECharts`

## 备选方案

- Vue 生态
- Next.js 全栈方案
- 自建轻量组件体系

## 选择理由

- React + TypeScript 在企业后台交付效率和人员匹配上更稳
- Vite 适合快速开发和本地调试
- TanStack Query 对数据驱动页面和状态刷新非常合适
- Ant Design 对表格、表单、审批类后台页面成熟度高

## 结果

优点：

- 交付效率高
- 常见后台场景组件成熟
- 容易与后端 OpenAPI 对接

代价：

- 如果组织已有统一前端标准，需要尽量跟随，避免双轨

