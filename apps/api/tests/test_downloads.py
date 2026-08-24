import pytest

from app.config import get_settings
from app.downloads import issue_signed_download, verify_signed_download


def test_signed_download_token_is_bound_to_file_and_owner():
    signed = issue_signed_download("file-1", "student-system", 60)
    assert verify_signed_download("file-1", "student-system", signed.expires, signed.token)
    assert not verify_signed_download("file-2", "student-system", signed.expires, signed.token)
    assert not verify_signed_download("file-1", "finance-system", signed.expires, signed.token)
    assert not verify_signed_download("file-1", "student-system", signed.expires, "0" * 64)


def test_signed_download_rejects_ttl_beyond_configured_maximum():
    settings = get_settings()
    with pytest.raises(ValueError):
        issue_signed_download("file-1", "student-system", settings.signed_download_max_ttl_seconds + 1)
