import { expect, test, type Page } from "@playwright/test";

const enabled = process.env.PDFHUB_STAGED_DOCUMENT_ASSIST_WEB_ENABLED === "true"
  && process.env.PDFHUB_PDF_EXTRACTIVE_ASSIST_TOOLS_ENABLED === "true";
const owner = "user:rcat-assist";
const base = {
  size: 1400, sha256: "a".repeat(64),
  source_system: owner, created_at: "2026-11-09T00:00:00Z",
  expires_at: null, content_type: "application/pdf",
};
const pdf = { ...base, id: "assist-pdf", original_name: "report.pdf" };

async function mock(page: Page, granted = true) {
  await page.route("**/api/v1/auth/me", (route) => route.fulfill({ json: {
    name: owner, display_name: "Operator", subject: "assist:test",
    scopes: granted ? ["files:read", "jobs:read", "pdf:extract-text"] : ["files:read"],
    roles: ["operator"], groups: [], is_admin: false, auth_source: "session",
  } }));
  await page.route("**/api/v1/files?limit=200&offset=0", (route) => route.fulfill({ json: [
    pdf, { ...pdf, id: "foreign", source_system: "user:other" },
    { ...pdf, id: "expired", expires_at: "2020-01-01T00:00:00Z" },
  ] }));
}

test("M03/M06 route returns 404 in default flag-OFF R1", async ({ page }) => {
  test.skip(enabled, "Only unchanged R1 build");
  const response = await page.goto("/staged/document-assist");
  expect(response?.status()).toBe(404);
});

test("M03/M06 owner-scoped PDF and typed question routes", async ({ page }) => {
  test.skip(!enabled, "Requires reviewed dev-only flags");
  await mock(page);
  const calls: { url: string; payload: unknown }[] = [];
  await page.route("**/api/v1/pdf/document-assist/*", async (route) => {
    calls.push({ url: route.request().url(), payload: route.request().postDataJSON() });
    await route.fulfill({ status: 202, json: {
      id: "assist-job", operation: "pdf-extractive-summary", status: "queued",
      progress: 0, input_file_ids: [pdf.id], output_file_id: null,
      params: {}, error: null, requested_by: owner,
    } });
  });
  await page.goto("/staged/document-assist?file=foreign");
  await expect(page.getByLabel("PDF ของฉัน").locator("option")).toHaveCount(1);
  await page.getByRole("button", { name: "สร้างสรุปจากต้นฉบับ" }).click();
  await expect(page.getByText("รหัสงาน: assist-job")).toBeVisible();
  await page.getByLabel("ค้นหลักฐานตามคำถาม (M06)").check();
  await page.getByLabel(/คำถามหรือข้อความที่ต้องการค้นหา/).fill("dissolved oxygen");
  await page.getByRole("button", { name: "ค้นหลักฐานใน PDF" }).click();
  expect(calls).toEqual([
    { url: expect.stringContaining("/document-assist/summary"), payload: { file_id: pdf.id } },
    { url: expect.stringContaining("/document-assist/evidence"), payload: { file_id: pdf.id, question: "dissolved oxygen" } },
  ]);
});

test("M03/M06 missing text scope rejects submission", async ({ page }) => {
  test.skip(!enabled, "Requires reviewed dev-only flags");
  await mock(page, false);
  await page.goto("/staged/document-assist");
  await expect(page.getByRole("alert")).toContainText("ไม่มีสิทธิ์");
  await expect(page.getByRole("button", { name: "สร้างสรุปจากต้นฉบับ" })).toBeDisabled();
});


test("M06 can ask again with explicit prior-question context and retains bounded result links", async ({ page }) => {
  test.skip(!enabled, "Requires reviewed dev-only M06 flags");
  await mock(page);
  const requests: unknown[] = [];
  await page.route("**/api/v1/pdf/document-assist/evidence", async (route) => {
    requests.push(route.request().postDataJSON());
    await route.fulfill({ status: 202, json: {
      id: "m06-turn-" + requests.length,
      operation: "pdf-extractive-evidence", status: "queued",
      progress: 0, input_file_ids: [pdf.id], output_file_id: null,
      params: {}, error: null, requested_by: owner,
    } });
  });
  await page.goto("/staged/document-assist?tool=evidence");
  const input = page.getByLabel(/คำถามหรือข้อความที่ต้องการค้นหา/);
  const submit = page.getByRole("button", { name: "ค้นหลักฐานใน PDF" });
  await input.fill("dissolved oxygen");
  await submit.click();
  await expect(page.getByRole("region", { name: "ประวัติคำถามใน PDF นี้" })
    .getByRole("link", { name: "ดูหลักฐานที่อ้างเลขหน้า" })).toHaveCount(1);
  await expect(page.getByLabel(/ใช้คำถามก่อนหน้าเป็นบริบทช่วยค้นหา/)).toBeChecked();

  await input.fill("water temperature");
  await submit.click();
  await expect(page.getByRole("region", { name: "ประวัติคำถามใน PDF นี้" })
    .getByRole("link", { name: "ดูหลักฐานที่อ้างเลขหน้า" })).toHaveCount(2);
  expect(requests).toEqual([
    { file_id: pdf.id, question: "dissolved oxygen" },
    { file_id: pdf.id, question: "water temperature", previous_question: "dissolved oxygen" },
  ]);
  await page.getByLabel(/ใช้คำถามก่อนหน้าเป็นบริบทช่วยค้นหา/).uncheck();
  await input.fill("school reports");
  await submit.click();
  expect(requests[2]).toEqual({ file_id: pdf.id, question: "school reports" });
  await expect(page.getByRole("region", { name: "ประวัติคำถามใน PDF นี้" })
    .getByRole("link", { name: "ดูหลักฐานที่อ้างเลขหน้า" })).toHaveCount(3);
  await page.getByRole("button", { name: "ล้างประวัติคำถามในหน้านี้" }).click();
  await expect(page.getByRole("region", { name: "ประวัติคำถามใน PDF นี้" })).toHaveCount(0);
});
