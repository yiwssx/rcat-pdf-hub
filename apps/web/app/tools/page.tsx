import { PdfHubApp } from "../components/pdf-hub-app";

// Same server-side private T90 rollout gate as the existing home route.
// The explorer is a presentation surface; backend access checks remain authoritative.
export const dynamic = "force-dynamic";

export default function ToolsExplorerPage() {
  const t90CatalogEnabled = (
    process.env.PDFHUB_T90_CODE_ROLLOUT_ENABLED === "true"
    && process.env.PDFHUB_T90_PRIVATE_PILOT_ENABLED === "true"
  );
  return <PdfHubApp initialView="tools" t90CatalogEnabled={t90CatalogEnabled}/>;
}
