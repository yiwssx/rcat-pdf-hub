import { expect, test } from "@playwright/test";

// Production/default build must never expose the staging form, even to users
// who know its exact URL. The backend separately keeps the API routes absent.
test("T90-1.4c experimental document form is 404 by default", async ({ page }) => {
  const response = await page.goto("/staged/document-data?file=guess");
  expect(response?.status()).toBe(404);
  await expect(page.getByText("จัดการข้อมูลและข้อความใน PDF")).toHaveCount(0);
});
