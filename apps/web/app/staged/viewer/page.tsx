import { notFound } from "next/navigation";
import { StagedPdfViewerClient } from "./staged-pdf-viewer-client";
import "../document-data/staged-document-data.css";
import "./viewer.css";

export const dynamic = "force-dynamic";

// M20 is a read-only, authenticated viewer. The route is absent by default.
// A reviewed source merge must not activate the tool in RCAT Production.
export default async function StagedPdfViewerPage({
  searchParams,
}: {
  searchParams: Promise<{ file?: string | string[] }>;
}) {
  if (process.env.PDFHUB_STAGED_M20_VIEWER_WEB_ENABLED !== "true") notFound();
  const { file } = await searchParams;
  return (
    <StagedPdfViewerClient
      requestedFileId={typeof file === "string" ? file : undefined}
    />
  );
}
