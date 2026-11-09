import { expect, test, type Page } from "@playwright/test";

const enabled = process.env.PDFHUB_STAGED_MARKUP_WEB_ENABLED === "true"
  && process.env.PDFHUB_PDF_MARKUP_TOOLS_ENABLED === "true";
const owner = "user:rcat-markup";
const file = {
  id: "markup-owner", original_name: "รายงาน.pdf", content_type: "application/pdf",
  size: 1050, sha256: "a".repeat(64), source_system: owner,
  created_at: "2026-11-09T00:00:00Z", expires_at: null,
};

async function mock(page: Page, allowed = true) {
  await page.route("**/api/v1/auth/me", (route) => route.fulfill({ json: {
    name: owner, display_name: "Test", subject: "test:markup",
    scopes: allowed ? ["files:read", "jobs:read", "pdf:stamp"] : ["jobs:read"],
    groups: [], roles: ["operator"], auth_source: "session", is_admin: false,
  } }));
  await page.route("**/api/v1/files?limit=200&offset=0", (route) => route.fulfill({ json: [
    file, { ...file, id: "foreign", source_system: "other" },
    { ...file, id: "expired", expires_at: "2020-01-01T00:00:00Z" },
  ] }));
  await page.route("**/api/v1/files/markup-owner/pages", (route) =>
    route.fulfill({ json: { file_id: file.id, pages: 2 } }));
}

test("M25/M26/M29 shared markup route is 404 by default", async ({ page }) => {
  test.skip(enabled, "Default-OFF only");
  expect((await page.goto("/staged/markup?tool=M29"))?.status()).toBe(404);
});

test("M25/M26/M29 use exact authenticated typed markup payload", async ({ page }) => {
  test.skip(!enabled, "Dev-only two independent gates required");
  await mock(page);
  const submitted: unknown[] = [];
  await page.route("**/api/v1/pdf/advanced/markup", async (route) => {
    submitted.push(route.request().postDataJSON());
    await route.fulfill({ status: 202, json: {
      id: String(submitted.length), operation: "pdf-markup", status: "queued", progress: 0,
      input_file_ids: [file.id], output_file_id: null, params: {},
      error: null, requested_by: owner,
    } });
  });
  await page.goto("/staged/markup?tool=M25&file=foreign");
  await expect(page.getByLabel("PDF ต้นฉบับของฉัน").locator("option")).toHaveCount(1);
  await page.getByRole("button", { name: "เพิ่ม Annotation" }).click();
  await expect(page.getByText("รหัสงาน: 1")).toBeVisible();
  await page.getByLabel("เครื่องมือ PDF Markup").selectOption("M26");
  await page.getByRole("button", { name: "ไฮไลต์ PDF" }).click();
  await expect(page.getByText("รหัสงาน: 2")).toBeVisible();
  await page.getByLabel("เครื่องมือ PDF Markup").selectOption("M29");
  await page.getByRole("button", { name: "ปิดทับข้อความ/รูปภาพ" }).click();
  await expect(page.getByText("รหัสงาน: 3")).toBeVisible();
  expect(submitted).toEqual([
    { file_id: file.id, mode:"annotation", page:1, x:36, y:36, width:180, height:60, text:"Review note" },
    { file_id: file.id, mode:"highlight", page:1, x:36, y:36, width:180, height:60, text:"" },
    { file_id: file.id, mode:"whiteout", page:1, x:36, y:36, width:180, height:60, text:"" },
  ]);
});

test("Markup does not enumerate PDF files without files:read scope", async ({ page }) => {
  test.skip(!enabled, "Dev-only two independent gates required");
  await mock(page, false);
  let calls = 0;
  await page.route("**/api/v1/files**", (route) => { calls++; return route.abort(); });
  await page.goto("/staged/markup");
  await expect(page.getByRole("alert")).toContainText("files:read");
  expect(calls).toBe(0);
});
