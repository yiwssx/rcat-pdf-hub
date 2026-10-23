"""T90 secured job artifact listing and legacy result compatibility."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app import security
from app.db import SessionLocal
from app.identity import create_session_token
from app.main import app
from app.models import FileRecord, JobOutputArtifact, JobRecord

ADMIN_KEY = "pdfh_ci_admin_key_change_me"
OWNER = "web-console:alpha"
OTHER = "web-console:other"


@pytest.fixture(autouse=True)
def bypass_external_rate_limit(monkeypatch):
    monkeypatch.setattr(security, "ensure_rate_limit", lambda *_a, **_kw: None)


def user_client(name=OWNER, *, scopes=None, admin=False):
    identity = {
        "name": name, "subject": name, "display_name": name,
        "groups": [], "scopes": scopes if scopes is not None else ["jobs:read", "files:read"],
        "source": "session", "is_identity_admin": admin,
    }
    client = TestClient(app)
    client.cookies.set("pdfhub_session", create_session_token(identity))
    return client


def seed(*, status="completed", links=True, foreign_child=False, expired_child=False, missing_primary=False):
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        bundle = FileRecord(
            original_name="converted-pages.zip", stored_name="t90-bundle.zip",
            content_type="application/zip", size=500, sha256="a"*64,
            source_system=OWNER, expires_at=now + timedelta(days=1),
        )
        first = FileRecord(
            original_name="page-0001.png", stored_name="t90-page-0001.png",
            content_type="image/png", size=100, sha256="b"*64,
            source_system=OWNER, expires_at=now + timedelta(days=1),
        )
        second = FileRecord(
            original_name="page-0002.png", stored_name="t90-page-0002.png",
            content_type="image/png", size=200, sha256="c"*64,
            source_system=OTHER if foreign_child else OWNER,
            expires_at=now - timedelta(hours=1) if expired_child else now + timedelta(days=1),
        )
        db.add_all([bundle, first, second])
        db.flush()
        job = JobRecord(
            operation="pdf-to-images", status=status, progress=100,
            input_file_ids_json="[]", params_json="{}",
            requested_by=OWNER, finished_at=now,
            output_file_id=None if missing_primary else bundle.id,
        )
        db.add(job)
        db.flush()
        if links:
            db.add_all([
                JobOutputArtifact(job_id=job.id, file_id=bundle.id, role="bundle", ordinal=None),
                JobOutputArtifact(job_id=job.id, file_id=first.id, role="part", ordinal=1),
                JobOutputArtifact(job_id=job.id, file_id=second.id, role="part", ordinal=2),
            ])
        db.commit()
        return job.id, bundle.id, first.id, second.id


def test_list_own_completed_parts_with_no_private_download_paths():
    job_id, primary, first, second = seed()
    res = user_client().get(f"/api/v1/jobs/{job_id}/artifacts")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["schema_version"] == "1.0.0"
    assert body["job_id"] == job_id
    assert body["status"] == "completed"
    assert body["primary_file_id"] == primary
    assert [a["file_id"] for a in body["artifacts"]] == [primary, first, second]
    assert [a["role"] for a in body["artifacts"]] == ["bundle", "part", "part"]
    assert [a["ordinal"] for a in body["artifacts"]] == [None, 1, 2]
    assert all(a["source_system"] == OWNER for a in body["artifacts"])
    assert all(set(a) == {"file_id","role","ordinal","file_name","content_type","size","sha256","source_system","expires_at"} for a in body["artifacts"])
    assert "stored_name" not in res.text and "download_url" not in res.text


def test_listing_denies_cross_user_even_identity_admin_wildcard():
    job_id, *_ = seed()
    assert user_client(OTHER).get(f"/api/v1/jobs/{job_id}/artifacts").status_code == 403
    assert user_client(OTHER, scopes=["*"], admin=True).get(f"/api/v1/jobs/{job_id}/artifacts").status_code == 403


def test_listing_denies_cross_user_even_bootstrap_wildcard():
    job_id, *_ = seed()
    assert TestClient(app).get(
        f"/api/v1/jobs/{job_id}/artifacts", headers={"X-API-Key": ADMIN_KEY}
    ).status_code == 403


def test_listing_requires_both_jobs_and_files_scope():
    job_id, *_ = seed()
    assert user_client(scopes=["jobs:read"]).get(f"/api/v1/jobs/{job_id}/artifacts").status_code == 403
    assert user_client(scopes=["files:read"]).get(f"/api/v1/jobs/{job_id}/artifacts").status_code == 403
    assert TestClient(app).get(f"/api/v1/jobs/{job_id}/artifacts").status_code == 401


def test_listing_rejects_unfinished_job():
    job_id, *_ = seed(status="running")
    assert user_client().get(f"/api/v1/jobs/{job_id}/artifacts").status_code == 409


def test_listing_rejects_foreign_child_even_when_job_owner_matches():
    job_id, *_ = seed(foreign_child=True)
    res = user_client().get(f"/api/v1/jobs/{job_id}/artifacts")
    assert res.status_code == 410
    assert "page-0002" not in res.text


def test_expired_parts_are_metadata_only_and_direct_download_is_gone():
    job_id, _, _, second = seed(expired_child=True)
    client = user_client()
    body = client.get(f"/api/v1/jobs/{job_id}/artifacts").json()
    assert len(body["artifacts"]) == 3
    assert next(a for a in body["artifacts"] if a["file_id"] == second)["expires_at"] is not None
    assert client.get(f"/api/v1/files/{second}/download").status_code == 410


def test_legacy_job_without_links_falls_back_to_owned_primary():
    job_id, primary, *_ = seed(links=False)
    body = user_client().get(f"/api/v1/jobs/{job_id}/artifacts")
    assert body.status_code == 200
    assert [(x["file_id"], x["role"]) for x in body.json()["artifacts"]] == [(primary, "bundle")]


def test_completed_job_with_deleted_primary_does_not_expose_parts():
    job_id, *_ = seed(missing_primary=True)
    assert user_client().get(f"/api/v1/jobs/{job_id}/artifacts").status_code == 410


def test_missing_primary_link_is_not_silently_recovered():
    job_id, primary, *_ = seed()
    with SessionLocal() as db:
        link = db.get(JobOutputArtifact, {"job_id": job_id, "file_id": primary})
        db.delete(link)
        db.commit()
    assert user_client().get(f"/api/v1/jobs/{job_id}/artifacts").status_code == 410


def test_corrupt_part_ordinals_fail_closed():
    job_id, _, _, second = seed()
    with SessionLocal() as db:
        link = db.get(JobOutputArtifact, {"job_id": job_id, "file_id": second})
        link.ordinal = 3
        db.commit()
    assert user_client().get(f"/api/v1/jobs/{job_id}/artifacts").status_code == 409


def test_lookup_unknown_job_returns_404():
    assert user_client().get("/api/v1/jobs/no-such-job/artifacts").status_code == 404
