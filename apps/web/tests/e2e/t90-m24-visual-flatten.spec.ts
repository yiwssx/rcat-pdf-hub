import { expect, test, type Page } from "@playwright/test";

const enabled = process.env.PDFHUB_STAGED_M24_FLATTEN_WEB_ENABLED === "true"
  && process.env.PDFHUB_PDF_FLATTEN_VISUAL_TOOLS_ENABLED === "true";
const owner = "user:rcat-m24";
const file = {
  id: "m24-owner", original_name: "รายงาน.pdf", content_type: "application/pdf",
  size: 1024, sha256: "a".repeat(64), source_system: owner,
  created_at: "2026-11-09T00:00:00Z", expires_at: null,
};

async function mocks(page: Page, allow = true) {
  await page.route("**/api/v1/auth/me", (route) => route.fulfill({ json: {
    name: owner, display_name: "Test", subject: "test:m24",
    scopes: allow ? ["files:read", "jobs:read", "pdf:convert"] : ["jobs:read"],
    groups: [], roles: ["operator"], auth_source: "session", is_admin: false,
  } }));
  await page.route("**/api/v1/files?limit=200&offset=0", (route) => route.fulfill({ json: [
    file,
    { ...file, id: "foreign", source_system: "user:other" },
    { ...file, id: "expired", expires_at: "2020-01-01T00:00:00Z" },
  ] }));
  await page.route("**/api/v1/files/m24-owner/pages", (route) => route.fulfill({ json: {
    file_id: file.id, pages: 2,
  } }));
}

test("M24 visual flatten route defaults to 404", async ({ page }) => {
  test.skip(enabled, "Default-OFF test");
  expect((await page.goto("/staged/flatten"))?.status()).toBe(404);
});

test("M24 visual flatten submits only a chosen owned PDF", async ({ page }) => {
  test.skip(!enabled, "Dev-only flag pair required");
  await mocks(page);
  const payloads: unknown[] = [];
  await page.route("**/api/v1/pdf/advanced/flatten-visual", async (route) => {
    payloads.push(route.request().postDataJSON());
    await route.fulfill({ status: 202, json: {
      id: "m24-job", operation: "flatten-pdf-visual", status: "queued", progress: 0,
      input_file_ids: [file.id], output_file_id: null, params: {},
      error: null, requested_by: owner,
    } });
  });
  await page.goto("/staged/flatten?file=foreign");
  await expect(page.getByLabel("PDF ที่เป็นของบัญชีนี้").locator("option")).toHaveCount(1);
  await page.getByRole("button", { name: "สร้าง PDF แบบภาพ" }).click();
  await expect(page.getByText("รหัสงาน: m24-job")).toBeVisible();
  expect(payloads).toEqual([{ file_id: file.id }]);
});

test("M24 lacking files:read cannot list or submit owned PDF", async ({ page }) => {
  test.skip(!enabled, "Dev-only flag pair required");
  await mocks(page, false);
  let calls = 0;
  await page.route("**/api/v1/files**", (route) => { calls++; return route.abort(); });
  await page.goto("/staged/flatten");
  await expect(page.getByRole("alert")).toContainText("files:read");
  expect(calls).toBe(0);
});
