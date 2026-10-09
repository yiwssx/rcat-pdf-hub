import { notFound } from "next/navigation";
import { PdfHubApp } from "../../components/pdf-hub-app";
import { findPdfTool, PDF_TOOLS } from "../../components/tool-catalog";

export function generateStaticParams() {
  return PDF_TOOLS.map((tool) => ({ slug: tool.id }));
}

export default async function ToolPage({
  params,
  searchParams,
}: {
  params: Promise<{ slug: string }>;
  searchParams: Promise<{ file?: string | string[] }>;
}) {
  const { slug } = await params;
  const { file } = await searchParams;

  if (!findPdfTool(slug)) notFound();

  // A URL conveys intent, not authorization. PdfHubApp will only select
  // a file ID after the authenticated workspace has returned an owned file.
  return <PdfHubApp initialTool={slug} initialFileId={typeof file === "string" ? file : undefined} />;
}
