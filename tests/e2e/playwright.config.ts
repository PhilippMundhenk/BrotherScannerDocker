import { defineConfig } from '@playwright/test';
import { HOST_PORT } from './helpers';

export default defineConfig({
  testDir: './tests',
  globalSetup: require.resolve('./global-setup'),
  // One container, one worker: the scanner pipeline is stateful (a rear scan
  // attaches to the latest front scan), so tests must not interleave.
  workers: 1,
  fullyParallel: false,
  retries: 0,
  timeout: 120_000,
  expect: { timeout: 15_000 },
  reporter: [['list'], ['html', { outputFolder: 'output/report', open: 'never' }]],
  outputDir: 'output/test-results',
  use: {
    baseURL: `http://localhost:${HOST_PORT}`,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chromium', use: { browserName: 'chromium' } }],
});
