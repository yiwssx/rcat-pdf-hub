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

  await page.route("**/api/v1/admin/jobs/triage?**", async (route) => {
    await route.fulfill({ json: { items: [], limit: 25, offset: 0, has_more: false } });
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

  await page.route("**/api/v1/jobs?limit=50**", async (route) => {
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
  await page.getByRole("radio", { name: "example.pdf" }).check();
  await page.getByRole("button", { name: /ตั้งค่าและดำเนินการ/ }).click();

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
  await expect(page).toHaveURL(/\/jobs\/job-watermark-1$/);
  await expect(page.getByRole("heading", { name: "สถานะงาน PDF" })).toBeVisible();
});

test("propagates the session through preview, job detail, drawer, download and upload", async ({ page }) => {
  const completed = {
    id: "job-compress-1", operation: "compress", status: "completed", progress: 100,
    input_file_ids: [initialFile.id], output_file_id: "file-output-1",
    params: {}, error: null, requested_by: "web-console:smoke-test",
  };
  await page.route("**/api/v1/jobs?limit=50", (route) => route.fulfill({ json: [completed] }));
  await page.route("**/api/v1/jobs/job-compress-1", (route) => route.fulfill({ json: completed }));
  await page.goto("/");

  await expect(page.locator("#workspace")).toBeVisible();
  await page.getByRole("button", { name: /example\.pdf/ }).first().click();
  await expect(page.locator("#workspace-target")).toBeVisible();

  await page.getByRole("button", { name: "ดูตัวอย่าง PDF" }).click();
  await expect(page.getByRole("img", { name: "Preview page 1" })).toBeVisible();

  await page.getByRole("button", { name: /ลดขนาด PDF/ }).click();
  await page.getByRole("button", { name: "บีบอัด PDF" }).click();
  await expect(page).toHaveURL(/\/jobs\/job-compress-1$/);
  await expect(page.getByRole("heading", { name: "สถานะงาน PDF" })).toBeVisible();
  await page.getByRole("button", { name: /งานล่าสุด/ }).click();
  await expect(page.locator(".v3JobDrawer")).toBeVisible();
  await expect(page.locator(".jobInfo").getByText("compress", { exact: true })).toBeVisible();
  await expect(page.locator(".v3JobDrawer .v3JobBadge.completed")).toContainText("100%");

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "ดาวน์โหลด", exact: true }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toContain("pdfhub-file-output-1");

  await page.locator(".v3JobDrawer").getByRole("button", { name: "×" }).click();
  await page.goto("/");
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
  await page.route("**/api/v1/jobs?limit=50", (route) => route.fulfill({ json: [{
    id: "job-compress-history-1", operation: "compress", status: "completed", progress: 100,
    input_file_ids: [initialFile.id], output_file_id: "file-output-1",
    params: {}, error: null, requested_by: "web-console:smoke-test",
  }] }));
  await page.goto("/");
  await page.getByRole("button", { name: /งานล่าสุด/ }).click();
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

  await page.getByRole("radio", { name: "example.pdf" }).check();
  await page.getByRole("button", { name: /ตั้งค่าและดำเนินการ/ }).click();
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
  await expect(page.getByRole("heading", { name: "เลือกจากคลังไฟล์" })).toBeVisible();
  await expect(page.getByText("ไฟล์บางรายการไม่อยู่ในคลังไฟล์ที่คุณเข้าถึงได้")).toBeVisible();
});

test("P7B.2 routed merge requires reviewed second input rather than picking a library PDF", async ({ page }) => {
  const otherPdf = { ...initialFile, id: "file-pdf-2", original_name: "unrelated.pdf" };
  await page.route("**/api/v1/files?limit=200&offset=0", (route) => route.fulfill({ json: [initialFile, otherPdf] }));
  await page.goto("/tools/merge-pdf?file=file-pdf-1");

  await expect(page.locator(".v3ToolPanel")).toHaveCount(0);
  await expect(page.getByRole("checkbox", { name: "example.pdf" })).toBeChecked();
  await expect(page.getByRole("checkbox", { name: "unrelated.pdf" })).not.toBeChecked();
  await expect(page.getByRole("button", { name: /ตั้งค่าและดำเนินการ/ })).toBeDisabled();
});

test("P7A.2 validates kind and count, reviews exact ordered merge inputs", async ({ page }) => {
  const secondPdf = { ...initialFile, id: "file-pdf-2", original_name: "second.pdf" };
  const image = { ...initialFile, id: "file-image-1", original_name: "scan.png", content_type: "image/png" };
  await page.route("**/api/v1/files?limit=200&offset=0", (route) => route.fulfill({ json: [initialFile, secondPdf, image] }));
  await page.route("**/api/v1/pdf/merge", (route) => route.fulfill({
    json: {
      id: "job-merge-1", operation: "merge", status: "queued", progress: 0,
      input_file_ids: ["file-pdf-2", "file-pdf-1"], output_file_id: null,
      params: {}, error: null, requested_by: "web-console:smoke-test",
    },
  }));

  await page.goto("/tools/merge-pdf");
  await expect(page.getByRole("heading", { name: "รวม PDF" })).toBeVisible();
  await expect(page.getByRole("checkbox", { name: "scan.png" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: /ตั้งค่าและดำเนินการ/ })).toBeDisabled();

  await page.getByRole("checkbox", { name: "example.pdf" }).check();
  await expect(page.getByRole("button", { name: /ตั้งค่าและดำเนินการ/ })).toBeDisabled();
  await page.getByRole("checkbox", { name: "second.pdf" }).check();
  await page.getByRole("button", { name: "เลื่อน second.pdf ขึ้น" }).click();
  await page.getByRole("button", { name: /ตั้งค่าและดำเนินการ/ }).click();

  await expect(page.locator(".v3MergeList")).toContainText("second.pdf");
  await expect(page.locator(".v3MergeList")).toContainText("example.pdf");
  await expect(page.locator(".v3MergeList")).not.toContainText("scan.png");

  const request = page.waitForRequest("**/api/v1/pdf/merge");
  await page.getByRole("button", { name: /รวม PDF 2 ไฟล์/ }).click();
  expect((await request).postDataJSON()).toEqual({ file_ids: ["file-pdf-2", "file-pdf-1"] });
});

test("P7A.2 single-file intake requires explicit choice and rejects other file types", async ({ page }) => {
  const image = { ...initialFile, id: "file-image-2", original_name: "photo.png", content_type: "image/png" };
  await page.route("**/api/v1/files?limit=200&offset=0", (route) => route.fulfill({ json: [image, initialFile] }));
  await page.goto("/tools/compress");

  await expect(page.locator("#workspace-target")).toHaveCount(0);
  await expect(page.getByRole("radio", { name: "photo.png" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: /ตั้งค่าและดำเนินการ/ })).toBeDisabled();
  await page.getByRole("radio", { name: "example.pdf" }).check();
  await page.getByRole("button", { name: /ตั้งค่าและดำเนินการ/ }).click();
  await expect(page.locator("#workspace-target")).toContainText("example.pdf");
});

test("P7A.2 image-to-PDF payload retains reviewed image sequence", async ({ page }) => {
  const first = { ...initialFile, id: "img-1", original_name: "first.png", content_type: "image/png" };
  const second = { ...initialFile, id: "img-2", original_name: "second.png", content_type: "image/png" };
  await page.route("**/api/v1/files?limit=200&offset=0", (route) => route.fulfill({ json: [first, second] }));
  await page.route("**/api/v1/pdf/images-to-pdf", (route) => route.fulfill({
    json: {
      id: "job-img-1", operation: "images-to-pdf", status: "queued", progress: 0,
      input_file_ids: ["img-2", "img-1"], output_file_id: null, params: {},
      error: null, requested_by: "web-console:smoke-test",
    },
  }));

  await page.goto("/tools/images-to-pdf");
  await page.getByRole("checkbox", { name: "first.png" }).check();
  await page.getByRole("checkbox", { name: "second.png" }).check();
  await page.getByRole("button", { name: "เลื่อน second.png ขึ้น" }).click();
  await page.getByRole("button", { name: /ตั้งค่าและดำเนินการ/ }).click();

  const request = page.waitForRequest("**/api/v1/pdf/images-to-pdf");
  await page.getByRole("button", { name: "สร้าง PDF จากภาพ" }).click();
  expect((await request).postDataJSON()).toMatchObject({ file_ids: ["img-2", "img-1"] });
});

test("P7B.1 journey shows explicit intake and configure steps with back navigation", async ({ page }) => {
  await page.goto("/tools/compress");
  const nav = page.getByRole("navigation", { name: "ขั้นตอนการทำงาน" });
  await expect(nav.locator('[aria-current="step"]')).toContainText("เลือกไฟล์");
  await page.getByRole("radio", { name: "example.pdf" }).check();
  await page.getByRole("button", { name: /ตั้งค่าและดำเนินการ/ }).click();
  await expect(nav.locator('[aria-current="step"]')).toContainText("ตั้งค่า");
  await page.locator(".v3DocumentBar .v3BackLink").click();
  await expect(nav.locator('[aria-current="step"]')).toContainText("เลือกไฟล์");

  await page.goto("/tools/archive");
  await expect(page.getByRole("navigation", { name: "ขั้นตอนการทำงาน" })).toContainText("จัดเก็บ");
});

test("P7B.1 synchronous double click creates exactly one backend processing job", async ({ page }) => {
  let requestCount = 0;
  await page.route("**/api/v1/pdf/compress", async (route) => {
    requestCount += 1;
    await new Promise((resolve) => setTimeout(resolve, 180));
    await route.fulfill({
      json: {
        id: "job-compress-guarded", operation: "compress", status: "completed", progress: 100,
        input_file_ids: ["file-pdf-1"], output_file_id: "file-output-1",
        params: {}, error: null, requested_by: "web-console:smoke-test",
      },
    });
  });

  await page.goto("/tools/compress?file=file-pdf-1");
  const button = page.getByRole("button", { name: "บีบอัด PDF" });
  await expect(button).toBeEnabled();
  await button.evaluate((node) => {
    (node as HTMLButtonElement).click();
    (node as HTMLButtonElement).click();
  });
  await expect(page).toHaveURL(/\/jobs\/job-compress-guarded$/);
  expect(requestCount).toBe(1);
  await expect(page.getByRole("heading", { name: "สถานะงาน PDF" })).toBeVisible();
});

test("P7B.2 stamp configuration reuses the reviewed second PDF without reselecting", async ({ page }) => {
  const stamp = { ...initialFile, id: "file-stamp-pdf", original_name: "stamp.pdf" };
  await page.route("**/api/v1/files?limit=200&offset=0", (route) => route.fulfill({ json: [initialFile, stamp] }));
  await page.goto("/tools/pdf-stamp");
  await page.getByRole("checkbox", { name: "example.pdf" }).check();
  await page.getByRole("checkbox", { name: "stamp.pdf" }).check();
  await page.getByRole("button", { name: /ตั้งค่าและดำเนินการ/ }).click();

  await expect(page.getByRole("combobox", { name: "ไฟล์ตราประทับ" })).toHaveValue("file-stamp-pdf");
  await expect(page.getByRole("region", { name: "ไฟล์ที่จะประมวลผล" })).toContainText("stamp.pdf");
  await expect(page.getByRole("button", { name: "ประทับ PDF" })).toBeEnabled();
});

test("P7B.2 archival intake agrees with PDF-only processing requirement", async ({ page }) => {
  const image = { ...initialFile, id: "image-for-archive", original_name: "photo.png", content_type: "image/png" };
  await page.route("**/api/v1/files?limit=200&offset=0", (route) => route.fulfill({ json: [image, initialFile] }));
  await page.goto("/tools/archive");
  await expect(page.getByRole("radio", { name: "photo.png" })).toHaveCount(0);
  await expect(page.getByRole("radio", { name: "example.pdf" })).toBeVisible();
  await expect(page.locator('input[type="file"]')).toHaveAttribute("accept", /application\/pdf/);
});

test("P7C.1 job link survives refresh and renders backend-authoritative state transitions", async ({ page }) => {
  let reads = 0;
  await page.route("**/api/v1/jobs/job-status-1", async (route) => {
    reads += 1;
    const status = reads === 1 ? "queued" : reads === 2 ? "running" : "completed";
    await route.fulfill({ json: {
      id: "job-status-1", operation: "compress", status,
      progress: status === "queued" ? 0 : status === "running" ? 55 : 100,
      input_file_ids: ["file-pdf-1"], output_file_id: status === "completed" ? "file-output-1" : null,
      params: {}, error: null, requested_by: "web-console:smoke-test",
    }});
  });
  await page.goto("/jobs/job-status-1");
  const main = page.getByRole("main", { name: "รายละเอียดงานประมวลผล" });
  await expect(main).toContainText("รอประมวลผล");
  await expect(main).toContainText("กำลังประมวลผล", { timeout: 10000 });
  await expect(main.locator(".v3JobBadge.completed")).toBeVisible({ timeout: 10000 });
  await expect(main.getByRole("progressbar", { name: "ความคืบหน้างาน" })).toHaveCount(0);
  await page.reload();
  await expect(main.locator(".v3JobBadge.completed")).toBeVisible();
});

test("P7C.1 owned job endpoint denies unknown and foreign jobs without disclosing data", async ({ page }) => {
  await page.route("**/api/v1/jobs/job-private-1", async (route) => route.fulfill({ status: 403, json: { detail: "Job belongs to another service" } }));
  await page.goto("/jobs/job-private-1");
  await expect(page.locator(".v3JobDetailCard [role='alert']")).toContainText("ไม่มีสิทธิ์");
  await expect(page.locator(".v3JobDetailCard")).not.toContainText("belongs to another service");
  await page.route("**/api/v1/jobs/job-missing-1", async (route) => route.fulfill({ status: 404, json: { detail: "Job not found" } }));
  await page.goto("/jobs/job-missing-1");
  await expect(page.locator(".v3JobDetailCard [role='alert']")).toContainText("ไม่พบงาน");
});

test("P7C.1 failed jobs allow scoped retry into new durable URL", async ({ page }) => {
  await page.route("**/api/v1/jobs/job-failed-1", async (route) => route.fulfill({ json: {
    id: "job-failed-1", operation: "compress", status: "failed", progress: 100,
    input_file_ids: ["file-pdf-1"], output_file_id: null, params: {},
    error: "worker internal trace", requested_by: "web-console:smoke-test",
  }}));
  await page.route("**/api/v1/jobs/job-failed-1/retry", async (route) => route.fulfill({ status: 202, json: {
    id: "job-retry-2", operation: "compress", status: "queued", progress: 0,
    input_file_ids: ["file-pdf-1"], output_file_id: null, params: {},
    error: null, requested_by: "web-console:smoke-test",
  }}));
  await page.goto("/jobs/job-failed-1");
  await expect(page.locator(".v3JobDetailCard [role='alert']")).toContainText("งานนี้ไม่สำเร็จ");
  await expect(page.getByRole("main")).not.toContainText("worker internal trace");
  page.once("dialog", (dialog) => void dialog.accept());
  await page.getByRole("button", { name: "ลองประมวลผลใหม่" }).click();
  await expect(page).toHaveURL(/\/jobs\/job-retry-2$/);
});

test("P7C.1 transient job fetch error offers manual retry", async ({ page }) => {
  let attempts = 0;
  await page.route("**/api/v1/jobs/job-outage-1", async (route) => {
    attempts += 1;
    if (attempts === 1) { await route.abort("failed"); return; }
    await route.fulfill({ json: {
      id: "job-outage-1", operation: "compress", status: "cancelled", progress: 100,
      input_file_ids: ["file-pdf-1"], output_file_id: null, params: {},
      error: null, requested_by: "web-console:smoke-test",
    }});
  });
  await page.goto("/jobs/job-outage-1");
  await expect(page.locator(".v3JobDetailCard [role='alert']")).toContainText("เชื่อมต่อสถานะงานไม่ได้");
  await page.getByRole("button", { name: "รีเฟรชสถานะ" }).click();
  await expect(page.getByRole("main")).toContainText("ยกเลิกงานแล้ว");
});

test("P7C.2 completed owned output opens durable result and downloads original file name", async ({ page }) => {
  const output = { ...initialFile, id: "file-output-1", original_name: "processed.pdf", size: 7216 };
  await page.route("**/api/v1/jobs/job-result-1", (route) => route.fulfill({ json: {
    id: "job-result-1", operation: "compress", status: "completed", progress: 100,
    input_file_ids: ["file-pdf-1"], output_file_id: "file-output-1",
    params: {}, error: null, requested_by: "web-console:smoke-test",
  } }));
  await page.route("**/api/v1/files/file-output-1", (route) => route.fulfill({ json: output }));
  await page.goto("/jobs/job-result-1");
  await page.getByRole("link", { name: /ดูผลลัพธ์และดาวน์โหลด/ }).click();
  await expect(page).toHaveURL(/\/jobs\/job-result-1\/result$/);
  await expect(page.getByText("processed.pdf")).toBeVisible();
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "ดาวน์โหลดผลลัพธ์" }).click();
  expect((await downloadPromise).suggestedFilename()).toBe("processed.pdf");
  await page.reload();
  await expect(page.getByRole("button", { name: "ดาวน์โหลดผลลัพธ์" })).toBeEnabled();
});

test("P7C.2 unfinished jobs never expose output metadata or download", async ({ page }) => {
  let fileReads = 0;
  await page.route("**/api/v1/jobs/job-queued-2", (route) => route.fulfill({ json: {
    id: "job-queued-2", operation: "compress", status: "queued", progress: 0,
    input_file_ids: ["file-pdf-1"], output_file_id: "file-output-1",
    params: {}, error: null, requested_by: "web-console:smoke-test",
  } }));
  await page.route("**/api/v1/files/file-output-1", (route) => { fileReads += 1; return route.fulfill({ json: initialFile }); });
  await page.goto("/jobs/job-queued-2/result");
  await expect(page.getByText(/งานนี้ยังไม่เสร็จ/)).toBeVisible();
  await expect(page.getByRole("button", { name: "ดาวน์โหลดผลลัพธ์" })).toHaveCount(0);
  expect(fileReads).toBe(0);
});

test("P7C.2 expired output hides download and identifies retention state", async ({ page }) => {
  await page.route("**/api/v1/jobs/job-expired-2", (route) => route.fulfill({ json: {
    id: "job-expired-2", operation: "compress", status: "completed", progress: 100,
    input_file_ids: ["file-pdf-1"], output_file_id: "file-output-1",
    params: {}, error: null, requested_by: "web-console:smoke-test",
  } }));
  await page.route("**/api/v1/files/file-output-1", (route) => route.fulfill({ json: {
    ...initialFile, id: "file-output-1", expires_at: "2020-01-01T00:00:00Z",
  } }));
  await page.goto("/jobs/job-expired-2/result");
  await expect(page.getByText(/ไฟล์ผลลัพธ์หมดอายุแล้ว/)).toBeVisible();
  await expect(page.getByRole("button", { name: "ดาวน์โหลดผลลัพธ์" })).toHaveCount(0);
});

test("P7C.2 denied job or missing output never leaks backend details", async ({ page }) => {
  await page.route("**/api/v1/jobs/job-denied-2", (route) => route.fulfill({ status: 403, json: { detail: "secret principal owner" } }));
  await page.goto("/jobs/job-denied-2/result");
  await expect(page.locator(".v3JobDetailCard [role='alert']")).toContainText("ไม่มีสิทธิ์");
  await expect(page.getByRole("main")).not.toContainText("secret principal owner");

  await page.route("**/api/v1/jobs/job-no-file-2", (route) => route.fulfill({ json: {
    id: "job-no-file-2", operation: "compress", status: "completed", progress: 100,
    input_file_ids: ["file-pdf-1"], output_file_id: "file-output-1",
    params: {}, error: null, requested_by: "web-console:smoke-test",
  } }));
  await page.route("**/api/v1/files/file-output-1", (route) => route.fulfill({ status: 404, json: { detail: "internal storage path" } }));
  await page.goto("/jobs/job-no-file-2/result");
  await expect(page.locator(".v3JobDetailCard [role='alert']")).toContainText("ไม่พบงานหรือไฟล์");
  await expect(page.getByRole("main")).not.toContainText("internal storage path");
});

test("P7C.2 expired-on-download responds to backend 410 without false success", async ({ page }) => {
  await page.route("**/api/v1/jobs/job-download-410", (route) => route.fulfill({ json: {
    id: "job-download-410", operation: "compress", status: "completed", progress: 100,
    input_file_ids: ["file-pdf-1"], output_file_id: "file-output-1",
    params: {}, error: null, requested_by: "web-console:smoke-test",
  } }));
  await page.route("**/api/v1/files/file-output-1", (route) => route.fulfill({ json: {
    ...initialFile, id: "file-output-1", original_name: "processed.pdf", expires_at: null,
  } }));
  await page.route("**/api/v1/files/file-output-1/download", (route) => route.fulfill({ status: 410, json: { detail: "storage not found" } }));
  await page.goto("/jobs/job-download-410/result");
  await page.getByRole("button", { name: "ดาวน์โหลดผลลัพธ์" }).click();
  await expect(page.locator(".v3JobDetailCard [role='alert']")).toContainText("หมดอายุหรือไม่พร้อมใช้งาน");
  await expect(page.getByRole("main")).not.toContainText("storage not found");
});

test("P7C.3 compatible PDF output chains to a new tool with no reupload", async ({ page }) => {
  const output = { ...initialFile, id: "file-chain-output", original_name: "processed.pdf", size: 7100 };
  let uploads = 0;
  await page.route("**/api/v1/jobs/job-chain-3", (route) => route.fulfill({ json: {
    id: "job-chain-3", operation: "watermark", status: "completed", progress: 100,
    input_file_ids: [initialFile.id], output_file_id: output.id,
    params: {}, error: null, requested_by: "web-console:smoke-test",
  }}));
  await page.route("**/api/v1/files/file-chain-output", (route) => route.fulfill({ json: output }));
  await page.route("**/api/v1/files?limit=200&offset=0", (route) => route.fulfill({ json: [initialFile, output] }));
  await page.route("**/api/v1/files", (route) => {
    if (route.request().method() === "POST") uploads += 1;
    return route.fallback();
  });
  await page.route("**/api/v1/pdf/compress", (route) => route.fulfill({ json: {
    id: "job-chain-3-new", operation: "compress", status: "queued", progress: 0,
    input_file_ids: [output.id], output_file_id: null, params: {},
    error: null, requested_by: "web-console:smoke-test",
  }}));

  await page.goto("/jobs/job-chain-3/result");
  const next = page.getByRole("region", { name: "ทำงานต่อด้วยเครื่องมืออื่น" });
  await expect(next).toBeVisible();
  await next.getByRole("link", { name: /ลดขนาด PDF/ }).click();
  await expect(page).toHaveURL(/\/tools\/compress\?file=file-chain-output$/);
  await expect(page.locator("#workspace-target")).toContainText("processed.pdf");
  const request = page.waitForRequest("**/api/v1/pdf/compress");
  await page.getByRole("button", { name: "บีบอัด PDF" }).click();
  expect((await request).postDataJSON()).toEqual({ file_id: output.id });
  expect(uploads).toBe(0);
});

test("P7C.3 image output offers only compatible follow-on workflows", async ({ page }) => {
  const output = { ...initialFile, id: "file-image-result", original_name: "scan.png", content_type: "image/png" };
  await page.route("**/api/v1/jobs/job-image-chain", (route) => route.fulfill({ json: {
    id: "job-image-chain", operation: "pdf-to-images", status: "completed", progress: 100,
    input_file_ids: [initialFile.id], output_file_id: output.id,
    params: {}, error: null, requested_by: "web-console:smoke-test",
  }}));
  await page.route("**/api/v1/files/file-image-result", (route) => route.fulfill({ json: output }));
  await page.goto("/jobs/job-image-chain/result");
  const next = page.getByRole("region", { name: "ทำงานต่อด้วยเครื่องมืออื่น" });
  await expect(next.getByRole("link", { name: /รูปภาพ → PDF/ })).toBeVisible();
  await expect(next.getByRole("link", { name: /ลดขนาด PDF/ })).toHaveCount(0);
  await expect(next.getByRole("link", { name: /สแกน \/ OCR/ })).toHaveCount(0);
});

test("P7C.3 expired outputs never receive a chaining link", async ({ page }) => {
  await page.route("**/api/v1/jobs/job-expired-chain", (route) => route.fulfill({ json: {
    id: "job-expired-chain", operation: "compress", status: "completed", progress: 100,
    input_file_ids: [initialFile.id], output_file_id: "file-chain-expired",
    params: {}, error: null, requested_by: "web-console:smoke-test",
  }}));
  await page.route("**/api/v1/files/file-chain-expired", (route) => route.fulfill({ json: {
    ...initialFile, id: "file-chain-expired", expires_at: "2020-01-01T00:00:00Z",
  }}));
  await page.goto("/jobs/job-expired-chain/result");
  await expect(page.getByText(/ไฟล์ผลลัพธ์หมดอายุแล้ว/)).toBeVisible();
  await expect(page.getByRole("region", { name: "ทำงานต่อด้วยเครื่องมืออื่น" })).toHaveCount(0);
});

test("P7D.1 My Jobs uses server-filtered owned history with status and pagination", async ({ page }) => {
  const allJobs = Array.from({ length: 22 }, (_, index) => ({
    id: `job-my-${String(index + 1).padStart(2, "0")}`,
    operation: "compress", status: index % 2 === 0 ? "completed" : "failed",
    progress: 100, input_file_ids: [initialFile.id],
    output_file_id: index % 2 === 0 ? "file-output-1" : null,
    params: {}, error: null, requested_by: "web-console:smoke-test",
  }));
  const queries: URL[] = [];
  await page.route("**/api/v1/jobs?limit=21&mine=true**", async (route) => {
    const url = new URL(route.request().url());
    queries.push(url);
    const status = url.searchParams.get("status");
    const filtered = allJobs.filter((job) => !status || job.status === status);
    const offset = Number(url.searchParams.get("offset") || 0);
    await route.fulfill({ json: filtered.slice(offset, offset + 21) });
  });

  await page.goto("/jobs");
  await expect(page.getByRole("heading", { name: "งานของฉัน" })).toBeVisible();
  await expect(page.locator(".v3JobsHistoryRow")).toHaveCount(20);
  await expect(page.getByRole("navigation", { name: "หน้าประวัติงาน" }).getByRole("button", { name: "ถัดไป →" })).toBeEnabled();
  await page.getByRole("navigation", { name: "หน้าประวัติงาน" }).getByRole("button", { name: "ถัดไป →" }).click();
  await expect(page.locator(".v3JobsHistoryRow")).toHaveCount(2);
  await expect(page.getByText("หน้า 2")).toBeVisible();
  await page.getByLabel("กรองสถานะงาน").selectOption("failed");
  await expect(page.locator(".v3JobsHistoryRow")).toHaveCount(11);
  expect(queries.every((url) => url.searchParams.get("mine") === "true")).toBe(true);
  expect(queries.some((url) => url.searchParams.get("status") === "failed")).toBe(true);
  await page.getByRole("link", { name: "ดูสถานะ →" }).first().click();
  await expect(page).toHaveURL(/\/jobs\/job-my-/);
});

test("P7D.1 My Jobs also requests mine=true for wildcard Admin identity", async ({ page }) => {
  await page.route("**/api/v1/auth/me", (route) => route.fulfill({ json: operatorIdentityFixture({
    name: "user:admin", display_name: "Administrator",
    roles: ["admin"], scopes: ["*"], is_admin: true,
  }) }));
  const requests: string[] = [];
  await page.route("**/api/v1/jobs?**", async (route) => {
    requests.push(route.request().url());
    await route.fulfill({ json: [] });
  });
  await page.goto("/jobs");
  await expect(page.getByRole("heading", { name: "งานของฉัน" })).toBeVisible();
  await expect(page.getByText("ไม่พบงานในสถานะนี้")).toBeVisible();
  expect(requests.length).toBeGreaterThan(0);
  expect(requests.every((url) => new URL(url).searchParams.get("mine") === "true")).toBe(true);
});

test("P7D.2 library opens a durable owner-checked file route, reloads and chooses a compatible tool", async ({ page }) => {
  await page.route("**/api/v1/files/file-pdf-1", (route) => route.fulfill({ json: initialFile }));
  await page.goto("/files");
  await page.locator(".v3LibraryRow .v3FileOpen").filter({ hasText: "example.pdf" }).click();
  await expect(page).toHaveURL(/\/files\/file-pdf-1$/);
  await expect(page.getByRole("main", { name: "รายละเอียดไฟล์ของฉัน" })).toContainText("example.pdf");
  await page.reload();
  await expect(page.getByRole("region", { name: "เครื่องมือสำหรับไฟล์นี้" })).toBeVisible();
  await page.getByRole("region", { name: "เครื่องมือสำหรับไฟล์นี้" }).getByRole("link", { name: /ลดขนาด PDF/ }).click();
  await expect(page).toHaveURL(/\/tools\/compress\?file=file-pdf-1$/);
  await expect(page.locator("#workspace-target")).toContainText("example.pdf");
});

test("P7D.2 deep link recovers an owned file beyond the bounded workspace list", async ({ page }) => {
  const file = { ...initialFile, id: "file-deep-recovery", original_name: "deep-link.pdf" };
  await page.route("**/api/v1/files?limit=200&offset=0", (route) => route.fulfill({ json: [] }));
  await page.route("**/api/v1/files/file-deep-recovery", (route) => route.fulfill({ json: file }));
  await page.goto("/tools/compress?file=file-deep-recovery");
  await expect(page.locator("#workspace-target")).toContainText("deep-link.pdf");
  await expect(page.getByRole("button", { name: "บีบอัด PDF" })).toBeEnabled();
  await page.reload();
  await expect(page.locator("#workspace-target")).toContainText("deep-link.pdf");
});

test("P7D.2 missing, denied and expired files never offer a tool action", async ({ page }) => {
  await page.route("**/api/v1/files/file-denied-detail", (route) => route.fulfill({
    status: 403, json: { detail: "private storage path" },
  }));
  await page.goto("/files/file-denied-detail");
  await expect(page.getByRole("main", { name: "รายละเอียดไฟล์ของฉัน" }).getByRole("alert")).toContainText("ไม่มีสิทธิ์");
  await expect(page.getByRole("main")).not.toContainText("private storage path");
  await expect(page.getByRole("region", { name: "เครื่องมือสำหรับไฟล์นี้" })).toHaveCount(0);

  await page.route("**/api/v1/files/file-missing-detail", (route) => route.fulfill({
    status: 404, json: { detail: "File not found" },
  }));
  await page.goto("/files/file-missing-detail");
  await expect(page.getByRole("main").getByRole("alert")).toContainText("ไม่พบไฟล์");

  const expired = { ...initialFile, id: "file-expired-detail", expires_at: "2020-01-01T00:00:00Z" };
  await page.route("**/api/v1/files/file-expired-detail", (route) => route.fulfill({ json: expired }));
  await page.goto("/files/file-expired-detail");
  await expect(page.getByRole("main", { name: "รายละเอียดไฟล์ของฉัน" })).toContainText("ไฟล์หมดอายุแล้ว");
  await expect(page.getByRole("region", { name: "เครื่องมือสำหรับไฟล์นี้" })).toHaveCount(0);

  await page.route("**/api/v1/files?limit=200&offset=0", (route) => route.fulfill({ json: [expired] }));
  await page.goto("/tools/compress?file=file-expired-detail");
  await expect(page.getByRole("main", { name: "รายละเอียดไฟล์ของฉัน" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: /ตั้งค่าและดำเนินการ/ })).toBeDisabled();
});

test("P7E.1 Admin navigation isolates six purpose-specific areas with stable deep links", async ({ page }) => {
  await page.goto("/admin");
  const nav = page.getByRole("navigation", { name: "เมนูผู้ดูแลระบบ" });
  await expect(nav.getByRole("link")).toHaveCount(6);
  await expect(nav.getByRole("link", { name: /ภาพรวม/ })).toHaveAttribute("aria-current", "page");
  await expect(page.locator(".v3AdminOverview")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Service Keys และ Policies" })).toHaveCount(0);

  await nav.getByRole("link", { name: /งานประมวลผล/ }).click();
  await expect(page).toHaveURL(/\/admin\?section=jobs$/);
  await expect(page.getByRole("region", { name: "ข้อมูลคิวงานของระบบ" })).toContainText("คิวและงานประมวลผล");
  await expect(page.getByRole("heading", { name: "สร้าง Service Key" })).toHaveCount(0);
  await page.reload();
  await expect(page.getByRole("navigation", { name: "เมนูผู้ดูแลระบบ" }).getByRole("link", { name: /งานประมวลผล/ })).toHaveAttribute("aria-current", "page");

  await page.getByRole("navigation", { name: "เมนูผู้ดูแลระบบ" }).getByRole("link", { name: /สิทธิ์เข้าถึง/ }).click();
  await expect(page.locator(".v3EffectiveAccess")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Service Keys และ Policies" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Webhook Delivery / DLQ" })).toHaveCount(0);

  await page.goto("/admin?section=storage");
  await expect(page.getByRole("region", { name: "สถานะพื้นที่จัดเก็บ" })).toContainText("Retention");
  await expect(page.getByRole("button", { name: "Reconcile" })).toHaveCount(0);

  await page.goto("/admin?section=diagnostics");
  await expect(page.locator(".v3Diagnostics")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Audit Trail" })).toBeVisible();

  await page.goto("/admin?section=integrations");
  await expect(page.getByRole("heading", { name: "Webhook Delivery / DLQ" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "สร้าง Service Key" })).toHaveCount(0);

  await page.goto("/admin?section=unknown");
  await expect(page.getByRole("navigation", { name: "เมนูผู้ดูแลระบบ" }).getByRole("link", { name: /ภาพรวม/ })).toHaveAttribute("aria-current", "page");
});

test("P7E.1 non-admin principal cannot see Admin areas or privileged panels", async ({ page }) => {
  await page.route("**/api/v1/auth/me", (route) => route.fulfill({
    json: operatorIdentityFixture({ name: "user:viewer", roles: ["viewer"], scopes: ["files:read", "jobs:read"], is_admin: false }),
  }));
  await page.goto("/admin?section=access");
  await expect(page.getByText("บัญชีนี้ไม่มีสิทธิ์ผู้ดูแล")).toBeVisible();
  await expect(page.getByRole("navigation", { name: "เมนูผู้ดูแลระบบ" })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "สร้าง Service Key" })).toHaveCount(0);
});

test("P7E.2 Admin Overview identifies actionable failures and links to responsible areas", async ({ page }) => {
  let healthy = false;
  await page.route("**/api/v1/admin/status", (route) => route.fulfill({ json: {
    database_ok: healthy, redis_ok: healthy, workers: healthy ? 2 : 0, queue_depth: 4,
    storage_backend: "local", storage_write_ok: healthy, gotenberg_ok: healthy,
    data_dir: "/data", disk: { total: 1024 * 1024 * 1024, used: 100, free: 1024 * 1024 },
    pdfhub_bytes: 2048, files: 3,
    jobs: { queued: 4, running: 0, completed: 2, failed: 0, cancelled: 0 },
    retention_hours: 24, cleanup_temporary_hours: 6,
    clamav_enabled: true, paperless_enabled: false,
    tools: { qpdf: healthy, gs: true },
    auth: { local_admin: false, oidc: true, ldap: false, web_console_auto_login: false },
    principal: "user:admin@example.org",
  } }));
  await page.goto("/admin?section=overview");
  const issues = page.getByRole("region", { name: "รายการตรวจสอบที่ควรดำเนินการ" });
  await expect(issues).toContainText("Database ตอบสนองผิดปกติ");
  await expect(issues).toContainText("Redis / คิวงานไม่พร้อม");
  await expect(issues).toContainText("Storage เขียนข้อมูลไม่ได้");
  await expect(issues).toContainText("มีงานรอแต่ไม่มี Worker");
  await expect(issues).toContainText("เครื่องมือประมวลผลไม่พร้อม");
  await expect(issues.getByRole("link", { name: "ไปตรวจสอบ →" })).toHaveCount(5);
  healthy = true;
  await page.getByRole("button", { name: "ตรวจสถานะใหม่" }).click();
  await expect(issues).toContainText("ไม่พบความผิดปกติจากข้อมูลสถานะที่ระบบตรวจสอบได้");
  await expect(issues.getByRole("link", { name: "ไปตรวจสอบ →" })).toHaveCount(0);
});

test("P7E.2 failed Admin status read offers safe retry instead of perpetual loading", async ({ page }) => {
  let calls = 0;
  await page.route("**/api/v1/admin/status", (route) => {
    calls += 1;
    if (calls === 1) return route.fulfill({ status: 503, json: { detail: "internal DB hostname" } });
    return route.fulfill({ json: {
      database_ok: true, redis_ok: true, workers: 1, queue_depth: 0,
      storage_backend: "local", storage_write_ok: true, gotenberg_ok: true, data_dir: "/data",
      disk: { total: 1000000, used: 10, free: 999990 },
      pdfhub_bytes: 2048, files: 1, jobs: { queued: 0, running: 0, completed: 0, failed: 0, cancelled: 0 },
      retention_hours: 24, cleanup_temporary_hours: 6, clamav_enabled: true, paperless_enabled: false,
      tools: { qpdf: true }, auth: {}, principal: "user:admin@example.org",
    } });
  });
  await page.goto("/admin?section=overview");
  const overviewAlert = page.locator(".v3AdminOverviewScreen [role='alert']");
  await expect(overviewAlert).toContainText("อ่านสถานะระบบไม่ได้");
  await expect(page.getByRole("main")).not.toContainText("internal DB hostname");
  await page.getByRole("button", { name: "ตรวจสถานะใหม่" }).click();
  await expect(page.locator(".v3AdminOverview")).toBeVisible();
  await expect(overviewAlert).toHaveCount(0);
});

test("P7F.1 Admin triage is read-only, paginated, scoped to safe fields and server-filtered", async ({ page }) => {
  const jobs = Array.from({ length: 27 }, (_, idx) => ({
    id: `triage-${String(idx).padStart(2, "0")}`,
    operation: idx % 2 ? "ocr" : "compress",
    status: idx % 2 ? "running" : "failed",
    progress: idx,
    created_at: "2026-10-09T07:00:00Z",
    started_at: null, finished_at: null,
    failure_recorded: idx % 2 === 0,
  }));
  const readUrls: URL[] = [];
  await page.route("**/api/v1/admin/jobs/triage?**", async (route) => {
    const url = new URL(route.request().url());
    readUrls.push(url);
    const filtered = jobs.filter((j) =>
      (!url.searchParams.has("status") || j.status === url.searchParams.get("status"))
      && (!url.searchParams.has("operation") || j.operation === url.searchParams.get("operation"))
    );
    const offset = Number(url.searchParams.get("offset") || 0);
    const limit = Number(url.searchParams.get("limit") || 25);
    await route.fulfill({ json: {
      items: filtered.slice(offset, offset + limit), limit, offset,
      has_more: filtered.length > offset + limit,
    } });
  });

  await page.goto("/admin?section=jobs");
  const section = page.getByRole("region", { name: "รายการงานสำหรับวิเคราะห์ปัญหา" });
  await expect(section).toBeVisible();
  await expect(section.locator(".v3AdminTriageRow")).toHaveCount(25);
  await expect(section).not.toContainText("secret-file-id");
  await expect(section).not.toContainText("user:alice");
  await expect(section.getByRole("button", { name: /Retry|Cancel|Repair/ })).toHaveCount(0);
  await section.getByRole("navigation", { name: "หน้ารายการงานระดับผู้ดูแล" }).getByRole("button", { name: "ถัดไป →" }).click();
  await expect(section.locator(".v3AdminTriageRow")).toHaveCount(2);
  await section.getByLabel("กรองสถานะงานของระบบ").selectOption("failed");
  await expect(section.locator(".v3AdminTriageRow")).toHaveCount(14);
  await section.getByLabel("กรองประเภทงาน").fill("compress");
  await section.getByRole("button", { name: "ใช้ตัวกรอง" }).click();
  await expect(section.locator(".v3AdminTriageRow")).toHaveCount(14);
  expect(readUrls.some((url) => url.searchParams.get("status") === "failed")).toBe(true);
  expect(readUrls.some((url) => url.searchParams.get("operation") === "compress")).toBe(true);
  expect(readUrls.every((url) => url.searchParams.get("limit") === "25")).toBe(true);
  expect(readUrls.every((url) => !url.searchParams.has("mine"))).toBe(true);
});

test("P7F.1 triage denial and audit failure never reveal raw response or enable actions", async ({ page }) => {
  await page.route("**/api/v1/admin/jobs/triage?**", async (route) => route.fulfill({
    status: 503, json: { detail: "secret audit file path" },
  }));
  await page.goto("/admin?section=jobs");
  const section = page.getByRole("region", { name: "รายการงานสำหรับวิเคราะห์ปัญหา" });
  await expect(section.getByRole("alert")).toContainText("ไม่สามารถอ่านรายการงาน");
  await expect(section).not.toContainText("secret audit file path");
  await expect(section.getByRole("button", { name: /Retry|Cancel|Repair/ })).toHaveCount(0);

  await page.route("**/api/v1/auth/me", async (route) => route.fulfill({
    json: operatorIdentityFixture({
      name: "user:viewer", roles: ["viewer"], scopes: ["jobs:read"], is_admin: false,
    }),
  }));
  await page.goto("/admin?section=jobs");
  await expect(page.getByRole("navigation", { name: "เมนูผู้ดูแลระบบ" })).toHaveCount(0);
  await expect(page.getByRole("region", { name: "รายการงานสำหรับวิเคราะห์ปัญหา" })).toHaveCount(0);
});

test("P7F.2 job cancellation requires confirmation and declines without API mutation", async ({ page }) => {
  let calls = 0;
  await page.route("**/api/v1/jobs/job-confirm-cancel", (route) => route.fulfill({ json: {
    id: "job-confirm-cancel", operation: "compress", status: calls ? "cancelled" : "queued", progress: 0,
    input_file_ids: ["file-pdf-1"], output_file_id: null, params: {},
    error: null, requested_by: "web-console:smoke-test",
  } }));
  await page.route("**/api/v1/jobs/job-confirm-cancel/cancel", (route) => {
    calls += 1;
    return route.fulfill({ json: {
      id: "job-confirm-cancel", operation: "compress", status: "cancelled", progress: 100,
      input_file_ids: ["file-pdf-1"], output_file_id: null, params: {},
      error: null, requested_by: "web-console:smoke-test",
    } });
  });

  await page.goto("/jobs/job-confirm-cancel");
  await expect(page.getByRole("button", { name: "ยกเลิกงาน" })).toBeVisible();
  page.once("dialog", (dialog) => void dialog.dismiss());
  await page.getByRole("button", { name: "ยกเลิกงาน" }).click();
  expect(calls).toBe(0);
  page.once("dialog", (dialog) => void dialog.accept());
  await page.getByRole("button", { name: "ยกเลิกงาน" }).click();
  await expect(page.getByRole("main")).toContainText("ยกเลิกงานแล้ว");
  expect(calls).toBe(1);
});

test("P7G.1 Admin Access shows effective role, scopes and quotas without credentials", async ({ page }) => {
  await page.route("**/api/v1/auth/me", (route) => route.fulfill({ json: {
    name: "user:admin@example.org", display_name: "RCAT Administrator", subject: "institution-admin",
    groups: ["pdfhub-admins"], roles: ["admin"], scopes: ["*"], auth_source: "oidc",
    is_admin: true, rate_limit_per_minute: 120, daily_job_limit: 500,
    max_storage_mb: 2048, quota_exempt: false,
  }}));
  await page.goto("/admin?section=access");
  const region = page.getByRole("region", { name: "โควตาที่มีผลจริง" });
  await expect(region).toContainText("120");
  await expect(region).toContainText("500");
  await expect(region).toContainText("2,048");
  await expect(page.locator(".v3EffectiveScopes")).toContainText("*");
  await expect(page.locator(".v3EffectiveAccess")).toContainText("admin");
  await expect(page.locator(".v3EffectiveAccess")).not.toContainText("password");
  await expect(page.locator(".v3EffectiveAccess")).not.toContainText("api_key");
});

test("P7G.1 bootstrap exemption is explicitly distinguished from a zero-valued limit", async ({ page }) => {
  await page.route("**/api/v1/auth/me", (route) => route.fulfill({ json: {
    name: "bootstrap-admin", display_name: "Bootstrap Admin", subject: null,
    groups: [], roles: ["admin"], scopes: ["*"], auth_source: "bootstrap",
    is_admin: true, rate_limit_per_minute: 0, daily_job_limit: 0,
    max_storage_mb: 0, quota_exempt: true,
  }}));
  await page.goto("/admin?section=access");
  const region = page.getByRole("region", { name: "โควตาที่มีผลจริง" });
  await expect(region.getByText("ไม่จำกัด")).toHaveCount(3);
  await expect(region).toContainText("ยกเว้นข้อจำกัดสำหรับ Bootstrap");
});

test("P7G.2 Storage health is manually initiated and never displays paths or file identities", async ({ page }) => {
  let scans = 0;
  await page.route("**/api/v1/admin/storage/health", async (route) => {
    scans += 1;
    await route.fulfill({ json: {
      dry_run: true, backend: "local", database_records: 12, storage_objects: 11,
      issue_count: 4, healthy: false,
      category_counts: { missing_object: 3, orphan_object: 1 },
      // Response must never include object paths. The API type excludes them.
    } });
  });
  await page.goto("/admin?section=storage");
  const section = page.getByRole("region", { name: "ตรวจสอบความสอดคล้องของ Storage" });
  await expect(section).toBeVisible();
  expect(scans).toBe(0);
  await section.getByRole("button", { name: "ตรวจสอบความสอดคล้อง" }).click();
  await expect(section).toContainText("พบรายการผิดปกติ 4 รายการ");
  await expect(section).toContainText("ไฟล์ใน Metadata");
  await expect(section).toContainText("มี Metadata แต่หาไฟล์ไม่พบ");
  await expect(section).toContainText("3");
  expect(scans).toBe(1);
  await expect(section).not.toContainText("/data/");
  await expect(section).not.toContainText("stored_name");
  await expect(section.getByRole("button", { name: /Repair|Delete|Fix/ })).toHaveCount(0);
});

test("P7G.2 Storage health denial and audit outages are presented without raw internals", async ({ page }) => {
  await page.route("**/api/v1/admin/storage/health", async (route) => {
    await route.fulfill({ status: 503, json: { detail: "sensitive audit path /data/private" } });
  });
  await page.goto("/admin?section=storage");
  const section = page.getByRole("region", { name: "ตรวจสอบความสอดคล้องของ Storage" });
  await section.getByRole("button", { name: "ตรวจสอบความสอดคล้อง" }).click();
  await expect(section.getByRole("alert")).toContainText("ตรวจสอบ Storage ไม่สำเร็จ");
  await expect(section).not.toContainText("/data/private");
});

test("P7G.2 revoking a service key requires explicit confirmation", async ({ page }) => {
  let active = true;
  let revocations = 0;
  const record = () => ({
    id: "service-key-1", name: "lab-service",
    scopes: ["files:read"], active,
    policy: { service_name: "lab-service", rate_limit_per_minute: 10,
      daily_job_limit: 20, max_storage_mb: 300, webhook_url: null },
  });
  await page.route("**/api/v1/admin/api-keys", (route) => route.fulfill({ json: [record()] }));
  await page.route("**/api/v1/admin/audit?limit=100", (route) => route.fulfill({ json: [] }));
  await page.route("**/api/v1/admin/webhook-deliveries?limit=100", (route) => route.fulfill({ json: [] }));
  await page.route("**/api/v1/admin/api-keys/service-key-1", (route) => {
    revocations += 1;
    active = false;
    return route.fulfill({ json: record() });
  });
  await page.goto("/admin?section=access");
  await page.getByRole("button", { name: "โหลดข้อมูล Admin" }).click();
  await expect(page.getByText("lab-service", { exact: true })).toBeVisible();
  page.once("dialog", (dialog) => void dialog.dismiss());
  await page.getByRole("button", { name: "Revoke" }).click();
  expect(revocations).toBe(0);
  page.once("dialog", (dialog) => void dialog.accept());
  await page.getByRole("button", { name: "Revoke" }).click();
  await expect(page.getByText("REVOKED", { exact: true })).toBeVisible();
  expect(revocations).toBe(1);
});

test("P7G.2 webhook replay requires consent and never displays raw delivery error", async ({ page }) => {
  let replays = 0;
  let state = "dead";
  const delivery = () => ({
    id: "delivery-integration-1", job_id: "job-private-1",
    service_name: "lab-service", event: "job.completed",
    status: state, attempt_count: 3, max_attempts: 5,
    last_status_code: 503, last_error: "secret /data/storage/private-key",
    updated_at: "2026-10-09T07:00:00Z",
  });
  await page.route("**/api/v1/admin/api-keys", (route) => route.fulfill({ json: [] }));
  await page.route("**/api/v1/admin/audit?limit=100", (route) => route.fulfill({ json: [] }));
  await page.route("**/api/v1/admin/webhook-deliveries?limit=100", (route) => route.fulfill({ json: [delivery()] }));
  await page.route("**/api/v1/admin/webhook-deliveries/delivery-integration-1/retry", (route) => {
    replays += 1;
    state = "queued";
    return route.fulfill({ json: delivery() });
  });
  await page.goto("/admin?section=integrations");
  await page.getByRole("button", { name: "โหลดข้อมูล Admin" }).click();
  await expect(page.getByRole("button", { name: "Replay" })).toBeVisible();
  await expect(page.getByRole("main")).not.toContainText("secret /data/storage/private-key");
  page.once("dialog", (dialog) => void dialog.dismiss());
  await page.getByRole("button", { name: "Replay" }).click();
  expect(replays).toBe(0);
  page.once("dialog", (dialog) => void dialog.accept());
  await page.getByRole("button", { name: "Replay" }).click();
  await expect(page.getByText("QUEUED", { exact: true })).toBeVisible();
  expect(replays).toBe(1);
});

test("P7G.2 updating a service policy is not submitted before confirmation", async ({ page }) => {
  let updates = 0;
  let perMinute = 10;
  const record = () => ({
    id: "service-key-2", name: "quota-service", active: true,
    scopes: ["files:read"],
    policy: { service_name: "quota-service", rate_limit_per_minute: perMinute,
      daily_job_limit: 20, max_storage_mb: 300, webhook_url: null },
  });
  await page.route("**/api/v1/admin/api-keys", (route) => route.fulfill({ json: [record()] }));
  await page.route("**/api/v1/admin/audit?limit=100", (route) => route.fulfill({ json: [] }));
  await page.route("**/api/v1/admin/webhook-deliveries?limit=100", (route) => route.fulfill({ json: [] }));
  await page.route("**/api/v1/admin/service-policies/quota-service", (route) => {
    updates += 1;
    perMinute = 50;
    return route.fulfill({ json: record().policy });
  });
  await page.goto("/admin?section=access");
  await page.getByRole("button", { name: "โหลดข้อมูล Admin" }).click();
  await page.getByRole("button", { name: "Policy" }).click();
  await page.getByRole("main").getByLabel("Requests/min").fill("50");
  page.once("dialog", (dialog) => void dialog.dismiss());
  await page.getByRole("button", { name: "บันทึก Policy" }).click();
  expect(updates).toBe(0);
  page.once("dialog", (dialog) => void dialog.accept());
  await page.getByRole("button", { name: "บันทึก Policy" }).click();
  await expect(page.getByRole("main")).toContainText("บันทึก policy ของ quota-service แล้ว");
  expect(updates).toBe(1);
});
