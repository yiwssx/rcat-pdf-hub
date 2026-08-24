import os

os.environ.setdefault("PDFHUB_DATABASE_URL", "sqlite+pysqlite:////tmp/pdfhub-tests.db")
os.environ.setdefault("PDFHUB_DATA_DIR", "/tmp/pdfhub-test-data")
os.environ.setdefault("PDFHUB_API_KEY_PEPPER", "ci-test-pepper-change-me")
os.environ.setdefault("PDFHUB_ADMIN_API_KEY", "pdfh_ci_admin_key_change_me")
os.environ.setdefault("PDFHUB_WEBHOOK_MASTER_SECRET", "ci-webhook-master-secret-change-me")
os.environ.setdefault("PDFHUB_DOWNLOAD_SIGNING_SECRET", "ci-download-signing-secret-change-me-at-least-32")

import pytest
from app.db import Base, engine


@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
