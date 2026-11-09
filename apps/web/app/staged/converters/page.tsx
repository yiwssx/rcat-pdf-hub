import { notFound } from "next/navigation";
import { StagedToPdfClient } from "./staged-to-pdf-client";
import "../document-data/staged-document-data.css";
import "./converters.css";

export const dynamic = "force-dynamic";

// Engineering-only route. OFF by default: never silently change the R1
// 9-tool catalog or make staged conversions public as a side effect of merge.
export default async function StagedConvertersPage({
  searchParams,
}: {
  searchParams: Promise<{ file?: string | string[]; tool?: string | string[] }>;
}) {
  if (
    process.env.PDFHUB_STAGED_TO_PDF_WEB_ENABLED !== "true" ||
    process.env.PDFHUB_TO_PDF_TOOLS_ENABLED !== "true"
  ) {
    notFound();
  }
  const { file, tool } = await searchParams;
  return (
    <StagedToPdfClient
      requestedFileId={typeof file === "string" ? file : undefined}
      requestedToolId={typeof tool === "string" ? tool : undefined}
    />
  );
}
