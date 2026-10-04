import hashlib
import hmac

from app.security import hash_api_key, new_api_key, settings


def test_new_api_key_format():
    key = new_api_key()
    assert key.startswith("pdfh_")
    assert len(key) > 30


def test_hash_is_stable_keyed_and_not_plaintext():
    value = "pdfh_test"
    digest = hash_api_key(value)
    expected = hmac.new(
        settings.api_key_pepper.encode("utf-8"),
        value.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    legacy = hashlib.sha256((settings.api_key_pepper + value).encode("utf-8")).hexdigest()

    assert digest == expected
    assert digest == hash_api_key(value)
    assert digest != value
    assert digest != legacy
