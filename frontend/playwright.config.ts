import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  fullyParallel: true,
  retries: 0,
  reporter: "line",
  use: {
    baseURL: "http://127.0.0.1:4173",
    trace: "retain-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile-chromium", use: { ...devices["Pixel 7"] } },
  ],
  webServer: [
    {
      command: "PYTHONPATH=src ALLOWED_ORIGINS=http://127.0.0.1:4173 uv run uvicorn app.main:app --host 127.0.0.1 --port 18100",
      cwd: "../backend",
      url: "http://127.0.0.1:18100/api/health",
      reuseExistingServer: true,
      timeout: 60_000,
    },
    {
      command: "VITE_DEV_API_PROXY=http://127.0.0.1:18100 npm run dev -- --port 4173",
      url: "http://127.0.0.1:4173",
      reuseExistingServer: true,
      timeout: 60_000,
    },
  ],
});
