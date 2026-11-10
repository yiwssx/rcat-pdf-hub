"""M05 real offline model capability probe, mocked transport only in CI."""
import json

import httpx
import pytest

from app.services import m05_offline_model_probe as probe


def _transport(*, targets=True, echo=False, status=None, bad_mime=False):
    calls = []

    def reply(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.host, request.url.path))
        if status:
            return httpx.Response(status, json={"error": "unavailable"})
        if request.url.path == "/languages":
            return httpx.Response(200, json=[
                {"code": "en", "targets": ["th"] if targets else []},
                {"code": "th", "targets": ["en"] if targets else []},
            ])
        assert request.url.path == "/translate"
        body = json.loads(request.content)
        expected = next(pair for pair in probe.PROBES if pair[0] == body["source"])
        assert (body["source"], body["target"], body["q"]) == expected
        translated = body["q"] if echo else (
            "เกษตรกรวัดความชื้นในดิน" if body["target"] == "th"
            else "The farmer examines soil moisture."
        )
        if bad_mime:
            return httpx.Response(200, text=translated)
        return httpx.Response(200, json={"translatedText": translated})

    return httpx.MockTransport(reply), calls


def test_real_direction_probe_uses_only_private_endpoint():
    transport, calls = _transport()
    assert probe.probe_local_translation_model(transport) == ("en->th", "th->en")
    assert calls == [
        ("GET", "pdf-translate", "/languages"),
        ("POST", "pdf-translate", "/translate"),
        ("POST", "pdf-translate", "/translate"),
    ]


@pytest.mark.parametrize("options,error", [
    ({"targets": False}, "directly available"),
    ({"echo": True}, "unusable translation"),
    ({"status": 503}, "unavailable"),
    ({"bad_mime": True}, "not JSON"),
])
def test_missing_model_or_fake_response_is_refused(options, error):
    transport, _ = _transport(**options)
    with pytest.raises(ValueError, match=error):
        probe.probe_local_translation_model(transport)


def test_source_only_overlay_is_gated_and_has_no_model_egress():
    from pathlib import Path
    overlay = Path(__file__).resolve().parents[3] / "compose.translation.dev.yaml"
    text = overlay.read_text(encoding="utf-8")
    assert "profiles: [m05-offline-dev]" in text
    assert "approved immutable libretranslate image digest required" in text
    assert "internal: true" in text
    assert "read_only: true" in text
    assert 'LT_UPDATE_MODELS: "false"' in text
    assert 'LT_LOAD_ONLY: "en,th"' in text
    assert "    ports:" not in text
    assert "PDFHUB_M05_LIBRETRANSLATE_IMAGE" in text



def test_m05_authenticated_readiness_is_default_off_and_fails_closed(monkeypatch):
    from fastapi import HTTPException
    from app.routers import pdf_private_translation as router

    monkeypatch.setattr(router, "settings", router.settings.model_copy(update={
        "pdf_translation_tools_enabled": False,
    }))
    with pytest.raises(HTTPException) as err:
        router.translation_readiness(principal=object())
    assert err.value.status_code == 404

    monkeypatch.setattr(router, "settings", router.settings.model_copy(update={
        "pdf_translation_tools_enabled": True,
    }))
    monkeypatch.setattr(probe, "probe_local_translation_model", lambda: ("en->th", "th->en"))
    assert router.translation_readiness(principal=object()).available is True

    def unavailable():
        raise ValueError("Internal service unavailable")
    monkeypatch.setattr(probe, "probe_local_translation_model", unavailable)
    failure = router.translation_readiness(principal=object())
    assert failure.available is False
    assert "unavailable" in failure.note
    assert "Internal service unavailable" not in failure.note
