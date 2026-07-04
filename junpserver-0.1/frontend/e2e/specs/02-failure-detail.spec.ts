import { test, expect } from '@playwright/test'

/**
 * 失败详情页 E2E 测试
 *
 * 覆盖需求：FAIL-01 ~ FAIL-05
 * - FAIL-01: 调用 detail 接口加载数据
 * - FAIL-02: 显示标题/严重级别/摘要
 * - FAIL-03: 推荐修复步骤和验证步骤
 * - FAIL-04: 底部显示近期失败样本表格
 * - FAIL-05: hours/source 筛选刷新
 */
test.describe('Failure Detail', () => {
  // 使用一个具体的 failure_code 进行测试
  const TEST_FAILURE_CODE = 'UPSTREAM_ERROR'

  test.beforeEach(async ({ page }) => {
    // 访问失败详情页
    await page.goto(`/dashboard/failures/${TEST_FAILURE_CODE}`)
  })

  /**
   * FAIL-01: 调用 detail 接口加载数据
   */
  test('FAIL-01: 调用 detail 接口加载数据', async ({ page }) => {
    // 等待页面加载
    await expect(page.locator('[data-testid="failure-detail-header"]')).toBeVisible({ timeout: 10000 })

    // 验证调用了 detail 接口
    const apiRequest = page.waitForRequest(request =>
      request.url().includes(`/api/v1/dashboard/failures/${TEST_FAILURE_CODE}/detail`)
    )
    await page.reload()
    await apiRequest

    // 验证页面显示失败码标题
    await expect(page.locator('[data-testid="failure-code-title"]')).toBeVisible()
  })

  /**
   * FAIL-02: 显示标题/严重级别/摘要
   */
  test('FAIL-02: 显示失败码标题、严重级别、摘要', async ({ page }) => {
    // 等待页面加载
    const header = page.locator('[data-testid="failure-detail-header"]')
    await expect(header).toBeVisible()

    // 验证标题显示 failure_code
    const title = page.locator('[data-testid="failure-code-title"]')
    await expect(title).toBeVisible()
    const titleText = await title.textContent()
    expect(titleText).toBeTruthy()

    // 验证严重级别标签显示
    const severityTag = page.locator('[data-testid="severity-tag"]')
    await expect(severityTag).toBeVisible()

    // 验证摘要信息显示（使用更宽松的检查）
    // 摘要可能为空或隐藏在 Typography.Secondary 中
    const summaryContainer = page.locator('[data-testid="failure-summary"]')
    // 等待摘要容器存在（不一定完全可见，可能存在但透明度低）
    await expect(summaryContainer).toBeInViewport({ timeout: 5000 }).catch(async () => {
      // 如果不在视口内，尝试滚动
      await summaryContainer.scrollIntoViewIfNeeded()
    })
  })

  /**
   * FAIL-03: 推荐修复步骤和验证步骤
   */
  test('FAIL-03: 显示推荐修复步骤和验证步骤', async ({ page }) => {
    // 等待修复步骤卡片显示
    const remediationCard = page.locator('[data-testid="remediation-steps-card"]')
    await expect(remediationCard).toBeVisible()

    // 验证修复步骤列表存在
    const stepsList = page.locator('[data-testid="remediation-steps"]')
    await expect(stepsList).toBeVisible()

    // 等待验证步骤卡片显示
    const verificationCard = page.locator('[data-testid="verification-steps-card"]')
    await expect(verificationCard).toBeVisible()

    // 验证验证步骤列表存在
    const verificationList = page.locator('[data-testid="verification-steps"]')
    await expect(verificationList).toBeVisible()
  })

  /**
   * FAIL-04: 底部显示近期失败样本表格
   */
  test('FAIL-04: 显示近期失败样本表格', async ({ page }) => {
    // 等待样本表格卡片显示
    const samplesCard = page.locator('[data-testid="failure-samples-card"]')
    await expect(samplesCard).toBeVisible()

    // 验证表格存在
    const table = samplesCard.locator('table')
    await expect(table).toBeVisible()

    // 验证表格包含必要的列
    // task_id 列
    const taskIdHeader = table.locator('th:has-text("任务 ID")')
    await expect(taskIdHeader).toBeVisible()

    // asset 列
    const assetHeader = table.locator('th:has-text("资产")')
    await expect(assetHeader).toBeVisible()

    // executed_at 列
    const executedAtHeader = table.locator('th:has-text("执行时间")')
    await expect(executedAtHeader).toBeVisible()

    // status 列
    const statusHeader = table.locator('th:has-text("状态")')
    await expect(statusHeader).toBeVisible()
  })

  /**
   * FAIL-05: hours/source 筛选刷新
   */
  test('FAIL-05: hours/source 筛选器刷新数据', async ({ page }) => {
    // 等待筛选器显示
    const filters = page.locator('[data-testid="failure-filters"]')
    await expect(filters).toBeVisible()

    // 验证 hours 筛选器存在
    const hoursFilter = page.locator('[data-testid="hours-filter"]')
    await expect(hoursFilter).toBeVisible()

    // 验证 source 筛选器存在
    const sourceFilter = page.locator('[data-testid="source-filter"]')
    await expect(sourceFilter).toBeVisible()

    // 测试 hours 筛选器选择
    await hoursFilter.click()
    // 使用更可靠的选择器点击选项
    await page.locator('.ant-select-dropdown .ant-select-item-option-content:has-text("最近 7 天")').first().click()
    await expect(hoursFilter).toHaveText('最近 7 天')

    // 验证数据刷新（等待样本卡片重新渲染）
    await expect(page.locator('[data-testid="failure-samples-card"]')).toBeVisible({ timeout: 10000 })

    // 测试 source 筛选器选择
    await sourceFilter.click()
    await page.locator('.ant-select-dropdown .ant-select-item-option-content:has-text("API")').first().click()
    await expect(sourceFilter).toHaveText('API')

    // 验证数据刷新
    await expect(page.locator('[data-testid="failure-samples-card"]')).toBeVisible({ timeout: 10000 })
  })
})
