import { expect, test, type Page } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { T90_DIRECTORY_TOOLS } from "../../app/components/t90-directory-catalog";
import { hasDedicatedT90Icon } from "../../app/components/v4-tool-icons";
import { authConfigFixture, emptyLibraryPage, integrationStatusFixture, operatorIdentityFixture } from "./api-fixtures";

/**
 * Evidence capture only: the real Next.js rendered UI and Chromium screenshots.
 * APIs are deterministic mocks, not a claim of authenticated Production UAT.
 * Run the SAME test against separately built baseline and candidate commits.
 */
const exampleFile = {
  id: "visual-example-pdf",
  original_name: "RCAT-document.pdf",
  content_type: "application/pdf",
  size: 189440,
  sha256: "a".repeat(64),
  source_system: "ui390-evidence",
  created_at: "2026-11-12T00:00:00Z",
  expires_at: null,
};

async function installEvidenceFixtures(page: Page) {
  await page.route("**/api/v1/auth/config", route => route.fulfill({ json: { ...authConfigFixture, institutional: { rcat_only: true } } }));
  await page.route("**/api/v1/auth/me", route => route.fulfill({ json: operatorIdentityFixture({
    name: "ui390-evidence", display_name: "RCAT Visual Review",
    subject: "ui390-evidence", is_admin: true, roles: ["admin"], scopes: ["*"],
  }) }));
  await page.route("**/api/v1/integrations/status", route => route.fulfill({ json: integrationStatusFixture }));
  await page.route("**/api/v1/files?**", route => route.fulfill({ json: [exampleFile] }));
  await page.route("**/api/v1/files/library**", route => route.fulfill({ json: { ...emptyLibraryPage(route.request().url()), items: [exampleFile], total: 1 } }));
  await page.route("**/api/v1/jobs?**", route => route.fulfill({ json: [] }));
  await page.route("**/api/v1/files/visual-example-pdf", route => route.fulfill({ json: exampleFile }));
  await page.route("**/api/v1/files/visual-example-pdf/preview**", route => route.fulfill({ status: 200, contentType: "image/png", body: Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=", "base64") }));
  await page.route("**/api/v1/admin/status", route => route.fulfill({ json: {
    database_ok: true, redis_ok: true, workers: 2, queue_depth: 1,
    storage_backend: "local", storage_write_ok: true, gotenberg_ok: true,
    data_dir: "/data", disk: { total: 1073741824, used: 3000, free: 536870912 },
    pdfhub_bytes: 2048, files: 2,
    jobs: { queued: 1, running: 0, completed: 2, failed: 0, cancelled: 0 },
    retention_hours: 24, cleanup_temporary_hours: 6, clamav_enabled: true,
    paperless_enabled: false, tools: { qpdf: true, gs: true, ocrmypdf: true, tesseract: true, pdftoppm: true },
    auth: { local_admin: true, oidc: true, ldap: false, web_console_auto_login: false },
    principal: "ui390-evidence",
  } }));
  await page.route("**/api/v1/admin/jobs/triage?**", route => route.fulfill({ json: { items: [], limit: 25, offset: 0, has_more: false } }));
  await page.route("**/api/v1/admin/storage/health", route => route.fulfill({ json: {
    dry_run: true, backend: "local", database_records: 2, storage_objects: 2,
    issue_count: 0, healthy: true, category_counts: {},
  } }));
}

test("VD2: capture comparable before/after real Chromium screenshots for the major views", async ({ page }) => {
  test.setTimeout(180_000);
  const variant = process.env.PDFHUB_VISUAL_VARIANT;
  if (variant !== "before" && variant !== "after") {
    test.skip(true, "Screenshot evidence is only enabled for explicit baseline/candidate comparisons");
    return;
  }
  await installEvidenceFixtures(page);
  const captureRoot = resolve("visual-evidence/ui390", variant);
  mkdirSync(captureRoot, { recursive: true });
  const results: Array<{ viewport: string; view: string; pathname: string; overflow: number }> = [];
  for (const [name, width, height] of [["desktop", 1366, 768], ["tablet", 768, 1024], ["mobile", 390, 844]] as const) {
    await page.setViewportSize({ width, height });
    for (const [view, target, selector] of [
      ["dashboard-directory", "/", "#workspace"],
      ["tools-explorer", variant === "before" ? "/" : "/tools", variant === "before" ? "#t90-tools" : ".v4Explorer"],
      ["files", "/files", ".v3FileLibrary"],
      ["jobs", "/jobs", ".v3JobsHistory"],
      ["admin", "/admin?section=overview", ".v3AdminMain"],
    ] as const) {
      await page.goto(target, { waitUntil: "domcontentloaded" });
      await expect(page.locator(selector)).toBeVisible({ timeout: 15000 });
      // Snapshot only settled UI state, not a transient fetch/loading frame.
      if (view === "tools-explorer" && variant === "before") {
        await page.locator("#t90-tools").scrollIntoViewIfNeeded();
      }
      if (view === "tools-explorer" && variant === "after") {
        await expect(page.getByRole("navigation", { name: "ประเภทเครื่องมือ PDF" })).toBeVisible();
        await expect(page.locator(".v4ToolListItem")).toHaveCount(12);
      }
      if (view === "files") {
        const fileRow = page.locator(".v3LibraryRow").first();
        await expect(fileRow.getByText("RCAT-document.pdf", { exact: true })).toBeVisible({ timeout: 15000 });
        // Full-page screenshots do not always paint offscreen content-visibility:auto rows.
        // Confirm the row works when scrolled into view, then force painting for evidence only.
        await fileRow.scrollIntoViewIfNeeded();
        await expect(fileRow).toBeVisible();
        await page.addStyleTag({ content: ".v3LibraryRow { content-visibility: visible !important; }" });
        await page.evaluate(() => window.scrollTo(0, 0));
      }
      if (view === "jobs") {
        await expect(page.getByText("ไม่พบงานในสถานะนี้")).toBeVisible({ timeout: 15000 });
      }
      if (view === "admin") {
        await expect(page.getByRole("navigation", { name: "เมนูผู้ดูแลระบบ" })).toBeVisible();
        await expect(page.locator(".v3EffectiveAccess")).toBeVisible();
      }
      await page.evaluate(() => document.fonts.ready);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      // The baseline may have visual defects. Capture them; new candidate must not.
      if (variant === "after") expect(overflow, `${name}/${view} horizontal overflow`).toBeLessThanOrEqual(1);
      await page.screenshot({ path: resolve(captureRoot, `${name}-${view}.png`), fullPage: true, animations: "disabled" });
      results.push({ viewport: name, view, pathname: target, overflow });
      if (view === "files") {
        await page.goto("/files/visual-example-pdf");
        await expect(page.getByRole("heading", { name: "รายละเอียดไฟล์" })).toBeVisible();
        if (variant === "after") {
          await page.getByRole("button", { name: "ดูตัวอย่าง PDF" }).click();
          const preview = page.getByRole("img", { name: "ตัวอย่างหน้าแรกของ RCAT-document.pdf" });
          await expect(preview).toBeVisible();
          await expect.poll(() => preview.evaluate(element => (element as HTMLImageElement).naturalWidth)).toBeGreaterThan(0);
        }
        const fileDetailOverflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
        if (variant === "after") expect(fileDetailOverflow, `${name}/file-detail overflow`).toBeLessThanOrEqual(1);
        await page.screenshot({ path: resolve(captureRoot, `${name}-file-detail.png`), fullPage: true, animations: "disabled" });
        results.push({ viewport: name, view: "file-detail", pathname: "/files/visual-example-pdf", overflow: fileDetailOverflow });
      }
      if (view === "dashboard-directory") {
        const recent = page.locator(".v3RecentFile").first();
        await expect(recent).toBeVisible();
        await recent.click();
        await expect(page.locator(".v3DocumentMode")).toBeVisible();
        if (variant === "after") await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(0);
        // Compare the same document origin, not the prior dashboard scroll position.
        await page.evaluate(() => window.scrollTo(0, 0));
        const workbenchOverflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
        if (variant === "after") expect(workbenchOverflow, `${name}/workspace overflow`).toBeLessThanOrEqual(1);
        await page.screenshot({ path: resolve(captureRoot, `${name}-workspace.png`), fullPage: true, animations: "disabled" });
        results.push({ viewport: name, view: "workspace", pathname: "/", overflow: workbenchOverflow });
      }
    }
  }
  writeFileSync(resolve(captureRoot, "manifest.json"), JSON.stringify({
    variant, source: process.env.PDFHUB_VISUAL_SOURCE_SHA || "unknown",
    browser: "playwright-chromium", data: "deterministic API fixtures (not Production UAT)",
    screenshots: results,
  }, null, 2));
});


test("V4 critical journeys: tool search, semantic icons, deep links, navigation and responsive shell", async ({ page }) => {
  test.setTimeout(120_000);
  test.skip(process.env.PDFHUB_VISUAL_VARIANT !== "after", "V4 interactions only apply to candidate");
  await installEvidenceFixtures(page);
  expect(T90_DIRECTORY_TOOLS).toHaveLength(90);
  expect(T90_DIRECTORY_TOOLS.every(item => hasDedicatedT90Icon(item.id))).toBe(true);
  for (const [name, width, height] of [["desktop", 1366, 768], ["tablet", 768, 1024], ["mobile", 390, 844]] as const) {
    await page.setViewportSize({ width, height });
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "งานเอกสาร ง่ายขึ้นในที่เดียว" })).toBeVisible();
    const nav = width <= 760
      ? page.getByRole("navigation", { name: "เมนูหลักบนมือถือ" })
      : page.getByRole("navigation", { name: "เมนูหลัก" });
    await expect(nav).toBeVisible();
    await nav.getByRole("link", { name: /เครื่องมือ/ }).click();
    await expect(page).toHaveURL(/\/tools$/);
    await expect(page.getByRole("heading", { name: "ค้นหาเครื่องมือ PDF" })).toBeVisible();
    const search = page.getByRole("searchbox", { name: "ค้นหาเครื่องมือ T90" });
    await search.fill("Merge PDF");
    const first = page.locator(".v4ToolListItem").first();
    await expect(first).toContainText("Merge PDF");
    await first.click();
    await expect(page).toHaveURL(/tool=M04/);
    await page.reload();
    await expect(page.getByRole("heading", { name: "Merge PDF" })).toBeVisible();
    await expect(page.locator(
      width <= 760 ? ".v4ToolDialog a[href='/tools/merge-pdf']" : ".v4ToolDetail a[href='/tools/merge-pdf']",
    )).toBeVisible();
    // Deep-link selection should survive refresh and follow browser history.
    await page.goBack();
    await expect(page).toHaveURL(/\/tools$/);
    await page.goForward();
    await expect(page).toHaveURL(/tool=M04/);
    if (width <= 760) {
      const detail = page.getByRole("dialog", { name: "รายละเอียดเครื่องมือที่เลือก" });
      await expect(detail).toBeVisible();
      await detail.getByRole("button", { name: "ปิดรายละเอียด" }).click();
      await expect(detail).not.toBeVisible();
    }
    await search.fill("");
    await page.getByRole("button", { name: /แปลงจาก PDF/ }).first().click();
    await expect(page.locator(".v4ToolListItem").first()).toContainText("PDF");
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow, `${name} V4 explorer overflow`).toBeLessThanOrEqual(1);

    // Management surfaces retain their actual actions, not just a visual skin.
    await page.goto("/files");
    await expect(page.getByRole("heading", { name: "ไฟล์ทั้งหมด" })).toBeVisible();
    await page.getByRole("button", { name: "ตาราง" }).click();
    await expect(page.locator(".v4FilesGrid")).toBeVisible();
    await page.getByRole("button", { name: "รายการ" }).click();
    await expect(page.locator(".v4FilesGrid")).toHaveCount(0);

    await page.goto("/jobs");
    await page.getByRole("button", { name: "สำเร็จ", exact: true }).click();
    await expect(page.getByLabel("กรองสถานะงาน")).toHaveValue("completed");

    await page.goto("/admin?section=overview");
    const adminNav = page.getByRole("navigation", { name: "เมนูผู้ดูแลระบบ" });
    await expect(adminNav).toBeVisible();
    await adminNav.getByRole("link", { name: /พื้นที่จัดเก็บ/ }).click();
    await expect(page.getByRole("heading", { name: "พื้นที่จัดเก็บและ Retention" })).toBeVisible();
  }
});
