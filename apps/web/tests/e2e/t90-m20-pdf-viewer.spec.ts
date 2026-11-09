import { expect, test, type Page } from "@playwright/test";

const owner = "user:rcat-m20";
const base = {
  content_type: "application/pdf", size: 1200, sha256: "a".repeat(64),
  source_system: owner, created_at: "2026-11-09T00:00:00Z", expires_at: null,
};
const first = { ...base, id: "m20-a", original_name: "รายงาน.pdf" };
const second = { ...base, id: "m20-b", original_name: "บทเรียน.pdf" };
const enabled = process.env.PDFHUB_STAGED_M20_VIEWER_WEB_ENABLED === "true";
const png = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScL0zAAAAABJRU5ErkJggg==",
  "base64",
);

async function mockOwner(page: Page, allowed = true) {
  await page.route("**/api/v1/auth/me", (route) => route.fulfill({ json: {
    name: owner, display_name: "Test", subject: "test:m20",
    scopes: allowed ? ["files:read"] : ["jobs:read"],
    groups: [], roles: ["operator"], auth_source: "session", is_admin: false,
  } }));
  await page.route("**/api/v1/files?limit=200&offset=0", (route) => route.fulfill({ json: [
    first, second, { ...first, id: "foreign", source_system: "user:other" },
    { ...first, id: "expired", expires_at: "2020-01-01T00:00:00Z" },
  ] }));
  await page.route("**/api/v1/files/m20-*/pages", (route) => route.fulfill({ json: {
    file_id: route.request().url().includes("m20-b") ? second.id : first.id,
    pages: 3,
  } }));
  await page.route("**/api/v1/files/m20-*/preview?**", (route) => route.fulfill({
    status: 200, contentType: "image/png", body: png,
  }));
}

test("M20 viewer is 404 in an unchanged, default-OFF Web build", async ({ page }) => {
  test.skip(enabled, "Default-OFF build only");
  const res = await page.goto("/staged/viewer");
  expect(res?.status()).toBe(404);
});

test("M20 only lists owned active PDF and previews bounded pages", async ({ page }) => {
  test.skip(!enabled, "Separate dev-only route opt-in required");
  await mockOwner(page);
  const previews: string[] = [];
  await page.route("**/api/v1/files/m20-*/preview?**", async (route) => {
    previews.push(route.request().url());
    await route.fulfill({ status: 200, contentType: "image/png", body: png });
  });
  await page.goto("/staged/viewer?file=foreign");
  await expect(page.getByRole("heading", { name: "ดูเอกสาร PDF" })).toBeVisible();
  await expect(page.getByLabel("PDF ของฉัน").locator("option")).toHaveCount(2);
  await expect(page.getByAltText("PDF หน้า 1")).toBeVisible();
  await page.getByRole("button", { name: "ถัดไป" }).click();
  await expect(page.getByAltText("PDF หน้า 2")).toBeVisible();
  expect(previews.some((url) => url.includes("m20-a/preview?page=2"))).toBe(true);
  expect(previews.every((url) => !url.includes("foreign") && !url.includes("expired"))).toBe(true);
  await page.getByLabel("PDF ของฉัน").selectOption(second.id);
  await expect(page.getByAltText("PDF หน้า 1")).toBeVisible();
  await expect(page.getByText("จาก 3 หน้า")).toBeVisible();
});

test("M20 missing files:read blocks file enumeration and preview", async ({ page }) => {
  test.skip(!enabled, "Separate dev-only route opt-in required");
  let calls = 0;
  await mockOwner(page, false);
  await page.route("**/api/v1/files**", (route) => { calls++; return route.abort(); });
  await page.goto("/staged/viewer");
  await expect(page.getByRole("alert")).toContainText("files:read");
  await expect(page.getByLabel("PDF ของฉัน")).toHaveCount(0);
  expect(calls).toBe(0);
});
