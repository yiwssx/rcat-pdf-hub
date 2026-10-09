import type { ToolDefinition } from "./v3-ui";

// Stable public slugs. Keep this catalog independent of auth and upload state.
export const PDF_TOOLS: readonly ToolDefinition[] = [
  { id: "ocr", title: "สแกน / OCR", description: "อ่านข้อความไทย + อังกฤษจากเอกสาร", icon: "scan", tone: "rose", badge: "ยอดนิยม" },
  { id: "merge-pdf", title: "รวม PDF", description: "รวมหลายไฟล์เป็นเอกสารเดียว", icon: "merge", tone: "blue" },
  { id: "split-rotate", title: "จัดหน้า PDF", description: "เลือก แยก และหมุนหน้า", icon: "organize", tone: "violet" },
  { id: "compress", title: "ลดขนาด PDF", description: "บีบอัดไฟล์สำหรับส่งและจัดเก็บ", icon: "compress", tone: "amber" },
  { id: "pdf-to-images", title: "PDF → รูปภาพ", description: "ส่งออกหน้าเอกสารเป็น PNG/JPEG", icon: "image", tone: "red" },
  { id: "images-to-pdf", title: "รูปภาพ → PDF", description: "รวมรูปภาพหลายไฟล์เป็น PDF", icon: "imagePdf", tone: "cyan" },
  { id: "watermark", title: "ลายน้ำ", description: "เพิ่มข้อความลายน้ำภาษาไทย", icon: "watermark", tone: "pink" },
  { id: "page-numbers", title: "เลขหน้า", description: "ใส่เลขหน้าและกำหนดตำแหน่ง", icon: "numbers", tone: "indigo" },
  { id: "pdfa", title: "PDF/A-2", description: "แปลงเพื่อจัดเก็บระยะยาว", icon: "pdfa", tone: "green" },
  { id: "office-to-pdf", title: "Office → PDF", description: "แปลง Word, Excel และ PowerPoint", icon: "office", tone: "orange" },
  { id: "pdf-stamp", title: "ประทับ PDF", description: "วางตราประทับจาก PDF อีกไฟล์", icon: "stamp", tone: "purple" },
  { id: "signed-link", title: "ลิงก์ดาวน์โหลด", description: "สร้างลิงก์ชั่วคราวเพื่อแชร์ไฟล์", icon: "link", tone: "sky" },
  { id: "archive", title: "คลังเอกสาร", description: "ส่งเอกสารเข้า Paperless", icon: "archive", tone: "teal" },
];

export function findPdfTool(slug: string): ToolDefinition | undefined {
  return PDF_TOOLS.find((tool) => tool.id === slug);
}
