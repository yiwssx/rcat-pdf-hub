import { expect, Page, Route, test } from "@playwright/test";

const pngPixel = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
  "base64",
);

const initialFile = {
  id: "file-pdf-1",
  original_name: "example.pdf",
  content_type: "application/pdf",
  size: 4096,
  sha256: "a".repeat(64),
  source_system: "smoke-test",
  created_at: "2026-08-31T08:00:00Z",
  expires_at: null,
};

async function installApiMocks(page: Page) {
  let sessionReady = false;

  async function requireSession(route: Route) {
    if (sessionReady && !route.request().headers()["x-api-key"]) return true;
    await route.fulfill({ status: 401, contentType: "application/json", body: JSON.stringify({ detail: "Authentication required" }) });
    return false;
  }

  await page.route("**/api/v1/auth/config", async (route) => {
    await route.fulfill({
      json: {
        session_cookie: "pdfhub_session",
        oidc: { enabled: false, issuer: null, login_url: null },
        ldap: { enabled: false },
        web_console: { auto_login: true },
      },
    });
  });

  await page.route("**/web-auth/session", async (route) => {
    sessionReady = true;
    await route.fulfill({ status: 204 });
  });

  await page.route("**/api/v1/auth/me", async (route) => {
    if (!(await requireSession(route))) return;
    await route.fulfill({
      json: {
        name: "web-console:smoke-test",
        display_name: "Web Console",
        subject: "smoke-test",
        scopes: ["files:read", "files:write", "jobs:read", "pdf:compress"],
        groups: [],
        auth_source: "web-console",
        is_admin: false,
      },
    });
  });

  await page.route("**/api/v1/integrations/status", async (route) => {
    if (!(await requireSession(route))) return;
    await route.fulfill({
      json: {
        storage_backend: "local",
        clamav_enabled: true,
        paperless_enabled: false,
        oidc_enabled: false,
        ldap_enabled: false,
        otel_enabled: false,
        prometheus_enabled: true,
      },
    });
  });

  await page.route("**/api/v1/files?limit=100", async (route) => {
    if (!(await requireSession(route))) return;
    await route.fulfill({ json: [initialFile] });
  });

  await page.route("**/api/v1/jobs?limit=50", async (route) => {
    if (!(await requireSession(route))) return;
    await route.fulfill({ json: [] });
  });

  await page.route("**/api/v1/files/file-pdf-1/preview**", async (route) => {
    if (!(await requireSession(route))) return;
    await route.fulfill({ status: 200, contentType: "image/png", body: pngPixel });
  });

  await page.route("**/api/v1/pdf/compress", async (route) => {
    if (!(await requireSession(route))) return;
    await route.fulfill({
      json: {
        id: "job-compress-1",
        operation: "compress",
        status: "completed",
        progress: 100,
        input_file_ids: [initialFile.id],
        output_file_id: "file-output-1",
        params: {},
        error: null,
        requested_by: "web-console:smoke-test",
      },
    });
  });

  await page.route("**/api/v1/files/file-output-1/download", async (route) => {
    if (!(await requireSession(route))) return;
    await route.fulfill({ status: 200, contentType: "application/pdf", body: "%PDF-1.4\n%%EOF\n" });
  });

  await page.route("**/api/v1/files", async (route) => {
    if (route.request().method() !== "POST") {
      await route.fallback();
      return;
    }
    if (!(await requireSession(route))) return;
    await route.fulfill({
      json: {
        id: "file-image-1",
        original_name: "scan.png",
        content_type: "image/png",
        size: 3,
        sha256: "b".repeat(64),
        source_system: "web-console:smoke-test",
        created_at: "2026-08-31T08:05:00Z",
        expires_at: null,
      },
    });
  });
}

test.beforeEach(async ({ page }) => {
  await installApiMocks(page);
});

test("opens a Web Console session without exposing API-key login", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByLabel("Service API Key")).toHaveCount(0);
  await expect(page.getByText("Web Console")).toBeVisible();
  await expect(page.locator("#workspace")).toBeVisible();
  await expect(page.getByRole("button", { name: "ผู้ดูแล" })).toHaveCount(0);
});

test("V3 opens only the selected task workspace", async ({ page }) => {
  await page.goto("/");

  await expect(page.locator("#workspace")).toBeVisible();
  await page.getByRole("button", { name: /ใส่ลายน้ำ PDF/ }).click();

  const workbench = page.locator("#advanced-tools");
  await expect(workbench).toBeVisible();
  await expect(workbench.locator("#watermark")).toBeVisible();
  await expect(workbench.locator("#pdf-to-images")).toBeHidden();

  await workbench.getByRole("button", { name: "ปิด" }).click();
  await expect(workbench).toBeHidden();
});

test("propagates the session through preview, job, download and upload", async ({ page }) => {
  await page.goto("/");

  await expect(page.locator("#workspace")).toBeVisible();
  await expect(page.locator("strong", { hasText: /^example\.pdf$/ })).toBeVisible();

  await page.getByRole("button", { name: "ดูตัวอย่าง PDF" }).click();
  await expect(page.getByRole("img", { name: "Preview page 1" })).toBeVisible();

  await page.getByRole("button", { name: "ลดขนาด PDF" }).click();
  await page.locator("#advanced-tools").getByRole("button", { name: "บีบอัด PDF" }).click();
  await expect(page.locator(".jobInfo").getByText("compress", { exact: true })).toBeVisible();
  await expect(page.locator(".badge.completed")).toContainText("100%");

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "ดาวน์โหลด", exact: true }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toContain("pdfhub-file-output-1");

  await page.locator("#files").setInputFiles({ name: "scan.png", mimeType: "image/png", buffer: Buffer.from([1, 2, 3]) });
  await expect(page.getByText("2 ไฟล์", { exact: true })).toBeVisible();
  await expect(page.locator("strong", { hasText: /^scan\.png$/ })).toBeVisible();
});
