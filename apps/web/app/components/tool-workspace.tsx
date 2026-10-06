"use client";

import { useEffect, useState } from "react";
import { IntegrationStatus, UploadedFile } from "../../lib/api";
import { ToolPanel } from "./tool-panel";

type ToolWorkspaceProps = {
  tool: string;
  auth: string;
  target: UploadedFile;
  pdfFiles: UploadedFile[];
  imageFiles: UploadedFile[];
  targetIsPdf: boolean;
  busy: boolean;
  integrations: IntegrationStatus | null;
  onSubmit: (operation: string, payload: object) => Promise<void>;
  onCreateSignedLink: (ttlSeconds: number) => Promise<string | null>;
  onArchive: () => Promise<void>;
  onMessage: (message: string) => void;
  onClose: () => void;
};

export function ToolWorkspace({
  tool,
  auth,
  target,
  pdfFiles,
  imageFiles,
  targetIsPdf,
  busy,
  integrations,
  onSubmit,
  onCreateSignedLink,
  onArchive,
  onMessage,
  onClose,
}: ToolWorkspaceProps) {
  const [signedUrl, setSignedUrl] = useState<string | null>(null);
  const [signedTtl, setSignedTtl] = useState(300);
  const [splitPages, setSplitPages] = useState("1-3");
  const [rotateDegrees, setRotateDegrees] = useState(90);
  const [rotatePages, setRotatePages] = useState("1-z");
  const [watermarkText, setWatermarkText] = useState("เอกสารภายใน");
  const [watermarkOpacity, setWatermarkOpacity] = useState(0.18);
  const [watermarkRotation, setWatermarkRotation] = useState(45);
  const [watermarkFontSize, setWatermarkFontSize] = useState(48);
  const [watermarkPosition, setWatermarkPosition] = useState("center");
  const [pageFormat, setPageFormat] = useState("หน้า {page} / {total}");
  const [pageStart, setPageStart] = useState(1);
  const [pagePosition, setPagePosition] = useState("bottom-center");
  const [stampId, setStampId] = useState("");
  const [stampPosition, setStampPosition] = useState("bottom-right");
  const [stampScale, setStampScale] = useState(0.2);
  const [imagePageSize, setImagePageSize] = useState("a4");
  const [imageFit, setImageFit] = useState("contain");
  const [imageDpi, setImageDpi] = useState(150);
  const [rasterFormat, setRasterFormat] = useState("png");
  const [rasterDpi, setRasterDpi] = useState(150);
  const [rasterFirstPage, setRasterFirstPage] = useState(1);
  const [rasterLastPage, setRasterLastPage] = useState("");
  const [mergeOrder, setMergeOrder] = useState<string[]>([]);

  useEffect(() => {
    setMergeOrder((old) => {
      const available = pdfFiles.map((file) => file.id);
      const kept = old.filter((id) => available.includes(id));
      return kept.length > 0 ? kept : available;
    });
  }, [pdfFiles]);

  useEffect(() => {
    setSignedUrl(null);
  }, [target.id]);

  async function run(operation: string) {
    if (!target.id && operation !== "merge" && operation !== "images-to-pdf") {
      onMessage("เลือกไฟล์ก่อน");
      return;
    }

    switch (operation) {
      case "merge":
        if (pdfFiles.length < 2) {
          onMessage("Merge ต้องมี PDF อย่างน้อย 2 ไฟล์");
          return;
        }
        await onSubmit("merge", {
          file_ids: mergeOrder.length ? mergeOrder : pdfFiles.map((file) => file.id),
        });
        return;
      case "images-to-pdf":
        if (imageFiles.length < 1) {
          onMessage("ต้องมีไฟล์ภาพอย่างน้อย 1 ไฟล์");
          return;
        }
        await onSubmit("images-to-pdf", {
          file_ids: imageFiles.map((file) => file.id),
          page_size: imagePageSize,
          fit: imageFit,
          margin: 18,
          dpi: imageDpi,
        });
        return;
      case "pdf-to-images":
        if (!targetIsPdf) {
          onMessage("PDF → รูปภาพ ต้องเลือกไฟล์ PDF");
          return;
        }
        await onSubmit("pdf-to-images", {
          file_id: target.id,
          format: rasterFormat,
          dpi: rasterDpi,
          first_page: rasterFirstPage,
          last_page: rasterLastPage ? Number(rasterLastPage) : null,
        });
        return;
      case "split":
        await onSubmit("split", { file_id: target.id, pages: splitPages });
        return;
      case "rotate":
        await onSubmit("rotate", {
          file_id: target.id,
          degrees: rotateDegrees,
          pages: rotatePages,
        });
        return;
      case "ocr":
        await onSubmit("ocr", {
          file_id: target.id,
          languages: "tha+eng",
          deskew: true,
          rotate_pages: true,
        });
        return;
      case "compress":
        await onSubmit("compress", { file_id: target.id });
        return;
      case "pdfa":
        await onSubmit("pdfa", {
          file_id: target.id,
          languages: "tha+eng",
          deskew: false,
          rotate_pages: false,
        });
        return;
      case "office-to-pdf":
        await onSubmit("office-to-pdf", { file_id: target.id });
        return;
      case "watermark":
        await onSubmit("watermark", {
          file_id: target.id,
          text: watermarkText,
          font_size: watermarkFontSize,
          opacity: watermarkOpacity,
          rotation: watermarkRotation,
          position: watermarkPosition,
          margin: 36,
        });
        return;
      case "page-numbers":
        await onSubmit("page-numbers", {
          file_id: target.id,
          format: pageFormat,
          start_number: pageStart,
          font_size: 10,
          position: pagePosition,
          margin: 24,
        });
        return;
      case "stamp":
        if (!stampId) {
          onMessage("เลือกไฟล์ PDF ที่จะใช้เป็นตราประทับก่อน");
          return;
        }
        await onSubmit("stamp", {
          file_id: target.id,
          stamp_file_id: stampId,
          position: stampPosition,
          scale: stampScale,
          margin: 24,
        });
        return;
      default:
        onMessage("ไม่รู้จัก operation");
    }
  }

  async function createSignedLink() {
    const url = await onCreateSignedLink(signedTtl);
    if (url) setSignedUrl(url);
  }

  async function copySignedLink() {
    if (!signedUrl) return;
    try {
      await navigator.clipboard.writeText(signedUrl);
      onMessage("คัดลอกลิงก์แล้ว");
    } catch {
      onMessage("คัดลอกอัตโนมัติไม่ได้");
    }
  }

  return (
    <ToolPanel
      tool={tool}
      auth={auth}
      target={target}
      pdfFiles={pdfFiles}
      imageFiles={imageFiles}
      targetIsPdf={targetIsPdf}
      busy={busy}
      integrations={integrations}
      signedUrl={signedUrl}
      signedTtl={signedTtl}
      splitPages={splitPages}
      rotateDegrees={rotateDegrees}
      rotatePages={rotatePages}
      watermarkText={watermarkText}
      watermarkOpacity={watermarkOpacity}
      watermarkRotation={watermarkRotation}
      watermarkFontSize={watermarkFontSize}
      watermarkPosition={watermarkPosition}
      pageFormat={pageFormat}
      pageStart={pageStart}
      pagePosition={pagePosition}
      stampId={stampId}
      stampPosition={stampPosition}
      stampScale={stampScale}
      imagePageSize={imagePageSize}
      imageFit={imageFit}
      imageDpi={imageDpi}
      rasterFormat={rasterFormat}
      rasterDpi={rasterDpi}
      rasterFirstPage={rasterFirstPage}
      rasterLastPage={rasterLastPage}
      mergeOrder={mergeOrder}
      setSignedTtl={setSignedTtl}
      setSplitPages={setSplitPages}
      setRotateDegrees={setRotateDegrees}
      setRotatePages={setRotatePages}
      setWatermarkText={setWatermarkText}
      setWatermarkOpacity={setWatermarkOpacity}
      setWatermarkRotation={setWatermarkRotation}
      setWatermarkFontSize={setWatermarkFontSize}
      setWatermarkPosition={setWatermarkPosition}
      setPageFormat={setPageFormat}
      setPageStart={setPageStart}
      setPagePosition={setPagePosition}
      setStampId={setStampId}
      setStampPosition={setStampPosition}
      setStampScale={setStampScale}
      setImagePageSize={setImagePageSize}
      setImageFit={setImageFit}
      setImageDpi={setImageDpi}
      setRasterFormat={setRasterFormat}
      setRasterDpi={setRasterDpi}
      setRasterFirstPage={setRasterFirstPage}
      setRasterLastPage={setRasterLastPage}
      setMergeOrder={setMergeOrder}
      onRun={(operation) => void run(operation)}
      onSignedLink={() => void createSignedLink()}
      onCopySignedLink={() => void copySignedLink()}
      onArchive={() => void onArchive()}
      onOrganize={(pages) => void onSubmit("organize", { file_id: target.id, pages })}
      onClose={onClose}
    />
  );
}
