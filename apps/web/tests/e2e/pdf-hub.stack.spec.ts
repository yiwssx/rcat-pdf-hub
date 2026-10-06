import { expect, test } from "@playwright/test";

const stackEnabled = process.env.PDFHUB_E2E_STACK === "1";
const pngPixel = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
  "base64",
);

test("production stack: web session, upload, process, preview and download", async ({ page }) => {
  test.skip(!stackEnabled, "Set PDFHUB_E2E_STACK=1 for real-stack smoke");
  test.setTimeout(180_000);

  await page.goto("/");
  await expect(page.getByLabel("Service API Key")).toHaveCount(0);
  await expect(page.locator("#workspace")).toBeVisible({ timeout: 30_000 });

  const filename = `stack-smoke-${Date.now()}.png`;
  const fileInput = page.locator("#files");
  await expect(fileInput).toBeEnabled({ timeout: 30_000 });
  const uploadResponsePromise = page.waitForResponse(
    (response) => response.request().method() === "POST" && new URL(response.url()).pathname === "/api/v1/files",
    { timeout: 30_000 },
  );
  await fileInput.setInputFiles({ name: filename, mimeType: "image/png", buffer: pngPixel });
  const uploadResponse = await uploadResponsePromise;
  const uploadBody = await uploadResponse.text();
  expect(uploadResponse.ok(), `upload failed with HTTP ${uploadResponse.status()}: ${uploadBody}`).toBe(true);
  await expect(page.locator("#workspace-target")).toContainText(filename, { timeout: 30_000 });

  await page.getByRole("button", { name: /รูปภาพ → PDF/ }).first().click();
  await page.getByRole("button", { name: "สร้าง PDF จากภาพ" }).click();

  const completed = page.locator(".v3JobItem").filter({ hasText: "images-to-pdf" }).locator(".v3JobBadge.completed").first();
  await expect(completed).toBeVisible({ timeout: 120_000 });

  const downloadButton = page.locator(".v3JobItem").filter({ hasText: "images-to-pdf" }).getByRole("button", { name: "ดาวน์โหลด" }).first();
  await expect(downloadButton).toBeVisible();
  const downloadPromise = page.waitForEvent("download");
  await downloadButton.click();
  const download = await downloadPromise;
  expect(download.suggestedFilename().toLowerCase()).toContain(".pdf");

  await page.goto("/files");
  const pdfRow = page.locator(".v3LibraryRow").filter({ hasText: ".pdf" }).first();
  await expect(pdfRow).toBeVisible({ timeout: 60_000 });
  await pdfRow.click();

  await page.getByRole("button", { name: "ดูตัวอย่าง PDF" }).click();
  await expect(page.getByRole("img", { name: "Preview page 1" })).toBeVisible({ timeout: 30_000 });
});
