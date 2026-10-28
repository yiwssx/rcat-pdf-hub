/** Browser-side page-range preflight; backend qpdf validator remains authoritative.
 *
 * Accepts an endpoint number (1..100000) or 'z' (last page), optional
 * ascending/descending ranges and comma-separated selections.
 * The actual page count is sourced from the authenticated PDF page endpoint.
 */
const PAGE_ENDPOINT = /^(?:[1-9][0-9]{0,5}|z)$/;

export function validatePdfPageRange(value: string, totalPages: number | null): string | null {
  if (!value || value.length > 256) return "กรุณาระบุช่วงหน้าไม่เกิน 256 ตัวอักษร";
  const tokens = value.split(",");
  if (tokens.length < 1) return "ระบุหน้าที่ต้องการ";
  for (const token of tokens) {
    const endpoints = token.split("-");
    if (endpoints.length < 1 || endpoints.length > 2 || endpoints.some((part) => !PAGE_ENDPOINT.test(part))) {
      return "รูปแบบช่วงหน้าไม่ถูกต้อง เช่น 1,3-5 หรือ 1-z";
    }
    for (const endpoint of endpoints) {
      if (endpoint === "z") continue;
      const page = Number(endpoint);
      if (!Number.isSafeInteger(page) || page > 100000) return "เลขหน้าต้องอยู่ระหว่าง 1–100000";
      if (totalPages !== null && page > totalPages) return `ไม่มีหน้าที่ ${page} (เอกสารมี ${totalPages} หน้า)`;
    }
  }
  if (totalPages !== null && totalPages < 1) return "PDF ไม่มีหน้าเอกสาร";
  return null;
}
