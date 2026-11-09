import { notFound } from "next/navigation";
import { StagedPdfAccessClient } from "./staged-pdf-access-client";
import "../document-data/staged-document-data.css";

export const dynamic = "force-dynamic";

// Never expose experimental password workflows in the nine-card RCAT pilot.
// Backend endpoints, secret handoffs and this Web route have independent gates.
export default async function StagedPdfAccessPage({
  searchParams,
}: {
  searchParams: Promise<{ file?: string | string[]; tool?: string | string[] }>;
}) {
  const unlock = process.env.PDFHUB_UNLOCK_PDF_TOOLS_ENABLED === "true";
  const protect = process.env.PDFHUB_PROTECT_PDF_TOOLS_ENABLED === "true";
  if (process.env.PDFHUB_STAGED_PDF_ACCESS_WEB_ENABLED !== "true" || (!unlock && !protect)) {
    notFound();
  }
  const { file, tool } = await searchParams;
  return (
    <StagedPdfAccessClient
      requestedFileId={typeof file === "string" ? file : undefined}
      requestedOperation={typeof tool === "string" ? tool : undefined}
      unlockEnabled={unlock}
      protectEnabled={protect}
    />
  );
}
