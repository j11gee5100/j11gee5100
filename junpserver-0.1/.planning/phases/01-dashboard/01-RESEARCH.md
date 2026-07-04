# Phase 1 Research: Dashboard 前端实现

**Researched:** 2026-04-06
**Responder Language:** Chinese

## 技术栈建议

### 核心框架
- **React 18+** - 当前最新版本，支持并发特性
- **TypeScript 5+** - 类型安全
- **Vite** - 快速构建和热更新

### UI 组件库
- **Ant Design 5.x** - 企业级组件库
  - Card 组件用于卡片布局
  - Alert 组件用于告警条（success/warning/error 对应 ok/warn/critical）
  - Table 组件用于失败样本表格
  - Skeleton 组件用于加载骨架屏
  - Statistic 组件用于 KPI 展示

### 数据管理
- **TanStack Query (React Query) 5.x** - 服务端状态管理
  - 自动缓存和后台刷新
  - 支持 60 秒轮询刷新
  - 错误重试机制
- **Zustand** (可选) - 轻量级客户端状态管理

### 路由
- **React Router 6.x** - 客户端路由

### 样式
- **Tailwind CSS** - 原子化 CSS，配合 Ant Design 使用

## 目录结构建议

```
src/
├── api/
│   ├── client.ts          # Axios 实例配置
│   └── dashboard.ts       # Dashboard API 调用
├── components/
│   ├── ui/
│   │   ├── AlertBanner.tsx     # 告警条组件
│   │   ├── StatCard.tsx        # 统计卡片
│   │   ├── FailureTable.tsx    # 失败样本表格
│   │   └── MetricCard.tsx      # 指标卡片
│   └── dashboard/
│       ├── DashboardPage.tsx
│       ├── FailureDetailPage.tsx
│       └── DashboardFilters.tsx
├── hooks/
│   ├── useDashboard.ts    # Dashboard 数据轮询
│   └── useFailureCode.ts  # 失败详情数据
├── pages/
│   ├── Dashboard.tsx
│   └── FailureDetail.tsx
├── types/
│   └── api.ts             # API 响应类型定义
└── utils/
    └── formatters.ts      # 时间/数字格式化
```

## 关键组件实现建议

### 告警条组件 (AlertBanner)
```typescript
interface AlertBannerProps {
  level: 'ok' | 'warn' | 'critical';
  summary: string;
}

// 颜色映射：
// ok → #52c41a (Ant Design green-6)
// warn → #faad14 (Ant Design gold-6)
// critical → #ff4d4f (Ant Design red-5)
```

### 数据轮询配置 (useDashboard)
```typescript
const { data, isLoading, error } = useQuery({
  queryKey: ['dashboard', { hours: 24 }],
  queryFn: () => fetchDashboardOverview(hours),
  refetchInterval: 60000, // 60 秒
  retry: 2,
});
```

### 失败分型榜单 (Top 5)
```typescript
// 按 count 降序排列，取前 5
const topFailures = sortBy(data?.by_failure_code, 'count').reverse().slice(0, 5);
```

## API 响应类型定义

```typescript
interface DashboardOverview {
  alerts: {
    level: 'ok' | 'warn' | 'critical';
    summary: string;
  };
  failure_summary: {
    total_failed: number;
    by_failure_code: Array<{
      failure_code: string;
      count: number;
    }>;
  };
  remediation_cards: Array<{
    failure_code: string;
    title: string;
    severity: 'low' | 'medium' | 'high';
    summary: string;
    recommended_actions: string[];
  }>;
}

interface FailureDetail {
  failure_code: string;
  title: string;
  severity: string;
  summary: string;
  recommended_actions: string[];
  verification_steps: string[];
  recent_failed_tasks: Array<{
    task_id: string;
    source: string;
    risk_level: string;
    target_asset_id: string;
    error_message: string;
    updated_at: string;
  }>;
}
```

## 空状态处理

无失败数据时使用 Ant Design 的 Empty 组件：

```tsx
<Empty
  image={Empty.PRESENTED_IMAGE_SIMPLE}
  description="系统健康，最近 24 小时无失败任务"
/>
```

## 错误处理

接口失败时显示：
- Alert 错误提示
- 重试按钮
- trace_id 展示

```tsx
{error && (
  <Alert
    type="error"
    message="加载失败"
    description={`错误：${error.message} (trace_id: ${traceId})`}
    action={
      <Button size="small" onClick={() => refetch()}>重试</Button>
    }
  />
)}
```

## 技术风险

1. **跨域问题** - 开发环境需配置 Vite proxy
2. **时间格式** - 后端 ISO 日期需前端格式化显示
3. **表格分页** - 大数据量时使用虚拟滚动

## 依赖版本

```json
{
  "react": "^18.2.0",
  "antd": "^5.12.0",
  "@tanstack/react-query": "^5.0.0",
  "react-router-dom": "^6.20.0",
  "axios": "^1.6.0"
}
```

---

*Research completed: 2026-04-06*
