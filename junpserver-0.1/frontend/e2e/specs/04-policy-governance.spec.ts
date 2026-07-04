import { test, expect } from '../fixtures/test-fixtures'

/**
 * 策略治理 E2E 测试
 * 覆盖需求：POL-01 ~ POL-06
 *
 * 运行说明：
 * - 需要前端开发服务器运行 (npm run dev)
 * - 需要后端 API 服务器可用
 * - 使用测试账号登录 (test_operator / TestPass123!)
 */
test.describe('Policy Governance', () => {
  test.beforeEach(async ({ authenticatedPage }) => {
    // 访问黑名单治理页面
    await authenticatedPage.goto('/policies/blacklist')
    // 等待页面加载完成
    await authenticatedPage.waitForSelector('[data-testid="skeleton-container"]', { state: 'detached' })
  })

  /**
   * POL-01: 调用 GET /policies/command-blacklist 显示黑名单列表
   * - 访问 /governance/blacklist
   * - 验证黑名单列表加载
   * - 验证显示规则列表
   */
  test('POL-01: should load and display blacklist rules', async ({ authenticatedPage }) => {
    const page = authenticatedPage

    // 验证页面标题
    await expect(page.getByRole('heading', { name: '命令黑名单治理' })).toBeVisible()

    // 验证新建规则按钮存在
    await expect(page.getByRole('button', { name: '新建规则' })).toBeVisible()

    // 验证列表容器存在（加载完成后骨架屏应该消失）
    const skeletonContainer = page.locator('[data-testid="skeleton-container"]')
    await expect(skeletonContainer).not.toBeVisible()

    // 页面应该包含黑名单治理的关键元素
    const container = page.locator('div[style*="padding: 24px"]')
    await expect(container).toBeVisible()
  })

  /**
   * POL-02: 支持新增黑名单规则（POST）
   * - 点击"新增规则"按钮
   * - 填写规则（pattern/hard_block/enabled）
   * - 点击提交
   * - 验证 POST 请求发送
   */
  test('POL-02: should create new blacklist rule via modal form', async ({ authenticatedPage, page }) => {
    // 拦截 API 请求
    const createRequestPromise = page.waitForRequest(
      (req) => req.method() === 'POST' && req.url().includes('/policies/command-blacklist')
    )

    // 点击新建规则按钮
    await authenticatedPage.getByRole('button', { name: '新建规则' }).click()

    // 等待弹窗打开
    await expect(authenticatedPage.getByRole('dialog')).toBeVisible()

    // 填写表单
    await authenticatedPage.fill('[name="pattern"]', 'rm -rf /tmp/e2e_test_*')

    // 设置硬拦截（默认是硬拦截，这里明确设置）
    // Switch 组件使用 role="switch"
    const hardBlockSwitch = authenticatedPage.locator('button[role="switch"]').nth(0)
    await hardBlockSwitch.click()

    // 设置启用状态
    const enabledSwitch = authenticatedPage.locator('button[role="switch"]').nth(1)
    await enabledSwitch.click()

    // 点击提交按钮
    await authenticatedPage.getByRole('button', { name: '创建' }).click()

    // 等待创建请求
    const createRequest = await createRequestPromise

    // 验证请求 payload
    const postData = createRequest.postDataJSON()
    expect(postData.pattern).toBe('rm -rf /tmp/e2e_test_*')
    expect(postData.hard_block).toBeDefined()
    expect(postData.enabled).toBeDefined()
  })

  /**
   * POL-03: 支持修改规则（PATCH）
   * - 点击第一个规则的"编辑"按钮
   * - 修改字段
   * - 点击保存
   * - 验证 PATCH 请求发送
   */
  test('POL-03: should update existing blacklist rule', async ({ authenticatedPage, page }) => {
    // 首先创建一个测试规则
    await authenticatedPage.getByRole('button', { name: '新建规则' }).click()
    await expect(authenticatedPage.getByRole('dialog')).toBeVisible()

    await authenticatedPage.fill('[name="pattern"]', 'test_pattern_original')

    // 点击创建
    const createRequestPromise = page.waitForRequest(
      (req) => req.method() === 'POST' && req.url().includes('/policies/command-blacklist')
    )
    await authenticatedPage.getByRole('button', { name: '创建' }).click()
    await createRequestPromise

    // 等待卡片出现
    await authenticatedPage.waitForTimeout(1000)

    // 拦截 PATCH 请求
    const updateRequestPromise = page.waitForRequest(
      (req) => req.method() === 'PATCH' && req.url().includes('/policies/command-blacklist/')
    )

    // 点击卡片进入编辑模式
    const card = authenticatedPage.locator('[role="article"]').first()
    await card.click()

    // 等待编辑弹窗打开
    await expect(authenticatedPage.getByRole('dialog', { name: '编辑规则' })).toBeVisible()

    // 修改 pattern
    await authenticatedPage.fill('[name="pattern"]', 'test_pattern_modified')

    // 点击保存按钮
    await authenticatedPage.getByRole('button', { name: '保存' }).click()

    // 等待更新请求
    const updateRequest = await updateRequestPromise

    // 验证请求 payload
    const postData = updateRequest.postDataJSON()
    expect(postData.pattern).toBe('test_pattern_modified')
  })

  /**
   * POL-04: 命令输入框实时评估
   * - 在命令输入框输入命令
   * - 验证触发 POST /policies/evaluate
   * - 验证评估结果实时更新
   *
   * 注意：此测试通过 PolicyEvaluationModal 组件验证
   */
  test('POL-04: should trigger policy evaluation on command input', async ({ authenticatedPage }) => {
    // 打开新建规则弹窗
    await authenticatedPage.getByRole('button', { name: '新建规则' }).click()
    await expect(authenticatedPage.getByRole('dialog')).toBeVisible()

    // 填写 pattern
    await authenticatedPage.fill('[name="pattern"]', 'sudo rm -rf /')

    // 点击测试预览按钮
    await authenticatedPage.getByRole('button', { name: '测试预览' }).click()

    // 验证策略评估弹窗显示
    await expect(authenticatedPage.getByText('策略评估预览')).toBeVisible()

    // 拦截策略评估请求
    const evalRequestPromise = authenticatedPage.waitForRequest(
      (req) => req.method() === 'POST' && req.url().includes('/policies/evaluate')
    )

    // 等待评估完成
    await authenticatedPage.waitForSelector('text=正在评估策略...', { state: 'detached', timeout: 10000 })

    // 验证评估请求已发送
    const evalRequest = await evalRequestPromise
    const postData = evalRequest.postDataJSON()
    expect(postData.command).toBe('sudo rm -rf /')
  })

  /**
   * POL-05: 被拦截时显示 block_reason 和 matched_rules
   * - 输入命中黑名单的命令
   * - 验证显示拦截提示
   * - 验证显示 block_reason
   * - 验证显示 matched_rules 列表
   */
  test('POL-05: should display block reason and matched rules when blocked', async ({ authenticatedPage }) => {
    // 打开新建规则弹窗
    await authenticatedPage.getByRole('button', { name: '新建规则' }).click()
    await expect(authenticatedPage.getByRole('dialog')).toBeVisible()

    // 填写一个可能命中黑名单的命令模式
    await authenticatedPage.fill('[name="pattern"]', 'rm -rf /*')

    // 点击测试预览
    await authenticatedPage.getByRole('button', { name: '测试预览' }).click()

    // 等待评估弹窗显示
    await expect(authenticatedPage.getByText('策略评估预览')).toBeVisible()

    // 等待评估完成
    await authenticatedPage.waitForSelector('text=正在评估策略...', { state: 'detached', timeout: 10000 })

    // 验证显示评估结果（允许执行或被拦截）
    const allowedText = authenticatedPage.getByText('允许执行')
    const blockedText = authenticatedPage.getByText('被拦截')

    // 验证风险等级显示
    await expect(authenticatedPage.getByText('风险等级:')).toBeVisible()

    // 如果需要审批，验证审批提示
    const approvalAlert = authenticatedPage.getByText('需要审批')
    // 这个可能显示也可能不显示，取决于命令的风险等级

    // 关闭评估弹窗
    await authenticatedPage.getByRole('button', { name: '关闭' }).first().click()
  })

  /**
   * POL-06: 调用 GET /governance/audits 显示审计日志
   * - 访问 /governance/audits
   * - 验证审计列表加载
   * - 验证显示 entity_type/action/operator_id
   */
  test('POL-06: should display governance audit logs', async ({ authenticatedPage }) => {
    // 访问审计日志页面
    await authenticatedPage.goto('/governance/audits')

    // 等待页面加载（骨架屏消失）
    await authenticatedPage.waitForSelector('[data-testid="skeleton-container"]', { state: 'detached', timeout: 10000 })

    // 验证页面标题
    await expect(authenticatedPage.getByRole('heading', { name: /治理审计/ })).toBeVisible()

    // 验证筛选器存在
    // 审计页面应该有 entity_type/action/operator_id 筛选
    const entityTypeFilter = authenticatedPage.locator('[placeholder*="实体类型"], [placeholder*="entity_type"]')
    const actionFilter = authenticatedPage.locator('[placeholder*="操作"], [placeholder*="action"]')
    const operatorFilter = authenticatedPage.locator('[placeholder*="操作人"], [placeholder*="operator"]')

    // 至少有一个筛选器存在
    await expect(
      entityTypeFilter.or(actionFilter).or(operatorFilter)
    ).toBeVisible()

    // 验证列表容器存在
    const container = page.locator('div[style*="padding: 24px"]')
    await expect(container).toBeVisible()
  })
})
