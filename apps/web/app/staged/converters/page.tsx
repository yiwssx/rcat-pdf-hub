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
  // Reuse the existing explicit per-format backend dev switches on the Web
  // staging host; none are enabled by default. Backend checks the same flags
  // again at API startup, queue dispatch and isolated native/URL sidecars.
  const enabledExperimentalIds: string[] = [];
  if (process.env.PDFHUB_HEIF_NATIVE_DEV_ENABLED === "true") {
    enabledExperimentalIds.push("T09", "T25");
  }
  if (process.env.PDFHUB_DWG_NATIVE_DEV_ENABLED === "true") enabledExperimentalIds.push("T20");
  if (process.env.PDFHUB_CHM_NATIVE_DEV_ENABLED === "true") enabledExperimentalIds.push("T30");
  if (process.env.PDFHUB_URL_TO_PDF_DEV_ENABLED === "true") enabledExperimentalIds.push("T33");
  if (process.env.PDFHUB_WPS_NATIVE_DEV_ENABLED === "true") enabledExperimentalIds.push("T34");
  const { file, tool } = await searchParams;
  return (
    <StagedToPdfClient
      requestedFileId={typeof file === "string" ? file : undefined}
      requestedToolId={typeof tool === "string" ? tool : undefined}
      enabledExperimentalIds={enabledExperimentalIds}
    />
  );
}
