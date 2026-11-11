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


test("experimental native and URL formats are withheld when their server flags are OFF", async ({ page }) => {
  test.skip(
    process.env.PDFHUB_STAGED_TO_PDF_WEB_ENABLED !== "true" ||
      process.env.PDFHUB_TO_PDF_TOOLS_ENABLED !== "true" ||
      ["PDFHUB_HEIF_NATIVE_DEV_ENABLED", "PDFHUB_DWG_NATIVE_DEV_ENABLED",
       "PDFHUB_CHM_NATIVE_DEV_ENABLED", "PDFHUB_WPS_NATIVE_DEV_ENABLED",
       "PDFHUB_URL_TO_PDF_DEV_ENABLED"].some((flag) => process.env[flag] === "true"),
    "Only applies to default-disabled experimental stage",
  );
  await mockSession(page);
  await page.goto("/staged/converters?tool=T33");
  await expect(page.getByLabel("เครื่องมือแปลงไฟล์")).toHaveValue("T01");
  for (const id of ["T09", "T20", "T25", "T30", "T33", "T34"]) {
    await expect(page.getByLabel("เครื่องมือแปลงไฟล์")
      .locator('option[value="' + id + '"]')).toHaveCount(0);
  }
});

test("explicitly gated T33 sends only a fileless HTTPS URL job", async ({ page }) => {
  test.skip(
    process.env.PDFHUB_STAGED_TO_PDF_WEB_ENABLED !== "true" ||
      process.env.PDFHUB_TO_PDF_TOOLS_ENABLED !== "true" ||
      process.env.PDFHUB_URL_TO_PDF_DEV_ENABLED !== "true",
    "T33 cannot be offered without the exact server-side experimental flag",
  );
  await mockSession(page);
  const submitted: Array<Record<string, unknown>> = [];
  await page.route("**/api/v1/pdf/to-pdf/url", async (route) => {
    submitted.push(route.request().postDataJSON());
    await route.fulfill({ status: 202, json: {
      id: "url-t33-accepted", operation: "url-to-pdf", status: "queued", progress: 0,
      input_file_ids: [], output_file_id: null, params: {}, error: null,
      requested_by: owner,
    } });
  });
  await page.goto("/staged/converters?tool=T33");
  await expect(page.getByLabel("เครื่องมือแปลงไฟล์")).toHaveValue("T33");
  await expect(page.getByLabel("ไฟล์ที่ผ่านการตรวจชนิดและเป็นของบัญชีนี้")).toHaveCount(0);
  await expect(page.getByLabel("อัปโหลดไฟล์ต้นฉบับ")).toHaveCount(0);
  const url = page.getByLabel("URL เว็บไซต์สาธารณะ (HTTPS)");
  await url.fill("http://127.0.0.1/internal");
  await expect(page.getByRole("button", { name: "แปลงเป็น PDF" })).toBeDisabled();
  await url.fill("https://example.org/public-article");
  await page.getByRole("button", { name: "แปลงเป็น PDF" }).click();
  await expect(page.getByText("รหัสงาน: url-t33-accepted")).toBeVisible();
  expect(submitted).toEqual([{ url: "https://example.org/public-article" }]);
});

test("explicitly gated T09 reuses owned-file conversion and does not fetch URLs", async ({ page }) => {
  test.skip(
    process.env.PDFHUB_STAGED_TO_PDF_WEB_ENABLED !== "true" ||
      process.env.PDFHUB_TO_PDF_TOOLS_ENABLED !== "true" ||
      process.env.PDFHUB_HEIF_NATIVE_DEV_ENABLED !== "true",
    "T09 only appears with the exact HEIF development gate",
  );
  await mockSession(page);
  const heic = { ...txt, id: "heic-test-1", original_name: "camera.heic", content_type: "image/heic" };
  await page.route("**/api/v1/files?limit=200&offset=0", (route) => route.fulfill({
    json: [heic, txt],
  }));
  const submitted: Array<Record<string, unknown>> = [];
  await page.route("**/api/v1/pdf/to-pdf/heic", async (route) => {
    submitted.push(route.request().postDataJSON());
    await route.fulfill({ status: 202, json: {
      id: "heic-t09-accepted", operation: "heic-to-pdf", status: "queued", progress: 0,
      input_file_ids: [heic.id], output_file_id: null, params: {},
      error: null, requested_by: owner,
    } });
  });
  await page.goto("/staged/converters?tool=T09");
  await expect(page.getByLabel("เครื่องมือแปลงไฟล์")).toHaveValue("T09");
  await page.getByLabel("ไฟล์ที่ผ่านการตรวจชนิดและเป็นของบัญชีนี้").selectOption(heic.id);
  await page.getByRole("button", { name: "แปลงเป็น PDF" }).click();
  await expect(page.getByText("รหัสงาน: heic-t09-accepted")).toBeVisible();
  expect(submitted).toEqual([{ file_id: heic.id }]);
});
