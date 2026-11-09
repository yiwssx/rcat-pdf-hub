import { expect, test, type Page } from "@playwright/test";

const owner = "user:to-pdf-stage-owner";
const txt = {
  id: "text-file-1", original_name: "ตัวอย่าง.txt", content_type: "text/plain",
  size: 120, sha256: "a".repeat(64), source_system: owner,
  created_at: "2026-11-09T00:00:00Z", expires_at: null,
};

async function mockSession(page: Page, scope = true) {
  await page.route("**/api/v1/auth/me", (route) => route.fulfill({
    json: {
      name: owner, display_name: "RCAT Converter Tester",
      subject: "rcat:test", scopes: scope
        ? ["files:read", "files:write", "jobs:read", "pdf:convert"]
        : ["files:read", "files:write", "jobs:read"],
      groups: [], roles: ["operator"], auth_source: "session", is_admin: false,
    },
  }));
  await page.route("**/api/v1/files?limit=200&offset=0", (route) => route.fulfill({
    json: [
      txt,
      { ...txt, id: "foreign", source_system: "user:other", original_name: "foreign.txt" },
      { ...txt, id: "mime-wrong", content_type: "image/jpeg" },
      { ...txt, id: "expired", expires_at: "2020-01-01T00:00:00Z" },
    ],
  }));
}

test("shared T90-2 converter is not published on default R1 server", async ({ page }) => {
  test.skip(
    process.env.PDFHUB_STAGED_TO_PDF_WEB_ENABLED === "true" &&
      process.env.PDFHUB_TO_PDF_TOOLS_ENABLED === "true",
    "Default-off check applies only to ordinary deployments",
  );
  const result = await page.goto("/staged/converters?tool=T14");
  expect(result?.status()).toBe(404);
});

test("one T90-2 stage handles typed upload source, scoped enqueue and result", async ({ page }) => {
  test.skip(
    process.env.PDFHUB_STAGED_TO_PDF_WEB_ENABLED !== "true" ||
      process.env.PDFHUB_TO_PDF_TOOLS_ENABLED !== "true",
    "Runs only in an explicitly gated development Web server",
  );
  await mockSession(page);
  const submitted: Array<Record<string, unknown>> = [];
  await page.route("**/api/v1/pdf/to-pdf/txt", async (route) => {
    submitted.push(route.request().postDataJSON());
    await route.fulfill({
      status: 202,
      json: { id: "stage-txt-42", operation: "txt-to-pdf", status: "queued", progress: 0,
        input_file_ids: [txt.id], output_file_id: null, params: {},
        error: null, requested_by: owner },
    });
  });

  await page.goto("/staged/converters?tool=T14&file=foreign");
  await expect(page.getByRole("heading", { name: "แปลงไฟล์เป็น PDF" })).toBeVisible();
  await expect(page.getByLabel("เครื่องมือแปลงไฟล์")).toHaveValue("T14");
  await expect(page.getByLabel("ไฟล์ที่ผ่านการตรวจชนิดและเป็นของบัญชีนี้")
    .locator("option")).toHaveCount(2); // empty option + user's TXT
  await expect(page.getByRole("note").first()).toContainText("Production");
  await expect(page.getByLabel("เครื่องมือแปลงไฟล์").locator('option[value="T21"]')).toHaveCount(0);
  await page.getByLabel("ไฟล์ที่ผ่านการตรวจชนิดและเป็นของบัญชีนี้").selectOption(txt.id);
  await page.getByRole("button", { name: "แปลงเป็น PDF" }).click();
  await expect(page.getByText("รหัสงาน: stage-txt-42")).toBeVisible();
  await expect(page.getByRole("link", { name: "ดูผลลัพธ์และดาวน์โหลดไฟล์" }))
    .toHaveAttribute("href", "/jobs/stage-txt-42/result");
  expect(submitted).toEqual([{ file_id: txt.id }]);
});

test("missing required operation scope blocks queueing in shared T90-2 stage", async ({ page }) => {
  test.skip(
    process.env.PDFHUB_STAGED_TO_PDF_WEB_ENABLED !== "true" ||
      process.env.PDFHUB_TO_PDF_TOOLS_ENABLED !== "true",
  );
  await mockSession(page, false);
  const submitted: string[] = [];
  await page.route("**/api/v1/pdf/to-pdf/**", (route) => {
    submitted.push(route.request().url());
    return route.abort();
  });
  await page.goto("/staged/converters?tool=T14");
  await expect(page.getByRole("alert")).toContainText("pdf:convert");
  await expect(page.getByRole("button", { name: "แปลงเป็น PDF" })).toBeDisabled();
  expect(submitted).toEqual([]);
});
