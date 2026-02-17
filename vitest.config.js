import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    // テスト環境
    environment: 'jsdom',

    // テストファイルパターン
    include: ['**/tests/**/*.test.js'],

    // Playwrightテストを除外
    exclude: ['**/node_modules/**', '**/*.spec.js', '**/e2e/**'],

    // セットアップファイル
    setupFiles: ['./tests/vitest-canvas-setup.js', './tests/vitest-setup.js'],

    // グローバル設定（describe, it, expect等をインポート不要にする）
    globals: true,

    // カバレッジ設定
    coverage: {
      provider: 'v8',
      reporter: ['text', 'lcov', 'html'],
      include: ['src/aspara/dashboard/static/js/**/*.js'],
      exclude: ['src/aspara/dashboard/static/js/**/*.test.js', 'src/aspara/dashboard/static/js/**/*.spec.js'],
      thresholds: {
        branches: 50,
        functions: 50,
        lines: 50,
        statements: 50,
      },
    },

    // テストタイムアウト
    testTimeout: 10000,

    // DOM環境設定
    environmentOptions: {
      jsdom: {
        url: 'http://localhost',
      },
    },
  },
});
