import { useState } from 'react'
import { Tabs, message, Skeleton, Empty, Typography, Alert, Button } from 'antd'
import { ReloadOutlined } from '@ant-design/icons'
import ApprovalCard from '../components/ApprovalCard'
import ApprovalDrawer from '../components/ApprovalDrawer'
import { useApprovals, useApprove } from '../hooks/useApprovals'
import type { Approval } from '../types/approval'

const { Title } = Typography

/**
 * ApprovalListPage - 审批中心页面
 *
 * Per D-02: L1/L2 Tab 切换按层级筛选
 * Per D-10: 409 冲突显示 Toast 提示并自动刷新
 *
 * Features:
 * - Tab 切换查看不同层级待审批列表
 * - Grid 响应式布局展示审批卡片
 * - 通过/驳回快速操作按钮
 * - 点击卡片打开详情抽屉
 * - 409 冲突自动刷新
 */
export default function ApprovalListPage() {
  // State 管理
  const [currentLevel, setCurrentLevel] = useState(1)
  const [selectedApproval, setSelectedApproval] = useState<Approval | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)

  // Hooks
  const { data: approvals, isLoading, isError, error, refetch } = useApprovals(currentLevel)
  const approveMutation = useApprove()

  // Tab 切换处理
  const handleTabChange = (key: string) => {
    setCurrentLevel(parseInt(key))
  }

  // 通过操作处理
  const handleApprove = (approvalId: string) => {
    approveMutation.mutate(
      { approvalId, comment: undefined },
      {
        onSuccess: () => {
          message.success('审批通过')
          refetch()
        },
        onError: (err: any) => {
          // 409 冲突处理
          if (err?.response?.status === 409) {
            message.warning('审批状态已变更')
            refetch()
          } else {
            message.error(err?.message || '操作失败')
          }
        },
      }
    )
  }

  // 驳回操作处理 - 打开抽屉让用户填写原因
  const handleReject = (approvalId: string) => {
    const approval = approvals?.find((a) => a.approval_id === approvalId)
    if (approval) {
      setSelectedApproval(approval)
      setDrawerOpen(true)
    }
  }

  // 查看详情处理
  const handleViewDetails = (approval: Approval) => {
    setSelectedApproval(approval)
    setDrawerOpen(true)
  }

  // 抽屉操作完成处理
  const handleOperationComplete = () => {
    setDrawerOpen(false)
    setSelectedApproval(null)
    refetch()
  }

  const tabItems = [
    {
      key: '1',
      label: `L1 审批 (${currentLevel === 1 ? approvals?.length ?? 0 : 0})`,
    },
    {
      key: '2',
      label: `L2 审批 (${currentLevel === 2 ? approvals?.length ?? 0 : 0})`,
    },
  ]

  return (
    <div style={{ padding: '24px' }}>
      {/* 页面标题 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <Title level={3} style={{ margin: 0 }}>审批中心</Title>
        <Button
          icon={<ReloadOutlined />}
          onClick={() => refetch()}
        >
          刷新
        </Button>
      </div>

      {/* L1/L2 Tab 切换 */}
      <Tabs
        activeKey={String(currentLevel)}
        items={tabItems}
        onChange={handleTabChange}
      />

      {/* Loading 状态 - 骨架屏 */}
      {isLoading && (
        <div data-testid="skeleton-container" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '16px' }}>
          {[1, 2, 3, 4].map((i) => (
            <div key={i} style={{ border: '1px solid #f0f0f0', borderRadius: '8px', padding: '16px' }}>
              <Skeleton active paragraph={{ rows: 3 }} />
            </div>
          ))}
        </div>
      )}

      {/* 错误状态 */}
      {isError && (
        <Alert
          type="error"
          message="加载失败"
          description={error?.message || '未知错误'}
          action={
            <Button onClick={() => refetch()}>
              重试
            </Button>
          }
        />
      )}

      {/* 空状态 */}
      {!isLoading && !isError && approvals && approvals.length === 0 && (
        <div style={{ textAlign: 'center', padding: '48px 0' }}>
          <Empty description="当前层级无待审批任务" />
        </div>
      )}

      {/* 卡片列表 Grid 响应式布局 */}
      {!isLoading && !isError && approvals && approvals.length > 0 && (
        <div
          data-testid="approval-card-grid"
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
            gap: '16px',
          }}
        >
          {approvals.map((approval) => (
            <ApprovalCard
              key={approval.approval_id}
              approval={approval}
              onApprove={handleApprove}
              onReject={handleReject}
              onViewDetails={handleViewDetails}
            />
          ))}
        </div>
      )}

      {/* 详情抽屉 */}
      <ApprovalDrawer
        open={drawerOpen}
        approval={selectedApproval}
        onClose={() => {
          setDrawerOpen(false)
          setSelectedApproval(null)
        }}
        onOperationComplete={handleOperationComplete}
      />
    </div>
  )
}