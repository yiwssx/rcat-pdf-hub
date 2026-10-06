import { expect, Page, test } from "@playwright/test";

async function installWorkspaceMocks(page: Page) {
  await page.route("**/api/v1/auth/config", async (route) => {
    await route.fulfill({
      json: {
        session_cookie: "pdfhub_session",
        oidc: { enabled: false, issuer: null, login_url: null },
        ldap: { enabled: false },
        web_console: { auto_login: true },
        local_admin: { enabled: false },
      },
    });
  });

  await page.route("**/api/v1/auth/me", async (route) => {
    await route.fulfill({
      json: {
        name: "ui-regression",
        display_name: "UI Regression",
        subject: "ui-regression",
        scopes: ["files:read", "files:write", "jobs:read", "jobs:manage", "pdf:compress"],
        groups: [],
        auth_source: "web-console",
        is_admin: false,
      },
    });
  });

  await page.route("**/api/v1/integrations/status", async (route) => {
    await route.fulfill({
      json: {
        storage_backend: "local",
        clamav_enabled: true,
        paperless_enabled: false,
        oidc_enabled: false,
        ldap_enabled: false,
        otel_enabled: false,
        prometheus_enabled: true,
      },
    });
  });

  await page.route("**/api/v1/files?limit=200&offset=0", async (route) => {
    await route.fulfill({ json: [] });
  });

  await page.route("**/api/v1/jobs?limit=50", async (route) => {
    await route.fulfill({ json: [] });
  });
}

test.beforeEach(async ({ page }) => {
  await installWorkspaceMocks(page);
});

test("keeps V3 readable and free of horizontal overflow on desktop", async ({ page }) => {
  await page.setViewportSize({ width: 1366, height: 768 });
  await page.goto("/");

  await expect(page.locator("#workspace")).toBeVisible();

  const metrics = await page.evaluate(() => ({
    bodyFontSize: Number.parseFloat(getComputedStyle(document.body).fontSize),
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }));

  expect(metrics.bodyFontSize).toBeGreaterThanOrEqual(17);
  expect(metrics.scrollWidth).toBeLessThanOrEqual(metrics.clientWidth);
});

test("keeps V3 usable on a narrow mobile viewport", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");

  await expect(page.locator("#workspace")).toBeVisible();
  await expect(page.getByRole("button", { name: /ลดขนาด PDF/ })).toBeVisible();

  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(1);
});

test("provides visible keyboard focus and honors reduced motion", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");

  const jobsButton = page.getByRole("button", { name: /งานล่าสุด/ });
  await jobsButton.focus();

  const focusStyle = await jobsButton.evaluate((element) => {
    const style = getComputedStyle(element);
    return { outlineStyle: style.outlineStyle, outlineWidth: style.outlineWidth };
  });
  expect(focusStyle.outlineStyle).not.toBe("none");
  expect(Number.parseFloat(focusStyle.outlineWidth)).toBeGreaterThan(0);

  await jobsButton.click();
  await expect(page.locator(".v3JobDrawer")).toBeVisible();
  await expect(page.locator(".v3JobDrawer")).toHaveCSS("animation-name", "none");
});
