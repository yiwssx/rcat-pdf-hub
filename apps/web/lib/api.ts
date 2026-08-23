export type UploadedFile = {
  id: string;
  original_name: string;
  content_type: string;
  size: number;
  sha256: string;
  source_system: string;
  created_at: string;
  expires_at: string | null;
};

export type Job = {
  id: string;
  operation: string;
  status: "queued" | "running" | "completed" | "failed";
  progress: number;
  input_file_ids: string[];
  output_file_id: string | null;
  params: Record<string, unknown>;
  error: string | null;
  requested_by: string;
};

export type ServicePolicy = {
  service_name: string;
  rate_limit_per_minute: number;
  daily_job_limit: number;
  max_storage_mb: number;
  webhook_url: string | null;
};

export type ApiKeyRecord = {
  id: string;
  name: string;
  scopes: string[];
  active: boolean;
  policy: ServicePolicy;
};

export type ApiKeyCreated = {
  id: string;
  name: string;
  api_key: string;
  scopes: string[];
  policy: ServicePolicy;
  webhook_secret: string | null;
};

export type AuditEvent = {
  timestamp: string;
  event: string;
  actor: string;
  resource_type: string | null;
  resource_id: string | null;
  details: Record<string, unknown>;
};

function headers(apiKey: string) {
  return { "X-API-Key": apiKey };
}

async function expectJson<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(await res.text());
  return res.json() as Promise<T>;
}

export async function uploadFile(file: File, apiKey: string): Promise<UploadedFile> {
  const form = new FormData();
  form.append("file", file);
  return expectJson<UploadedFile>(await fetch("/api/v1/files", { method: "POST", headers: headers(apiKey), body: form }));
}

export async function listFiles(apiKey: string): Promise<UploadedFile[]> {
  return expectJson<UploadedFile[]>(await fetch("/api/v1/files?limit=100", { headers: headers(apiKey), cache: "no-store" }));
}

export async function createJob(path: string, payload: object, apiKey: string): Promise<Job> {
  return expectJson<Job>(await fetch(`/api/v1/pdf/${path}`, {
    method: "POST",
    headers: { ...headers(apiKey), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }));
}

export async function listJobs(apiKey: string): Promise<Job[]> {
  return expectJson<Job[]>(await fetch("/api/v1/jobs?limit=50", { headers: headers(apiKey), cache: "no-store" }));
}

export async function fetchPreview(fileId: string, apiKey: string, page = 1, width = 900): Promise<Blob> {
  const res = await fetch(`/api/v1/files/${fileId}/preview?page=${page}&width=${width}`, {
    headers: headers(apiKey),
    cache: "no-store",
  });
  if (!res.ok) throw new Error(await res.text());
  return res.blob();
}

export async function fetchDownload(fileId: string, apiKey: string): Promise<Blob> {
  const res = await fetch(`/api/v1/files/${fileId}/download`, { headers: headers(apiKey) });
  if (!res.ok) throw new Error(await res.text());
  return res.blob();
}

export async function listApiKeys(apiKey: string): Promise<ApiKeyRecord[]> {
  return expectJson<ApiKeyRecord[]>(await fetch("/api/v1/admin/api-keys", { headers: headers(apiKey), cache: "no-store" }));
}

export async function createApiKey(payload: object, apiKey: string): Promise<ApiKeyCreated> {
  return expectJson<ApiKeyCreated>(await fetch("/api/v1/admin/api-keys", {
    method: "POST",
    headers: { ...headers(apiKey), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }));
}

export async function revokeApiKey(keyId: string, apiKey: string): Promise<ApiKeyRecord> {
  return expectJson<ApiKeyRecord>(await fetch(`/api/v1/admin/api-keys/${keyId}`, {
    method: "DELETE",
    headers: headers(apiKey),
  }));
}

export async function updateServicePolicy(policy: ServicePolicy, apiKey: string): Promise<ServicePolicy> {
  return expectJson<ServicePolicy>(await fetch(`/api/v1/admin/service-policies/${encodeURIComponent(policy.service_name)}`, {
    method: "PUT",
    headers: { ...headers(apiKey), "Content-Type": "application/json" },
    body: JSON.stringify({
      rate_limit_per_minute: policy.rate_limit_per_minute,
      daily_job_limit: policy.daily_job_limit,
      max_storage_mb: policy.max_storage_mb,
      webhook_url: policy.webhook_url || null,
    }),
  }));
}

export async function listAudit(apiKey: string): Promise<AuditEvent[]> {
  return expectJson<AuditEvent[]>(await fetch("/api/v1/admin/audit?limit=100", { headers: headers(apiKey), cache: "no-store" }));
}
