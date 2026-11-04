import type { ToolDefinition } from "./v3-ui";

// Deliberately separate from the immutable 13-card T90-0 legacy registry.
// Only the explicit build-time M08 gate exposes this new tool.
export const M08_UNLOCK_TOOL: ToolDefinition = {
  id: "unlock-pdf",
  title: "ปลดล็อก PDF",
  description: "ปลดล็อกด้วยรหัสผ่านที่ได้รับอนุญาต ไม่จัดเก็บรหัสผ่าน",
  icon: "unlock",
  tone: "purple",
};
