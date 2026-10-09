import { notFound } from "next/navigation";
import { PdfHubApp } from "../../components/pdf-hub-app";

export default async function FilePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  if (!id || id.length > 128 || !/^[A-Za-z0-9_-]+$/.test(id)) notFound();
  return <PdfHubApp initialView="file" initialFileId={id} />;
}
