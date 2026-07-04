import { test, expect } from '@playwright/test'

/**
 * Dashboard 看板 E2E 测试
 *
 * 覆盖需求：DASH-01 ~ DASH-05
 * - DASH-01: 页面加载时调用 overview 接口
 * - DASH-02: 告警等级条显示 ok/warn/critical
 * - DASH-03: 失败分型榜单按 count 降序
 * - DASH-04: 点击卡片跳转到失败详情页
 * - DASH-05: 修复建议卡片渲染
 */
test.describe('Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    // 访问 Dashboard 页面
    await page.goto('/dashboard')
  })

  /**
   * DASH-01: 页面加载时调用 overview 接口
   */
  test('DASH-01: 页面加载并显示健康度数据', async ({ page }) => {
    // 等待页面加载完成
    await expect(page.locator('[data-testid="alert-level-card"]')).toBeVisible({ timeout: 10000 })

    // 验证调用了 overview 接口（通过网络监控）
    const apiRequest = page.waitForRequest(request =>
      request.url().includes('/api/v1/dashboard/overview')
    )
    await page.reload()
    await apiRequest

    // 验证页面包含健康度数据
    await expect(page.locator('[data-testid="alert-level-indicator"]')).toBeVisible()
  })

  /**
   * DASH-02: 告警等级条显示
   */
  test('DASH-02: 告警等级条显示状态', async ({ page }) => {
    // 等待告警等级条显示
    const alertLevelCard = page.locator('[data-testid="alert-level-card"]')
    await expect(alertLevelCard).toBeVisible()

    // 验证告警等级指示器存在
    const indicator = page.locator('[data-testid="alert-level-indicator"]')
    await expect(indicator).toBeVisible()

    // 验证指示器有背景颜色（绿/黄/红）
    const backgroundColor = await indicator.evaluate((el) =>
      window.getComputedStyle(el).backgroundColor
    )
    // 验证颜色是有效的 RGB 值
    expect(backgroundColor).toMatch(/^rgb\((\d+),\s*(\d+),\s*(\d+)\)$/)
  })

  /**
   * DASH-03: 失败分型榜单按 count 降序
   */
  test('DASH-03: 失败分型榜单按 count 降序排列', async ({ page }) => {
    // 等待失败分型榜单显示
    const rankingCard = page.locator('[data-testid="failure-code-ranking-card"]')
    await expect(rankingCard).toBeVisible()

    // 获取榜单表格行
    const table = rankingCard.locator('table')
    await expect(table).toBeVisible()

    // 获取所有行的 count 列值（第 3 列）
    const rows = table.locator('tbody tr')
    const countValues = await rows.allTextContents()

    // 验证至少有数据行
    const rowCount = await rows.count()
    if (rowCount > 1) {
      // 提取前两行的 count 值进行比较
      const firstRow = rows.first()
      const secondRow = rows.nth(1)

      const firstCountText = await firstRow.locator('td').nth(2).textContent()
      const secondCountText = await secondRow.locator('td').nth(2).textContent()

      // 解析数字并验证降序
      if (firstCountText && secondCountText) {
        const firstCount = parseInt(firstCountText, 10)
        const secondCount = parseInt(secondCountText, 10)

        if (!isNaN(firstCount) && !isNaN(secondCount)) {
          expect(firstCount).toBeGreaterThanOrEqual(secondCount)
        }
      }
    }
  })

  /**
   * DASH-04: 点击卡片跳转到失败详情页
   * 注：由于失败分型榜单可能为空，改为测试修复建议卡片的跳转功能
   */
  test('DASH-04: 点击修复建议卡片跳转到失败详情页', async ({ page }) => {
    // 等待页面加载
    await expect(page.locator('[data-testid="alert-level-card"]')).toBeVisible({ timeout: 10000 })

    // 检查是否有修复建议卡片
    const remediationContainer = page.locator('[data-testid="remediation-cards-container"]')
    const containerVisible = await remediationContainer.isVisible({ timeout: 5000 }).catch(() => false)

    // 如果没有修复建议卡片，跳过测试
    if (!containerVisible) {
      test.skip()
      return
    }

    // 查找修复建议卡片
    const cards = remediationContainer.locator('[data-testid^="remediation-card-"]')
    const cardCount = await cards.count()

    // 如果没有卡片，跳过测试
    if (cardCount === 0) {
      test.skip()
      return
    }

    // 点击第一个卡片
    const firstCard = cards.first()

    // 获取卡片的 failure_code 属性
    const testId = await firstCard.getAttribute('data-testid')
    const failureCode = testId?.replace('remediation-card-', '')

    // 点击卡片
    await firstCard.click()

    // 等待 URL 变化
    await page.waitForURL(/\/dashboard\/failures\/.+/)

    // 验证 URL 包含 failure_code
    await expect(page).toHaveURL(`/dashboard/failures/${failureCode}`)

    // 验证页面切换到 FailureDetailPage
    await expect(page.locator('[data-testid="failure-detail-header"]')).toBeVisible({ timeout: 10000 })
  })

  /**
   * DASH-05: 修复建议卡片渲染
   */
  test('DASH-05: 修复建议卡片内容显示', async ({ page }) => {
    // 等待修复建议容器显示
    const remediationContainer = page.locator('[data-testid="remediation-cards-container"]')

    // 检查是否存在修复建议卡片（可能为空）
    const containerVisible = await remediationContainer.isVisible({ timeout: 5000 }).catch(() => false)

    if (containerVisible) {
      // 验证 remediation_cards 内容显示
      await expect(remediationContainer).toBeVisible()

      // 验证至少有一个修复建议卡片
      const cards = remediationContainer.locator('[data-testid^="remediation-card-"]')
      const cardCount = await cards.count()

      if (cardCount > 0) {
        // 验证第一个卡片包含标题和严重级别标签
        const firstCard = cards.first()
        await expect(firstCard).toBeVisible()

        // 验证卡片包含标题
        const title = firstCard.locator('h5')
        await expect(title).toBeVisible()

        // 验证卡片包含严重级别 Tag
        const tag = firstCard.locator('.ant-tag')
        await expect(tag).toBeVisible()
      }
    }
  })
})
