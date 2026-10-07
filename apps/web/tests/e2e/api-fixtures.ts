export const authConfigFixture = {
  session_cookie: "pdfhub_session",
  oidc: { enabled: false, issuer: null, login_url: null },
  ldap: { enabled: false },
  web_console: { auto_login: true },
  local_admin: { enabled: false },
};

export const integrationStatusFixture = {
  storage_backend: "local",
  clamav_enabled: true,
  paperless_enabled: false,
  oidc_enabled: false,
  ldap_enabled: false,
  otel_enabled: false,
  prometheus_enabled: true,
};

export function operatorIdentityFixture(overrides: Record<string, unknown> = {}) {
  return {
    name: "web-console:test",
    display_name: "Web Console",
    subject: "test",
    scopes: ["files:read", "files:write", "jobs:read", "jobs:manage", "pdf:compress"],
    groups: [],
    roles: ["operator"],
    auth_source: "web-console",
    is_admin: false,
    ...overrides,
  };
}

export function emptyLibraryPage(requestUrl: string) {
  const url = new URL(requestUrl);
  return {
    items: [],
    total: 0,
    limit: Number(url.searchParams.get("limit") || "50"),
    offset: Number(url.searchParams.get("offset") || "0"),
    has_more: false,
  };
}
