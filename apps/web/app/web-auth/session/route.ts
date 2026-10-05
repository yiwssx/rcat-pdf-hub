import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function POST() {
  const baseUrl = process.env.PDFHUB_INTERNAL_API_URL || "http://api:8000";
  let upstream: Response;

  try {
    upstream = await fetch(`${baseUrl}/internal/web-console/session`, {
      method: "POST",
      cache: "no-store",
    });
  } catch {
    return NextResponse.json({ detail: "PDF Hub API is unavailable" }, { status: 502 });
  }

  const body = await upstream.text();
  const response = new NextResponse(body || null, { status: upstream.status });
  const contentType = upstream.headers.get("content-type");
  const setCookie = upstream.headers.get("set-cookie");

  if (contentType) response.headers.set("content-type", contentType);
  if (setCookie) response.headers.set("set-cookie", setCookie);
  response.headers.set("cache-control", "no-store");
  return response;
}
