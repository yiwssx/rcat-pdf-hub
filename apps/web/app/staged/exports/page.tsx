import { notFound } from "next/navigation";
import { StagedFromPdfClient } from "./staged-from-pdf-client";
import "../document-data/staged-document-data.css";
import "./exports.css";

export const dynamic = "force-dynamic";

// Source-only engineering route: invisible in default R1 deployments and
// independent of the To-PDF gate. A future operator must separately approve
// BOTH web and backend flags before use on a test host.
export default async function StagedExportsPage({
  searchParams,
}: {
  searchParams: Promise<{ file?: string | string[]; tool?: string | string[] }>;
}) {
  if (
    process.env.PDFHUB_STAGED_FROM_PDF_WEB_ENABLED !== "true" ||
    process.env.PDFHUB_FROM_PDF_TOOLS_ENABLED !== "true"
  ) {
    notFound();
  }
  const { file, tool } = await searchParams;
  return (
    <StagedFromPdfClient
      requestedFileId={typeof file === "string" ? file : undefined}
      requestedToolId={typeof tool === "string" ? tool : undefined}
    />
  );
}
