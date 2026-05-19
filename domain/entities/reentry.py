"""ReentryToken — interviewer-issued recovery ticket (Plan REV-4)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReentryTicket:
    """
    Single-use recovery ticket. Minted by interviewer when candidate locks
    themselves out (cleared cookies / changed Wi-Fi).

    Rate limited at the InterviewSession level: max 3 per session.
    Once consumed, re-mints the same `interview_session` cookie. Original
    admission token is NEVER re-accepted.
    """

    token: str
    session_id: str
    expires_at_iso: str
    consumed_at_iso: str | None = None

    def is_consumable(self) -> bool:
        return self.consumed_at_iso is None
