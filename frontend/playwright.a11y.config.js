const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests',
  timeout: 45_000,
  retries: 0,
  use: {
    baseURL: 'http://127.0.0.1:4173',
    headless: true,
  },
  webServer: {
    command: 'PORT=4173 npm start',
    url: 'http://127.0.0.1:4173',
    timeout: 120_000,
    reuseExistingServer: false,
  },
  reporter: [['list']],
});
