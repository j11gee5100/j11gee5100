export const visibilityOptions = [
  { label: '私有', value: 'private' },
  { label: '共享', value: 'shared' },
]

const visibilityLabelMap = visibilityOptions.reduce<Record<string, string>>((acc, item) => {
  acc[item.value] = item.label
  return acc
}, {})

export function formatVisibility(value?: string) {
  if (!value) return '-'
  return visibilityLabelMap[value] || value
}

export function visibilityTagColor(value?: string) {
  if (value === 'shared') return 'blue'
  if (value === 'private') return 'default'
  return 'default'
}
