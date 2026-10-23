"""Opt-in per-process worker heartbeat backed by short-lived DB sessions.

No Redis dependency in this thread. Job completion, cancellation and
fencing always happen through conditional SQL, not a cached Python flag.
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field

from app.db import SessionLocal
from app.write_journal import renew_execution_lease

log = logging.getLogger(__name__)


@dataclass
class WorkerHeartbeat:
    job_id: str
    token: str
    epoch: int
    ttl_seconds: int
    interval_seconds: int
    _stop: threading.Event = field(default_factory=threading.Event, init=False)
    _lost: threading.Event = field(default_factory=threading.Event, init=False)
    _thread: threading.Thread | None = field(default=None, init=False)

    def __post_init__(self):
        if self.interval_seconds < 5 or self.interval_seconds * 3 >= self.ttl_seconds:
            raise ValueError("Heartbeat interval must be under one third of lease TTL")

    @property
    def lost(self) -> bool:
        return self._lost.is_set()

    def beat_once(self) -> bool:
        with SessionLocal() as db:
            return renew_execution_lease(
                db, job_id=self.job_id, token=self.token,
                epoch=self.epoch, ttl_seconds=self.ttl_seconds,
            )

    def _run(self) -> None:
        while not self._stop.wait(self.interval_seconds):
            try:
                if not self.beat_once():
                    self._lost.set()
                    return
            except Exception:
                # Transient DB connection/lock errors must not produce a false
                # success. The next beat may recover, but every write/publish
                # still must satisfy the DB expiry+token predicate.
                log.exception("Execution heartbeat failed for job %s", self.job_id)

    def start(self) -> None:
        if self._thread is not None:
            raise RuntimeError("Heartbeat can only start once")
        self._thread = threading.Thread(
            target=self._run, name="pdfhub-lease-heartbeat", daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            # Bound the wait; never block job cleanup indefinitely on a DB outage.
            self._thread.join(timeout=2)
