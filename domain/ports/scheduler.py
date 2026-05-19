"""
Scheduler port — schedules timed callbacks for auto-submit and poll fallback.

THIS PORT FORBIDS IN-PROCESS IMPLEMENTATIONS (Plan REV-1).

Background: APScheduler running inside Daphne would lose every pending
auto-submit timer on a single web-container restart. Spec AC #4 requires
"連續 5 場 60 分鐘不出事" — a lost timer at minute 60 is a hard failure.

The only sanctioned implementation is `web/apps/scheduling/adapters.py`,
which proxies to django-q2 with a Postgres jobstore in a separate container.
"""
from __future__ import annotations

from datetime import datetime
from typing import Protocol


class Scheduler(Protocol):
    """
    Schedule a callable to run at a specific UTC time.

    `key` MUST be unique per scheduled job; re-scheduling the same key
    cancels the prior schedule and queues a new one (idempotent re-arm).
    """

    def schedule_at(
        self,
        key: str,
        run_at: datetime,
        callable_path: str,  # dotted path e.g. "domain.usecases.auto_submit.run"
        payload: dict,
    ) -> None: ...

    def cancel(self, key: str) -> None: ...
