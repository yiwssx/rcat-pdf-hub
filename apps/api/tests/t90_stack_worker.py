"""Child entrypoint for T90-0.11 real integration tests on isolated CI services.

No production code paths are monkeypatched globally: the PDF encoder is a
short deterministic stub to isolate the worker/RQ/DB/S3 transport behavior.
Object uploads, Redis/RQ, PostgreSQL commits, and SIGKILL are real.
"""
from __future__ import annotations

import sys
import time
import os
import json
from pathlib import Path

# Direct script execution sets sys.path[0] to /app/tests rather than /app.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import worker_tasks
from app.queue import redis_conn
from app.services import pdf_tools


def fake_compress(_source: Path, destination: Path) -> None:
    destination.write_bytes(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n")


def main() -> int:
    mode = sys.argv[1]
    pdf_tools.compress = fake_compress
    worker_tasks.scan_file = lambda _path: "clean"

    if mode == "rq":
        from rq import Queue, Worker

        name = sys.argv[2]
        queue = Queue(name, connection=redis_conn)
        worker = Worker([queue], connection=redis_conn, name=f"t90-{name}-{sys.argv[3]}")
        worker.work(burst=True, logging_level="ERROR")
        return 0

    if mode == "rq-kill-workhorse":
        # Run a REAL RQ parent worker. Its forked work-horse writes to S3
        # and signals its own PID to the controller, which kills only the
        # work-horse. Parent RQ must reap and classify the failed queue job.
        from rq import Queue, Worker

        name, marker = sys.argv[2], Path(sys.argv[3])
        actual_store = worker_tasks.store_staged_file

        def upload_then_wait(path, area, filename=None):
            stored_name = actual_store(path, area, filename=filename)
            temporary_marker = marker.with_suffix(".writing")
            temporary_marker.write_text(json.dumps({
                "pid": os.getpid(), "ppid": os.getppid(),
                "stored_name": stored_name,
            }), encoding="utf-8")
            temporary_marker.replace(marker)
            while True:
                time.sleep(1)

        worker_tasks.store_staged_file = upload_then_wait
        queue = Queue(name, connection=redis_conn)
        Worker([queue], connection=redis_conn,
               name=f"t90-reap-{name}").work(
                   burst=True, logging_level="ERROR",
               )
        return 0

    if mode == "stall-after-s3":
        job_id = sys.argv[2]
        marker = Path(sys.argv[3])
        real_store = worker_tasks.store_staged_file

        def store_then_stall(path, area, filename=None):
            stored_name = real_store(path, area, filename=filename)
            marker.write_text(stored_name, encoding="utf-8")
            # Controller sends SIGKILL after verifying the actual S3 object.
            # Python exception/finally handlers cannot run.
            while True:
                time.sleep(1)

        worker_tasks.store_staged_file = store_then_stall
        worker_tasks.process_job(job_id)
        raise AssertionError("Stalled child should have been SIGKILLed")

    if mode == "ack-lost":
        job_id = sys.argv[2]
        real_store = worker_tasks.store_staged_file

        def stored_but_lost_ack(path, area, filename=None):
            real_store(path, area, filename=filename)
            raise OSError("synthetic lost network acknowledgment after real S3 upload")

        worker_tasks.store_staged_file = stored_but_lost_ack
        try:
            worker_tasks.process_job(job_id)
        except OSError as exc:
            if "synthetic lost network acknowledgment" in str(exc):
                return 0
            raise
        raise AssertionError("Worker unexpectedly succeeded despite injected network failure")

    raise ValueError("Unknown T90 CI subprocess mode")


if __name__ == "__main__":
    raise SystemExit(main())
