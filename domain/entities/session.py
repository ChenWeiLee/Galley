"""Interview session — the candidate's exam instance."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum


class SessionState(str, Enum):
    PENDING = "pending"  # token issued, not yet consumed
    ACTIVE = "active"  # candidate admitted, deadline_utc set
    FROZEN = "frozen"  # past deadline_utc; auto-submit happened
    REVIEWED = "reviewed"  # interviewer marked it complete


@dataclass
class InterviewSession:
    """
    One candidate × one problem × one time window.

    `deadline_utc` is the SINGLE SOURCE OF TIME (Patch #2). Set once when the
    candidate is admitted; both the auto-submit scheduler job and the
    candidate's countdown display read this same field. Never reassigned.
    """

    id: str  # ULID-ish string
    problem_slug: str
    candidate_label: str  # human-friendly identifier (not PII)
    duration_seconds: int  # set when the session is created
    deadline_utc: datetime | None = None  # set on admit; null for PENDING
    state: SessionState = SessionState.PENDING
    started_at: datetime | None = None
    interviewer_username: str = ""
    reentries_used: int = 0  # rate-limit 3 per session (Plan REV-4)

    def admit(self, now: datetime) -> None:
        """Transition PENDING → ACTIVE. Set deadline_utc once."""
        if self.state != SessionState.PENDING:
            raise ValueError(
                f"Session {self.id} cannot be admitted from state {self.state.value}"
            )
        self.started_at = now
        self.deadline_utc = now + timedelta(seconds=self.duration_seconds)
        self.state = SessionState.ACTIVE

    def freeze(self) -> None:
        """Transition ACTIVE → FROZEN at deadline."""
        if self.state != SessionState.ACTIVE:
            raise ValueError(
                f"Session {self.id} cannot be frozen from state {self.state.value}"
            )
        self.state = SessionState.FROZEN

    def remaining_seconds(self, now: datetime) -> int:
        """Compute remaining time. Negative if past deadline."""
        if self.deadline_utc is None:
            return self.duration_seconds
        return int((self.deadline_utc - now).total_seconds())

    def can_reentry(self) -> bool:
        """Plan REV-4: rate-limit interviewer-issued reentry to 3 per session."""
        return self.state == SessionState.ACTIVE and self.reentries_used < 3
