import { notFound } from "next/navigation";
import { StagedImageWatermarkClient } from "./staged-image-watermark-client";
import "../document-data/staged-document-data.css";
import "./image-watermark.css";

export const dynamic = "force-dynamic";

export default async function StagedImageWatermarkPage({
  searchParams,
}: {
  searchParams: Promise<{ file?: string | string[] }>;
}) {
  if (process.env.PDFHUB_STAGED_IMAGE_WATERMARK_WEB_ENABLED !== "true"
      || process.env.PDFHUB_PDF_IMAGE_WATERMARK_TOOLS_ENABLED !== "true") notFound();
  const { file } = await searchParams;
  return <StagedImageWatermarkClient requestedFileId={typeof file === "string" ? file : undefined} />;
}
