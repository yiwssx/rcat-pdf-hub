import { notFound } from "next/navigation";
import { StagedDocumentDataClient } from "./staged-document-data-client";
import "./staged-document-data.css";

// Read flags per request; an OFF production build must never prerender the route.
export const dynamic = "force-dynamic";

export default async function StagedDocumentDataPage({
  searchParams,
}: {
  searchParams: Promise<{ file?: string | string[] }>;
}) {
  // Two explicit opt-in flags. Neither the normal /tools catalog nor
  // the public 13-operation route registry changes in this engineering phase.
  if (
    process.env.PDFHUB_STAGED_DOCUMENT_WEB_ENABLED !== "true" ||
    process.env.PDFHUB_DOCUMENT_DATA_TOOLS_ENABLED !== "true"
  ) {
    notFound();
  }
  const { file } = await searchParams;
  return <StagedDocumentDataClient requestedFileId={typeof file === "string" ? file : undefined} />;
}
