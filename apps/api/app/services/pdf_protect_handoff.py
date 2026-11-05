"""M09: two PDF credentials in an encrypted, one-time Valkey handoff.

A dedicated M09 AEAD key and Redis namespace avoid cross-operation confusion
with M08. PostgreSQL, RQ and audit events receive only the opaque job ID.
"""
from __future__ import annotations

import base64
import json
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import get_settings
from app.queue import redis_conn
from app.services.pdf_access_control import _password
from app.services.pdf_unlock_handoff import JOB_ID, TTL_SECONDS, valid_handoff_key

PREFIX = "pdfhub:m09:passwords:"
MAX_PASSWORD_BYTES = 1024
MAX_CIPHERTEXT_BYTES = 4096


def _cipher() -> AESGCM:
    config = get_settings()
    if not config.protect_pdf_tools_enabled or not valid_handoff_key(config.protect_pdf_handoff_key):
        raise RuntimeError("M09 credential handoff not configured")
    return AESGCM(base64.urlsafe_b64decode(config.protect_pdf_handoff_key))


def _key(job_id: str) -> str:
    if not JOB_ID.fullmatch(job_id):
        raise ValueError("Invalid M09 job reference")
    return PREFIX + job_id


def _aad(job_id: str, owner: str, file_id: str) -> bytes:
    if not owner or not file_id:
        raise ValueError("Invalid M09 owner/source binding")
    return f"m09:protect:v1:{job_id}:{owner}:{file_id}".encode("utf-8")


def validate_credentials(user_password: str, owner_password: str) -> None:
    for name, value in (
        ("user_password", user_password),
        ("owner_password", owner_password),
    ):
        _password(value, name)
        if len(value.encode("utf-8")) > MAX_PASSWORD_BYTES:
            raise ValueError("M09 password byte budget exceeded")
    if user_password == owner_password:
        raise ValueError("M09 requires distinct user and owner passwords")


def publish_credentials(
    job_id: str, owner: str, file_id: str, *,
    user_password: str, owner_password: str,
) -> None:
    """AEAD ciphertext only; atomic NX/EX; never keep passwords in job args."""
    validate_credentials(user_password, owner_password)
    payload = json.dumps(
        {"user_password": user_password, "owner_password": owner_password},
        ensure_ascii=False, separators=(",", ":"),
    ).encode("utf-8")
    nonce = os.urandom(12)
    sealed = nonce + _cipher().encrypt(nonce, payload, _aad(job_id, owner, file_id))
    try:
        created = redis_conn.set(_key(job_id), sealed, nx=True, ex=TTL_SECONDS)
    except Exception:
        raise RuntimeError("M09 credential handoff unavailable") from None
    if created is not True:
        raise RuntimeError("M09 credentials already staged")


def take_credentials(job_id: str, owner: str, file_id: str) -> tuple[str, str]:
    """Consume once via GETDEL; no second chance after crash or wrong AAD."""
    cipher = _cipher()
    try:
        sealed = redis_conn.getdel(_key(job_id))
    except Exception:
        raise RuntimeError("M09 credential handoff unavailable") from None
    if not isinstance(sealed, bytes) or not 29 <= len(sealed) <= MAX_CIPHERTEXT_BYTES:
        raise ValueError("M09 credentials expired or already consumed")
    try:
        plaintext = cipher.decrypt(sealed[:12], sealed[12:], _aad(job_id, owner, file_id))
        decoded = json.loads(plaintext.decode("utf-8"))
        if not isinstance(decoded, dict) or set(decoded) != {"user_password", "owner_password"}:
            raise ValueError("M09 credential schema invalid")
        user_password = decoded["user_password"]
        owner_password = decoded["owner_password"]
        validate_credentials(user_password, owner_password)
        return user_password, owner_password
    except (InvalidTag, UnicodeDecodeError, ValueError, TypeError):
        raise ValueError("M09 credentials could not be verified") from None


def erase_credentials(job_id: str) -> None:
    """Best effort for failed submission or cancellation; expiry is fallback."""
    try:
        redis_conn.delete(_key(job_id))
    except Exception:
        return
