import { isAdminArea } from "../components/admin-area-nav";
import { PdfHubApp } from "../components/pdf-hub-app";

export default async function AdminPage({
  searchParams,
}: {
  searchParams: Promise<{ section?: string }>;
}) {
  const { section } = await searchParams;
  return <PdfHubApp initialView="admin" initialAdminArea={isAdminArea(section) ? section : "overview"}/>;
}
