import { expect, Page, Route, test } from "@playwright/test";
import { authConfigFixture, integrationStatusFixture, operatorIdentityFixture } from "./api-fixtures";

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
    await route.fulfill({ json: authConfigFixture });
  });

  await page.route("**/web-auth/session", async (route) => {
    sessionReady = true;
    await route.fulfill({ status: 204 });
  });

  await page.route("**/api/v1/auth/me", async (route) => {
    const referer = route.request().headers()["referer"] || "";
    if (/\/admin\/?(?:[?#]|$)/.test(referer)) {
      sessionReady = true;
      await route.fulfill({
        json: {
          name: "user:admin@example.org",
          display_name: "RCAT Administrator",
          subject: "oidc-admin-1",
          scopes: ["*"],
          groups: ["pdfhub-admins"],
          roles: ["admin"],
          auth_source: "oidc",
          is_admin: true,
        },
      });
      return;
    }
    if (!(await requireSession(route))) return;
    await route.fulfill({
      json: operatorIdentityFixture({
        name: "web-console:smoke-test",
        subject: "smoke-test",
      }),
    });
  });

  await page.route("**/api/v1/admin/status", async (route) => {
    await route.fulfill({
      json: {
        database_ok: true,
        redis_ok: true,
        workers: 3,
        queue_depth: 0,
        storage_backend: "local",
        storage_write_ok: true,
        gotenberg_ok: true,
        data_dir: "/data",
        disk: { total: 107374182400, used: 21474836480, free: 85899345920 },
        pdfhub_bytes: 4096,
        files: 1,
        jobs: { queued: 0, running: 0, completed: 1, failed: 0, cancelled: 0 },
        retention_hours: 24,
        cleanup_temporary_hours: 6,
        clamav_enabled: true,
        paperless_enabled: false,
        tools: { qpdf: true, gs: true, ocrmypdf: true, tesseract: true, pdftoppm: true },
        auth: { local_admin: true, oidc: true, ldap: false, web_console_auto_login: false },
        principal: "user:admin@example.org",
      },
    });
  });

  await page.route("**/api/v1/integrations/status", async (route) => {
    if (!(await requireSession(route))) return;
    await route.fulfill({ json: integrationStatusFixture });
  });

  await page.route("**/api/v1/files?limit=200&offset=0", async (route) => {
    if (!(await requireSession(route))) return;
    await route.fulfill({ json: [initialFile] });
  });

  await page.route("**/api/v1/files/library**", async (route) => {
    if (!(await requireSession(route))) return;
    const url = new URL(route.request().url());
    const q = (url.searchParams.get("q") || "").toLowerCase();
    const kind = url.searchParams.get("kind") || "all";
    const offset = Number(url.searchParams.get("offset") || "0");
    let items = [initialFile];
    if (q) items = items.filter((file) => file.original_name.toLowerCase().includes(q));
    if (kind === "image") items = [];
    await route.fulfill({
      json: {
        items,
        total: items.length,
        limit: Number(url.searchParams.get("limit") || "50"),
        offset,
        has_more: false,
      },
    });
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
  await expect(page).toHaveURL(/\/tools\/watermark$/);
  await expect(page.locator("#workspace-target")).toHaveCount(0);
  await page.getByRole("button", { name: /example\.pdf/ }).first().click();

  await expect(page.locator("#workspace-target")).toBeVisible();
  await expect(page.locator(".v3ToolPanel")).toBeVisible();
  await expect(page.locator(".v3ToolPanel")).toContainText("ลายน้ำ PDF");
  await expect(page.locator(".jobsSection")).toHaveCount(0);
  await expect(page.locator(".advancedSection")).toHaveCount(0);

  await page.getByRole("button", { name: "กลับไปเลือกเครื่องมือ" }).click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.locator(".v3ToolPanel")).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "จัดการเอกสารของคุณ" })).toBeVisible();
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

test("files route sends search and filters to the paged server API", async ({ page }) => {
  await page.goto("/files");
  await expect(page.getByText("example.pdf", { exact: true })).toBeVisible();

  const searchRequest = page.waitForRequest((request) => {
    const url = new URL(request.url());
    return url.pathname === "/api/v1/files/library" && url.searchParams.get("q") === "missing";
  });
  await page.getByLabel("ค้นหาชื่อไฟล์").fill("missing");
  await searchRequest;
  await expect(page.getByText("example.pdf", { exact: true })).toHaveCount(0);

  const filterRequest = page.waitForRequest((request) => {
    const url = new URL(request.url());
    return url.pathname === "/api/v1/files/library" && url.searchParams.get("kind") === "pdf";
  });
  await page.getByLabel("ค้นหาชื่อไฟล์").fill("");
  await page.getByLabel("ประเภทไฟล์").selectOption("pdf");
  await filterRequest;
  await expect(page.getByText("example.pdf", { exact: true })).toBeVisible();
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


test("admin console exposes effective identity role groups and scopes", async ({ page }) => {
  await page.goto("/admin");

  const access = page.locator(".v3EffectiveAccess");
  await expect(access).toBeVisible();
  await expect(access).toContainText("RCAT Administrator");
  await expect(access).toContainText("oidc");
  await expect(access).toContainText("pdfhub-admins");
  await expect(access).toContainText("admin");
  await expect(access.locator("code")).toHaveText("*");
  await expect(access.locator('input[type="password"]')).toHaveCount(0);
  await expect(access.locator('input[name*="key" i]')).toHaveCount(0);
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

test("P7A.1 deep links keep tool intent across navigation, reload, and reject unknown slugs", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /ลดขนาด PDF/ }).first().click();
  await expect(page).toHaveURL(/\/tools\/compress$/);
  await expect(page.getByRole("heading", { name: "ลดขนาด PDF" })).toBeVisible();
  await expect(page.locator("#workspace-target")).toHaveCount(0);

  await page.reload();
  await expect(page.getByRole("heading", { name: "ลดขนาด PDF" })).toBeVisible();
  await expect(page.locator("#workspace-target")).toHaveCount(0);

  await page.goBack();
  await expect(page.getByRole("heading", { name: "จัดการเอกสารของคุณ" })).toBeVisible();
  await page.goForward();
  await expect(page.getByRole("heading", { name: "ลดขนาด PDF" })).toBeVisible();

  await page.getByRole("button", { name: /example\.pdf/ }).first().click();
  await expect(page.locator("#workspace-target")).toContainText("example.pdf");
  await expect(page.locator(".v3ToolPanel")).toContainText("ลดขนาด PDF");

  await page.goto("/tools/unknown-tool");
  await expect(page.getByText("404")).toBeVisible();
});

test("P7A.1 file-selected deep links respect the authorized library", async ({ page }) => {
  await page.goto("/tools/compress?file=file-pdf-1");
  await expect(page.locator("#workspace-target")).toContainText("example.pdf");
  await page.reload();
  await expect(page.locator("#workspace-target")).toContainText("example.pdf");

  await page.goto("/tools/compress?file=unowned-file-id");
  await expect(page.locator("#workspace-target")).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "เลือกไฟล์ที่มีอยู่" })).toBeVisible();
});

test("P7A.1 routed merge never adds an unrelated library PDF implicitly", async ({ page }) => {
  const otherPdf = { ...initialFile, id: "file-pdf-2", original_name: "unrelated.pdf" };
  await page.route("**/api/v1/files?limit=200&offset=0", (route) => route.fulfill({ json: [initialFile, otherPdf] }));
  await page.goto("/tools/merge-pdf?file=file-pdf-1");

  await expect(page.locator(".v3ToolPanel")).toBeVisible();
  await expect(page.locator(".v3MergeList")).toContainText("example.pdf");
  await expect(page.locator(".v3MergeList")).not.toContainText("unrelated.pdf");
  await expect(page.getByRole("button", { name: /รวม PDF/ }).last()).toBeDisabled();
});
