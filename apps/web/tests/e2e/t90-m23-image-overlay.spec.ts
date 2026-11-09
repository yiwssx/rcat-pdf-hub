import { expect, test, type Page } from "@playwright/test";

const owner = "user:rcat-m23";
const base = {
  size: 1200, sha256: "a".repeat(64), source_system: owner,
  created_at: "2026-11-09T00:00:00Z", expires_at: null,
};
const pdf = { ...base, id: "m23-pdf", original_name: "รายงาน.pdf", content_type: "application/pdf" };
const image = { ...base, id: "m23-png", original_name: "รูปภาพ.png", content_type: "image/png" };
const enabled = process.env.PDFHUB_STAGED_IMAGE_OVERLAY_WEB_ENABLED === "true"
  && process.env.PDFHUB_PDF_IMAGE_OVERLAY_TOOLS_ENABLED === "true";

async function mocks(page: Page, scope = true) {
  await page.route("**/api/v1/auth/me", (route) => route.fulfill({ json: {
    name: owner, display_name: "Test", subject: "test:m23",
    scopes: ["files:read", "files:write", "jobs:read", ...(scope ? ["pdf:stamp"] : [])],
    groups: [], roles: ["operator"], auth_source: "session", is_admin: false,
  } }));
  await page.route("**/api/v1/files?limit=200&offset=0", (route) => route.fulfill({ json: [
    pdf, image,
    { ...image, id: "foreign", source_system: "user:foreign" },
    { ...pdf, id: "expired", expires_at: "2020-01-01T00:00:00Z" },
  ] }));
}

test("M23 route remains absent in default R1 Web build", async ({ page }) => {
  test.skip(enabled, "Default-off check only applies in unchanged deployments");
  const res = await page.goto("/staged/image-overlay");
  expect(res?.status()).toBe(404);
});

test("M23 stage submits exactly owned PDF, image and bounded geometry", async ({ page }) => {
  test.skip(!enabled, "Requires explicitly approved dev-only Web flags");
  await mocks(page);
  const submissions: unknown[] = [];
  await page.route("**/api/v1/pdf/advanced/add-image", async (route) => {
    submissions.push(route.request().postDataJSON());
    await route.fulfill({ status: 202, json: {
      id: "m23-job", operation: "add-pdf-image", status: "queued", progress: 0,
      input_file_ids: [pdf.id, image.id], output_file_id: null, params: {},
      error: null, requested_by: owner,
    } });
  });
  await page.goto("/staged/image-overlay?file=foreign");
  await expect(page.getByRole("heading", { name: "เพิ่มรูปภาพลงใน PDF" })).toBeVisible();
  await expect(page.getByLabel("PDF ต้นฉบับที่เป็นของบัญชีนี้").locator("option")).toHaveCount(2);
  await expect(page.getByLabel("ภาพ JPEG/PNG ของบัญชีนี้").locator("option")).toHaveCount(2);
  await page.getByLabel("PDF ต้นฉบับที่เป็นของบัญชีนี้").selectOption(pdf.id);
  await page.getByLabel("ภาพ JPEG/PNG ของบัญชีนี้").selectOption(image.id);
  await page.getByRole("button", { name: "เพิ่มรูปภาพลงใน PDF" }).click();
  await expect(page.getByText("รหัสงาน: m23-job")).toBeVisible();
  expect(submissions).toEqual([{
    file_id: pdf.id, image_file_id: image.id, page: 1,
    x: 30, y: 30, width: 120, height: 80,
  }]);
});

test("M23 missing stamp scope disables submission", async ({ page }) => {
  test.skip(!enabled, "Requires explicitly approved dev-only Web flags");
  await mocks(page, false);
  await page.goto("/staged/image-overlay");
  await expect(page.getByRole("alert")).toContainText("pdf:stamp");
  await expect(page.getByRole("button", { name: "เพิ่มรูปภาพลงใน PDF" })).toBeDisabled();
});
