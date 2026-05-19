"""
AutoSubmitUseCase — fired by the scheduler at `session.deadline_utc` (Patch #2).

Critical for AC #4.2: timer drift ≤ 10s. Triggered by django-q2 in the
SEPARATE scheduler container — a Daphne restart cannot lose this job.

What it does:
1. Load the session.
2. If already FROZEN, no-op (idempotent — scheduler may retry on transient fail).
3. Take the latest CodeSnapshot (or empty if candidate never typed) and
   create a forced Submission.
4. Transition the session ACTIVE → FROZEN.

Domain doesn't know what a "snapshot" is in DB terms — that's the
SnapshotRepository's job (Step 7 adds it; this UC takes the latest text).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from domain.entities import InterviewSession, SessionState
from domain.ports import SessionRepository


class LatestSnapshotSource(Protocol):
    """Step 7 will provide the actual implementation."""

    def latest_code(self, session_id: str) -> tuple[str, str] | None:
        """Return (language, source_code) or None if no snapshot exists."""
        ...


class ForcedSubmissionSink(Protocol):
    """Step 8 wires this to the real submission flow; for Step 6 it can be a stub."""

    def record_forced(self, session_id: str, language: str, source: str) -> None: ...


@dataclass
class AutoSubmitUseCase:
    sessions: SessionRepository
    snapshots: LatestSnapshotSource
    sink: ForcedSubmissionSink

    def execute(self, session_id: str) -> InterviewSession:
        session = self.sessions.get(session_id)
        if session is None:
            return None  # nothing to do — session vanished
        if session.state in (SessionState.FROZEN, SessionState.REVIEWED):
            return session  # idempotent — already frozen
        if session.state != SessionState.ACTIVE:
            return session  # PENDING never admitted; nothing to submit

        latest = self.snapshots.latest_code(session_id)
        if latest is not None:
            language, source = latest
            self.sink.record_forced(session_id, language, source)
        # else: candidate never typed — record an empty forced submission
        else:
            self.sink.record_forced(session_id, "python", "")

        session.freeze()
        self.sessions.save(session)
        return session
