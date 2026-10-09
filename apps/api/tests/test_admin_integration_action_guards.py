import json

from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest

from app.db import SessionLocal
from app.main import app
from app.models import ApiKey, JobRecord, ServicePolicy, WebhookDelivery
from app.routers import admin as admin_router
from app.schemas import ServicePolicyUpdate
from app.security import hash_api_key, Principal


def admin_client():
    return TestClient(app), {"X-API-Key": "pdfh_ci_admin_key_change_me"}


def seed_services():
    db = SessionLocal()
    db.add_all([
        ApiKey(id="service-key-1", name="integration-service",
               key_hash=hash_api_key("pdfh_test_key"), scopes_json=json.dumps(["files:read"])),
        ServicePolicy(service_name="integration-service", rate_limit_per_minute=10,
                      daily_job_limit=20, max_storage_mb=300),
        JobRecord(id="webhook-job", operation="compress", status="completed",
                  input_file_ids_json="[]", params_json="{}",
                  requested_by="integration-service"),
        WebhookDelivery(id="delivery-1", job_id="webhook-job",
                        service_name="integration-service", url="https://example.com/hook",
                        event="job.completed", status="dead", attempt_count=3),
    ])
    db.commit()
    db.close()


def test_privileged_integration_mutations_fail_closed_on_unavailable_audit(monkeypatch):
    seed_services()
    monkeypatch.setattr(admin_router, "audit_event", lambda *args, **kwargs: False)
    client, headers = admin_client()
    create = client.post("/api/v1/admin/api-keys", headers=headers, json={
        "name": "another-key", "scopes": ["files:read"],
    })
    assert create.status_code == 503
    assert client.delete("/api/v1/admin/api-keys/service-key-1", headers=headers).status_code == 503
    update = client.put("/api/v1/admin/service-policies/integration-service",
                        headers=headers, json={
                            "rate_limit_per_minute": 55, "daily_job_limit": 60,
                            "max_storage_mb": 700, "webhook_url": None,
                        })
    assert update.status_code == 503
    assert client.post("/api/v1/admin/webhook-deliveries/delivery-1/retry",
                       headers=headers).status_code == 503

    db = SessionLocal()
    try:
        assert db.query(ApiKey).count() == 1
        assert db.get(ApiKey, "service-key-1").active is True
        policy = db.get(ServicePolicy, "integration-service")
        assert policy.rate_limit_per_minute == 10
        assert policy.daily_job_limit == 20
        delivery = db.get(WebhookDelivery, "delivery-1")
        assert delivery.status == "dead"
        assert delivery.attempt_count == 3
    finally:
        db.close()


def test_invalid_replay_state_refuses_without_audit(monkeypatch):
    seed_services()
    events = []
    monkeypatch.setattr(admin_router, "audit_event",
                        lambda event, *args, **kwargs: events.append(event) or True)
    db = SessionLocal()
    try:
        row = db.get(WebhookDelivery, "delivery-1")
        row.status = "delivered"
        db.commit()
    finally:
        db.close()
    client, headers = admin_client()
    response = client.post("/api/v1/admin/webhook-deliveries/delivery-1/retry", headers=headers)
    assert response.status_code == 409
    assert "webhook.requeue_requested" not in events


def test_integration_action_audit_intent_guard_direct(monkeypatch):
    calls = []
    monkeypatch.setattr(admin_router, "audit_event",
                        lambda event, *args, **kwargs: calls.append(event) or True)
    principal = Principal(name="bootstrap-admin", scopes={"*"}, auth_source="bootstrap")
    admin_router._require_action_audit("policy.intent", principal, "service_policy", "id1", {"safe": True})
    assert calls == ["policy.intent"]
    monkeypatch.setattr(admin_router, "audit_event", lambda *args, **kwargs: False)
    with pytest.raises(HTTPException) as error:
        admin_router._require_action_audit("policy.intent", principal, "service_policy", "id1", {})
    assert error.value.status_code == 503


def test_service_policy_intent_audited_before_change_direct(monkeypatch):
    seed_services()
    events = []
    monkeypatch.setattr(admin_router, "audit_event",
                        lambda event, *args, **kwargs: events.append(event) or True)
    db = SessionLocal()
    try:
        principal = Principal(name="bootstrap-admin", scopes={"*"}, auth_source="bootstrap")
        response = admin_router.update_service_policy(
            service_name="integration-service",
            req=ServicePolicyUpdate(rate_limit_per_minute=11, daily_job_limit=22,
                                    max_storage_mb=333, webhook_url=None),
            principal=principal, db=db)
        assert response.rate_limit_per_minute == 11
        assert events == ["service_policy.update_requested", "service_policy.updated"]
    finally:
        db.close()
