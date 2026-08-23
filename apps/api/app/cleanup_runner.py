import logging
import time

from app.cleanup import cleanup_once
from app.config import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pdfhub.cleanup")
settings = get_settings()


def main() -> None:
    while True:
        try:
            logger.info("retention cleanup: %s", cleanup_once())
        except Exception:
            logger.exception("retention cleanup failed")
        time.sleep(max(60, settings.cleanup_interval_seconds))


if __name__ == "__main__":
    main()
