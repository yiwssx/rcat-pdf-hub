import { expect, test } from "@playwright/test";

const apiKey = process.env.PDFHUB_E2E_API_KEY || "";
const stackEnabled = process.env.PDFHUB_E2E_STACK === "1";
const pngPixel = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
  "base64",
);

test("production stack: login, upload, process, preview and download", async ({ page }) => {
  test.skip(!stackEnabled || !apiKey, "Set PDFHUB_E2E_STACK=1 and PDFHUB_E2E_API_KEY for real-stack smoke");
  test.setTimeout(180_000);

  await page.goto("/");
  await page.getByLabel("Service API Key").fill(apiKey);
  await page.getByRole("button", { name: "เชื่อมต่อ" }).click();
  await expect(page.locator("#workspace")).toBeVisible({ timeout: 30_000 });

  const filename = `stack-smoke-${Date.now()}.png`;
  await page.locator("#files").setInputFiles({ name: filename, mimeType: "image/png", buffer: pngPixel });
  await expect(page.getByText(filename, { exact: true })).toBeVisible();

  await page.getByRole("button", { name: /รูปภาพ → PDF/ }).first().click();
  await page.getByRole("button", { name: "สร้าง PDF จากภาพ" }).click();

  const completed = page.locator(".job").filter({ hasText: "images-to-pdf" }).locator(".badge.completed").first();
  await expect(completed).toBeVisible({ timeout: 120_000 });

  const downloadButton = page.locator(".job").filter({ hasText: "images-to-pdf" }).getByRole("button", { name: "ดาวน์โหลด" }).first();
  await expect(downloadButton).toBeVisible();
  const downloadPromise = page.waitForEvent("download");
  await downloadButton.click();
  const download = await downloadPromise;
  expect(download.suggestedFilename().toLowerCase()).toContain(".pdf");

  const targetSelect = page.locator("#workspace-target select").first();
  await expect.poll(async () => targetSelect.locator("option").count(), { timeout: 60_000 }).toBeGreaterThan(2);
  const options = await targetSelect.locator("option").evaluateAll((nodes) =>
    nodes.map((node) => ({ value: (node as HTMLOptionElement).value, label: (node.textContent || "").trim() })),
  );
  const output = options.find((item) => item.value && item.label.toLowerCase().endsWith(".pdf"));
  expect(output, "processed PDF should appear in Workspace").toBeTruthy();
  await targetSelect.selectOption(output!.value);

  await page.getByRole("button", { name: "ดูตัวอย่าง PDF" }).click();
  await expect(page.getByRole("img", { name: "Preview page 1" })).toBeVisible({ timeout: 30_000 });
});
