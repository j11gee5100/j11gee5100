import { defineConfig, devices } from '@playwright/test'

/**
 * Playwright E2E 测试配置
 *
 * 配置要点：
 * - 测试文件位于 e2e/specs/目录
 * - 并行执行测试
 * - 支持 Chromium 和 WebKit 浏览器
 * - 自动启动 Vite dev server
 */
export default defineConfig({
  testDir: './e2e/specs',

  // 并行执行
  fullyParallel: true,

  // 每个测试文件超时
  timeout: 30 * 1000,

  // 重试配置（CI环境重试 2 次）
  retries: process.env.CI ? 2 : 0,

  // 每个 worker 最大并发数
  workers: process.env.CI ? 1 : undefined,

  // 报表配置
  reporter: 'html',

  // 共享配置
  use: {
    // 基础 URL
    baseURL: process.env.BASE_URL || 'http://localhost:3000',

    // 浏览器选项
    headless: process.env.HEADLESS === 'false' ? false : true,

    // 截图（仅失败时）
    screenshot: 'only-on-failure',

    // 视频（仅失败时）
    video: 'retain-on-failure',

    // 追踪（保留成功测试的追踪）
    trace: 'retain-on-failure',
  },

  // 浏览器配置
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    // WebKit 测试暂时禁用（需要安装浏览器）
    // {
    //   name: 'webkit',
    //   use: { ...devices['Desktop Safari'] },
    // },
  ],

  // Web 服务器配置（自动启动 Vite dev server）
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:3000',
    reuseExistingServer: !process.env.CI,
    timeout: 120 * 1000,
  },
})
