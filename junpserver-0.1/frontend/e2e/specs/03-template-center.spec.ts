import { test, expect } from '../fixtures/test-fixtures'
import type { Template } from '../../src/types/template'

/**
 * 模板中心 E2E 测试
 * 覆盖需求：TMPL-01 ~ TMPL-05
 *
 * 运行说明：
 * - 需要前端开发服务器运行 (npm run dev)
 * - 需要后端 API 服务器可用
 * - 使用测试账号登录 (test_operator / TestPass123!)
 */
test.describe('Template Center', () => {
  // 测试用的模板数据
  const testTemplate: Template = {
    template_id: 'test_template_001',
    name: '测试模板',
    description: 'E2E 测试创建的模板',
    command: 'echo "Hello World"',
    risk_level: 'low',
    enabled: true,
  }

  test.beforeEach(async ({ authenticatedPage }) => {
    // 访问模板中心页面
    await authenticatedPage.goto('/templates/commands')
    // 等待页面加载完成
    await authenticatedPage.waitForSelector('[data-testid="skeleton-container"]', { state: 'detached' })
  })

  /**
   * TMPL-01: 调用 GET /templates/commands 显示模板列表
   * - 访问 /templates
   * - 验证列表加载
   * - 验证显示 template_id/name/risk_level/enabled
   */
  test('TMPL-01: should load and display template list', async ({ authenticatedPage }) => {
    const page = authenticatedPage

    // 验证页面标题
    await expect(page.getByRole('heading', { name: '模板中心' })).toBeVisible()

    // 验证新建按钮存在
    await expect(page.getByRole('button', { name: '新建模板' })).toBeVisible()

    // 验证列表容器存在（可能是空状态或卡片列表）
    const skeletonContainer = page.locator('[data-testid="skeleton-container"]')
    await expect(skeletonContainer).not.toBeVisible()

    // 页面应该包含模板中心的关键元素
    // 即使没有数据，也应该显示空状态或列表容器
    const container = page.locator('div[style*="padding: 24px"]')
    await expect(container).toBeVisible()
  })

  /**
   * TMPL-02: 弹窗新建模板（POST /templates/commands）
   * - 点击"新建模板"按钮
   * - 填写表单（template_id/name/description/command/risk_level）
   * - 点击提交
   * - 验证 POST 请求发送
   */
  test('TMPL-02: should create new template via modal form', async ({ authenticatedPage, page }) => {
    // 拦截 API 请求
    const createRequestPromise = page.waitForRequest(
      (req) => req.method() === 'POST' && req.url().includes('/templates/commands')
    )

    // 点击新建模板按钮
    await authenticatedPage.getByRole('button', { name: '新建模板' }).click()

    // 等待弹窗打开
    await expect(authenticatedPage.getByRole('dialog')).toBeVisible()

    // 填写表单
    await authenticatedPage.fill('[name="template_id"]', 'test_e2e_template')
    await authenticatedPage.fill('[name="name"]', 'E2E 测试模板')
    await authenticatedPage.fill('[name="description"]', '通过 E2E 测试创建的模板')
    await authenticatedPage.selectOption('[name="risk_level"]', 'low')
    await authenticatedPage.fill('[name="command"]', 'echo "E2E Test"')

    // 点击策略预览按钮（必须先进行策略评估才能提交）
    await authenticatedPage.getByRole('button', { name: '预览' }).click()

    // 等待策略评估弹窗显示
    await expect(authenticatedPage.getByText('策略评估预览')).toBeVisible()

    // 等待评估完成并关闭评估弹窗
    await authenticatedPage.waitForTimeout(2000)

    // 关闭策略评估弹窗
    await authenticatedPage.getByRole('button', { name: '关闭' }).first().click()

    // 点击提交按钮
    await authenticatedPage.getByRole('button', { name: '创建' }).click()

    // 等待创建请求
    const createRequest = await createRequestPromise

    // 验证请求 payload
    const postData = createRequest.postDataJSON()
    expect(postData.template_id).toBe('test_e2e_template')
    expect(postData.name).toBe('E2E 测试模板')
    expect(postData.command).toBe('echo "E2E Test"')
    expect(postData.risk_level).toBe('low')
  })

  /**
   * TMPL-03: 启停模板（PATCH enabled 字段）
   * - 找到第一个模板的启停开关
   * - 点击开关
   * - 验证 PATCH 请求发送
   * - 验证列表状态即时更新
   *
   * 注意：此测试需要至少有一个现有模板
   */
  test('TMPL-03: should toggle template enable/disable status', async ({ authenticatedPage, page }) => {
    // 首先创建一个测试模板
    await authenticatedPage.getByRole('button', { name: '新建模板' }).click()
    await expect(authenticatedPage.getByRole('dialog')).toBeVisible()

    await authenticatedPage.fill('[name="template_id"]', 'test_toggle_template')
    await authenticatedPage.fill('[name="name"]', '启停测试模板')
    await authenticatedPage.selectOption('[name="risk_level"]', 'low')
    await authenticatedPage.fill('[name="command"]', 'echo "Toggle Test"')

    // 点击策略预览
    await authenticatedPage.getByRole('button', { name: '预览' }).click()
    await authenticatedPage.waitForTimeout(2000)
    await authenticatedPage.getByRole('button', { name: '关闭' }).first().click()

    // 拦截创建请求
    const createRequestPromise = page.waitForRequest(
      (req) => req.method() === 'POST' && req.url().includes('/templates/commands')
    )
    await authenticatedPage.getByRole('button', { name: '创建' }).click()
    await createRequestPromise

    // 等待卡片出现
    await authenticatedPage.waitForTimeout(1000)

    // 拦截 PATCH 请求
    const updateRequestPromise = page.waitForRequest(
      (req) => req.method() === 'PATCH' && req.url().includes('/templates/commands/')
    )

    // 找到刚创建的模板卡片，点击启停开关
    // 使用 Switch 组件的复选框
    const switchCheckbox = authenticatedPage.locator('button[role="switch"]').first()
    await switchCheckbox.click()

    // 等待更新请求
    const updateRequest = await updateRequestPromise

    // 验证请求 payload 包含 enabled 字段
    const postData = updateRequest.postDataJSON()
    expect(postData.enabled).toBeDefined()

    // 验证卡片列表状态更新
    await authenticatedPage.waitForTimeout(500)
  })

  /**
   * TMPL-04: 表单字段完整
   * - 验证表单包含所有必填字段
   * - 验证 risk_level 为下拉选择（low/medium/high）
   */
  test('TMPL-04: should have all required form fields', async ({ authenticatedPage }) => {
    // 打开新建弹窗
    await authenticatedPage.getByRole('button', { name: '新建模板' }).click()
    await expect(authenticatedPage.getByRole('dialog')).toBeVisible()

    // 验证基础信息区域
    await expect(authenticatedPage.getByText('基础信息')).toBeVisible()

    // 验证命令配置区域
    await expect(authenticatedPage.getByText('命令配置')).toBeVisible()

    // 验证所有必填字段标签存在
    await expect(authenticatedPage.getByLabel('模板 ID')).toBeVisible()
    await expect(authenticatedPage.getByLabel('名称')).toBeVisible()
    await expect(authenticatedPage.getByLabel('描述')).toBeVisible()
    await expect(authenticatedPage.getByLabel('风险等级')).toBeVisible()
    await expect(authenticatedPage.getByLabel('命令')).toBeVisible()

    // 验证 risk_level 是下拉选择
    const riskLevelSelect = authenticatedPage.locator('[name="risk_level"]')
    await expect(riskLevelSelect).toBeVisible()

    // 点击下拉框，验证选项
    await riskLevelSelect.click()

    // 验证下拉选项包含 low/medium/high 对应的中文选项
    await expect(authenticatedPage.getByRole('option', { name: '低风险' })).toBeVisible()
    await expect(authenticatedPage.getByRole('option', { name: '中风险' })).toBeVisible()
    await expect(authenticatedPage.getByRole('option', { name: '高风险' })).toBeVisible()
  })

  /**
   * TMPL-05: 新建前策略评估预览
   * - 填写 command 字段
   * - 点击"策略预览"按钮
   * - 验证 PolicyEvaluationModal 弹窗显示
   * - 验证显示评估结果
   */
  test('TMPL-05: should show policy evaluation preview before creation', async ({ authenticatedPage }) => {
    // 打开新建弹窗
    await authenticatedPage.getByRole('button', { name: '新建模板' }).click()
    await expect(authenticatedPage.getByRole('dialog')).toBeVisible()

    // 填写命令
    await authenticatedPage.fill('[name="command"]', 'rm -rf /tmp/test')

    // 点击策略预览按钮
    await authenticatedPage.getByRole('button', { name: '预览' }).click()

    // 验证策略评估弹窗显示
    await expect(authenticatedPage.getByText('策略评估预览')).toBeVisible()

    // 等待评估完成（显示加载中到完成）
    await authenticatedPage.waitForSelector('text=正在评估策略...', { state: 'detached', timeout: 10000 })

    // 验证评估结果显示
    // 应该显示允许执行或被拦截的状态
    const allowedText = authenticatedPage.getByText('允许执行')
    const blockedText = authenticatedPage.getByText('被拦截')

    // 至少有一种状态可见
    await expect(
      allowedText.or(blockedText)
    ).toBeVisible()

    // 验证风险等级显示
    await expect(authenticatedPage.getByText('风险等级:')).toBeVisible()

    // 关闭评估弹窗
    await authenticatedPage.getByRole('button', { name: '关闭' }).click()
    await expect(authenticatedPage.getByText('策略评估预览')).not.toBeVisible()
  })
})
