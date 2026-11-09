import { expect, test, type Page } from "@playwright/test";

const enabled = process.env.PDFHUB_STAGED_IMAGE_WATERMARK_WEB_ENABLED === "true"
  && process.env.PDFHUB_PDF_IMAGE_WATERMARK_TOOLS_ENABLED === "true";
const owner = "user:rcat-m21";
const base = {
  size: 1250, sha256: "b".repeat(64), source_system: owner,
  created_at: "2026-11-09T00:00:00Z", expires_at: null,
};
const pdf = { ...base, id:"m21-pdf", original_name:"report.pdf", content_type:"application/pdf" };
const image = { ...base, id:"m21-img", original_name:"logo.png", content_type:"image/png" };

async function mock(page:Page,allowed=true) {
  await page.route("**/api/v1/auth/me",route=>route.fulfill({json:{
    name:owner,display_name:"Test",subject:"test:m21",
    scopes:allowed?["files:read","jobs:read","pdf:watermark"]:["jobs:read"],
    groups:[],roles:["operator"],auth_source:"session",is_admin:false,
  }}));
  await page.route("**/api/v1/files?limit=200&offset=0",route=>route.fulfill({json:[
    pdf,image,{...pdf,id:"foreign",source_system:"other"},
    {...image,id:"expired",expires_at:"2020-01-01T00:00:00Z"},
  ]}));
}

test("M21 image watermark route is 404 by default",async({page})=>{
  test.skip(enabled,"default-OFF only");
  expect((await page.goto("/staged/image-watermark"))?.status()).toBe(404);
});

test("M21 sends distinct owner PDF and image with real opacity",async({page})=>{
  test.skip(!enabled,"dev-only Web/backend opt-in");
  await mock(page);
  const payloads:unknown[]=[];
  await page.route("**/api/v1/pdf/advanced/image-watermark",async route=>{
    payloads.push(route.request().postDataJSON());
    await route.fulfill({status:202,json:{
      id:"watermark-job",operation:"watermark-pdf-image",status:"queued",progress:0,
      input_file_ids:[pdf.id,image.id],output_file_id:null,params:{},error:null,requested_by:owner,
    }});
  });
  await page.goto("/staged/image-watermark?file=foreign");
  await expect(page.getByLabel("PDF ต้นฉบับของฉัน").locator("option")).toHaveCount(2);
  await expect(page.getByLabel("รูป PNG/JPEG ของฉัน").locator("option")).toHaveCount(2);
  await page.getByLabel("PDF ต้นฉบับของฉัน").selectOption(pdf.id);
  await page.getByLabel("รูป PNG/JPEG ของฉัน").selectOption(image.id);
  await page.getByRole("button",{name:"เพิ่มลายน้ำรูปภาพ"}).click();
  await expect(page.getByText("รหัสงาน: watermark-job")).toBeVisible();
  expect(payloads).toEqual([{file_id:pdf.id,image_file_id:image.id,relative_width:.3,opacity:.2}]);
});

test("M21 denies enumeration without files:read",async({page})=>{
  test.skip(!enabled,"dev-only opt-in");
  await mock(page,false);
  let calls=0;
  await page.route("**/api/v1/files**",route=>{calls++;return route.abort();});
  await page.goto("/staged/image-watermark");
  await expect(page.getByRole("alert")).toContainText("files:read");
  expect(calls).toBe(0);
});
