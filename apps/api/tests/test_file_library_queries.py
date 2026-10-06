from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
import pytest

from app import security
from app.db import SessionLocal
from app.identity import create_session_token
from app.main import app
from app.models import FileRecord


ADMIN_KEY = "pdfh_ci_admin_key_change_me"


@pytest.fixture(autouse=True)
def disable_external_rate_limit(monkeypatch):
    monkeypatch.setattr(security, "ensure_rate_limit", lambda *args, **kwargs: None)


def _file(
    name: str,
    *,
    content_type: str,
    size: int,
    source: str,
    created_at: datetime,
    expires_at: datetime | None,
) -> FileRecord:
    return FileRecord(
        original_name=name,
        stored_name=f"{source.replace(':', '-')}-{name}",
        content_type=content_type,
        size=size,
        sha256=(name.encode("utf-8").hex() + "0" * 64)[:64],
        source_system=source,
        created_at=created_at,
        expires_at=expires_at,
    )


def _seed_library() -> None:
    now = datetime.now(timezone.utc)
    db = SessionLocal()
    db.add_all(
        [
            _file(
                "Alpha Report.pdf",
                content_type="application/pdf",
                size=300,
                source="user:alpha",
                created_at=now - timedelta(days=5),
                expires_at=None,
            ),
            _file(
                "Beta Report.pdf",
                content_type="application/pdf",
                size=100,
                source="user:alpha",
                created_at=now - timedelta(days=4),
                expires_at=now + timedelta(days=1),
            ),
            _file(
                "Gamma Scan.png",
                content_type="image/png",
                size=200,
                source="user:alpha",
                created_at=now - timedelta(days=3),
                expires_at=now + timedelta(days=1),
            ),
            _file(
                "Old Report.pdf",
                content_type="application/pdf",
                size=50,
                source="user:alpha",
                created_at=now - timedelta(days=2),
                expires_at=now - timedelta(days=1),
            ),
            _file(
                "Other.docx",
                content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                size=400,
                source="user:other",
                created_at=now - timedelta(days=1),
                expires_at=None,
            ),
        ]
    )
    db.commit()
    db.close()


def _user_client(name: str = "user:alpha") -> TestClient:
    identity = {
        "name": name,
        "subject": name,
        "display_name": name,
        "groups": [],
        "scopes": ["files:read"],
        "source": "session",
        "is_identity_admin": False,
    }
    client = TestClient(app)
    client.cookies.set("pdfhub_session", create_session_token(identity))
    return client


def test_library_query_search_filter_sort_and_pagination():
    _seed_library()
    client = TestClient(app)
    headers = {"X-API-Key": ADMIN_KEY}

    first = client.get(
        "/api/v1/files/library",
        params={"q": "report", "kind": "pdf", "sort": "name", "order": "asc", "limit": 1, "offset": 0},
        headers=headers,
    )
    assert first.status_code == 200
    payload = first.json()
    assert payload["total"] == 2
    assert payload["limit"] == 1
    assert payload["offset"] == 0
    assert payload["has_more"] is True
    assert [item["original_name"] for item in payload["items"]] == ["Alpha Report.pdf"]

    second = client.get(
        "/api/v1/files/library",
        params={"q": "report", "kind": "pdf", "sort": "name", "order": "asc", "limit": 1, "offset": 1},
        headers=headers,
    )
    assert second.status_code == 200
    assert second.json()["has_more"] is False
    assert [item["original_name"] for item in second.json()["items"]] == ["Beta Report.pdf"]

    with_expired = client.get(
        "/api/v1/files/library",
        params={"q": "report", "kind": "pdf", "include_expired": "true", "sort": "name", "order": "asc"},
        headers=headers,
    )
    assert with_expired.status_code == 200
    assert with_expired.json()["total"] == 3
    assert [item["original_name"] for item in with_expired.json()["items"]] == [
        "Alpha Report.pdf",
        "Beta Report.pdf",
        "Old Report.pdf",
    ]


def test_library_query_enforces_ownership_and_server_side_kind_filter():
    _seed_library()
    client = _user_client()

    response = client.get(
        "/api/v1/files/library",
        params={"sort": "size", "order": "desc"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 3
    assert [item["original_name"] for item in payload["items"]] == [
        "Alpha Report.pdf",
        "Gamma Scan.png",
        "Beta Report.pdf",
    ]
    assert all(item["source_system"] == "user:alpha" for item in payload["items"])

    images = client.get("/api/v1/files/library", params={"kind": "image"})
    assert images.status_code == 200
    assert images.json()["total"] == 1
    assert images.json()["items"][0]["original_name"] == "Gamma Scan.png"


def test_library_query_treats_search_wildcards_as_literal_and_validates_sort():
    _seed_library()
    client = TestClient(app)
    headers = {"X-API-Key": ADMIN_KEY}

    literal_wildcard = client.get("/api/v1/files/library", params={"q": "%"}, headers=headers)
    assert literal_wildcard.status_code == 200
    assert literal_wildcard.json()["total"] == 0

    invalid_sort = client.get("/api/v1/files/library", params={"sort": "unknown"}, headers=headers)
    assert invalid_sort.status_code == 422


def test_legacy_file_list_contract_remains_available():
    _seed_library()
    client = _user_client()

    response = client.get("/api/v1/files", params={"limit": 2, "offset": 0})
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert len(response.json()) == 2
