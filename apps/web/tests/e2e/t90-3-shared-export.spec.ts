import { expect, test, type Page } from "@playwright/test";

const owner = "user:from-pdf-stage-owner";
const pdf = {
  id: "owned-pdf-1", original_name: "รายงาน.pdf", content_type: "application/pdf",
  size: 4096, sha256: "a".repeat(64), source_system: owner,
  created_at: "2026-11-09T00:00:00Z", expires_at: null,
};

async function mockAccount(page: Page, grants: string[] = ["pdf:pdf-to-image"]) {
  await page.route("**/api/v1/auth/me", (route) => route.fulfill({
    json: {
      name: owner, display_name: "RCAT Export Tester", subject: "rcat:test-export",
      scopes: ["files:read", "files:write", "jobs:read", ...grants],
      groups: [], roles: ["operator"], auth_source: "session", is_admin: false,
    },
  }));
  await page.route("**/api/v1/files?limit=200&offset=0", (route) => route.fulfill({
    json: [
      pdf,
      { ...pdf, id: "another-owner", source_system: "user:other", original_name: "secret.pdf" },
      { ...pdf, id: "bad-mime", content_type: "image/png" },
      { ...pdf, id: "expired", expires_at: "2020-01-01T00:00:00Z" },
    ],
  }));
}

const stageEnabled = process.env.PDFHUB_STAGED_FROM_PDF_WEB_ENABLED === "true"
  && process.env.PDFHUB_FROM_PDF_TOOLS_ENABLED === "true";

test("From-PDF stage URL defaults to 404 on unchanged Production build", async ({ page }) => {
  test.skip(stageEnabled, "Only default-off configurations are checked");
  const response = await page.goto("/staged/exports?tool=F07");
  expect(response?.status()).toBe(404);
});

test("shared export selects own PDFs and requests a genuine bounded XLSX job", async ({ page }) => {
  test.skip(!stageEnabled, "Requires explicitly gated development server");
  await mockAccount(page);
  const payloads: Array<Record<string, unknown>> = [];
  await page.route("**/api/v1/pdf/from-pdf/excel", async (route) => {
    payloads.push(route.request().postDataJSON());
    await route.fulfill({ status: 202, json: {
      id: "export-xlsx-1", operation: "pdf-to-excel", status: "queued",
      progress: 0, input_file_ids: [pdf.id], output_file_id: null,
      params: {}, error: null, requested_by: owner,
    } });
  });
  await page.goto("/staged/exports?tool=F07&file=another-owner");
  await expect(page.getByRole("heading", { name: "แปลง PDF เป็นไฟล์อื่น" })).toBeVisible();
  await expect(page.getByLabel("รูปแบบไฟล์ผลลัพธ์")).toHaveValue("F07");
  await expect(page.getByLabel("รูปแบบไฟล์ผลลัพธ์").locator('option[value="F15"]')).toHaveCount(0);
  await expect(page.getByLabel("ไฟล์ PDF ของบัญชีนี้").locator("option")).toHaveCount(2);
  await page.getByLabel("ไฟล์ PDF ของบัญชีนี้").selectOption(pdf.id);
  await page.getByRole("button", { name: "แปลง PDF" }).click();
  await expect(page.getByText("รหัสงาน: export-xlsx-1")).toBeVisible();
  await expect(page.getByRole("link", { name: "ดูผลลัพธ์และดาวน์โหลด" }))
    .toHaveAttribute("href", "/jobs/export-xlsx-1/result");
  expect(payloads).toEqual([{ file_id: pdf.id }]);
});

test("OCR requires dedicated scope even when other exports are available", async ({ page }) => {
  test.skip(!stageEnabled, "Requires explicitly gated development server");
  await mockAccount(page);
  const called: string[] = [];
  await page.route("**/api/v1/pdf/from-pdf/**", (route) => {
    called.push(route.request().url());
    return route.abort();
  });
  await page.goto("/staged/exports?tool=F01");
  await expect(page.getByRole("alert")).toContainText("pdf:ocr");
  await expect(page.getByRole("button", { name: "แปลง PDF" })).toBeDisabled();
  expect(called).toEqual([]);
});
