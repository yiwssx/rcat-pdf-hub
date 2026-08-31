import { expect, Page, Route, test } from "@playwright/test";

const LOCAL_USER = "admin";
const LOCAL_PASSWORD = "local-test-password-123";
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
  source_system: "identity:test-local",
  created_at: "2026-08-31T08:00:00Z",
  expires_at: null,
};

async function installApiMocks(page: Page) {
  let sessionActive = false;

  async function requireSession(route: Route) {
    if (sessionActive) return true;
    await route.fulfill({ status: 401, contentType: "application/json", body: JSON.stringify({ detail: "Authentication required" }) });
    return false;
  }

  await page.route("**/api/v1/auth/config", async (route) => {
    await route.fulfill({
      json: {
        session_cookie: "pdfhub_session",
        local: { enabled: true },
        oidc: { enabled: false, issuer: null, login_url: null },
        ldap: { enabled: false },
        api_key: { enabled: true },
      },
    });
  });

  await page.route("**/api/v1/auth/local/login", async (route) => {
    const body = route.request().postDataJSON() as { username?: string; password?: string };
    if (body.username !== LOCAL_USER || body.password !== LOCAL_PASSWORD) {
      await route.fulfill({ status: 401, contentType: "application/json", body: JSON.stringify({ detail: "Local authentication failed" }) });
      return;
    }
    sessionActive = true;
    await route.fulfill({
      json: {
        name: "identity:local-test",
        display_name: "Local Admin",
        subject: "admin",
        scopes: ["*"],
        groups: ["local-admin"],
        auth_source: "local",
        is_admin: true,
      },
    });
  });

  await page.route("**/api/v1/auth/me", async (route) => {
    if (!(await requireSession(route))) return;
    await route.fulfill({
      json: {
        name: "identity:local-test",
        display_name: "Local Admin",
        subject: "admin",
        scopes: ["*"],
        groups: ["local-admin"],
        auth_source: "local",
        is_admin: true,
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
        requested_by: "identity:test-local",
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
        source_system: "identity:test-local",
        created_at: "2026-08-31T08:05:00Z",
        expires_at: null,
      },
    });
  });
}

test.beforeEach(async ({ page }) => {
  await installApiMocks(page);
});

test("shows human local login and rejects invalid credentials", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByLabel("Service API Key")).toHaveCount(0);
  await expect(page.getByText("โหมด Local Development")).toBeVisible();
  await page.getByLabel("ชื่อผู้ใช้ Local").fill(LOCAL_USER);
  await page.getByLabel("รหัสผ่าน Local").fill("wrong-password");
  await page.getByRole("button", { name: "เข้าสู่ระบบ", exact: true }).click();

  await expect(page.getByRole("heading", { name: "พร้อมเริ่มจัดการ PDF" })).toBeVisible();
  await expect(page.locator("#workspace")).toHaveCount(0);
  await expect(page.locator(".status")).toContainText("Local authentication failed");
});

test("logs in locally and propagates the session through preview, job, download and upload", async ({ page }) => {
  await page.goto("/");

  await page.getByLabel("ชื่อผู้ใช้ Local").fill(LOCAL_USER);
  await page.getByLabel("รหัสผ่าน Local").fill(LOCAL_PASSWORD);
  await page.getByRole("button", { name: "เข้าสู่ระบบ", exact: true }).click();

  await expect(page.getByText("Local Admin", { exact: true })).toBeVisible();
  await expect(page.locator("#workspace")).toBeVisible();
  await expect(page.getByText("example.pdf", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "จัดการหน้าและเอกสาร" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "แปลงไฟล์" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "ปรับแต่งเอกสาร" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "แชร์และจัดเก็บ" })).toBeVisible();

  await page.getByRole("button", { name: "ดูตัวอย่าง PDF" }).click();
  await expect(page.getByRole("img", { name: "Preview page 1" })).toBeVisible();

  await page.getByRole("button", { name: /ลดขนาด PDF/ }).click();
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
