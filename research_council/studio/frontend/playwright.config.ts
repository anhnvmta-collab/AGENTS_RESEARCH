import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 120000,
  expect: { timeout: 15000 },
  reporter: [
    ["list"],
    ["json", { outputFile: "../../docs/audits/studio-playwright.json" }],
  ],
  use: {
    baseURL: "http://127.0.0.1:8765",
    viewport: { width: 1600, height: 1100 },
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  webServer: {
    command:
      "..\\..\\.venv\\Scripts\\python.exe ..\\..\\scripts\\studio_e2e_server.py",
    url: "http://127.0.0.1:8765/api/health",
    reuseExistingServer: false,
    timeout: 30000,
  },
});
