import { expect, test, type Page } from "@playwright/test";

const owner = "user:rcat-access";
const base = {
  size: 1200, sha256: "a".repeat(64),
  source_system: owner, created_at: "2026-11-09T00:00:00Z", expires_at: null,
  content_type: "application/pdf",
};
const pdf = { ...base, id: "own-pdf", original_name: "รายงาน.pdf" };
const stageEnabled = process.env.PDFHUB_STAGED_PDF_ACCESS_WEB_ENABLED === "true";
const unlock = process.env.PDFHUB_UNLOCK_PDF_TOOLS_ENABLED === "true";
const protect = process.env.PDFHUB_PROTECT_PDF_TOOLS_ENABLED === "true";

async function mock(page: Page, scope = true) {
  await page.route("**/api/v1/auth/me", (route) => route.fulfill({ json: {
    name: owner, display_name: "Operator", subject: "test:owner",
    scopes: ["files:read", "jobs:read", ...(scope ? ["pdf:unlock", "pdf:protect"] : [])],
    roles: ["operator"], groups: [], is_admin: false, auth_source: "session",
  } }));
  await page.route("**/api/v1/files?limit=200&offset=0", (route) => route.fulfill({ json: [
    pdf, { ...pdf, id: "foreign", source_system: "user:other" },
    { ...pdf, id: "expired", expires_at: "2020-01-01T00:00:00Z" },
  ] }));
}

test("M08/M09 password Web stage is absent in unchanged R1", async ({ page }) => {
  test.skip(stageEnabled && (unlock || protect), "Dev-only stage explicitly enabled");
  const response = await page.goto("/staged/pdf-access");
  expect(response?.status()).toBe(404);
});

test("M08 owner-only source and transient password submission", async ({ page }) => {
  test.skip(!(stageEnabled && unlock), "Requires explicit dev-only M08+Web flags");
  await mock(page);
  const inputs: unknown[] = [];
  await page.route("**/api/v1/pdf/unlock-pdf", async (route) => {
    inputs.push(route.request().postDataJSON());
    await route.fulfill({ status: 202, json: {
      id: "m08-job", operation: "unlock-pdf", status: "queued",
      progress: 0, input_file_ids: [pdf.id], output_file_id: null,
      params: {}, error: null, requested_by: owner,
    } });
  });
  await page.goto("/staged/pdf-access?file=foreign&tool=unlock-pdf");
  await expect(page.getByLabel("PDF ของฉัน").locator("option")).toHaveCount(1);
  await page.getByLabel("รหัสผ่าน PDF ที่ต้องการปลดล็อก").fill("secret-cannot-be-logged");
  await page.getByRole("button", { name: "ปลดล็อก PDF" }).click();
  await expect(page.getByText("รหัสงาน: m08-job")).toBeVisible();
  await expect(page.getByLabel("รหัสผ่าน PDF ที่ต้องการปลดล็อก")).toHaveValue("");
  await expect(page.getByText("secret-cannot-be-logged")).toHaveCount(0);
  expect(inputs).toEqual([{ file_id: pdf.id, password: "secret-cannot-be-logged" }]);
});

test("M09 requires different confirmed passwords and never includes them in job details", async ({ page }) => {
  test.skip(!(stageEnabled && protect), "Requires explicit dev-only M09+Web flags");
  await mock(page);
  await page.route("**/api/v1/pdf/protect-pdf", (route) => route.fulfill({ status: 202, json: {
    id: "m09-job", operation: "protect-pdf", status: "queued",
    progress: 0, input_file_ids: [pdf.id], output_file_id: null,
    params: {}, error: null, requested_by: owner,
  } }));
  await page.goto("/staged/pdf-access?tool=protect-pdf");
  await page.getByLabel("รหัสผ่านเปิด PDF", { exact: true }).fill("user-pass-abc");
  await page.getByLabel("ยืนยันรหัสผ่านเปิด PDF").fill("user-pass-abc");
  await page.getByLabel("รหัสผ่านเจ้าของ PDF", { exact: true }).fill("owner-pass-xyz");
  await page.getByLabel("ยืนยันรหัสผ่านเจ้าของ PDF").fill("owner-pass-xyz");
  await page.getByRole("button", { name: "เข้ารหัส PDF" }).click();
  await expect(page.getByText("รหัสงาน: m09-job")).toBeVisible();
  await expect(page.getByLabel("รหัสผ่านเปิด PDF", { exact: true })).toHaveValue("");
  await expect(page.getByLabel("รหัสผ่านเจ้าของ PDF", { exact: true })).toHaveValue("");
});

test("M08/M09 missing scoped permissions cannot submit", async ({ page }) => {
  test.skip(!(stageEnabled && (unlock || protect)), "Requires dev-only Web stage");
  await mock(page, false);
  await page.goto("/staged/pdf-access");
  await expect(page.getByRole("alert")).toContainText("ไม่มีสิทธิ์");
  await expect(page.getByRole("button", { name: /PDF/ }).last()).toBeDisabled();
});
