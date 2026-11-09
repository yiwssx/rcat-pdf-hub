import { notFound } from "next/navigation";
import { StagedPdfMarkupClient } from "./staged-pdf-markup-client";
import "../document-data/staged-document-data.css";
import "./markup.css";

export const dynamic = "force-dynamic";

export default async function StagedPdfMarkupPage({
  searchParams,
}: {
  searchParams: Promise<{ file?: string | string[]; tool?: string | string[] }>;
}) {
  if (process.env.PDFHUB_STAGED_MARKUP_WEB_ENABLED !== "true"
      || process.env.PDFHUB_PDF_MARKUP_TOOLS_ENABLED !== "true") notFound();
  const { file, tool } = await searchParams;
  return <StagedPdfMarkupClient
    requestedFileId={typeof file === "string" ? file : undefined}
    requestedToolId={typeof tool === "string" ? tool : undefined}
  />;
}
