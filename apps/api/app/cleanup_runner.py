import logging
import time

from app.cleanup import cleanup_once
from app.config import get_settings
from app.reconcile import reconcile_stale_jobs_once

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pdfhub.cleanup")
settings = get_settings()


def main() -> None:
    while True:
        try:
            logger.info("job reconciliation: %s", reconcile_stale_jobs_once())
        except Exception:
            logger.exception("job reconciliation failed")
        try:
            logger.info("retention cleanup: %s", cleanup_once())
        except Exception:
            logger.exception("retention cleanup failed")
        time.sleep(max(60, settings.cleanup_interval_seconds))


if __name__ == "__main__":
    main()
