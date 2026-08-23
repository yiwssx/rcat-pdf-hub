from app.security import hash_api_key, new_api_key


def test_new_api_key_format():
    key = new_api_key()
    assert key.startswith("pdfh_")
    assert len(key) > 30


def test_hash_is_stable_and_not_plaintext():
    value = "pdfh_test"
    assert hash_api_key(value) == hash_api_key(value)
    assert hash_api_key(value) != value
