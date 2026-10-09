import json
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
import pytest

from app import security
from app.db import SessionLocal
from app.identity import create_session_token
from app.main import app
from app.models import JobRecord


@pytest.fixture(autouse=True)
def disable_external_rate_limit(monkeypatch):
    monkeypatch.setattr(security, "ensure_rate_limit", lambda *args, **kwargs: None)


def seed_jobs():
    base = datetime(2026, 10, 9, 5, 0, tzinfo=timezone.utc)
    db = SessionLocal()
    rows = [
        ("alpha-new", "user:alpha", "running", 4),
        ("beta-new", "user:beta", "completed", 3),
        ("alpha-done", "user:alpha", "completed", 2),
        ("alpha-old", "user:alpha", "completed", 1),
    ]
    for suffix, owner, status, minutes in rows:
        db.add(JobRecord(
            id=f"job-{suffix}", operation="compress", status=status, progress=50,
            input_file_ids_json=json.dumps([]), params_json="{}",
            requested_by=owner, created_at=base + timedelta(minutes=minutes),
        ))
    db.commit()
    db.close()


def user_client(name="user:alpha"):
    client = TestClient(app)
    client.cookies.set("pdfhub_session", create_session_token({
        "name": name, "subject": name, "display_name": name,
        "groups": [], "scopes": ["jobs:read"],
        "source": "session", "is_identity_admin": False,
    }))
    return client


def test_my_jobs_filters_owner_even_with_admin_wildcard():
    seed_jobs()
    user = user_client()
    response = user.get("/api/v1/jobs", params={"mine": "true", "limit": 100})
    assert response.status_code == 200
    assert [row["id"] for row in response.json()] == [
        "job-alpha-new", "job-alpha-done", "job-alpha-old",
    ]
    assert all(row["requested_by"] == "user:alpha" for row in response.json())

    admin = TestClient(app)
    headers = {"X-API-Key": "pdfh_ci_admin_key_change_me"}
    all_jobs = admin.get("/api/v1/jobs", headers=headers, params={"limit": 100})
    assert all_jobs.status_code == 200
    assert len(all_jobs.json()) == 4
    admin_mine = admin.get("/api/v1/jobs", headers=headers, params={"mine": "true"})
    assert admin_mine.status_code == 200
    assert admin_mine.json() == []


def test_my_jobs_applies_status_filter_before_pagination():
    seed_jobs()
    user = user_client()
    first = user.get("/api/v1/jobs", params={
        "mine": "true", "status": "completed", "limit": 1, "offset": 0,
    })
    second = user.get("/api/v1/jobs", params={
        "mine": "true", "status": "completed", "limit": 1, "offset": 1,
    })
    assert [job["id"] for job in first.json()] == ["job-alpha-done"]
    assert [job["id"] for job in second.json()] == ["job-alpha-old"]


def test_my_jobs_bounds_and_permissions():
    seed_jobs()
    user = user_client()
    for params in ({"limit": 101}, {"offset": -1}, {"status": "unknown"}, {"offset": 100001}):
        assert user.get("/api/v1/jobs", params=params).status_code == 422

    anonymous = TestClient(app)
    assert anonymous.get("/api/v1/jobs", params={"mine": "true"}).status_code == 401



def test_job_detail_denies_foreign_and_missing_ids_and_rejects_invalid_state_actions():
    seed_jobs()
    viewer = user_client()
    owned = viewer.get("/api/v1/jobs/job-alpha-new")
    assert owned.status_code == 200
    assert owned.json()["requested_by"] == "user:alpha"

    foreign = viewer.get("/api/v1/jobs/job-beta-new")
    assert foreign.status_code == 403
    missing = viewer.get("/api/v1/jobs/no-such-job")
    assert missing.status_code == 404

    admin = TestClient(app)
    headers = {"X-API-Key": "pdfh_ci_admin_key_change_me"}
    assert admin.post("/api/v1/jobs/job-alpha-done/cancel", headers=headers).status_code == 409
    assert admin.post("/api/v1/jobs/job-alpha-new/retry", headers=headers).status_code == 409



def test_my_jobs_handler_query_branches_directly():
    """Exercise handler logic in-process as well as through the HTTP tests above."""
    from fastapi import HTTPException
    from app.security import Principal
    from app.routers.jobs import get_job, list_jobs

    seed_jobs()
    db = SessionLocal()
    try:
        user = Principal(name="user:alpha", scopes={"jobs:read"}, auth_source="session")
        completed = list_jobs(
            limit=1, offset=1, mine=True, status="completed", principal=user, db=db
        )
        assert [item.id for item in completed] == ["job-alpha-old"]

        all_own = list_jobs(
            limit=100, offset=0, mine=False, status=None, principal=user, db=db
        )
        assert [item.id for item in all_own] == [
            "job-alpha-new", "job-alpha-done", "job-alpha-old",
        ]

        admin = Principal(name="bootstrap-admin", scopes={"*"}, auth_source="bootstrap")
        admin_all = list_jobs(
            limit=100, offset=0, mine=False, status=None, principal=admin, db=db
        )
        assert len(admin_all) == 4
        admin_mine = list_jobs(
            limit=100, offset=0, mine=True, status=None, principal=admin, db=db
        )
        assert admin_mine == []

        assert get_job("job-alpha-new", principal=user, db=db).id == "job-alpha-new"
        with pytest.raises(HTTPException) as foreign:
            get_job("job-beta-new", principal=user, db=db)
        assert foreign.value.status_code == 403
        with pytest.raises(HTTPException) as missing:
            get_job("not-found", principal=user, db=db)
        assert missing.value.status_code == 404
    finally:
        db.close()
