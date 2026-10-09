import json

from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest

from app.db import SessionLocal
from app.main import app
from app.models import ApiKey, JobRecord, ServicePolicy, WebhookDelivery
from app.routers import admin as admin_router
from app.security import Principal


def admin_client():
    return TestClient(app), {"X-API-Key": "pdfh_ci_admin_key_change_me"}


def seed_integration():
    db = SessionLocal()
    try:
        key = ApiKey(name="test-integration", key_hash="h" * 64,
                     scopes_json=json.dumps(["jobs:read"]), active=True)
        policy = ServicePolicy(service_name="test-integration", rate_limit_per_minute=50,
                               daily_job_limit=10, max_storage_mb=200, webhook_url=None)
        job = JobRecord(operation="compress", status="completed", input_file_ids_json="[]",
                        params_json="{}", requested_by="test-integration")
        db.add_all([key, policy, job])
        db.commit()
        db.refresh(key)
        db.refresh(job)
        delivery = WebhookDelivery(job_id=job.id, service_name="test-integration",
                                   url="https://example.org/hook", event="job.completed", status="dead",
                                   attempt_count=3, last_error="private failure")
        db.add(delivery)
        db.commit()
        db.refresh(delivery)
        return key.id, delivery.id
    finally:
        db.close()


def test_admin_mutations_fail_closed_when_intent_audit_unavailable(monkeypatch):
    key_id, delivery_id = seed_integration()
    monkeypatch.setattr(admin_router, "audit_event", lambda *args, **kwargs: False)
    web, headers = admin_client()
    created = web.post("/api/v1/admin/api-keys", headers=headers, json={
        "name": "new-integration", "scopes": ["jobs:read"],
    })
    revoked = web.delete(f"/api/v1/admin/api-keys/{key_id}", headers=headers)
    changed = web.put("/api/v1/admin/service-policies/test-integration", headers=headers, json={
        "rate_limit_per_minute": 9, "daily_job_limit": 2, "max_storage_mb": 20,
        "webhook_url": None,
    })
    requeued = web.post(f"/api/v1/admin/webhook-deliveries/{delivery_id}/retry", headers=headers)
    for response in (created, revoked, changed, requeued):
        assert response.status_code == 503, response.text
        assert response.json()["detail"] == "Admin action audit unavailable"
    db = SessionLocal()
    try:
        assert db.get(ApiKey, key_id).active is True
        assert db.query(ApiKey).count() == 1
        assert db.get(ServicePolicy, "test-integration").rate_limit_per_minute == 50
        assert db.get(WebhookDelivery, delivery_id).status == "dead"
    finally:
        db.close()


def test_integration_actions_log_minimal_intent_before_mutation(monkeypatch):
    key_id, delivery_id = seed_integration()
    events = []
    monkeypatch.setattr(admin_router, "audit_event", lambda *args, **kwargs: events.append((args, kwargs)) or True)
    web, headers = admin_client()
    created = web.post("/api/v1/admin/api-keys", headers=headers, json={
        "name": "another-integration", "scopes": ["jobs:read"],
    })
    assert created.status_code == 200, created.text
    policy = web.put("/api/v1/admin/service-policies/test-integration", headers=headers, json={
        "rate_limit_per_minute": 40, "daily_job_limit": 9, "max_storage_mb": 190,
        "webhook_url": None,
    })
    assert policy.status_code == 200, policy.text
    replay = web.post(f"/api/v1/admin/webhook-deliveries/{delivery_id}/retry", headers=headers)
    assert replay.status_code == 200, replay.text
    revoke = web.delete(f"/api/v1/admin/api-keys/{key_id}", headers=headers)
    assert revoke.status_code == 200, revoke.text
    requested = [args for args, _ in events if args[0].endswith("_requested")]
    assert [args[0] for args in requested] == [
        "api_key.create_requested", "service_policy.update_requested",
        "webhook.requeue_requested", "api_key.revoke_requested",
    ]
    assert all("http" not in json.dumps(args[4]) and "pdfh_" not in json.dumps(args[4]) for args in requested)


def test_audit_guard_handler_direct_denies_when_audit_not_writable(monkeypatch):
    monkeypatch.setattr(admin_router, "audit_event", lambda *args, **kwargs: False)
    principal = Principal(name="local-admin:reviewer", scopes={"*"}, is_identity_admin=True,
                          roles={"admin"}, auth_source="local-admin")
    with pytest.raises(HTTPException) as raised:
        admin_router._require_admin_action_audit("service_policy.update_requested", principal,
                                                  "service_policy", "unit-test", {"count": 1})
    assert raised.value.status_code == 503
