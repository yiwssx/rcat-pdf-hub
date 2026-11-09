import { expect, test, type Page } from "@playwright/test";

const owner = "user:rcat-m07";
const base = {
  original_name: "รายงาน.pdf", content_type: "application/pdf",
  size: 2048, sha256: "b".repeat(64), source_system: owner,
  created_at: "2026-11-09T00:00:00Z", expires_at: null,
};
const pdf = { ...base, id: "m07-pdf" };
const enabled = process.env.PDFHUB_STAGED_SPLIT_ZIP_WEB_ENABLED === "true"
  && process.env.PDFHUB_SPLIT_ZIP_TOOLS_ENABLED === "true"
  && process.env.PDFHUB_MULTI_OUTPUT_ARTIFACTS_ENABLED === "true";

async function mockOwner(page: Page, splitScope = true) {
  await page.route("**/api/v1/auth/me", (route) => route.fulfill({ json: {
    name: owner, display_name: "Test", subject: "test:m07",
    scopes: ["files:read", "jobs:read", ...(splitScope ? ["pdf:split"] : [])],
    groups: [], roles: ["operator"], auth_source: "session", is_admin: false,
  } }));
  await page.route("**/api/v1/files?limit=200&offset=0", (route) => route.fulfill({ json: [
    pdf, { ...pdf, id: "foreign", source_system: "user:foreign" },
    { ...pdf, id: "expired", expires_at: "2020-01-01T00:00:00Z" },
  ] }));
  await page.route("**/api/v1/files/m07-pdf/pages", (route) => route.fulfill({
    json: { file_id: pdf.id, pages: 5 },
  }));
}

test("M07 split ZIP staging is 404 by default", async ({ page }) => {
  test.skip(enabled, "Default-OFF build only");
  const res = await page.goto("/staged/split-zip");
  expect(res?.status()).toBe(404);
});

test("M07 submits a bounded owner-selected range to the existing split ZIP route", async ({ page }) => {
  test.skip(!enabled, "Requires separately authorized development-only flags");
  await mockOwner(page);
  const payloads: unknown[] = [];
  await page.route("**/api/v1/pdf/split-to-zip", async (route) => {
    payloads.push(route.request().postDataJSON());
    await route.fulfill({ status: 202, json: {
      id: "m07-job", operation: "split-to-zip", status: "queued", progress: 0,
      input_file_ids: [pdf.id], output_file_id: null, params: {},
      error: null, requested_by: owner,
    } });
  });
  await page.goto("/staged/split-zip?file=foreign");
  await expect(page.getByRole("heading", { name: "แยกหน้า PDF เป็น ZIP" })).toBeVisible();
  await expect(page.locator("#m07-file option")).toHaveCount(1);
  await expect(page.getByText("จำนวนหน้า: 5 หน้า")).toBeVisible();
  await page.getByLabel("หน้าที่จะแยก").fill("1,3-5");
  await page.getByRole("button", { name: "แยก PDF เป็น ZIP" }).click();
  await expect(page.getByText("รหัสงาน: m07-job")).toBeVisible();
  expect(payloads).toEqual([{ file_id: pdf.id, pages: "1,3-5" }]);
});

test("M07 does not submit without pdf:split scope", async ({ page }) => {
  test.skip(!enabled, "Requires separately authorized development-only flags");
  await mockOwner(page, false);
  await page.goto("/staged/split-zip");
  await expect(page.getByRole("alert")).toContainText("pdf:split");
  await expect(page.getByRole("button", { name: "แยก PDF เป็น ZIP" })).toBeDisabled();
});
