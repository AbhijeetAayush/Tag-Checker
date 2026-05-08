from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone

from sqlalchemy import select

from db import SessionLocal
from models import AuditRun, RunStatus


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _claim_next_run() -> str | None:
    """
    Very small "worker" that runs inside the API process.
    For production scale, split this into a separate worker service + queue.
    """
    with SessionLocal() as db:
        run = db.execute(
            select(AuditRun).where(AuditRun.status == RunStatus.queued).order_by(AuditRun.created_at.asc()).limit(1)
        ).scalar_one_or_none()
        if not run:
            return None

        # Best-effort claim. (For a real queue, use a lease/CAS update.)
        run.status = RunStatus.running
        run.started_at = _now()
        run.pages_done = 0
        if run.pages_total_estimate is None:
            run.pages_total_estimate = 5
        db.commit()
        return run.id


def _execute_run(run_id: str) -> None:
    # Simulate work and progress updates.
    try:
        with SessionLocal() as db:
            run = db.get(AuditRun, run_id)
            if not run or run.status != RunStatus.running:
                return
            total = run.pages_total_estimate or 5

        for i in range(total):
            time.sleep(0.6)
            with SessionLocal() as db:
                run = db.get(AuditRun, run_id)
                if not run or run.status != RunStatus.running:
                    return
                run.pages_done = min(total, i + 1)
                db.commit()

        with SessionLocal() as db:
            run = db.get(AuditRun, run_id)
            if not run or run.status != RunStatus.running:
                return
            run.status = RunStatus.succeeded
            run.finished_at = _now()
            db.commit()
    except Exception as e:
        with SessionLocal() as db:
            run = db.get(AuditRun, run_id)
            if not run:
                return
            run.status = RunStatus.failed
            run.finished_at = _now()
            run.error_code = "worker_exception"
            run.error_message = str(e)[:1900]
            db.commit()


def _loop(stop_event: threading.Event) -> None:
    while not stop_event.is_set():
        run_id = _claim_next_run()
        if not run_id:
            time.sleep(0.5)
            continue
        _execute_run(run_id)


class InProcessRunner:
    def __init__(self) -> None:
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=_loop, args=(self._stop,), name="audit-runner", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)


def serialize_run_config(payload: dict) -> str:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)

