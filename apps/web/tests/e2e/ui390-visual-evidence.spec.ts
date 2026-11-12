import { expect, test, type Page } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
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
  const captureRoot = resolve("test-results/ui390", variant);
  mkdirSync(captureRoot, { recursive: true });
  const results: Array<{ viewport: string; view: string; pathname: string; overflow: number }> = [];
  for (const [name, width, height] of [["desktop", 1366, 768], ["mobile", 390, 844]] as const) {
    await page.setViewportSize({ width, height });
    for (const [view, target, selector] of [
      ["dashboard-directory", "/", "#workspace"],
      ["files", "/files", ".v3FileLibrary"],
      ["jobs", "/jobs", ".v3JobsHistory"],
      ["admin", "/admin?section=overview", ".v3AdminMain"],
    ] as const) {
      await page.goto(target, { waitUntil: "domcontentloaded" });
      await expect(page.locator(selector)).toBeVisible({ timeout: 15000 });
      await page.evaluate(() => document.fonts.ready);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      // The baseline may have visual defects. Capture them; new candidate must not.
      if (variant === "after") expect(overflow, `${name}/${view} horizontal overflow`).toBeLessThanOrEqual(1);
      await page.screenshot({ path: resolve(captureRoot, `${name}-${view}.png`), fullPage: true, animations: "disabled" });
      results.push({ viewport: name, view, pathname: target, overflow });
      if (view === "dashboard-directory") {
        const recent = page.locator(".v3RecentFile").first();
        await expect(recent).toBeVisible();
        await recent.click();
        await expect(page.locator(".v3DocumentMode")).toBeVisible();
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
