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
        local_admin: { enabled: false },
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
        scopes: ["files:read", "files:write", "jobs:read", "jobs:manage", "pdf:compress"],
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

  await page.route("**/api/v1/files?limit=200&offset=0", async (route) => {
    if (!(await requireSession(route))) return;
    await route.fulfill({ json: [initialFile] });
  });

  await page.route("**/api/v1/jobs?limit=50", async (route) => {
    if (!(await requireSession(route))) return;
    await route.fulfill({ json: [] });
  });


  await page.route("**/api/v1/files/file-pdf-1/pages", async (route) => {
    if (!(await requireSession(route))) return;
    await route.fulfill({ json: { file_id: initialFile.id, pages: 3 } });
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

  await page.route("**/api/v1/pdf/watermark", async (route) => {
    if (!(await requireSession(route))) return;
    await route.fulfill({
      json: {
        id: "job-watermark-1",
        operation: "watermark",
        status: "queued",
        progress: 0,
        input_file_ids: [initialFile.id],
        output_file_id: null,
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

  await page.route("**/api/v1/files/file-pdf-1/download", async (route) => {
    if (!(await requireSession(route))) return;
    await route.fulfill({ status: 200, contentType: "application/pdf", body: "%PDF-1.4\n%%EOF\n" });
  });

  await page.route("**/api/v1/jobs/terminal", async (route) => {
    if (!(await requireSession(route))) return;
    await route.fulfill({ json: { deleted: 1 } });
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
  await expect(page.getByLabel("เมนูบัญชี").getByText("Web Console")).toBeVisible();
  await expect(page.locator("#workspace")).toBeVisible();
  await expect(page.locator(".v3HomeTitle")).toContainText("จัดการเอกสารของคุณ");
  await expect(page.locator(".welcomeHero")).toHaveCount(0);
  await expect(page.locator(".authCard")).toHaveCount(0);
});

test("V3 switches from home into a focused tool workspace without long-page sections", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByText("example.pdf", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: /ลายน้ำ/ }).first().click();

  await expect(page.locator("#workspace-target")).toBeVisible();
  await expect(page.locator(".v3ToolPanel")).toBeVisible();
  await expect(page.locator(".v3ToolPanel")).toContainText("ลายน้ำ PDF");
  await expect(page.locator(".jobsSection")).toHaveCount(0);
  await expect(page.locator(".advancedSection")).toHaveCount(0);

  await page.getByRole("button", { name: "กลับไปเลือกเครื่องมือ" }).click();
  await expect(page.locator(".v3ToolPanel")).toHaveCount(0);
  await expect(page.getByText("ทำอะไรกับไฟล์นี้?")).toBeVisible();
});

test("tool workspace owns settings and submits the configured watermark payload", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /example\.pdf/ }).first().click();
  await page.getByRole("button", { name: /ลายน้ำ/ }).click();

  await page.getByLabel("ข้อความ").fill("เอกสารทดสอบ");
  await page.getByLabel("ความโปร่งใส").fill("0.25");

  const requestPromise = page.waitForRequest("**/api/v1/pdf/watermark");
  await page.getByRole("button", { name: "ใส่ลายน้ำ" }).click();
  const request = await requestPromise;

  expect(request.postDataJSON()).toMatchObject({
    file_id: initialFile.id,
    text: "เอกสารทดสอบ",
    opacity: 0.25,
    rotation: 45,
    position: "center",
    margin: 36,
  });
  await expect(page.locator(".v3JobDrawer")).toBeVisible();
  await page.locator(".v3JobDrawer").getByRole("button", { name: "×" }).click();
  await page.getByRole("button", { name: /ลายน้ำ/ }).click();
  await expect(page.getByLabel("ข้อความ")).toHaveValue("เอกสารทดสอบ");
});

test("propagates the session through preview, job drawer, download and upload", async ({ page }) => {
  await page.goto("/");

  await expect(page.locator("#workspace")).toBeVisible();
  await page.getByRole("button", { name: /example\.pdf/ }).first().click();
  await expect(page.locator("#workspace-target")).toBeVisible();

  await page.getByRole("button", { name: "ดูตัวอย่าง PDF" }).click();
  await expect(page.getByRole("img", { name: "Preview page 1" })).toBeVisible();

  await page.getByRole("button", { name: /ลดขนาด PDF/ }).click();
  await page.getByRole("button", { name: "บีบอัด PDF" }).click();
  await expect(page.locator(".v3JobDrawer")).toBeVisible();
  await expect(page.locator(".jobInfo").getByText("compress", { exact: true })).toBeVisible();
  await expect(page.locator(".v3JobBadge.completed")).toContainText("100%");

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "ดาวน์โหลด", exact: true }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toContain("pdfhub-file-output-1");

  await page.locator(".v3JobDrawer").getByRole("button", { name: "×" }).click();
  await page.getByRole("button", { name: /กลับ/ }).click();
  await page.locator("#files").setInputFiles({ name: "scan.png", mimeType: "image/png", buffer: Buffer.from([1, 2, 3]) });
  await expect(page.locator("#workspace-target")).toBeVisible();
  await expect(page.locator("#workspace-target strong")).toHaveText("scan.png");
});

test("files is a dedicated route instead of a section in the home page", async ({ page }) => {
  await page.goto("/files");
  await expect(page.getByRole("heading", { name: "ไฟล์ทั้งหมด" })).toBeVisible();
  await expect(page.getByText("example.pdf", { exact: true })).toBeVisible();
  await expect(page.locator(".v3FileLibrary")).toBeVisible();
});


test("page organizer uses thumbnails instead of the old form wall", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /example\.pdf/ }).first().click();
  await page.getByRole("button", { name: /จัดหน้า PDF/ }).click();
  await expect(page.locator(".v3PageOrganizer")).toBeVisible();
  await expect(page.locator(".v3PageThumb")).toHaveCount(3);
  await page.getByRole("button", { name: "หมุนหน้า 1" }).click();
  await expect(page.getByRole("button", { name: "บันทึกการจัดหน้า 3 หน้า" })).toBeVisible();
});

test("admin login is a dedicated route and never requests a Service API Key", async ({ page }) => {
  await page.goto("/admin/login");
  await expect(page.getByLabel("Service API Key")).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "ผู้ดูแล RCAT PDF Hub" })).toBeVisible();
  await expect(page.getByText(/Local Admin ยังไม่ได้เปิดใช้/)).toBeVisible();
});


test("completed jobs expose file context and can clear terminal history", async ({ page }) => {
  page.on("dialog", (dialog) => void dialog.accept());
  await page.goto("/");
  await page.getByRole("button", { name: /example\.pdf/ }).first().click();
  await page.getByRole("button", { name: /ลดขนาด PDF/ }).click();
  await page.getByRole("button", { name: "บีบอัด PDF" }).click();

  const drawer = page.locator(".v3JobDrawer");
  await expect(drawer).toContainText("example.pdf");
  await expect(drawer.getByRole("button", { name: "ล้างประวัติ" })).toBeVisible();
  await drawer.getByRole("button", { name: "ล้างประวัติ" }).click();
  await expect(drawer).toContainText("ยังไม่มีงานประมวลผล");
});

test("files route provides direct download action", async ({ page }) => {
  await page.goto("/files");
  const row = page.locator(".v3LibraryRow").filter({ hasText: "example.pdf" });
  const downloadPromise = page.waitForEvent("download");
  await row.getByRole("button", { name: "ดาวน์โหลด" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toContain("example.pdf");
});
