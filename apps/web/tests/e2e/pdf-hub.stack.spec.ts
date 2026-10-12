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

  // P7 routes submitted jobs to their durable detail page, not the legacy Job Drawer.
  await expect(page).toHaveURL(/\/jobs\/[A-Za-z0-9_-]+$/, { timeout: 30_000 });
  const jobDetail = page.getByRole("main", { name: "รายละเอียดงานประมวลผล" });
  await expect(jobDetail.getByRole("heading", { name: "images-to-pdf" })).toBeVisible();
  await expect(jobDetail.locator(".v3JobBadge.completed")).toBeVisible({ timeout: 120_000 });

  // Download through the authenticated result page and verify the file handoff.
  await jobDetail.getByRole("link", { name: /ดูผลลัพธ์และดาวน์โหลด/ }).click();
  await expect(page).toHaveURL(/\/jobs\/[A-Za-z0-9_-]+\/result$/);
  const downloadButton = page.getByRole("button", { name: "ดาวน์โหลดผลลัพธ์" });
  await expect(downloadButton).toBeEnabled();
  const downloadPromise = page.waitForEvent("download");
  await downloadButton.click();
  const download = await downloadPromise;
  expect(download.suggestedFilename().toLowerCase()).toContain(".pdf");

  // My Files now opens a durable file-detail route. Select a supported tool to preview.
  await page.goto("/files");
  const pdfRow = page.locator(".v3LibraryRow").filter({ hasText: ".pdf" }).first();
  await expect(pdfRow).toBeVisible({ timeout: 60_000 });
  await pdfRow.locator(".v3FileOpen").click();
  await expect(page.getByRole("main", { name: "รายละเอียดไฟล์ของฉัน" })).toBeVisible();
  await page.getByRole("region", { name: "เครื่องมือสำหรับไฟล์นี้" })
    .getByRole("link", { name: /ลดขนาด PDF/ }).click();
  await expect(page.locator("#workspace-target")).toContainText(".pdf", { timeout: 30_000 });
  await page.getByRole("button", { name: "ดูตัวอย่าง PDF" }).click();
  await expect(page.getByRole("img", { name: "Preview page 1" })).toBeVisible({ timeout: 30_000 });
});
