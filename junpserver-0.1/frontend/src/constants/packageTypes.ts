export const packageTypeOptions = [
  { label: '显卡驱动', value: 'driver' },
  { label: 'Python 环境', value: 'python_runtime' },
  { label: 'Python 依赖', value: 'python_dependency' },
  { label: '系统依赖', value: 'system_dependency' },
  { label: '运行时', value: 'runtime' },
  { label: '推理服务', value: 'inference_server' },
  { label: '应用包', value: 'application_package' },
  { label: '命令步骤', value: 'command_step' },
  { label: '补丁', value: 'patch' },
  { label: '自定义', value: 'custom' },
]

export const packageTypeFilterOptions = [
  { label: '全部类型', value: '' },
  ...packageTypeOptions,
]

export const packageTypeLabel = packageTypeOptions.reduce<Record<string, string>>((acc, item) => {
  acc[item.value] = item.label
  return acc
}, {})

export function formatPackageType(value?: string) {
  if (!value) return '-'
  return packageTypeLabel[value] || value
}
