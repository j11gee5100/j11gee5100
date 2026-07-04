import { Typography, Card } from 'antd'

interface PlaceholderPageProps {
  title: string
  path: string
}

/**
 * Placeholder page component for routes that are under development
 * Will be replaced by actual page components in subsequent plans
 */
export function PlaceholderPage({ title, path }: PlaceholderPageProps) {
  return (
    <div style={{ padding: '24px' }}>
      <Card>
        <Typography.Title level={3}>{title}</Typography.Title>
        <Typography.Text type="secondary">
          页面开发中 - Path: {path}
        </Typography.Text>
        <Typography.Paragraph style={{ marginTop: '16px' }}>
          该页面将在后续计划中实现完整功能。
        </Typography.Paragraph>
      </Card>
    </div>
  )
}

export default PlaceholderPage