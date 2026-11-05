import type { ToolDefinition } from "./v3-ui";

// Deliberately separate from the immutable 13-card T90-0 legacy registry.
// Each staged tool has its own explicit build-time opt-in gate.
export const M18_EXTRACT_IMAGES_TOOL: ToolDefinition = {
  id: "extract-images",
  title: "ดึงรูปภาพจาก PDF",
  description: "ดึงภาพ PNG/JPEG ที่ฝังอยู่ใน PDF จริง ไม่ใช่ภาพหน้ากระดาษ",
  icon: "image",
  tone: "cyan",
};

export const M08_UNLOCK_TOOL: ToolDefinition = {
  id: "unlock-pdf",
  title: "ปลดล็อก PDF",
  description: "ปลดล็อกด้วยรหัสผ่านที่ได้รับอนุญาต ไม่จัดเก็บรหัสผ่าน",
  icon: "unlock",
  tone: "purple",
};

export const M09_PROTECT_TOOL: ToolDefinition = {
  id: "protect-pdf",
  title: "ป้องกัน PDF ด้วยรหัสผ่าน",
  description: "เข้ารหัส AES-256 โดยตั้งรหัสผ่านสำหรับเปิดและรหัสผ่านเจ้าของเอกสาร",
  icon: "unlock",
  tone: "indigo",
};
