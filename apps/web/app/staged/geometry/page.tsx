import { notFound } from "next/navigation";
import { StagedGeometryClient } from "./staged-geometry-client";
import "../document-data/staged-document-data.css";
import "./geometry.css";

export const dynamic = "force-dynamic";

export default async function StagedGeometryPage({
  searchParams,
}: {
  searchParams: Promise<{ file?: string | string[]; tool?: string | string[] }>;
}) {
  if (
    process.env.PDFHUB_STAGED_GEOMETRY_WEB_ENABLED !== "true" ||
    process.env.PDFHUB_GEOMETRY_TOOLS_ENABLED !== "true"
  ) {
    notFound();
  }
  const { file, tool } = await searchParams;
  return <StagedGeometryClient requestedFileId={typeof file === "string" ? file : undefined} requestedToolId={typeof tool === "string" ? tool : undefined} />;
}
