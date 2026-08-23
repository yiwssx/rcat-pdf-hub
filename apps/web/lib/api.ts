export type UploadedFile = {
  id: string;
  original_name: string;
  size: number;
  sha256: string;
};

export type Job = {
  id: string;
  operation: string;
  status: "queued" | "running" | "completed" | "failed";
  progress: number;
  output_file_id: string | null;
  error: string | null;
};

function headers(apiKey: string) {
  return { "X-API-Key": apiKey };
}

export async function uploadFile(file: File, apiKey: string): Promise<UploadedFile> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch("/api/v1/files", { method: "POST", headers: headers(apiKey), body: form });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function createJob(path: string, payload: object, apiKey: string): Promise<Job> {
  const res = await fetch(`/api/v1/pdf/${path}`, {
    method: "POST",
    headers: { ...headers(apiKey), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function listJobs(apiKey: string): Promise<Job[]> {
  const res = await fetch("/api/v1/jobs?limit=20", { headers: headers(apiKey), cache: "no-store" });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export function downloadUrl(fileId: string) {
  return `/api/v1/files/${fileId}/download`;
}
