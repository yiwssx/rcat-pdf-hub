import { notFound } from "next/navigation";
import { StagedRepairClient } from "./staged-repair-client";
import "../document-data/staged-document-data.css";

export const dynamic = "force-dynamic";

export default async function StagedRepairPage({
  searchParams,
}: {
  searchParams: Promise<{ file?: string | string[] }>;
}) {
  if (process.env.PDFHUB_STAGED_M32_REPAIR_WEB_ENABLED !== "true"
      || process.env.PDFHUB_PDF_REPAIR_STRUCTURE_TOOLS_ENABLED !== "true") notFound();
  const { file } = await searchParams;
  return <StagedRepairClient requestedFileId={typeof file === "string" ? file : undefined} />;
}
