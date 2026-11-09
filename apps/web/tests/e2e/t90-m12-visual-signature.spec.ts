import { expect, test, type Page } from "@playwright/test";

const enabled = process.env.PDFHUB_STAGED_SIGNATURE_WEB_ENABLED === "true"
  && process.env.PDFHUB_PDF_IMAGE_OVERLAY_TOOLS_ENABLED === "true";
const owner = "user:rcat-m12";
const common = {
  size: 1600, sha256: "a".repeat(64), source_system: owner,
  created_at: "2026-11-10T00:00:00Z", expires_at: null,
};
const pdf = { ...common, id: "m12-source", original_name: "signed-document.pdf", content_type: "application/pdf" };
const png = { ...common, id: "m12-png", original_name: "visual-signature.png", content_type: "image/png" };

async function mocks(page: Page, allowed = true) {
  await page.route("**/api/v1/auth/me", (route) => route.fulfill({ json: {
    name: owner, display_name: "Operator", subject: "m12:test",
    scopes: allowed ? ["files:read", "files:write", "jobs:read", "pdf:stamp"] : ["files:read"],
    roles: ["operator"], groups: [], is_admin: false, auth_source: "session",
  } }));
  await page.route("**/api/v1/files?limit=200&offset=0", (route) => route.fulfill({ json: [
    pdf, { ...pdf, id: "foreign", source_system: "user:someone-else" },
    { ...pdf, id: "expired", expires_at: "2020-01-01T00:00:00Z" },
  ] }));
}

test("M12 visual-signature page is 404 by default", async ({ page }) => {
  test.skip(enabled, "Only applies to default-OFF R1");
  const response = await page.goto("/staged/signature");
  expect(response?.status()).toBe(404);
});

test("M12 drawn signature uploads real PNG, then queues existing owner-scoped M23", async ({ page }) => {
  test.skip(!enabled, "Requires separately enabled dev-only M12 + M23 flags");
  await mocks(page);
  const seen: unknown[] = [];
  await page.route("**/api/v1/files", async (route) => {
    expect(route.request().method()).toBe("POST");
    const body = route.request().postDataBuffer();
    expect(body?.includes(Buffer.from("image/png"))).toBe(true);
    await route.fulfill({ status: 201, json: png });
  });
  await page.route("**/api/v1/pdf/advanced/add-image", async (route) => {
    seen.push(route.request().postDataJSON());
    await route.fulfill({ status: 202, json: {
      id: "m12-job", operation: "add-pdf-image", status: "queued",
      progress: 0, input_file_ids: [pdf.id, png.id], output_file_id: null,
      params: {}, error: null, requested_by: owner,
    } });
  });
  await page.goto("/staged/signature?file=foreign");
  await expect(page.getByRole("heading", { name: "ลงลายเซ็นภาพบน PDF" })).toBeVisible();
  await expect(page.getByLabel("PDF ของฉัน").locator("option")).toHaveCount(1);
  const submit = page.getByRole("button", { name: "วางลายเซ็นลง PDF" });
  await expect(submit).toBeDisabled();
  const box = await page.locator("#m12-canvas").boundingBox();
  expect(box).not.toBeNull();
  await page.mouse.move(box!.x + 30, box!.y + 90);
  await page.mouse.down();
  await page.mouse.move(box!.x + 180, box!.y + 60, { steps: 8 });
  await page.mouse.up();
  await expect(submit).toBeEnabled();
  await submit.click();
  await expect(page.getByText("รหัสงาน: m12-job")).toBeVisible();
  expect(seen).toEqual([{
    file_id: pdf.id, image_file_id: png.id,
    page: 1, x: 50, y: 45, width: 180, height: 55,
  }]);
});

test("M12 rejects missing scope even if user supplies a PNG", async ({ page }) => {
  test.skip(!enabled, "Requires dev-only M12 + M23 flags");
  await mocks(page, false);
  await page.goto("/staged/signature");
  await page.getByLabel("ใช้ภาพลายเซ็น PNG").check();
  await page.locator("#m12-upload").setInputFiles({
    name: "signature.png",
    mimeType: "image/png",
    buffer: Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScL0zAAAAABJRU5ErkJggg==", "base64"),
  });
  await expect(page.getByRole("alert")).toContainText("files:write");
  await expect(page.getByRole("button", { name: "วางลายเซ็นลง PDF" })).toBeDisabled();
});
