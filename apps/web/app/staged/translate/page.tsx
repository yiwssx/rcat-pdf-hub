import { notFound } from "next/navigation";
import { StagedTranslationClient } from "./staged-translation-client";
import "../document-data/staged-document-data.css";

export const dynamic = "force-dynamic";

export default async function StagedTranslationPage({
  searchParams,
}: {
  searchParams: Promise<{ file?: string | string[] }>;
}) {
  if (process.env.PDFHUB_STAGED_TRANSLATION_WEB_ENABLED !== "true"
      || process.env.PDFHUB_PDF_TRANSLATION_TOOLS_ENABLED !== "true") notFound();
  const { file } = await searchParams;
  return <StagedTranslationClient requestedFileId={typeof file === "string" ? file : undefined} />;
}
