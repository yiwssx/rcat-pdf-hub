import { expect, test, type Page } from "@playwright/test";

const owner = "user:rcat-manage";
const sample = {
  id: "manage-owner-file", original_name: "รายงาน.pdf",
  content_type: "application/pdf", size: 2400, sha256: "c".repeat(64),
  source_system: owner, created_at: "2026-11-09T00:00:00Z", expires_at: null,
};
const webEnabled = process.env.PDFHUB_STAGED_MANAGE_WEB_ENABLED === "true";
const enabled = (tool: string): boolean => {
  const env = process.env;
  const byTool: Record<string, string[]> = {
    M14: ["PDFHUB_MANAGE_PAGE_TOOLS_ENABLED"],
    M15: ["PDFHUB_MANAGE_PAGE_TOOLS_ENABLED"],
    M16: ["PDFHUB_EXTRACT_PAGES_TOOLS_ENABLED"],
    M18: ["PDFHUB_EXTRACT_EMBEDDED_IMAGES_TOOLS_ENABLED"],
    M22: ["PDFHUB_PDF_TEXT_OVERLAY_TOOLS_ENABLED"],
    M30: ["PDFHUB_GRAYSCALE_PDF_TOOLS_ENABLED"],
    M31: ["PDFHUB_HEADER_FOOTER_TOOLS_ENABLED"],
    M33: ["PDFHUB_PDF_FILLER_TOOLS_ENABLED"],
  };
  return webEnabled && (byTool[tool] ?? []).every((key) => env[key] === "true");
};

async function mocks(page: Page, scopes = [
  "files:read", "jobs:read", "pdf:split", "pdf:extract-images", "pdf:stamp",
  "pdf:grayscale", "pdf:header-footer", "pdf:convert",
]) {
  await page.route("**/api/v1/auth/me", (route) => route.fulfill({ json: {
    name: owner, display_name: "Test", subject: "test:manage",
    scopes, groups: [], roles: ["operator"], auth_source: "session", is_admin: false,
  } }));
  await page.route("**/api/v1/files?limit=200&offset=0", (route) => route.fulfill({ json: [
    sample,
    { ...sample, id: "foreign", source_system: "user:other" },
    { ...sample, id: "expired", expires_at: "2020-01-01T00:00:00Z" },
  ] }));
  await page.route("**/api/v1/files/manage-owner-file/pages", (route) =>
    route.fulfill({ json: { file_id: sample.id, pages: 3 } }));
}

test("Manage staging page is absent in the default-OFF Web build", async ({ page }) => {
  test.skip(webEnabled, "Default-OFF route test");
  const res = await page.goto("/staged/manage?tool=M14");
  expect(res?.status()).toBe(404);
});

test("M14/M15 create independent typed jobs in one reused Web form", async ({ page }) => {
  test.skip(!enabled("M14") || !enabled("M15"), "Dev-only Manage pages flags required");
  await mocks(page);
  const payloads: Array<{ path: string; body: unknown }> = [];
  await page.route("**/api/v1/pdf/manage-pages/*", async (route) => {
    payloads.push({ path: route.request().url(), body: route.request().postDataJSON() });
    await route.fulfill({ status: 202, json: {
      id: String(payloads.length), operation: "pages", status: "queued", progress: 0,
      input_file_ids: [sample.id], output_file_id: null, params: {},
      error: null, requested_by: owner,
    } });
  });
  await page.goto("/staged/manage?tool=M14");
  await page.getByLabel("รายการหมายเลขหน้า").fill("2");
  await page.getByRole("button", { name: "เริ่มดำเนินการ" }).click();
  await expect(page.getByText("รหัสงาน: 1")).toBeVisible();
  await page.getByLabel("เครื่องมือ Manage PDF").selectOption("M15");
  await page.getByLabel("รายการหมายเลขหน้า").fill("3,1,2");
  await page.getByRole("button", { name: "เริ่มดำเนินการ" }).click();
  await expect(page.getByText("รหัสงาน: 2")).toBeVisible();
  expect(payloads[0].body).toEqual({ file_id: sample.id, pages: [2] });
  expect(payloads[1].body).toEqual({ file_id: sample.id, order: [3, 1, 2] });
});

test("Manage tools never list files without files:read scope", async ({ page }) => {
  test.skip(!webEnabled, "Dev-only Web gate required");
  await mocks(page, ["jobs:read"]);
  let calls = 0;
  await page.route("**/api/v1/files**", (route) => { calls++; return route.abort(); });
  await page.goto("/staged/manage");
  await expect(page.getByRole("alert")).toContainText("files:read");
  expect(calls).toBe(0);
});
