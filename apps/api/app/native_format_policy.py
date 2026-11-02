"""Authoritative T90-2 native-development format policy.

Pure configuration mapping shared by upload validation, staged dispatch,
signed native sidecar and its isolated server. Never import filetypes or a
converter from this module: validation must not form an import cycle.
"""
from __future__ import annotations

from typing import Mapping

from app.config import get_settings

# MIME, original filename suffix, explicit development feature flag.
NATIVE_DEV_TO_PDF_INPUTS: Mapping[str, tuple[str, str, str]] = {
    "heic-to-pdf": ("image/heic", ".heic", "heif_native_dev_enabled"),
    "heif-to-pdf": ("image/heif", ".heif", "heif_native_dev_enabled"),
    "dwg-to-pdf": ("image/vnd.dwg", ".dwg", "dwg_native_dev_enabled"),
    "chm-to-pdf": ("application/vnd.ms-htmlhelp", ".chm", "chm_native_dev_enabled"),
    "wps-to-pdf": ("application/vnd.ms-works", ".wps", "wps_native_dev_enabled"),
}
NATIVE_DEV_TO_PDF_OPERATIONS = frozenset(NATIVE_DEV_TO_PDF_INPUTS)


def native_dev_enabled(operation: str) -> bool:
    spec = NATIVE_DEV_TO_PDF_INPUTS.get(operation)
    if spec is None:
        return False
    settings = get_settings()
    return bool(settings.to_pdf_tools_enabled and getattr(settings, spec[2], False))
