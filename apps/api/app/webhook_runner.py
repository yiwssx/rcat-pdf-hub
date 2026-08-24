import time

from app.audit import audit_event
from app.config import get_settings
from app.db import SessionLocal
from app.webhooks import process_due_webhooks

settings = get_settings()


def run_forever() -> None:
    while True:
        db = SessionLocal()
        try:
            process_due_webhooks(db)
        except Exception as exc:
            db.rollback()
            audit_event(
                "webhook.dispatch_cycle_failed",
                "system",
                "webhook_delivery",
                None,
                {"error": str(exc)[-1000:]},
            )
        finally:
            db.close()
        time.sleep(settings.webhook_dispatch_interval_seconds)


if __name__ == "__main__":
    run_forever()
