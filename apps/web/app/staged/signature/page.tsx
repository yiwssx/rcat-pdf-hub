import { notFound } from "next/navigation";
import { StagedVisualSignatureClient } from "./staged-visual-signature-client";
import "../document-data/staged-document-data.css";
import "./signature.css";

export const dynamic = "force-dynamic";

// A visual signature uses M23's existing owner-scoped JPEG/PNG overlay engine.
// This does not produce a certificate-backed cryptographic PDF signature.
export default async function StagedVisualSignaturePage({
  searchParams,
}: {
  searchParams: Promise<{ file?: string | string[] }>;
}) {
  if (process.env.PDFHUB_STAGED_SIGNATURE_WEB_ENABLED !== "true"
      || process.env.PDFHUB_PDF_IMAGE_OVERLAY_TOOLS_ENABLED !== "true") notFound();
  const { file } = await searchParams;
  return <StagedVisualSignatureClient requestedFileId={typeof file === "string" ? file : undefined} />;
}
