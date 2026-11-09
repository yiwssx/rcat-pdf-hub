import { notFound } from "next/navigation";
import { StagedDocumentAssistClient } from "./staged-document-assist-client";
import "../document-data/staged-document-data.css";

export const dynamic = "force-dynamic";

// Both gates must explicitly opt in; ordinary nine-tool RCAT UX is unchanged.
export default async function StagedDocumentAssistPage({
  searchParams,
}: {
  searchParams: Promise<{ file?: string | string[]; tool?: string | string[] }>;
}) {
  if (process.env.PDFHUB_STAGED_DOCUMENT_ASSIST_WEB_ENABLED !== "true"
    || process.env.PDFHUB_PDF_EXTRACTIVE_ASSIST_TOOLS_ENABLED !== "true") notFound();
  const { file, tool } = await searchParams;
  return (
    <StagedDocumentAssistClient
      requestedFileId={typeof file === "string" ? file : undefined}
      requestedTool={typeof tool === "string" ? tool : undefined}
    />
  );
}
