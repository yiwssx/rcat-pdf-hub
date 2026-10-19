"""DNS doctor unit tests must never require a running Docker stack."""
from __future__ import annotations

import importlib.util
import os
import socket
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "doctor-upload-dns.py"
SPEC = importlib.util.spec_from_file_location("upload_dns_doctor", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
doctor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(doctor)


class UploadDnsDoctorTests(unittest.TestCase):
    def test_default_internal_hosts(self):
        with patch.dict(os.environ, {
            "PDFHUB_DATABASE_URL": "postgresql+psycopg://user:secret@postgres:5432/pdfhub",
            "PDFHUB_REDIS_URL": "redis://valkey:6379/0",
            "PDFHUB_GOTENBERG_URL": "http://gotenberg:3000",
            "PDFHUB_STORAGE_BACKEND": "local",
            "PDFHUB_CLAMAV_ENABLED": "false",
        }, clear=True):
            self.assertEqual(doctor.targets_from_environment(), {
                "PostgreSQL": ("postgres", 5432),
                "Valkey": ("valkey", 6379),
                "Gotenberg": ("gotenberg", 3000),
            })

    def test_optional_s3_and_clamav(self):
        with patch.dict(os.environ, {
            "PDFHUB_STORAGE_BACKEND": "s3",
            "PDFHUB_S3_ENDPOINT_URL": "http://seaweedfs:8333",
            "PDFHUB_CLAMAV_ENABLED": "true",
            "PDFHUB_CLAMAV_HOST": "clamav",
            "PDFHUB_CLAMAV_PORT": "3310",
        }, clear=True):
            targets = doctor.targets_from_environment()
            self.assertEqual(targets["S3 storage"], ("seaweedfs", 8333))
            self.assertEqual(targets["ClamAV"], ("clamav", 3310))

    def test_reject_missing_s3_endpoint(self):
        with patch.dict(os.environ, {"PDFHUB_STORAGE_BACKEND": "s3"}, clear=True):
            with self.assertRaisesRegex(ValueError, "S3 is enabled"):
                doctor.targets_from_environment()

    def test_dns_failure_does_not_attempt_tcp(self):
        with patch.object(socket, "getaddrinfo", side_effect=socket.gaierror(-3, "Temporary failure in name resolution")):
            with patch.object(socket, "create_connection") as tcp:
                self.assertFalse(doctor.check_target("PostgreSQL", "postgres", 5432))
                tcp.assert_not_called()

    def test_unavailable_port_does_not_report_dns_failure(self):
        with patch.object(socket, "getaddrinfo", return_value=[object()]):
            with patch.object(socket, "create_connection", side_effect=ConnectionRefusedError(111, "refused")):
                self.assertFalse(doctor.check_target("Valkey", "valkey", 6379))


if __name__ == "__main__":
    unittest.main()
