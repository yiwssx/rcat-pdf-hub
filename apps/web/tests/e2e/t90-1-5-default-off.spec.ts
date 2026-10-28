import { expect, test } from "@playwright/test";

test("T90-1.5 geometry staging URL remains 404 by default", async ({ page }) => {
  const response = await page.goto("/staged/geometry?file=guess");
  expect(response?.status()).toBe(404);
  await expect(page.getByRole("heading", { name: "ครอบตัดและเปลี่ยนขนาดหน้า PDF" })).toHaveCount(0);
});
