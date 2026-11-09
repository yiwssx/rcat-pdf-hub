import { notFound } from "next/navigation";
import { StagedVisualFlattenClient } from "./staged-visual-flatten-client";
import "../document-data/staged-document-data.css";

export const dynamic = "force-dynamic";

export default async function StagedVisualFlattenPage({
  searchParams,
}: {
  searchParams: Promise<{ file?: string | string[] }>;
}) {
  if (process.env.PDFHUB_STAGED_M24_FLATTEN_WEB_ENABLED !== "true"
      || process.env.PDFHUB_PDF_FLATTEN_VISUAL_TOOLS_ENABLED !== "true") notFound();
  const { file } = await searchParams;
  return <StagedVisualFlattenClient requestedFileId={typeof file === "string" ? file : undefined} />;
}
