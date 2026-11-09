import { notFound } from "next/navigation";
import { StagedSplitZipClient } from "./staged-split-zip-client";
import "../document-data/staged-document-data.css";

export const dynamic = "force-dynamic";

// Three independent opt-in gates: never expose M07 as a side effect of merging.
export default async function StagedSplitZipPage({
  searchParams,
}: {
  searchParams: Promise<{ file?: string | string[] }>;
}) {
  if (
    process.env.PDFHUB_STAGED_SPLIT_ZIP_WEB_ENABLED !== "true" ||
    process.env.PDFHUB_SPLIT_ZIP_TOOLS_ENABLED !== "true" ||
    process.env.PDFHUB_MULTI_OUTPUT_ARTIFACTS_ENABLED !== "true"
  ) notFound();
  const { file } = await searchParams;
  return <StagedSplitZipClient requestedFileId={typeof file === "string" ? file : undefined} />;
}
