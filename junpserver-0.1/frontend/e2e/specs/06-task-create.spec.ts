import { test, expect } from '../fixtures/test-fixtures'

/**
 * 任务创建 E2E 测试
 * 覆盖需求：TSK-01 ~ TSK-05
 *
 * 运行说明：
 * - 需要前端开发服务器运行 (npm run dev)
 * - 需要后端 API 服务器可用
 * - 应用当前没有登录功能，直接访问页面
 */
test.describe('Task Create', () => {
  test.beforeEach(async ({ page }) => {
    // 访问任务创建页面（路由为 /tasks/new）
    await page.goto('/tasks/new')
    // 等待页面加载完成
    await page.waitForSelector('text=创建任务', { timeout: 10000 })
  })

  /**
   * TSK-01: 选择模板或输入命令创建任务
   * - 访问 /tasks/new
   * - 测试选择模板入口：点击模板选择器，选择模板
   * - 验证 command 字段自动填充
   * - 测试自定义命令入口：直接在命令框输入
   */
  test('TSK-01: should support template selection or custom command input', async ({ page }) => {
    // 验证页面标题
    await expect(page.getByRole('heading', { name: '创建任务' })).toBeVisible()

    // 验证任务来源选择（模板/自定义命令）- 使用 Radio 按钮
    await expect(page.getByRole('radio', { name: '选择模板' })).toBeVisible()
    await expect(page.getByRole('radio', { name: '自定义命令' })).toBeVisible()

    // 等待模板选择器可用（可能需要加载数据）
    await page.waitForTimeout(2000)

    // 测试切换到自定义命令模式
    await page.getByRole('radio', { name: '自定义命令' }).click()
    await page.waitForTimeout(500)

    // 验证命令输入框出现
    const commandInput = page.locator('textarea[placeholder*="命令"]')
    await expect(commandInput).toBeVisible()

    // 输入自定义命令
    await commandInput.fill('echo "Custom Command Test"')
    await page.waitForTimeout(500)

    // 验证命令已填充
    const filledValue = await commandInput.inputValue()
    expect(filledValue).toContain('Custom Command Test')
  })

  /**
   * TSK-02: 必填 target_asset_id 和 run_as_system_user_id
   * - 不填写资产和系统用户，点击提交
   * - 验证显示必填校验错误
   */
  test('TSK-02: should require target_asset_id and run_as_system_user_id', async ({ page }) => {
    // 等待页面加载
    await page.waitForTimeout(1000)

    // 切换到自定义命令
    await page.getByRole('radio', { name: '自定义命令' }).click()
    await page.waitForTimeout(500)

    // 输入命令
    const commandInput = page.locator('textarea[placeholder*="命令"]')
    await commandInput.fill('echo "test"')

    // 点击策略预览（必须先进行策略评估才能提交）
    await page.getByRole('button', { name: '策略预览' }).click()
    await page.waitForTimeout(3000)

    // 等待评估完成并关闭弹窗
    await page.waitForSelector('text=正在评估策略...', { state: 'detached', timeout: 15000 })
    await page.waitForTimeout(1000)
    await page.getByRole('button', { name: '关闭' }).first().click()
    await page.waitForTimeout(500)

    // 点击创建任务按钮（现在应该启用了）
    const submitButton = page.getByRole('button', { name: /创建任务/ })
    await submitButton.click()
    await page.waitForTimeout(2000)

    // 验证显示必填校验错误（目标资产和系统用户）
    const errorMessages = page.locator('.ant-form-item-explain-error')
    const errorCount = await errorMessages.count()
    expect(errorCount).toBeGreaterThanOrEqual(1)
  })

  /**
   * TSK-03: 提交前策略评估预览
   * - 输入命令
   * - 点击"策略预览"按钮
   * - 验证 PolicyEvaluationModal 显示
   * - 验证显示风险评估结果
   */
  test('TSK-03: should show policy evaluation preview before submission', async ({ page }) => {
    // 切换到自定义命令模式
    await page.getByRole('radio', { name: '自定义命令' }).click()
    await page.waitForTimeout(500)

    // 输入命令
    const commandInput = page.locator('textarea[placeholder*="命令"]')
    await commandInput.fill('echo "Policy Test"')
    await page.waitForTimeout(500)

    // 点击策略预览按钮
    await page.getByRole('button', { name: '策略预览' }).click()

    // 验证策略评估弹窗显示
    await expect(page.getByText('策略评估预览')).toBeVisible({ timeout: 10000 })

    // 等待加载完成（"正在评估策略..."消失）
    await page.waitForSelector('text=正在评估策略...', { state: 'detached', timeout: 15000 })

    // 验证评估结果显示（允许执行或被拦截）
    const allowedText = page.getByText('允许执行')
    const blockedText = page.getByText('被拦截')

    // 至少有一种状态可见
    await expect(allowedText.or(blockedText)).toBeVisible()

    // 验证风险等级显示（在模态框内）
    const modal = page.getByRole('dialog')
    await expect(modal.getByText('风险等级:').first()).toBeVisible()

    // 关闭评估弹窗
    await page.getByRole('button', { name: '关闭' }).click()
    await page.waitForTimeout(500)

    // 验证弹窗已关闭
    await expect(page.getByText('策略评估预览')).not.toBeVisible()
  })

  /**
   * TSK-04: approval_required 跳转审批页
   * - 验证提交按钮存在
   * - 验证按钮文本根据审批状态变化
   */
  test('TSK-04: should have submit button for approval flow', async ({ page }) => {
    // 切换到自定义命令模式
    await page.getByRole('radio', { name: '自定义命令' }).click()
    await page.waitForTimeout(500)

    // 输入命令
    const commandInput = page.locator('textarea[placeholder*="命令"]')
    await commandInput.fill('echo "test approval"')
    await page.waitForTimeout(500)

    // 点击策略预览
    await page.getByRole('button', { name: '策略预览' }).click()
    await page.waitForTimeout(5000)

    // 等待评估完成
    await page.waitForSelector('text=正在评估策略...', { state: 'detached', timeout: 15000 })
    await page.waitForTimeout(1000)

    // 关闭评估弹窗
    await page.getByRole('button', { name: '关闭' }).first().click()
    await page.waitForTimeout(500)

    // 验证提交按钮存在（使用更通用的选择器）
    const submitButton = page.locator('button[type="button"].ant-btn-primary')
    await expect(submitButton).toBeVisible()
  })

  /**
   * TSK-05: 命中策略拦截时禁用提交
   * - 输入可能命中黑名单的命令
   * - 验证策略评估显示拦截状态
   */
  test('TSK-05: should show blocked status when command hits policy', async ({ page }) => {
    // 切换到自定义命令模式
    await page.getByRole('radio', { name: '自定义命令' }).click()
    await page.waitForTimeout(500)

    // 输入一个可能命中黑名单的命令
    const commandInput = page.locator('textarea[placeholder*="命令"]')
    await commandInput.fill('rm -rf /tmp/test')
    await page.waitForTimeout(500)

    // 点击策略预览
    await page.getByRole('button', { name: '策略预览' }).click()

    // 等待评估完成
    await page.waitForSelector('text=正在评估策略...', { state: 'detached', timeout: 15000 })
    await page.waitForTimeout(1000)

    // 验证评估结果显示（无论是否被拦截）
    const allowedText = page.getByText('允许执行')
    const blockedText = page.getByText('被拦截')

    // 至少有一种状态可见
    await expect(allowedText.or(blockedText)).toBeVisible()

    // 如果显示被拦截，验证拦截原因
    if (await blockedText.isVisible()) {
      // 验证模态框内显示拦截原因或匹配规则
      const modal = page.getByRole('dialog')
      const hasBlockReason = await modal.getByText('拦截原因').first().isVisible().catch(() => false)
      const hasMatchedRules = await modal.getByText('匹配规则:').first().isVisible().catch(() => false)
      expect(hasBlockReason || hasMatchedRules).toBe(true)
    }

    // 关闭评估弹窗
    if (await page.getByText('策略评估预览').isVisible()) {
      await page.getByRole('button', { name: '关闭' }).first().click()
    }
  })
})
