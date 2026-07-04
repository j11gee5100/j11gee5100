import { Tag } from 'antd'

type RiskLevel = 'low' | 'medium' | 'high'

interface RiskBadgeProps {
  level: RiskLevel
  size?: 'small' | 'default'
}

/**
 * RiskBadge displays risk level with color-coded Tag
 * - low: green (success)
 * - medium: yellow/orange (warning)
 * - high: red (error)
 *
 * Note: Ant Design v5 Tag doesn't support size prop directly.
 * For 'small' display, consider using smaller font through style.
 */
export default function RiskBadge({ level }: RiskBadgeProps) {
  const colorMap: Record<RiskLevel, string> = {
    low: 'success',
    medium: 'warning',
    high: 'error',
  }

  const labelMap: Record<RiskLevel, string> = {
    low: 'LOW',
    medium: 'MEDIUM',
    high: 'HIGH',
  }

  return (
    <Tag color={colorMap[level]} style={{ borderRadius: 0 }}>
      {labelMap[level]}
    </Tag>
  )
}