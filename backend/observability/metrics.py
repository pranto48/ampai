from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from statistics import median
from threading import Lock
from time import monotonic
from typing import Deque, Dict, Optional


@dataclass
class _JobResult:
    duration_seconds: float
    success: bool
    policy_rejected: bool


class OperationalMetrics:
    """In-memory rolling metrics for AI edit operations."""

    def __init__(self, max_samples: int = 2000) -> None:
        self._max_samples = max_samples
        self._samples: Deque[_JobResult] = deque(maxlen=max_samples)
        self._active: Dict[str, float] = {}
        self._lock = Lock()

    def start_job(self, job_id: str) -> None:
        with self._lock:
            self._active[job_id] = monotonic()

    def end_job(self, job_id: str, success: bool, policy_rejected: bool = False) -> None:
        with self._lock:
            started = self._active.pop(job_id, None)
            if started is None:
                return
            self._samples.append(
                _JobResult(duration_seconds=monotonic() - started, success=success, policy_rejected=policy_rejected)
            )

    def snapshot(self) -> Dict[str, Optional[float]]:
        with self._lock:
            if not self._samples:
                return {
                    "jobs_observed": 0,
                    "success_rate": None,
                    "median_pr_creation_time_seconds": None,
                    "policy_rejection_rate": None,
                }
            total = len(self._samples)
            successes = sum(1 for s in self._samples if s.success)
            policy_rejections = sum(1 for s in self._samples if s.policy_rejected)
            durations = [s.duration_seconds for s in self._samples]
            return {
                "jobs_observed": total,
                "success_rate": successes / total,
                "median_pr_creation_time_seconds": median(durations),
                "policy_rejection_rate": policy_rejections / total,
            }


METRICS = OperationalMetrics()
