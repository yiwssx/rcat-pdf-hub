import { expect, test, type Page } from "@playwright/test";

const enabled = process.env.PDFHUB_STAGED_M32_REPAIR_WEB_ENABLED === "true"
  && process.env.PDFHUB_PDF_REPAIR_STRUCTURE_TOOLS_ENABLED === "true";
const owner = "user:rcat-m32";
const file = {
  id:"m32-owner", original_name:"bad.pdf", content_type:"application/pdf",
  size:1200, sha256:"a".repeat(64), source_system:owner,
  created_at:"2026-11-09T00:00:00Z", expires_at:null,
};
async function mock(page:Page, allowed=true) {
  await page.route("**/api/v1/auth/me", route => route.fulfill({json:{
    name:owner, display_name:"Test", subject:"test:m32",
    scopes:allowed?["files:read","jobs:read","pdf:convert"]:["jobs:read"],
    groups:[], roles:["operator"], auth_source:"session", is_admin:false,
  }}));
  await page.route("**/api/v1/files?limit=200&offset=0", route => route.fulfill({json:[
    file, {...file, id:"foreign",source_system:"other"},
    {...file, id:"expired",expires_at:"2020-01-01T00:00:00Z"},
  ]}));
}

test("M32 repair route is absent by default", async ({page}) => {
  test.skip(enabled, "Default-OFF only");
  expect((await page.goto("/staged/repair"))?.status()).toBe(404);
});

test("M32 only submits user-owned repair with strict file_id", async ({page}) => {
  test.skip(!enabled, "Dev-only independent backend and Web flags required");
  await mock(page);
  const received:unknown[]=[];
  await page.route("**/api/v1/pdf/advanced/repair-structure", async route => {
    received.push(route.request().postDataJSON());
    await route.fulfill({status:202,json:{
      id:"m32-job",operation:"repair-pdf-structure",status:"queued",progress:0,
      input_file_ids:[file.id],output_file_id:null,params:{},error:null,requested_by:owner,
    }});
  });
  await page.goto("/staged/repair?file=foreign");
  await expect(page.getByLabel("PDF ของบัญชีนี้").locator("option")).toHaveCount(1);
  await page.getByRole("button",{name:"ซ่อมโครงสร้าง PDF"}).click();
  await expect(page.getByText("รหัสงาน: m32-job")).toBeVisible();
  expect(received).toEqual([{file_id:file.id}]);
});

test("M32 missing files:read denies enumeration", async ({page}) => {
  test.skip(!enabled,"Dev-only flags required");
  await mock(page,false);
  let calls=0;
  await page.route("**/api/v1/files**",route=>{calls++;return route.abort();});
  await page.goto("/staged/repair");
  await expect(page.getByRole("alert")).toContainText("files:read");
  expect(calls).toBe(0);
});
