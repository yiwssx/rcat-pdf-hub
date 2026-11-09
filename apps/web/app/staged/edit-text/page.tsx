import { notFound } from "next/navigation";
import { StagedPdfTextEditorClient } from "./staged-pdf-text-editor-client";
import "../document-data/staged-document-data.css";
import "./edit-text.css";

export const dynamic = "force-dynamic";

// Not linked from the R1 nine-tool catalog. Both route and backend gates are OFF.
export default async function StagedPdfTextEditPage({
  searchParams,
}: {
  searchParams: Promise<{ file?: string | string[] }>;
}) {
  if (process.env.PDFHUB_STAGED_PDF_EDIT_WEB_ENABLED !== "true"
      || process.env.PDFHUB_PDF_EDIT_TEXT_TOOLS_ENABLED !== "true") notFound();
  const { file } = await searchParams;
  return <StagedPdfTextEditorClient requestedFileId={typeof file === "string" ? file : undefined} />;
}
