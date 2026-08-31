import { expect, Page, Route, test } from "@playwright/test";

const VALID_KEY = "pdfh_test_valid";
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

async function requireApiKey(route: Route) {
  if (route.request().headers()["x-api-key"] === VALID_KEY) return true;
  await route.fulfill({ status: 401, contentType: "application/json", body: JSON.stringify({ detail: "Missing or invalid API key" }) });
  return false;
}

async function installApiMocks(page: Page) {
  await page.route("**/api/v1/auth/config", async (route) => {
    await route.fulfill({
      json: {
        session_cookie: "pdfhub_session",
        oidc: { enabled: false, issuer: null, login_url: null },
        ldap: { enabled: false },
        api_key: { enabled: true },
      },
    });
  });

  await page.route("**/api/v1/auth/me", async (route) => {
    if (!(await requireApiKey(route))) return;
    await route.fulfill({
      json: {
        name: "service:smoke-test",
        display_name: "Smoke Service",
        subject: null,
        scopes: ["files:read", "files:write", "jobs:read", "pdf:compress"],
        groups: [],
        auth_source: "api_key",
        is_admin: false,
      },
    });
  });

  await page.route("**/api/v1/integrations/status", async (route) => {
    if (!(await requireApiKey(route))) return;
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
    if (!(await requireApiKey(route))) return;
    await route.fulfill({ json: [initialFile] });
  });

  await page.route("**/api/v1/jobs?limit=50", async (route) => {
    if (!(await requireApiKey(route))) return;
    await route.fulfill({ json: [] });
  });

  await page.route("**/api/v1/files/file-pdf-1/preview**", async (route) => {
    if (!(await requireApiKey(route))) return;
    await route.fulfill({ status: 200, contentType: "image/png", body: pngPixel });
  });

  await page.route("**/api/v1/pdf/compress", async (route) => {
    if (!(await requireApiKey(route))) return;
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
        requested_by: "service:smoke-test",
      },
    });
  });

  await page.route("**/api/v1/files/file-output-1/download", async (route) => {
    if (!(await requireApiKey(route))) return;
    await route.fulfill({ status: 200, contentType: "application/pdf", body: "%PDF-1.4\n%%EOF\n" });
  });

  await page.route("**/api/v1/files", async (route) => {
    if (route.request().method() !== "POST") {
      await route.fallback();
      return;
    }
    if (!(await requireApiKey(route))) return;
    await route.fulfill({
      json: {
        id: "file-image-1",
        original_name: "scan.png",
        content_type: "image/png",
        size: 3,
        sha256: "b".repeat(64),
        source_system: "smoke-test",
        created_at: "2026-08-31T08:05:00Z",
        expires_at: null,
      },
    });
  });
}

test.beforeEach(async ({ page }) => {
  await installApiMocks(page);
});

test("rejects an invalid API key without entering authenticated UI", async ({ page }) => {
  await page.goto("/");

  await page.getByLabel("Service API Key").fill("pdfh_wrong_key");
  await page.getByRole("button", { name: "เชื่อมต่อ" }).click();

  await expect(page.getByRole("heading", { name: "พร้อมเริ่มจัดการ PDF" })).toBeVisible();
  await expect(page.locator("#workspace")).toHaveCount(0);
  await expect(page.locator(".status")).toContainText("Missing or invalid API key");
});

test("connects with a valid key and propagates auth through preview, job, download and upload", async ({ page }) => {
  await page.goto("/");

  await page.getByLabel("Service API Key").fill(VALID_KEY);
  await page.getByRole("button", { name: "เชื่อมต่อ" }).click();

  await expect(page.getByText("Smoke Service")).toBeVisible();
  await expect(page.locator("#workspace")).toBeVisible();
  await expect(page.getByText("example.pdf", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "ดูตัวอย่าง PDF" }).click();
  await expect(page.getByRole("img", { name: "Preview page 1" })).toBeVisible();

  await page.getByRole("button", { name: "ลดขนาด PDF" }).click();
  await expect(page.locator(".jobInfo").getByText("compress", { exact: true })).toBeVisible();
  await expect(page.locator(".badge.completed")).toContainText("100%");

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "ดาวน์โหลด" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toContain("pdfhub-file-output-1");

  await page.locator("#files").setInputFiles({ name: "scan.png", mimeType: "image/png", buffer: Buffer.from([1, 2, 3]) });
  await expect(page.getByText("2 ไฟล์", { exact: true })).toBeVisible();
  await expect(page.getByText("scan.png", { exact: true })).toBeVisible();
});
