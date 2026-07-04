import dayjs from 'dayjs'
import relativeTime from 'dayjs/plugin/relativeTime'

// 启用相对时间插件
dayjs.extend(relativeTime)

export const formatDateTime = (date: string): string => {
  return dayjs(date).format('YYYY-MM-DD HH:mm:ss')
}

export const formatRelativeTime = (date: string): string => {
  return dayjs(date).fromNow()
}

export const formatNumber = (num: number): string => {
  return num.toLocaleString('zh-CN')
}
