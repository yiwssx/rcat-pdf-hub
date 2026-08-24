from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import JobRecord, ServicePolicy, WebhookDelivery
from app.webhooks import deliver_webhook, queue_job_webhook, retry_dead_webhook


def test_webhook_delivery_retries_then_moves_to_dead_letter_queue():
    db = SessionLocal()
    try:
        policy = ServicePolicy(
            service_name="student-system",
            rate_limit_per_minute=120,
            daily_job_limit=1000,
            max_storage_mb=2048,
            webhook_url="https://hooks.example.org/pdfhub",
        )
        job = JobRecord(
            operation="merge",
            status="completed",
            progress=100,
            input_file_ids_json="[]",
            params_json="{}",
            requested_by="student-system",
        )
        db.add_all([policy, job])
        db.commit()
        db.refresh(job)

        delivery = queue_job_webhook(db, job)
        assert delivery is not None
        duplicate = queue_job_webhook(db, job)
        assert duplicate is not None
        assert duplicate.id == delivery.id
        assert db.scalar(select(func.count()).select_from(WebhookDelivery)) == 1

        delivery.max_attempts = 2
        db.commit()

        # No webhook allowlist is configured in unit tests, so delivery fails safely
        # without making an outbound network request.
        assert not deliver_webhook(db, delivery)
        assert delivery.status == "retrying"
        assert delivery.attempt_count == 1

        assert not deliver_webhook(db, delivery)
        assert delivery.status == "dead"
        assert delivery.attempt_count == 2
        assert delivery.last_error

        retry_dead_webhook(db, delivery, "bootstrap-admin")
        assert delivery.status == "queued"
        assert delivery.attempt_count == 0
        assert delivery.last_error is None
    finally:
        db.close()
