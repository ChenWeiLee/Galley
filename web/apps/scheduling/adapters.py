"""
DjangoQScheduler — implements `domain.ports.Scheduler` via django-q2.

CRITICAL (Plan REV-1, Patch #2): this adapter must be invoked from within the
web container, but the actual job execution happens in the SEPARATE scheduler
container running `python manage.py qcluster`. The Postgres jobstore (already
active because Q_CLUSTER.orm = "default") is the durable medium between them.

A Daphne restart cannot lose pending jobs because they live in Postgres.
"""
from __future__ import annotations

from datetime import datetime

from django_q.models import Schedule
from django_q.tasks import schedule

from domain.ports.scheduler import Scheduler


class DjangoQScheduler(Scheduler):
    def schedule_at(
        self, key: str, run_at: datetime, callable_path: str, payload: dict
    ) -> None:
        # django-q2: Schedule with `next_run` and a single-shot type. Re-arming
        # with the same `name` (key) requires deleting the prior row first
        # (idempotent re-schedule per port contract).
        Schedule.objects.filter(name=key).delete()
        schedule(
            callable_path,
            *payload.get("args", []),
            **payload.get("kwargs", {}),
            name=key,
            schedule_type=Schedule.ONCE,
            next_run=run_at,
            # `repeats` is ignored when schedule_type=ONCE; django-q2 fires
            # exactly once regardless. Kept explicit so reviewers don't think
            # this is a recurring task. (See judging/apps.py for the recurring
            # poll_pending_submissions schedule where repeats=-1 means forever.)
        )

    def cancel(self, key: str) -> None:
        Schedule.objects.filter(name=key).delete()


def auto_submit_task(session_id: str) -> str:
    """
    Top-level callable invoked by django-q2 when the scheduled time arrives.

    Must be importable as `web.apps.scheduling.adapters.auto_submit_task` from
    the scheduler container. Returns a string for django-q2's task log.
    """
    # Late imports keep this module light to import; scheduling tasks should
    # never participate in Django app startup graphs.
    from domain.usecases.auto_submit import AutoSubmitUseCase

    from web.apps.candidate.repos import DjangoSessionRepository
    from web.apps.judging.snapshot import SnapshotSource
    from web.apps.judging.submission_sink import DjangoSubmissionSink

    uc = AutoSubmitUseCase(
        sessions=DjangoSessionRepository(),
        snapshots=SnapshotSource(),
        sink=DjangoSubmissionSink(),
    )
    s = uc.execute(session_id)
    return f"auto_submit({session_id}) → {s.state.value if s else 'missing'}"
