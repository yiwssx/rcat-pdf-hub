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
        roles: ["operator"],
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

  await page.route("**/api/v1/files/library**", async (route) => {
    const url = new URL(route.request().url());
    await route.fulfill({
      json: {
        items: [],
        total: 0,
        limit: Number(url.searchParams.get("limit") || "50"),
        offset: Number(url.searchParams.get("offset") || "0"),
        has_more: false,
      },
    });
  });

  await page.route("**/api/v1/jobs?limit=50", async (route) => {
    await route.fulfill({ json: [] });
  });
}

type AccessibilityFinding = {
  severity: "critical" | "serious";
  rule: string;
  target: string;
  message: string;
};

async function automatedAccessibilityFindings(page: Page): Promise<AccessibilityFinding[]> {
  return page.evaluate(() => {
    const findings: AccessibilityFinding[] = [];
    const target = (element: Element) => {
      const id = element.getAttribute("id");
      const cls = element.getAttribute("class")?.trim().split(/\s+/).slice(0, 2).join(".");
      return `${element.tagName.toLowerCase()}${id ? `#${id}` : cls ? `.${cls}` : ""}`;
    };
    const named = (element: HTMLElement) => {
      const ariaLabel = element.getAttribute("aria-label")?.trim();
      const labelledBy = element.getAttribute("aria-labelledby");
      const labelledText = labelledBy
        ? labelledBy.split(/\s+/).map((id) => document.getElementById(id)?.textContent?.trim() || "").join(" ").trim()
        : "";
      const nativeLabels = "labels" in element
        ? Array.from((element as HTMLInputElement).labels || []).map((label) => label.textContent?.trim() || "").join(" ").trim()
        : "";
      return Boolean(ariaLabel || labelledText || nativeLabels || element.textContent?.trim() || element.getAttribute("title")?.trim());
    };

    if (!document.documentElement.lang.trim()) {
      findings.push({ severity: "serious", rule: "html-lang", target: "html", message: "Document language is missing." });
    }

    document.querySelectorAll("img").forEach((element) => {
      if (!element.hasAttribute("alt")) {
        findings.push({ severity: "critical", rule: "image-alt", target: target(element), message: "Image has no alt attribute." });
      }
    });

    document.querySelectorAll<HTMLElement>("button, a[href], [role='button'], input, select, textarea").forEach((element) => {
      if (element instanceof HTMLInputElement && element.type === "hidden") return;
      if (!named(element)) {
        findings.push({ severity: "critical", rule: "accessible-name", target: target(element), message: "Interactive control has no accessible name." });
      }
    });

    document.querySelectorAll<HTMLElement>("[aria-hidden='true']").forEach((element) => {
      if (element.matches("button, a[href], input, select, textarea, [tabindex]:not([tabindex='-1'])")) {
        findings.push({ severity: "critical", rule: "aria-hidden-focus", target: target(element), message: "Focusable content is hidden from assistive technology." });
      }
    });

    const ids = new Map<string, number>();
    document.querySelectorAll<HTMLElement>("[id]").forEach((element) => {
      const id = element.id;
      ids.set(id, (ids.get(id) || 0) + 1);
    });
    ids.forEach((count, id) => {
      if (count > 1) {
        findings.push({ severity: "serious", rule: "duplicate-id", target: `#${id}`, message: `ID appears ${count} times.` });
      }
    });

    document.querySelectorAll<HTMLElement>("[tabindex]").forEach((element) => {
      const value = Number(element.getAttribute("tabindex"));
      if (value > 0) {
        findings.push({ severity: "serious", rule: "positive-tabindex", target: target(element), message: "Positive tabindex overrides natural focus order." });
      }
    });

    return findings;
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

test("keeps the paged file-library controls usable on mobile", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/files");

  await expect(page.getByRole("heading", { name: "ไฟล์ทั้งหมด" })).toBeVisible();
  await expect(page.getByLabel("ค้นหาชื่อไฟล์")).toBeVisible();
  await expect(page.getByLabel("ประเภทไฟล์")).toBeVisible();

  const layout = await page.evaluate(() => ({
    overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    offenders: Array.from(document.querySelectorAll<HTMLElement>("body *"))
      .map((element) => {
        const rect = element.getBoundingClientRect();
        return {
          tag: element.tagName,
          className: element.className,
          left: Math.round(rect.left),
          right: Math.round(rect.right),
          width: Math.round(rect.width),
        };
      })
      .filter((item) => item.right > window.innerWidth + 1 || item.left < -1)
      .slice(0, 12),
  }));
  expect(layout.overflow, JSON.stringify(layout.offenders)).toBeLessThanOrEqual(1);
});

test("has no critical or serious automated accessibility findings", async ({ page }) => {
  for (const path of ["/", "/files"]) {
    await page.goto(path);
    await page.waitForLoadState("networkidle");
    const findings = await automatedAccessibilityFindings(page);
    expect(
      findings.filter((finding) => finding.severity === "critical" || finding.severity === "serious"),
      `${path}: ${JSON.stringify(findings, null, 2)}`,
    ).toEqual([]);
  }
});
