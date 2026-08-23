from app.webhooks import _host_allowed, derive_webhook_secret


def test_webhook_allowlist_matching():
    assert _host_allowed("system.example.org", ["system.example.org"])
    assert _host_allowed("api.internal.example.org", ["*.internal.example.org"])
    assert not _host_allowed("evil.example.net", ["*.internal.example.org"])


def test_webhook_secrets_are_stable_and_service_specific():
    first = derive_webhook_secret("student-system")
    assert first == derive_webhook_secret("student-system")
    assert first != derive_webhook_secret("finance-system")
    assert len(first) == 64
