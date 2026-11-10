import { expect, test, type Page } from "@playwright/test";

const enabled = process.env.PDFHUB_STAGED_PDF_EDIT_WEB_ENABLED === "true"
  && process.env.PDFHUB_PDF_EDIT_TEXT_TOOLS_ENABLED === "true";
const owner = "user:m01-editor";
const original = {
  id: "m01-pdf", original_name: "source.pdf",
  content_type: "application/pdf", size: 1800, sha256: "a".repeat(64),
  source_system: owner, created_at: "2026-11-10T00:00:00Z", expires_at: null,
};

async function mock(page: Page, allowed = true) {
  await page.route("**/api/v1/auth/me", (route) => route.fulfill({ json: {
    name: owner, display_name: "Operator", subject: "m01:test",
    scopes: allowed ? ["files:read", "jobs:read", "pdf:stamp"] : ["files:read"],
    groups: [], roles: ["operator"], auth_source: "session", is_admin: false,
  } }));
  await page.route("**/api/v1/files?limit=200&offset=0", (route) => route.fulfill({ json: [
    original, { ...original, id: "foreign", source_system: "user:other" },
    { ...original, id: "expired", expires_at: "2020-01-01T00:00:00Z" },
  ] }));
}

test("M01 is unavailable in unchanged default-OFF R1 build", async ({ page }) => {
  test.skip(enabled, "Only applies to default-OFF R1 deployment");
  const response = await page.goto("/staged/edit-text?file=foreign");
  expect(response?.status()).toBe(404);
});

test("M01 only accepts one owned PDF and valid same-length ASCII", async ({ page }) => {
  test.skip(!enabled, "Requires dev-only independent Web and backend flags");
  await mock(page);
  const submissions: unknown[] = [];
  await page.route("**/api/v1/pdf/advanced/edit-existing-text", (route) => {
    submissions.push(route.request().postDataJSON());
    return route.fulfill({ status: 202, json: {
      id: "m01-job", operation: "edit-existing-pdf-text", status: "queued",
      progress: 0, input_file_ids: [original.id], output_file_id: null,
      params: {}, error: null, requested_by: owner,
    } });
  });
  await page.goto("/staged/edit-text?file=foreign");
  await expect(page.getByRole("heading", { name: "แก้ไขข้อความเดิมใน PDF" })).toBeVisible();
  await expect(page.getByLabel("PDF ของฉัน").locator("option")).toHaveCount(1);
  const action = page.getByRole("button", { name: "แก้ไขข้อความเดิมใน PDF" });
  await page.getByLabel("ข้อความเดิมที่ต้องการแก้ไข").fill("ORIGINAL");
  await page.getByLabel("ข้อความใหม่ (จำนวนตัวอักษรเท่ากัน)").fill("SHORT");
  await expect(action).toBeDisabled();
  await page.getByLabel("ข้อความใหม่ (จำนวนตัวอักษรเท่ากัน)").fill("MODIFIED");
  await page.getByLabel("หน้า PDF").fill("1");
  await expect(action).toBeEnabled();
  await action.click();
  await expect(page.getByText("รหัสงาน: m01-job")).toBeVisible();
  expect(submissions).toEqual([{
    file_id: original.id, page: 1, old_text: "ORIGINAL", new_text: "MODIFIED",
  }]);
});

test("M01 missing pdf:stamp permission denies operation", async ({ page }) => {
  test.skip(!enabled, "Requires dev-only independent Web and backend flags");
  await mock(page, false);
  await page.goto("/staged/edit-text");
  await page.getByLabel("ข้อความเดิมที่ต้องการแก้ไข").fill("ORIGINAL");
  await page.getByLabel("ข้อความใหม่ (จำนวนตัวอักษรเท่ากัน)").fill("MODIFIED");
  await expect(page.getByRole("alert")).toContainText("pdf:stamp");
  await expect(page.getByRole("button", { name: "แก้ไขข้อความเดิมใน PDF" })).toBeDisabled();
});


test("M01 staged UI accepts bounded Thai base consonants without enabling Production", async ({ page }) => {
  test.skip(!enabled, "Requires independent dev-only Web and backend flags");
  await mock(page);
  let submitted: unknown = null;
  await page.route("**/api/v1/pdf/advanced/edit-existing-text", async (route) => {
    submitted = route.request().postDataJSON();
    await route.fulfill({ status: 202, json: {
      id: "m01-thai-job", operation: "edit-existing-pdf-text", status: "queued",
      progress: 0, input_file_ids: [original.id], output_file_id: null,
      params: {}, error: null, requested_by: owner,
    } });
  });
  await page.goto("/staged/edit-text");
  const action = page.getByRole("button", { name: "แก้ไขข้อความเดิมใน PDF" });
  await page.getByLabel("ข้อความเดิมที่ต้องการแก้ไข").fill("กขค");
  await page.getByLabel("ข้อความใหม่ (จำนวนตัวอักษรเท่ากัน)").fill("คขก");
  await expect(action).toBeEnabled();
  await action.click();
  await expect(page.getByText("รหัสงาน: m01-thai-job")).toBeVisible();
  expect(submitted).toEqual({
    file_id: original.id, page: 1, old_text: "กขค", new_text: "คขก",
  });
  await page.getByLabel("ข้อความใหม่ (จำนวนตัวอักษรเท่ากัน)").fill("คัข");
  await expect(action).toBeDisabled();
});
