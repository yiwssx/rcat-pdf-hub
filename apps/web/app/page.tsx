import { PdfHubApp } from "./components/pdf-hub-app";

// The private RCAT rollout is a runtime setting (NOT a NEXT_PUBLIC bundle
// constant). Preserve the nine-tool default when the opt-in overlay is absent.
export const dynamic = "force-dynamic";

export default function Home() {
  const t90CatalogEnabled = (
    process.env.PDFHUB_T90_CODE_ROLLOUT_ENABLED === "true"
    && process.env.PDFHUB_T90_PRIVATE_PILOT_ENABLED === "true"
  );
  return <PdfHubApp t90CatalogEnabled={t90CatalogEnabled} />;
}
