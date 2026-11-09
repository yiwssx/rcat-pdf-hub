import { notFound } from "next/navigation";
import { StagedImageOverlayClient } from "./staged-image-overlay-client";
import "../document-data/staged-document-data.css";
import "./image-overlay.css";

export const dynamic = "force-dynamic";

// No production exposure by code merge. UI and backend gates are independent.
export default async function StagedImageOverlayPage({
  searchParams,
}: {
  searchParams: Promise<{ file?: string | string[] }>;
}) {
  if (
    process.env.PDFHUB_STAGED_IMAGE_OVERLAY_WEB_ENABLED !== "true" ||
    process.env.PDFHUB_PDF_IMAGE_OVERLAY_TOOLS_ENABLED !== "true"
  ) notFound();
  const { file } = await searchParams;
  return (
    <StagedImageOverlayClient
      requestedFileId={typeof file === "string" ? file : undefined}
    />
  );
}
