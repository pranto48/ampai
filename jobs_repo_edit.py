from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from queue import Empty, Queue
from typing import Any, Dict, Generator, Optional

from database import get_config, set_config
from services.repo_edit_orchestrator import RepoEditOrchestrator, RepoTargetContext

TRANSIENT_ERRORS = (TimeoutError, ConnectionError)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RepoEditJobStore:
    PREFIX = "repo_edit_job:"
    IDEMP_PREFIX = "repo_edit_idemp:"

    def create_job(self, payload: Dict[str, Any], idempotency_key: Optional[str]) -> Dict[str, Any]:
        if idempotency_key:
            existing_id = get_config(f"{self.IDEMP_PREFIX}{idempotency_key}", "")
            if existing_id:
                existing = self.get_job(existing_id)
                if existing:
                    return existing
        job_id = f"rej_{uuid.uuid4().hex[:12]}"
        now = _now()
        job = {
            "id": job_id,
            "status": "queued",
            "phase": "queued",
            "created_at": now,
            "updated_at": now,
            "events": [{"at": now, "status": "queued", "payload": {"message": "Job queued"}}],
            "error": None,
            "cancel_requested": False,
            "request": payload,
            "result": None,
            "idempotency_key": idempotency_key,
        }
        self.save_job(job)
        if idempotency_key:
            set_config(f"{self.IDEMP_PREFIX}{idempotency_key}", job_id)
        return job

    def save_job(self, job: Dict[str, Any]) -> None:
        job["updated_at"] = _now()
        set_config(f"{self.PREFIX}{job['id']}", json.dumps(job))

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        raw = get_config(f"{self.PREFIX}{job_id}", "")
        if not raw:
            return None
        return json.loads(raw)

    def transition(self, job_id: str, status: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        job = self.get_job(job_id)
        if not job:
            raise ValueError("Job not found")
        now = _now()
        job["status"] = status
        job["phase"] = status
        job.setdefault("events", []).append({"at": now, "status": status, "payload": payload or {}})
        self.save_job(job)
        return job

    def fail(self, job_id: str, error_payload: Dict[str, Any]) -> Dict[str, Any]:
        job = self.transition(job_id, "failed", {"error": error_payload})
        job["error"] = error_payload
        self.save_job(job)
        return job


class RepoEditJobManager:
    def __init__(self) -> None:
        self.store = RepoEditJobStore()
        self.queue: "Queue[str]" = Queue(maxsize=200)
        self.subscribers: dict[str, list[Queue]] = {}
        self.lock = threading.Lock()
        self.worker = threading.Thread(target=self._worker_loop, daemon=True, name="repo-edit-worker")
        self.worker.start()

    def enqueue(self, request_payload: Dict[str, Any], idempotency_key: Optional[str]) -> Dict[str, Any]:
        job = self.store.create_job(request_payload, idempotency_key)
        if job["status"] == "queued" and not job.get("result") and len(job.get("events", [])) == 1:
            self.queue.put_nowait(job["id"])
        return job

    def cancel(self, job_id: str) -> Optional[Dict[str, Any]]:
        job = self.store.get_job(job_id)
        if not job:
            return None
        job["cancel_requested"] = True
        self.store.save_job(job)
        return self.store.transition(job_id, "cancel_requested", {"message": "Cancellation requested"})

    def subscribe(self, job_id: str) -> Queue:
        q: Queue = Queue(maxsize=50)
        with self.lock:
            self.subscribers.setdefault(job_id, []).append(q)
        return q

    def unsubscribe(self, job_id: str, q: Queue) -> None:
        with self.lock:
            listeners = self.subscribers.get(job_id, [])
            if q in listeners:
                listeners.remove(q)

    def _emit(self, job: Dict[str, Any]) -> None:
        with self.lock:
            listeners = list(self.subscribers.get(job["id"], []))
        for q in listeners:
            try:
                q.put_nowait(job)
            except Exception:
                pass

    def _worker_loop(self) -> None:
        while True:
            try:
                job_id = self.queue.get(timeout=1)
            except Empty:
                continue
            self._process_job(job_id)

    def _process_job(self, job_id: str) -> None:
        job = self.store.get_job(job_id)
        if not job:
            return
        if job.get("cancel_requested"):
            job = self.store.transition(job_id, "cancelled", {"message": "Cancelled before start"})
            self._emit(job)
            return
        req = job["request"]
        token = req["github_token"]
        ctx = RepoTargetContext(**req["context"])
        orchestrator = RepoEditOrchestrator(github_token=token)
        max_attempts = int(req.get("max_attempts", 4))
        delay = 1.0
        for attempt in range(1, max_attempts + 1):
            try:
                for phase in ["planning", "editing", "validating", "pushing", "pr_opened"]:
                    current = self.store.transition(job_id, phase, {"attempt": attempt})
                    self._emit(current)
                    if phase != "pr_opened":
                        time.sleep(0.01)
                result = orchestrator.run(req["instruction"], ctx)
                final = self.store.transition(job_id, result.status, {"attempt": attempt, "result": asdict(result)})
                final["result"] = asdict(result)
                self.store.save_job(final)
                self._emit(final)
                return
            except TRANSIENT_ERRORS as exc:
                if attempt == max_attempts:
                    failed = self.store.fail(job_id, {"type": exc.__class__.__name__, "message": str(exc), "attempt": attempt})
                    self._emit(failed)
                    return
                backoff = delay * (2 ** (attempt - 1))
                retried = self.store.transition(job_id, "retrying", {"attempt": attempt, "backoff_seconds": backoff})
                self._emit(retried)
                time.sleep(backoff)
            except Exception as exc:  # noqa: BLE001
                failed = self.store.fail(job_id, {"type": exc.__class__.__name__, "message": str(exc), "attempt": attempt})
                self._emit(failed)
                return


manager = RepoEditJobManager()


def stream_events(job_id: str) -> Generator[str, None, None]:
    q = manager.subscribe(job_id)
    try:
        existing = manager.store.get_job(job_id)
        if existing:
            yield f"data: {json.dumps(existing)}\n\n"
        while True:
            update = q.get(timeout=30)
            yield f"data: {json.dumps(update)}\n\n"
    except Empty:
        yield ": keepalive\n\n"
    finally:
        manager.unsubscribe(job_id, q)
