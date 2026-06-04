const fs = require('fs');
const path = require('path');
const { defineConfig } = require('@playwright/test');

const repoRoot = path.resolve(__dirname, '..');
const pythonCandidates =
  process.env.PLAYWRIGHT_PYTHON
    ? [process.env.PLAYWRIGHT_PYTHON]
    : process.platform === 'win32'
    ? [
        path.resolve(repoRoot, '.venv', 'Scripts', 'python.exe'),
        path.resolve(repoRoot, 'venv', 'Scripts', 'python.exe'),
        'python',
      ]
    : [
        path.resolve(repoRoot, '.venv', 'bin', 'python'),
        path.resolve(repoRoot, 'venv', 'bin', 'python'),
        'python3',
        'python',
      ];
const pythonExe =
  pythonCandidates.find((candidate) => candidate.includes(path.sep) && fs.existsSync(candidate)) ||
  pythonCandidates[pythonCandidates.length - 1];
const backendScript = path.resolve(repoRoot, 'backend', 'scripts', 'run_e2e_server.py');
const backendDb = path.resolve(repoRoot, 'backend', 'e2e.db').replace(/\\/g, '/');
const useSystemChrome =
  process.env.PLAYWRIGHT_USE_SYSTEM_CHROME !== 'false' && !process.env.CI;
const browserChannel = process.env.PLAYWRIGHT_BROWSER_CHANNEL || 'chrome';

module.exports = defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  workers: process.env.CI ? 1 : undefined,
  expect: {
    timeout: 10_000,
  },
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  use: {
    baseURL: 'http://127.0.0.1:4173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  webServer: [
    {
      command: `"${pythonExe}" "${backendScript}"`,
      cwd: repoRoot,
      url: 'http://127.0.0.1:5100/api/health',
      reuseExistingServer: false,
      timeout: 120_000,
      env: {
        ...process.env,
        DATABASE_URL: `sqlite:///${backendDb}`,
        PORT: '5100',
      },
    },
    {
      command: 'npm run dev -- --host 127.0.0.1 --port 4173',
      cwd: __dirname,
      url: 'http://127.0.0.1:4173',
      reuseExistingServer: false,
      timeout: 120_000,
      env: {
        ...process.env,
        VITE_API_PROXY_TARGET: 'http://127.0.0.1:5100',
        VITE_AMAP_JS_KEY: 'playwright-amap-key',
        VITE_PORT: '4173',
        VITE_CJS_IGNORE_WARNING: '1',
      },
    },
  ],
  projects: [
    {
      name: 'chromium',
      use: {
        browserName: 'chromium',
        ...(useSystemChrome ? { channel: browserChannel } : {}),
      },
    },
  ],
});
