#!/usr/bin/env python3
"""Read-only R1 Compose runtime preflight; consumes config JSON on stdin.

Never prints raw configuration, identity credentials, DSNs or secret values.
Does not start/stop containers or contact any external endpoint.
"""
from __future__ import annotations

import json
import sys
from urllib.parse import urlparse

SERVICES = ("api", "worker-interactive", "worker", "worker-heavy")
REQUIRED = {
    "PDFHUB_RCAT_INSTITUTIONAL_ONLY": "true",
    "PDFHUB_OIDC_ENABLED": "true",
    "PDFHUB_OIDC_ISSUER": "https://accounts.google.com",
    "PDFHUB_LDAP_ENABLED": "false",
    "PDFHUB_SESSION_COOKIE_SECURE": "true",
    "PDFHUB_WEB_CONSOLE_AUTO_LOGIN": "false",
    "PDFHUB_CLAMAV_ENABLED": "true",
    "PDFHUB_CLAMAV_FAIL_CLOSED": "true",
    "PDFHUB_FROM_PDF_TOOLS_ENABLED": "false",
}
# These settings are intentionally not forwarded by the current Compose file.
# In the API they default to False; a missing Compose key therefore means OFF.
# If a future Compose file forwards a key, an explicit 'true' must fail closed.
# All T90 experimental capabilities remain disabled in the nine-tool R1.
# A newly forwarded Compose flag must not silently open an uncertified route.
# Missing keys are OFF because Settings defaults are False; explicit TRUE
# in API or any worker is rejected (and consistency is checked below).
OPTIONAL_OFF = (
    "PDFHUB_TO_PDF_TOOLS_ENABLED",
    "PDFHUB_MULTI_OUTPUT_ARTIFACTS_ENABLED",
    "PDFHUB_SPLIT_ZIP_TOOLS_ENABLED",
    "PDFHUB_EXTRACT_PAGES_TOOLS_ENABLED",
    "PDFHUB_EXTRACT_EMBEDDED_IMAGES_TOOLS_ENABLED",
    "PDFHUB_GRAYSCALE_PDF_TOOLS_ENABLED",
    "PDFHUB_HEADER_FOOTER_TOOLS_ENABLED",
    "PDFHUB_UNLOCK_PDF_TOOLS_ENABLED",
    "PDFHUB_PROTECT_PDF_TOOLS_ENABLED",
    "PDFHUB_DOCUMENT_DATA_TOOLS_ENABLED",
    "PDFHUB_GEOMETRY_TOOLS_ENABLED",
    "PDFHUB_PDF_FILLER_TOOLS_ENABLED",
    "PDFHUB_MANAGE_PAGE_TOOLS_ENABLED",
    "PDFHUB_PDF_TEXT_OVERLAY_TOOLS_ENABLED",
    "PDFHUB_PDF_IMAGE_OVERLAY_TOOLS_ENABLED",
    "PDFHUB_PDF_IMAGE_WATERMARK_TOOLS_ENABLED",
    "PDFHUB_PDF_REPAIR_STRUCTURE_TOOLS_ENABLED",
    "PDFHUB_PDF_EXTRACTIVE_ASSIST_TOOLS_ENABLED",
    "PDFHUB_PDF_EDIT_TEXT_TOOLS_ENABLED",
    "PDFHUB_PDF_TRANSLATION_TOOLS_ENABLED",
    "PDFHUB_PDF_MARKUP_TOOLS_ENABLED",
    "PDFHUB_PDF_FLATTEN_VISUAL_TOOLS_ENABLED",
    "PDFHUB_T90_PRIVATE_PILOT_ENABLED",
    "PDFHUB_CHM_NATIVE_DEV_ENABLED",
    "PDFHUB_HEIF_NATIVE_DEV_ENABLED",
    "PDFHUB_URL_TO_PDF_DEV_ENABLED",
    "PDFHUB_WPS_NATIVE_DEV_ENABLED",
    "PDFHUB_DWG_NATIVE_DEV_ENABLED",
)
# Code-first is an explicit second operating mode, not an implicit bypass
# of the existing nine-tool R1 security check. The static Compose marker
# comes exclusively from the opt-in production overlay.
T90_MARKER = "PDFHUB_T90_CODE_ROLLOUT_ENABLED"
T90_CORE_REQUIRED = frozenset({
    "PDFHUB_TO_PDF_TOOLS_ENABLED",
    "PDFHUB_MULTI_OUTPUT_ARTIFACTS_ENABLED",
    "PDFHUB_SPLIT_ZIP_TOOLS_ENABLED",
    "PDFHUB_EXTRACT_PAGES_TOOLS_ENABLED",
    "PDFHUB_EXTRACT_EMBEDDED_IMAGES_TOOLS_ENABLED",
    "PDFHUB_GRAYSCALE_PDF_TOOLS_ENABLED",
    "PDFHUB_HEADER_FOOTER_TOOLS_ENABLED",
    "PDFHUB_DOCUMENT_DATA_TOOLS_ENABLED",
    "PDFHUB_GEOMETRY_TOOLS_ENABLED",
    "PDFHUB_PDF_FILLER_TOOLS_ENABLED",
    "PDFHUB_MANAGE_PAGE_TOOLS_ENABLED",
    "PDFHUB_PDF_TEXT_OVERLAY_TOOLS_ENABLED",
    "PDFHUB_PDF_IMAGE_OVERLAY_TOOLS_ENABLED",
    "PDFHUB_PDF_IMAGE_WATERMARK_TOOLS_ENABLED",
    "PDFHUB_PDF_REPAIR_STRUCTURE_TOOLS_ENABLED",
    "PDFHUB_PDF_EXTRACTIVE_ASSIST_TOOLS_ENABLED",
    "PDFHUB_PDF_EDIT_TEXT_TOOLS_ENABLED",
    "PDFHUB_PDF_TRANSLATION_TOOLS_ENABLED",
    "PDFHUB_PDF_MARKUP_TOOLS_ENABLED",
    "PDFHUB_PDF_FLATTEN_VISUAL_TOOLS_ENABLED",
    "PDFHUB_T90_PRIVATE_PILOT_ENABLED",
})
T90_WEB_REQUIRED = (
    "PDFHUB_STAGED_TO_PDF_WEB_ENABLED",
    "PDFHUB_STAGED_FROM_PDF_WEB_ENABLED",
    "PDFHUB_STAGED_MANAGE_WEB_ENABLED",
    "PDFHUB_STAGED_TRANSLATION_WEB_ENABLED",
    "PDFHUB_STAGED_PDF_ACCESS_WEB_ENABLED",
    "PDFHUB_STAGED_DOCUMENT_ASSIST_WEB_ENABLED",
    "PDFHUB_STAGED_DOCUMENT_WEB_ENABLED",
    "PDFHUB_STAGED_GEOMETRY_WEB_ENABLED",
    "PDFHUB_STAGED_PDF_EDIT_WEB_ENABLED",
    "PDFHUB_STAGED_M24_FLATTEN_WEB_ENABLED",
    "PDFHUB_STAGED_IMAGE_OVERLAY_WEB_ENABLED",
    "PDFHUB_STAGED_IMAGE_WATERMARK_WEB_ENABLED",
    "PDFHUB_STAGED_MARKUP_WEB_ENABLED",
    "PDFHUB_STAGED_M32_REPAIR_WEB_ENABLED",
    "PDFHUB_STAGED_SIGNATURE_WEB_ENABLED",
    "PDFHUB_STAGED_SPLIT_ZIP_WEB_ENABLED",
    "PDFHUB_STAGED_M20_VIEWER_WEB_ENABLED",
)

CREDENTIALS = ("PDFHUB_OIDC_CLIENT_ID", "PDFHUB_OIDC_CLIENT_SECRET")


def normalize_environment(raw: object) -> dict[str, str]:
    if isinstance(raw, dict):
        return {k: str(v) for k, v in raw.items() if isinstance(k, str)}
    if isinstance(raw, list):
        result = {}
        for item in raw:
            if not isinstance(item, str) or "=" not in item:
                raise ValueError("Invalid Compose environment value")
            key, value = item.split("=", 1)
            result[key] = value
        return result
    raise ValueError("Missing Compose environment")


def inspect_compose(data: object) -> list[str]:
    """Return only nonsecret field names and diagnostic categories."""
    failures = []
    if not isinstance(data, dict) or not isinstance(data.get("services"), dict):
        return ["invalid_compose_json"]
    services = data["services"]
    envs = {}
    for name in SERVICES:
        service = services.get(name)
        if not isinstance(service, dict):
            failures.append("missing_service:" + name)
            continue
        try:
            envs[name] = normalize_environment(service.get("environment"))
        except ValueError:
            failures.append("missing_environment:" + name)
    if "api" not in envs:
        return failures
    api = envs["api"]
    marker = api.get(T90_MARKER, "false").lower()
    if marker not in {"true", "false"}:
        failures.append("invalid_code_rollout_marker")
    t90_code_first = marker == "true"
    for key, old_expected in REQUIRED.items():
        expected = ("true" if key == "PDFHUB_FROM_PDF_TOOLS_ENABLED" and t90_code_first
                    else old_expected)
        if api.get(key, "").lower() != expected.lower():
            failures.append("insecure_setting:" + key)
    for key in OPTIONAL_OFF:
        expected = "true" if t90_code_first and key in T90_CORE_REQUIRED else "false"
        if api.get(key, "false").lower() != expected:
            failures.append("insecure_setting:" + key)
    # A T90 code-first overlay never silently enables native decoders, their
    # distinct license boundaries or the URL fetcher's host-firewall policy.
    # M08/M09 remain OFF until non-repo AES-GCM handoff keys are provisioned.
    if t90_code_first:
        web = services.get("web")
        if not isinstance(web, dict):
            failures.append("missing_service:web")
        else:
            try:
                web_env = normalize_environment(web.get("environment"))
            except ValueError:
                failures.append("missing_environment:web")
            else:
                for key in (*T90_CORE_REQUIRED, "PDFHUB_FROM_PDF_TOOLS_ENABLED",
                            *T90_WEB_REQUIRED):
                    if web_env.get(key, "").lower() != "true":
                        failures.append("insecure_web_rollout_setting:" + key)
    for name in CREDENTIALS:
        value = api.get(name, "").strip()
        if not value or value.startswith("replace-"):
            failures.append("missing_credential:" + name)
    base = api.get("PDFHUB_PUBLIC_BASE_URL", "")
    url = urlparse(base)
    if not (url.scheme == "https" and url.hostname and
            (url.hostname == "rcat.ac.th" or url.hostname.endswith(".rcat.ac.th"))
            and not url.username and not url.password and url.port in (None, 443)):
        failures.append("unsafe_public_base_url")
    for name in SERVICES:
        if name not in envs or name == "api":
            continue
        env = envs[name]
        for key in (*REQUIRED, *OPTIONAL_OFF, *CREDENTIALS, T90_MARKER,
                    "PDFHUB_PUBLIC_BASE_URL"):
            if env.get(key, "") != api.get(key, ""):
                failures.append("service_environment_mismatch:" + name + ":" + key)
    return failures


def main() -> None:
    try:
        data = json.load(sys.stdin)
        failures = inspect_compose(data)
    except (ValueError, json.JSONDecodeError):
        print("R1 HOST PREFLIGHT: BLOCKED (invalid Compose JSON)", file=sys.stderr)
        raise SystemExit(2)
    if failures:
        print("R1 HOST PREFLIGHT: BLOCKED; no secrets printed", file=sys.stderr)
        for failure in sorted(set(failures)):
            print(" - " + failure, file=sys.stderr)
        raise SystemExit(1)
    print("RCAT HOST CONFIG: PASS (read-only, R1 or explicitly marked T90 "
          "code-first mode). Live OAuth, AV, Thai QA, backup and deployment "
          "success are NOT established by this check.")


if __name__ == "__main__":
    main()
