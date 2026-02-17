// @ts-check
import { defineConfig, devices } from '@playwright/test';

const BASE_PORT = 6113;

/**
 * @see https://playwright.dev/docs/test-configuration
 */
export default defineConfig({
  // E2Eテストのみを対象にする（Vitestとの競合を避ける）
  testDir: './tests/e2e',

  // 並列実行の worker 数
  // CI では 2 workers、ローカルでは制限なし
  workers: process.env.CI ? 2 : undefined,

  // テストの実行タイムアウト
  timeout: 30 * 1000,

  // テスト実行の期待値
  expect: {
    // 要素が表示されるまでの最大待機時間
    timeout: 5000,
  },

  // 失敗したテストのスクリーンショットを撮る
  use: {
    // ベースURL
    baseURL: `http://localhost:${BASE_PORT}`,

    // スクリーンショットを撮る
    screenshot: 'only-on-failure',

    // トレースを記録する
    trace: 'on-first-retry',

    // ダウンロードを許可
    acceptDownloads: true,
  },

  // テスト実行のレポート形式
  // 'list' はコンソール出力のみ、HTMLレポートは生成しない
  reporter: process.env.CI ? 'github' : 'list',

  // テスト前にサーバーを自動起動
  webServer: {
    command: `uv run aspara dashboard --port ${BASE_PORT}`,
    port: BASE_PORT,
    reuseExistingServer: !process.env.CI,
    timeout: 60 * 1000,
  },

  // プロジェクト設定
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
    },
    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
    },
  ],
});
