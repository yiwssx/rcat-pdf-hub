import type { UploadedFile } from "../../lib/api";

type Kind = "pdf" | "image" | "office" | "any";

export type ToolInputRule = {
  kind: Kind;
  flow: "processing" | "sharing" | "archiving";
  pdfPreview: boolean;
  min: number;
  max?: number;
  accept?: string;
};

const PDF = ".pdf,application/pdf";
const IMAGE = ".jpg,.jpeg,.png,.webp,.tif,.tiff,.bmp,image/jpeg,image/png,image/webp,image/tiff,image/bmp";
const OFFICE = ".doc,.docx,.xls,.xlsx,.ppt,.pptx,.odt,.ods,.odp,.rtf";

export const TOOL_INPUT_RULES: Readonly<Record<string, ToolInputRule>> = {
  "ocr": { kind: "pdf", flow: "processing", pdfPreview: true, min: 1, max: 1, accept: PDF },
  "merge-pdf": { kind: "pdf", flow: "processing", pdfPreview: true, min: 2, accept: PDF },
  "split-rotate": { kind: "pdf", flow: "processing", pdfPreview: true, min: 1, max: 1, accept: PDF },
  "compress": { kind: "pdf", flow: "processing", pdfPreview: true, min: 1, max: 1, accept: PDF },
  "pdf-to-images": { kind: "pdf", flow: "processing", pdfPreview: true, min: 1, max: 1, accept: PDF },
  "images-to-pdf": { kind: "image", flow: "processing", pdfPreview: false, min: 1, accept: IMAGE },
  "watermark": { kind: "pdf", flow: "processing", pdfPreview: true, min: 1, max: 1, accept: PDF },
  "page-numbers": { kind: "pdf", flow: "processing", pdfPreview: true, min: 1, max: 1, accept: PDF },
  "pdfa": { kind: "pdf", flow: "processing", pdfPreview: true, min: 1, max: 1, accept: PDF },
  "office-to-pdf": { kind: "office", flow: "processing", pdfPreview: false, min: 1, max: 1, accept: OFFICE },
  "pdf-stamp": { kind: "pdf", flow: "processing", pdfPreview: true, min: 2, max: 2, accept: PDF },
  "signed-link": { kind: "any", flow: "sharing", pdfPreview: false, min: 1, max: 1 },
  "archive": { kind: "pdf", flow: "archiving", pdfPreview: true, min: 1, max: 1, accept: PDF },
};
const images = new Set(["image/jpeg", "image/png", "image/webp", "image/tiff", "image/bmp"]);
const officeExtensions = /\.(doc|docx|xls|xlsx|ppt|pptx|odt|ods|odp|rtf)$/i;

export function isEligibleToolFile(tool: string, file: UploadedFile): boolean {
  const rule = TOOL_INPUT_RULES[tool];
  if (!rule) return false;
  if (file.size <= 0) return false;
  const type = file.content_type.toLowerCase();
  switch (rule.kind) {
    case "pdf": return type === "application/pdf" || file.original_name.toLowerCase().endsWith(".pdf");
    case "image": return images.has(type);
    case "office": return officeExtensions.test(file.original_name);
    case "any": return true;
  }
}

export function validateToolInputs(tool: string, selected: UploadedFile[]): string | null {
  const rule = TOOL_INPUT_RULES[tool];
  if (!rule) return "ไม่รู้จักเครื่องมือ";
  if (new Set(selected.map((file) => file.id)).size !== selected.length) return "ไฟล์ที่เลือกซ้ำกัน";
  if (selected.length < rule.min) return `ต้องเลือกไฟล์อย่างน้อย ${rule.min} ไฟล์`;
  if (rule.max && selected.length > rule.max) return `เลือกได้ไม่เกิน ${rule.max} ไฟล์`;
  if (selected.some((file) => !isEligibleToolFile(tool, file))) return "พบไฟล์ไม่รองรับหรือไฟล์ว่างในชุดที่เลือก";
  return null;
}
