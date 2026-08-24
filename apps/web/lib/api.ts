export const SESSION_AUTH = "__pdfhub_session__";

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

export type AuthConfig = {
  session_cookie: string;
  oidc: { enabled: boolean; issuer: string | null; login_url: string | null };
  ldap: { enabled: boolean };
  api_key: { enabled: boolean };
};

export type AuthMe = {
  name: string;
  display_name: string | null;
  subject: string | null;
  scopes: string[];
  groups: string[];
  auth_source: string;
  is_admin: boolean;
};

export type IntegrationStatus = {
  storage_backend: "local" | "s3";
  clamav_enabled: boolean;
  paperless_enabled: boolean;
  oidc_enabled: boolean;
  ldap_enabled: boolean;
  otel_enabled: boolean;
  prometheus_enabled: boolean;
};

export type ArchiveRecord = {
  id: string;
  file_id: string;
  integration_name: string;
  external_id: string | null;
  status: string;
  error: string | null;
  created_at: string;
  updated_at: string;
};

export type SignedDownload = {
  file_id: string;
  url: string;
  expires_at: string;
};

export type WebhookDelivery = {
  id: string;
  job_id: string;
  service_name: string;
  url: string;
  event: string;
  status: "queued" | "retrying" | "delivered" | "dead";
  attempt_count: number;
  max_attempts: number;
  next_attempt_at: string;
  last_error: string | null;
  last_status_code: number | null;
  created_at: string;
  updated_at: string;
  delivered_at: string | null;
};

function headers(auth: string): Record<string, string> {
  return auth === SESSION_AUTH ? {} : { "X-API-Key": auth };
}

async function expectJson<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(await res.text());
  return res.json() as Promise<T>;
}

function request(path: string, init: RequestInit = {}) {
  return fetch(path, { credentials: "same-origin", ...init });
}

export async function getAuthConfig(): Promise<AuthConfig> {
  return expectJson<AuthConfig>(await request("/api/v1/auth/config", { cache: "no-store" }));
}

export async function getMe(auth = SESSION_AUTH): Promise<AuthMe> {
  return expectJson<AuthMe>(await request("/api/v1/auth/me", { headers: headers(auth), cache: "no-store" }));
}

export async function ldapLogin(username: string, password: string): Promise<AuthMe> {
  return expectJson<AuthMe>(await request("/api/v1/auth/ldap/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  }));
}

export async function logoutSession(): Promise<void> {
  const res = await request("/api/v1/auth/logout", { method: "POST" });
  if (!res.ok) throw new Error(await res.text());
}

export async function getIntegrationStatus(auth: string): Promise<IntegrationStatus> {
  return expectJson<IntegrationStatus>(await request("/api/v1/integrations/status", {
    headers: headers(auth), cache: "no-store",
  }));
}

export async function uploadFile(file: File, auth: string): Promise<UploadedFile> {
  const form = new FormData();
  form.append("file", file);
  return expectJson<UploadedFile>(await request("/api/v1/files", { method: "POST", headers: headers(auth), body: form }));
}

export async function listFiles(auth: string): Promise<UploadedFile[]> {
  return expectJson<UploadedFile[]>(await request("/api/v1/files?limit=100", { headers: headers(auth), cache: "no-store" }));
}

export async function createJob(path: string, payload: object, auth: string): Promise<Job> {
  return expectJson<Job>(await request(`/api/v1/pdf/${path}`, {
    method: "POST",
    headers: { ...headers(auth), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }));
}

export async function listJobs(auth: string): Promise<Job[]> {
  return expectJson<Job[]>(await request("/api/v1/jobs?limit=50", { headers: headers(auth), cache: "no-store" }));
}

export async function fetchPreview(fileId: string, auth: string, page = 1, width = 900): Promise<Blob> {
  const res = await request(`/api/v1/files/${fileId}/preview?page=${page}&width=${width}`, {
    headers: headers(auth), cache: "no-store",
  });
  if (!res.ok) throw new Error(await res.text());
  return res.blob();
}

export async function fetchDownload(fileId: string, auth: string): Promise<Blob> {
  const res = await request(`/api/v1/files/${fileId}/download`, { headers: headers(auth) });
  if (!res.ok) throw new Error(await res.text());
  return res.blob();
}

export async function createSignedDownload(fileId: string, auth: string, ttlSeconds = 300): Promise<SignedDownload> {
  return expectJson<SignedDownload>(await request(`/api/v1/files/${fileId}/signed-download?ttl_seconds=${ttlSeconds}`, {
    method: "POST", headers: headers(auth),
  }));
}

export async function archiveToPaperless(fileId: string, auth: string): Promise<ArchiveRecord> {
  return expectJson<ArchiveRecord>(await request(`/api/v1/integrations/paperless/${fileId}`, {
    method: "POST", headers: headers(auth),
  }));
}

export async function listApiKeys(auth: string): Promise<ApiKeyRecord[]> {
  return expectJson<ApiKeyRecord[]>(await request("/api/v1/admin/api-keys", { headers: headers(auth), cache: "no-store" }));
}

export async function createApiKey(payload: object, auth: string): Promise<ApiKeyCreated> {
  return expectJson<ApiKeyCreated>(await request("/api/v1/admin/api-keys", {
    method: "POST",
    headers: { ...headers(auth), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }));
}

export async function revokeApiKey(keyId: string, auth: string): Promise<ApiKeyRecord> {
  return expectJson<ApiKeyRecord>(await request(`/api/v1/admin/api-keys/${keyId}`, {
    method: "DELETE", headers: headers(auth),
  }));
}

export async function updateServicePolicy(policy: ServicePolicy, auth: string): Promise<ServicePolicy> {
  return expectJson<ServicePolicy>(await request(`/api/v1/admin/service-policies/${encodeURIComponent(policy.service_name)}`, {
    method: "PUT",
    headers: { ...headers(auth), "Content-Type": "application/json" },
    body: JSON.stringify({
      rate_limit_per_minute: policy.rate_limit_per_minute,
      daily_job_limit: policy.daily_job_limit,
      max_storage_mb: policy.max_storage_mb,
      webhook_url: policy.webhook_url || null,
    }),
  }));
}

export async function listWebhookDeliveries(auth: string, status = ""): Promise<WebhookDelivery[]> {
  const query = status ? `?status=${encodeURIComponent(status)}&limit=100` : "?limit=100";
  return expectJson<WebhookDelivery[]>(await request(`/api/v1/admin/webhook-deliveries${query}`, {
    headers: headers(auth), cache: "no-store",
  }));
}

export async function retryWebhookDelivery(deliveryId: string, auth: string): Promise<WebhookDelivery> {
  return expectJson<WebhookDelivery>(await request(`/api/v1/admin/webhook-deliveries/${deliveryId}/retry`, {
    method: "POST", headers: headers(auth),
  }));
}

export async function listAudit(auth: string): Promise<AuditEvent[]> {
  return expectJson<AuditEvent[]>(await request("/api/v1/admin/audit?limit=100", { headers: headers(auth), cache: "no-store" }));
}
