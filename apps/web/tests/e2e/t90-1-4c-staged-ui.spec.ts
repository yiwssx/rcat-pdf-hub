import { expect, test, type Page } from "@playwright/test";

const owner = "user:staged-owner";
const pdf = {
  id: "stage-pdf-1", original_name: "ราชการ.pdf", content_type: "application/pdf",
  size: 1459, sha256: "a".repeat(64), source_system: owner,
  created_at: "2026-10-27T08:00:00Z", expires_at: null,
};

async function stageMocks(page: Page) {
  await page.route("**/api/v1/auth/me", (route) => route.fulfill({
    json: {
      name: owner, display_name: "RCAT Tester", subject: "stage:tester",
      scopes: ["files:read", "jobs:read", "pdf:metadata", "pdf:extract-text"],
      groups: [], roles: ["operator"], auth_source: "session", is_admin: false,
    },
  }));
  await page.route("**/api/v1/files?limit=200&offset=0", (route) => route.fulfill({
    json: [
      pdf,
      { ...pdf, id: "foreign-pdf", source_system: "user:someone-else", original_name: "foreign.pdf" },
      { ...pdf, id: "renamed-png", content_type: "image/png", original_name: "renamed.pdf" },
      { ...pdf, id: "empty-file", size: 0, original_name: "empty.pdf" },
      { ...pdf, id: "expired-file", expires_at: "2020-01-01T00:00:00Z", original_name: "expired.pdf" },
    ],
  }));
}

test("opt-in staged UI only offers owner-verified PDFs and explains extraction limitations", async ({ page }) => {
  await stageMocks(page);
  await page.goto("/staged/document-data?file=foreign-pdf");
  await expect(page.getByRole("heading", { name: "จัดการข้อมูลและข้อความใน PDF" })).toBeVisible();
  const fileSelect = page.getByLabel("PDF ที่อัปโหลดแล้ว");
  await expect(fileSelect.locator("option")).toHaveCount(1);
  await expect(fileSelect).toHaveValue(pdf.id);
  await expect(page.getByRole("note")).toContainText("ไม่ใช่ OCR");
  await expect(page.getByRole("note")).toContainText("ไม่ใช่การลบข้อมูลส่วนบุคคลทั้งหมด");
});

test("staged document edit form sends bounded Thai metadata and selected-field null", async ({ page }) => {
  await stageMocks(page);
  const sent: Array<Record<string, unknown>> = [];
  await page.route("**/api/v1/pdf/document-data/edit-metadata", async (route) => {
    sent.push(route.request().postDataJSON());
    await route.fulfill({
      status: 202,
      json: {
        id: "staged-edit-job", operation: "edit-metadata", status: "queued", progress: 0,
        input_file_ids: [pdf.id], output_file_id: null,
        params: {}, error: null, requested_by: owner,
      },
    });
  });
  await page.goto("/staged/document-data?file=" + pdf.id);
  await page.getByRole("radio", { name: "แก้ไขข้อมูลเอกสาร" }).check();
  await page.getByRole("checkbox", { name: "ชื่อเรื่อง (Title)" }).check();
  await page.getByRole("textbox", { name: "ค่า ชื่อเรื่อง (Title)" }).fill("สรุปผลงานภาษาไทย");
  await page.getByRole("checkbox", { name: "ผู้สร้าง (Author)" }).check();
  await page.getByRole("button", { name: "สร้างงานทดลอง" }).click();
  await expect(page.getByRole("status").filter({ hasText: "staged-edit-job" })).toBeVisible();
  expect(sent).toEqual([{ file_id: pdf.id, changes: { title: "สรุปผลงานภาษาไทย", author: null } }]);
  await expect(page.getByRole("link", { name: "เปิดดูผลและดาวน์โหลดจากหน้าผลงาน" }))
    .toHaveAttribute("href", "/jobs/staged-edit-job/result");
});

test("staged extract-text and remove-metadata use separate approved endpoints", async ({ page }) => {
  await stageMocks(page);
  const endpoints: string[] = [];
  for (const operation of ["extract-text", "remove-metadata"]) {
    await page.route("**/api/v1/pdf/document-data/" + operation, (route) => {
      endpoints.push(operation);
      expect(route.request().postDataJSON()).toEqual({ file_id: pdf.id });
      return route.fulfill({
        status: 202,
        json: {
          id: "stage-" + operation, operation, status: "queued", progress: 0,
          input_file_ids: [pdf.id], output_file_id: null,
          params: {}, error: null, requested_by: owner,
        },
      });
    });
  }
  await page.goto("/staged/document-data");
  await page.getByRole("button", { name: "สร้างงานทดลอง" }).click();
  await expect(page.getByText("รหัสงาน: stage-extract-text")).toBeVisible();
  await page.getByRole("radio", { name: "ลบ Info และ XMP ที่รองรับ" }).check();
  await page.getByRole("button", { name: "สร้างงานทดลอง" }).click();
  await expect(page.getByText("รหัสงาน: stage-remove-metadata")).toBeVisible();
  expect(endpoints).toEqual(["extract-text", "remove-metadata"]);
});


test("staged controls fail closed when identity lacks metadata and text scopes", async ({ page }) => {
  await stageMocks(page);
  await page.route("**/api/v1/auth/me", (route) => route.fulfill({
    json: {
      name: owner, display_name: "Scoped viewer", subject: "stage:viewer",
      scopes: ["files:read", "jobs:read"], groups: [],
      roles: ["viewer"], auth_source: "session", is_admin: false,
    },
  }));
  const requests: string[] = [];
  await page.route("**/api/v1/pdf/document-data/**", (route) => {
    requests.push(route.request().url());
    return route.abort();
  });
  await page.goto("/staged/document-data");
  await expect(page.getByRole("button", { name: "สร้างงานทดลอง" })).toBeDisabled();
  await expect(page.getByRole("alert")).toContainText("pdf:extract-text");
  await page.getByRole("radio", { name: "แก้ไขข้อมูลเอกสาร" }).check();
  await expect(page.getByRole("alert")).toContainText("pdf:metadata");
  await expect(page.getByRole("button", { name: "สร้างงานทดลอง" })).toBeDisabled();
  expect(requests).toEqual([]);
});

test("staged editing demands selected metadata fields before submitting", async ({ page }) => {
  await stageMocks(page);
  const requests: string[] = [];
  await page.route("**/api/v1/pdf/document-data/edit-metadata", (route) => {
    requests.push(route.request().url());
    return route.abort();
  });
  await page.goto("/staged/document-data");
  await page.getByRole("radio", { name: "แก้ไขข้อมูลเอกสาร" }).check();
  await page.getByRole("button", { name: "สร้างงานทดลอง" }).click();
  await expect(page.getByRole("alert")).toContainText("กรุณาเลือกอย่างน้อยหนึ่งฟิลด์");
  expect(requests).toEqual([]);
});
