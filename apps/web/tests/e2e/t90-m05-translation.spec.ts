import { expect, test, type Page } from "@playwright/test";

const enabled = process.env.PDFHUB_STAGED_TRANSLATION_WEB_ENABLED === "true"
  && process.env.PDFHUB_PDF_TRANSLATION_TOOLS_ENABLED === "true";
const owner = "user:rcat-translate";
const pdf = {
  id: "m05-pdf", original_name: "source.pdf", content_type: "application/pdf",
  size: 1200, sha256: "a".repeat(64), source_system: owner,
  created_at: "2026-11-09T00:00:00Z", expires_at: null,
};

async function mock(page: Page, granted = true) {
  await page.route("**/api/v1/auth/me", (route) => route.fulfill({ json: {
    name: owner, display_name: "Operator", subject: "translate:test",
    scopes: granted ? ["files:read", "jobs:read", "pdf:extract-text"] : ["files:read"],
    roles: ["operator"], groups: [], is_admin: false, auth_source: "session",
  } }));
  await page.route("**/api/v1/files?limit=200&offset=0", (route) => route.fulfill({ json: [
    pdf, { ...pdf, id: "foreign", source_system: "user:other" },
    { ...pdf, id: "expired", expires_at: "2020-01-01T00:00:00Z" },
  ] }));
}

test("M05 translation is not visible in unchanged R1", async ({ page }) => {
  test.skip(enabled, "Only default R1");
  expect((await page.goto("/staged/translate"))?.status()).toBe(404);
});

test("M05 owner-isolated PDF creates typed language-pair job", async ({ page }) => {
  test.skip(!enabled, "Only reviewed dev-only flags");
  await mock(page);
  const submissions: unknown[] = [];
  await page.route("**/api/v1/pdf/translation/text", async (route) => {
    submissions.push(route.request().postDataJSON());
    await route.fulfill({ status: 202, json: {
      id: "m05-job", operation: "translate-pdf-text", status: "queued",
      progress: 0, input_file_ids: [pdf.id], output_file_id: null,
      params: {}, error: null, requested_by: owner,
    } });
  });
  await page.goto("/staged/translate?file=foreign");
  await expect(page.getByLabel("PDF ของฉัน").locator("option")).toHaveCount(1);
  await page.getByLabel("รูปแบบผลลัพธ์").selectOption("text");
  await page.getByRole("button", { name: "แปลข้อความ PDF ภายในระบบ" }).click();
  await expect(page.getByText("รหัสงาน: m05-job")).toBeVisible();
  expect(submissions).toEqual([{ file_id: pdf.id, source_language: "en", target_language: "th" }]);
});

test("M05 rejects submission without extraction permission", async ({ page }) => {
  test.skip(!enabled, "Only reviewed dev-only flags");
  await mock(page, false);
  await page.goto("/staged/translate");
  await expect(page.getByRole("alert")).toContainText("ต้องมีสิทธิ์");
  await expect(page.getByRole("button", { name: "แปลข้อความ PDF ภายในระบบ" })).toBeDisabled();
});
