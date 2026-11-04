"""M08: encrypted, single-use and short-lived password handoff.

Only an opaque job ID reaches PostgreSQL/RQ. Valkey holds ciphertext for
at most 5 minutes, never the plaintext PDF password. A distinct operator-
provisioned AEAD key is required on both API and Worker processes.
"""
from __future__ import annotations

import base64
import binascii
import os
import re

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import get_settings
from app.queue import redis_conn
from app.services.pdf_access_control import _password

TTL_SECONDS = 300
JOB_ID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z")
PREFIX = "pdfhub:m08:password:"


def valid_handoff_key(value: str) -> bool:
    if not isinstance(value, str) or len(value) != 44:
        return False
    try:
        raw = base64.b64decode(value, altchars=b"-_", validate=True)
    except (ValueError, binascii.Error):
        return False
    return len(raw) == 32 and base64.urlsafe_b64encode(raw).decode("ascii") == value


def _aead() -> AESGCM:
    config = get_settings()
    if not config.unlock_pdf_tools_enabled or not valid_handoff_key(config.unlock_pdf_handoff_key):
        raise RuntimeError("M08 password handoff not configured")
    return AESGCM(base64.urlsafe_b64decode(config.unlock_pdf_handoff_key))


def _key(job_id: str) -> str:
    if not JOB_ID.fullmatch(job_id):
        raise ValueError("Invalid M08 job reference")
    return PREFIX + job_id


def _aad(job_id: str, owner: str, file_id: str) -> bytes:
    if not owner or not file_id:
        raise ValueError("Invalid M08 owner/source binding")
    return f"m08:unlock:v1:{job_id}:{owner}:{file_id}".encode("utf-8")


def publish_password(job_id: str, owner: str, file_id: str, password: str) -> None:
    """Write only AEAD ciphertext, with atomic NX+TTL, before queue submission."""
    value = _password(password, "password")
    if len(value.encode("utf-8")) > 1024:
        raise ValueError("M08 password byte budget exceeded")
    nonce = os.urandom(12)
    encrypted = nonce + _aead().encrypt(nonce, value.encode("utf-8"), _aad(job_id, owner, file_id))
    try:
        created = redis_conn.set(_key(job_id), encrypted, nx=True, ex=TTL_SECONDS)
    except Exception:
        raise RuntimeError("M08 password handoff unavailable") from None
    if created is not True:
        raise RuntimeError("M08 password authorization already exists")


def take_password(job_id: str, owner: str, file_id: str) -> str:
    """Consume via atomic GETDEL. No retries or password lookup after this call."""
    aead = _aead()
    try:
        payload = redis_conn.getdel(_key(job_id))
    except Exception:
        raise RuntimeError("M08 password handoff unavailable") from None
    if not isinstance(payload, bytes) or len(payload) < 29 or len(payload) > 2048:
        raise ValueError("M08 password authorization expired or already used")
    try:
        raw = aead.decrypt(payload[:12], payload[12:], _aad(job_id, owner, file_id))
        value = raw.decode("utf-8")
        _password(value, "password")
        return value
    except (InvalidTag, UnicodeDecodeError, ValueError):
        raise ValueError("M08 password authorization could not be verified") from None


def erase_password(job_id: str) -> None:
    """Best effort on cancelled/failed submissions; TTL remains hard fallback."""
    try:
        redis_conn.delete(_key(job_id))
    except Exception:
        # Never log an exception that might contain Redis secret material.
        return
