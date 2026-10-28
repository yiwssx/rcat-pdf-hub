import { expect, test, type Page } from "@playwright/test";

const owner = "user:geometry-e2e";
const pdf = {
  id: "geometry-pdf-1", original_name: "เอกสาร.pdf", content_type: "application/pdf",
  size: 2187, sha256: "f".repeat(64), source_system: owner,
  created_at: "2026-10-28T07:00:00Z", expires_at: null,
};

async function mocks(page: Page, scoped = true) {
  await page.route("**/api/v1/auth/me", (route) => route.fulfill({
    json: { name: owner, display_name: "Geometry Tester", subject: "geo:tester",
      scopes: scoped ? ["files:read","jobs:read","pdf:crop","pdf:resize"] : ["files:read","jobs:read"],
      groups: [], roles: ["operator"], auth_source: "session", is_admin: false },
  }));
  await page.route("**/api/v1/files?limit=200&offset=0", (route) => route.fulfill({
    json: [pdf, { ...pdf, id: "someone-elses-file", source_system: "someone" },
      { ...pdf, id: "fake-pdf", content_type: "image/png" },
      { ...pdf, id: "expired", expires_at: "2020-01-01T00:00:00Z" }],
  }));
}

test("staged geometry filters owner/MIME and discloses crop/privacy and resize limitations", async ({ page }) => {
  await mocks(page);
  await page.goto("/staged/geometry?file=someone-elses-file");
  await expect(page.getByRole("heading", { name: "ครอบตัดและเปลี่ยนขนาดหน้า PDF" })).toBeVisible();
  await expect(page.getByLabel("PDF ที่อัปโหลดแล้ว")).toHaveValue(pdf.id);
  await expect(page.getByLabel("PDF ที่อัปโหลดแล้ว").locator("option")).toHaveCount(1);
  await expect(page.getByRole("note")).toContainText("ไม่ใช่การลบข้อมูล");
  await expect(page.getByRole("note")).toContainText("อัตราส่วนผิดเพี้ยน");
});

test("crop and resize submit only approved numeric fields and owner file", async ({ page }) => {
  await mocks(page);
  const submitted: Array<{op: string, payload: Record<string, unknown>}> = [];
  for (const operation of ["crop-pdf", "resize-pdf"]) {
    await page.route("**/api/v1/pdf/geometry/" + operation, (route) => {
      submitted.push({ op: operation, payload: route.request().postDataJSON() });
      return route.fulfill({ status: 202, json: { id: "stage-" + operation,
        operation, status: "queued", progress: 0, input_file_ids: [pdf.id],
        output_file_id: null, params: {}, error: null, requested_by: owner } });
    });
  }
  await page.goto("/staged/geometry");
  await page.getByLabel("หน้าที่จะ Crop").fill("1,3");
  await page.getByRole("button", { name: "สร้างงานทดลอง" }).click();
  await expect(page.getByText("รหัสงาน: stage-crop-pdf")).toBeVisible();
  await page.getByRole("radio", { name: /เปลี่ยนขนาดหน้ากระดาษ/ }).check();
  await page.getByLabel(/ความกว้าง/).fill("600");
  await page.getByLabel(/ความสูง/).fill("840");
  await page.getByRole("button", { name: "สร้างงานทดลอง" }).click();
  await expect(page.getByText("รหัสงาน: stage-resize-pdf")).toBeVisible();
  expect(submitted).toEqual([
    { op: "crop-pdf", payload: { file_id: pdf.id, left: 20, bottom: 20, right: 460, top: 700, pages: [1, 3] } },
    { op: "resize-pdf", payload: { file_id: pdf.id, width: 600, height: 840 } },
  ]);
  await expect(page.getByRole("link", { name: "ดูผลและดาวน์โหลด PDF" }))
    .toHaveAttribute("href", "/jobs/stage-resize-pdf/result");
});

test("malformed page selection fails before upload or enqueue", async ({ page }) => {
  await mocks(page);
  const received: string[] = [];
  await page.route("**/api/v1/pdf/geometry/**", (route) => {
    received.push(route.request().url());
    return route.abort();
  });
  await page.goto("/staged/geometry");
  await page.getByLabel("หน้าที่จะ Crop").fill("1,1");
  await page.getByRole("button", { name: "สร้างงานทดลอง" }).click();
  await expect(page.locator(".t90DocumentStageError")).toContainText("ไม่ซ้ำกัน");
  expect(received).toEqual([]);
});

test("missing geometry scope prevents any stage submission", async ({ page }) => {
  await mocks(page, false);
  const received: string[] = [];
  await page.route("**/api/v1/pdf/geometry/**", (route) => {
    received.push(route.request().url());
    return route.abort();
  });
  await page.goto("/staged/geometry");
  await expect(page.locator(".t90DocumentStageCard p[role='alert']").filter({ hasText: "pdf:crop" })).toBeVisible();
  await expect(page.getByRole("button", { name: "สร้างงานทดลอง" })).toBeDisabled();
  await page.getByRole("radio", { name: /เปลี่ยนขนาดหน้ากระดาษ/ }).check();
  await expect(page.locator(".t90DocumentStageCard p[role='alert']").filter({ hasText: "pdf:resize" })).toBeVisible();
  await expect(page.getByRole("button", { name: "สร้างงานทดลอง" })).toBeDisabled();
  expect(received).toEqual([]);
});
