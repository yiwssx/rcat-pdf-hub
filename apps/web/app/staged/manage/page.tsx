import { notFound } from "next/navigation";
import { StagedManageClient, type ManageId } from "./staged-manage-client";
import "../document-data/staged-document-data.css";
import "./manage.css";

export const dynamic = "force-dynamic";

// A source merge cannot activate tools: the entire Web route is default OFF.
// Individual backend gates are also OFF and continue to guard every operation.
export default async function StagedManagePage({
  searchParams,
}: {
  searchParams: Promise<{ file?: string | string[]; tool?: string | string[] }>;
}) {
  if (process.env.PDFHUB_STAGED_MANAGE_WEB_ENABLED !== "true") notFound();
  const { file, tool } = await searchParams;
  const backendFlags: Record<ManageId, boolean> = {
    M07: process.env.PDFHUB_SPLIT_ZIP_TOOLS_ENABLED === "true"
      && process.env.PDFHUB_MULTI_OUTPUT_ARTIFACTS_ENABLED === "true",
    M14: process.env.PDFHUB_MANAGE_PAGE_TOOLS_ENABLED === "true",
    M15: process.env.PDFHUB_MANAGE_PAGE_TOOLS_ENABLED === "true",
    M16: process.env.PDFHUB_EXTRACT_PAGES_TOOLS_ENABLED === "true",
    M18: process.env.PDFHUB_EXTRACT_EMBEDDED_IMAGES_TOOLS_ENABLED === "true",
    M22: process.env.PDFHUB_PDF_TEXT_OVERLAY_TOOLS_ENABLED === "true",
    M30: process.env.PDFHUB_GRAYSCALE_PDF_TOOLS_ENABLED === "true",
    M31: process.env.PDFHUB_HEADER_FOOTER_TOOLS_ENABLED === "true",
    M33: process.env.PDFHUB_PDF_FILLER_TOOLS_ENABLED === "true",
  };
  return <StagedManageClient
    requestedFileId={typeof file === "string" ? file : undefined}
    requestedToolId={typeof tool === "string" ? tool : undefined}
    enabledToolIds={(Object.keys(backendFlags) as ManageId[]).filter((id) => backendFlags[id])}
    allowMultiOutput={process.env.PDFHUB_MULTI_OUTPUT_ARTIFACTS_ENABLED === "true"}
  />;
}
