import hashlib
import hmac
import time
from dataclasses import dataclass

from app.config import get_settings

settings = get_settings()


@dataclass(frozen=True)
class SignedDownloadToken:
    expires: int
    token: str


def _message(file_id: str, owner: str, expires: int) -> bytes:
    return f"{file_id}\n{owner}\n{expires}".encode("utf-8")


def issue_signed_download(file_id: str, owner: str, ttl_seconds: int | None = None) -> SignedDownloadToken:
    ttl = ttl_seconds if ttl_seconds is not None else settings.signed_download_default_ttl_seconds
    if ttl < 30 or ttl > settings.signed_download_max_ttl_seconds:
        raise ValueError(
            f"ttl_seconds must be between 30 and {settings.signed_download_max_ttl_seconds}"
        )
    expires = int(time.time()) + ttl
    token = hmac.new(
        settings.download_signing_secret.encode("utf-8"),
        _message(file_id, owner, expires),
        hashlib.sha256,
    ).hexdigest()
    return SignedDownloadToken(expires=expires, token=token)


def verify_signed_download(file_id: str, owner: str, expires: int, token: str) -> bool:
    now = int(time.time())
    if expires <= now:
        return False
    if expires - now > settings.signed_download_max_ttl_seconds:
        return False
    expected = hmac.new(
        settings.download_signing_secret.encode("utf-8"),
        _message(file_id, owner, expires),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, token)
