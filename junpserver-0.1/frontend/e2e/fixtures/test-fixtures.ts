import { test as base, expect } from '@playwright/test'

/**
 * E2E 测试共享 fixtures
 *
 * 提供：
 * - authenticatedPage: 已认证访问的 Page 实例
 * - testUserData: 测试数据工厂
 *
 * 注意：当前应用未实现登录页面，直接使用 authenticatedPage 访问页面即可
 */

// 测试用户数据（保留供未来使用）
export const testUserData = {
  operator: {
    username: 'test_operator',
    password: 'test_password',
  },
  approverL1: {
    username: 'test_approver_l1',
    password: 'test_password',
  },
  approverL2: {
    username: 'test_approver_l2',
    password: 'test_password',
  },
}

// 登录处理函数（保留供未来使用）
export async function loginAsOperator(page: any) {
  // 检查登录页面是否存在
  await page.goto('/login')
  const loginPageExists = await page.isVisible('input[type="text"]').catch(() => false)
  if (loginPageExists) {
    await page.fill('input[type="text"]', testUserData.operator.username)
    await page.fill('input[type="password"]', testUserData.operator.password)
    await page.click('button:has-text("登录")')
    await page.waitForURL(/\/(dashboard|approvals|templates|policies|tasks)/)
  }
  // 如果登录页面不存在，直接继续（应用无认证）
}

export async function loginAsApprover(page: any, level: number = 1) {
  const user = level === 1 ? testUserData.approverL1 : testUserData.approverL2
  await page.goto('/login')
  const loginPageExists = await page.isVisible('input[type="text"]').catch(() => false)
  if (loginPageExists) {
    await page.fill('input[type="text"]', user.username)
    await page.fill('input[type="password"]', user.password)
    await page.click('button:has-text("登录")')
    await page.waitForURL(/\/(dashboard|approvals|templates|policies|tasks)/)
  }
}

export async function logout(page: any) {
  try {
    await page.click('button:has-text("退出")')
    await page.waitForURL(/\/login/)
  } catch {
    // 无认证系统，忽略登出
  }
}

// 扩展 Playwright test
export const test = base.extend<{
  authenticatedPage: any
  testUserData: typeof testUserData
}>({
  authenticatedPage: async ({ page }, use) => {
    // 尝试登录（如果登录页面存在）
    await loginAsOperator(page)
    await use(page)
    // 清理（可选）
  },
  testUserData: async ({}, use) => {
    await use(testUserData)
  },
})

export { expect }
