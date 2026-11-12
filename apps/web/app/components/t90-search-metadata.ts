/**
 * Presentation-only T90 search synonyms. Catalog route, ID, title and access
 * decisions remain authoritative in t90-directory-catalog and the API.
 */
const TERMS: Readonly<Record<string, string>> = {
  M01: "แก้ไข pdf แก้ข้อความ edit",
  M02: "บีบอัด ลดขนาด ย่อไฟล์ ไฟล์ใหญ่ compress",
  M03: "สรุป ย่อเนื้อหา summary",
  M04: "รวมไฟล์ รวมเอกสาร ผสาน merge",
  M05: "แปลเอกสาร แปลภาษา ไทย อังกฤษ translate",
  M06: "ถามตอบ ค้นคำตอบ เอกสาร ค้นข้อความ",
  M07: "แยกไฟล์ แยกหน้า split",
  M08: "ปลดล็อก รหัสผ่าน unlock password",
  M09: "เข้ารหัส ตั้งรหัสผ่าน ป้องกัน protect password",
  M10: "หมุนหน้า หมุนเอกสาร rotate",
  M11: "ครอบตัด ตัดขอบ crop",
  M12: "ลงลายมือชื่อ เซ็นเอกสาร ลายเซ็น sign",
  M13: "ข้อมูลเอกสาร metadata",
  M14: "ลบหน้า delete page",
  M15: "เรียงหน้า จัดลำดับหน้า reorder organize",
  M16: "ดึงหน้า แยกหน้า extract",
  M17: "ข้อความจาก pdf คัดลอกข้อความ text",
  M18: "ดึงรูปภาพ ภาพจาก pdf extract images",
  M19: "หมายเลขหน้า ใส่เลขหน้า page numbers",
  M20: "อ่าน pdf เปิด pdf ดูเอกสาร viewer",
  M21: "ลายน้ำ ข้อความบนเอกสาร watermark",
  M22: "เพิ่มข้อความ พิมพ์ข้อความ add text",
  M23: "แทรกรูปภาพ ใส่ภาพ add image",
  M24: "flatten แปลงเลเยอร์ คงรูป",
  M25: "เขียนกำกับ คำอธิบาย annotate",
  M26: "ไฮไลต์ เน้นข้อความ highlight",
  M27: "ลบข้อมูลเอกสาร remove metadata",
  M28: "ปรับขนาดกระดาษ resize page",
  M29: "ปิดทับข้อความ whiteout",
  M30: "ขาวดำ เทา grayscale",
  M31: "ส่วนหัว ส่วนท้าย header footer",
  M32: "ซ่อม pdf repair",
  M33: "กรอกแบบฟอร์ม เติมข้อมูล fill form",
  T01: "word เวิร์ด doc เอกสาร แปลงเป็น pdf",
  T05: "docx เวิร์ด word เอกสาร แปลงเป็น pdf",
  T02: "รูปภาพ ภาพ jpg jpeg แปลงเป็น pdf",
  T03: "รูปภาพ ภาพ png แปลงเป็น pdf",
  T06: "excel เอ็กเซล ตาราง xlsx แปลงเป็น pdf",
  T07: "powerpoint พาวเวอร์พอยท์ สไลด์ ppt แปลงเป็น pdf",
  T08: "powerpoint พาวเวอร์พอยท์ สไลด์ pptx แปลงเป็น pdf",
  F01: "ocr อ่านตัวหนังสือจากภาพ สแกนภาพ ถอดข้อความ ภาษาไทย",
  F02: "pdf เป็น word เวิร์ด แปลงจาก pdf",
  F03: "pdf เป็นรูปภาพ jpg jpeg แปลงจาก pdf",
  F04: "pdf เป็นรูปภาพ png แปลงจาก pdf",
  F07: "pdf เป็น excel ตาราง สเปรดชีต xlsx",
  F08: "pdf เป็น powerpoint สไลด์ ppt"
};

/** Curated shortcuts, not telemetry-based popularity assertions. */
export const FEATURED_T90_TOOL_IDS: readonly string[] = [
  "M04", "M02", "T01", "T06", "F01", "M07",
];

export function toolSearchTerms(toolId: string): string {
  return TERMS[toolId] ?? "";
}
