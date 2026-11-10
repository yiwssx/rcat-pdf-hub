"""M05 real local English/Thai model readiness probe, NOT a mock translation.

Only two fixed public sentences are sent; never source PDF or sensitive data.
The model container must be explicitly provisioned in a network without egress.
"""
from __future__ import annotations

import json

import httpx

from app.services import pdf_private_translation as private

MAX_LANGUAGES_JSON = 32 * 1024
MAX_TRANSLATION_JSON = 16 * 1024
PROBES = (
    ("en", "th", "The farmer measures soil moisture."),
    ("th", "en", "เกษตรกรตรวจสอบความชื้นในดิน"),
)


def _bounded_json(response: httpx.Response, limit: int):
    if response.status_code != 200:
        raise ValueError("M05 offline model service unavailable")
    if "application/json" not in response.headers.get("content-type", "").lower():
        raise ValueError("M05 offline model response is not JSON")
    data = bytearray()
    for chunk in response.iter_bytes():
        data.extend(chunk)
        if len(data) > limit:
            raise ValueError("M05 offline model response exceeds budget")
    try:
        return json.loads(data)
    except (UnicodeError, json.JSONDecodeError):
        raise ValueError("M05 offline model response is invalid JSON") from None


def probe_local_translation_model(
    transport: httpx.BaseTransport | None = None,
) -> tuple[str, str]:
    """Verify installed direct en->th and th->en paths with non-echoing output.

    Success is an API-level capability signal, not certified translation
    fidelity, model-package licensing, typography or document QA.
    """
    with httpx.Client(
        base_url=private.TRANSLATOR_ORIGIN,
        transport=transport,
        timeout=12.0,
        follow_redirects=False,
        trust_env=False,
    ) as client:
        try:
            with client.stream("GET", "/languages",
                               headers={"Accept": "application/json"}) as reply:
                rows = _bounded_json(reply, MAX_LANGUAGES_JSON)
            if not isinstance(rows, list) or not 2 <= len(rows) <= 200:
                raise ValueError("M05 offline languages list invalid")
            targets = {}
            for entry in rows:
                if not isinstance(entry, dict):
                    raise ValueError("M05 offline language entry invalid")
                code, to = entry.get("code"), entry.get("targets")
                if not isinstance(code, str) or not isinstance(to, list) or any(
                    not isinstance(item, str) for item in to
                ):
                    raise ValueError("M05 offline language targets invalid")
                targets[code] = set(to)
            if "th" not in targets.get("en", set()) or "en" not in targets.get("th", set()):
                raise ValueError("M05 requires directly available en/th and th/en offline models")

            for source, target, sample in PROBES:
                with client.stream(
                    "POST", "/translate",
                    json={"q": sample, "source": source,
                          "target": target, "format": "text"},
                    headers={"Accept": "application/json"},
                ) as reply:
                    payload = _bounded_json(reply, MAX_TRANSLATION_JSON)
                if not isinstance(payload, dict):
                    raise ValueError("M05 offline translation payload invalid")
                result = payload.get("translatedText")
                if (not isinstance(result, str) or not result.strip()
                        or len(result) > 4000 or result.strip() == sample):
                    raise ValueError("M05 offline model returned unusable translation")
                if target == "th" and not any("\u0e00" <= ch <= "\u0e7f" for ch in result):
                    raise ValueError("M05 offline English-to-Thai model returned no Thai text")
                if target == "en" and not any(ch.isascii() and ch.isalpha() for ch in result):
                    raise ValueError("M05 offline Thai-to-English model returned no English text")
        except httpx.HTTPError:
            raise ValueError("M05 offline model service unavailable") from None
    return "en->th", "th->en"


if __name__ == "__main__":
    try:
        directions = probe_local_translation_model()
    except ValueError as error:
        raise SystemExit(str(error)) from None
    print("M05 offline model: supported directions " + ", ".join(directions))
    print("M05 status: model API probe passed; document and license QA remain pending")
