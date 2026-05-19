"""
ReentryUseCase — recover from cookie loss (Plan REV-4).

Two operations:
- `mint_reentry(session_id)` — interviewer-only, rate-limited to 3 per session.
- `consume_reentry(reentry_token)` — candidate-side, restores the cookie.

Critical invariant: the ORIGINAL admission token is never re-accepted. Recovery
goes through a SEPARATE table and a separate use case so logic and observability
are clear.
"""
from __future__ import annotations

from dataclasses import dataclass

from domain.entities import InterviewSession
from domain.ports import ReentryRepository, SessionRepository


class ReentryError(Exception):
    """Raised when a reentry attempt fails."""


@dataclass
class ReentryUseCase:
    sessions: SessionRepository
    reentries: ReentryRepository

    def mint(self, session_id: str, ttl_seconds: int = 3600) -> str:
        """
        Issue a reentry token. Caller (view layer) must verify that the request
        is authenticated as the session's interviewer.

        Returns the raw token string (already persisted).
        """
        session = self.sessions.get(session_id)
        if session is None:
            raise ReentryError("session_missing")
        if not session.can_reentry():
            raise ReentryError(
                "reentry_limit_exhausted"
                if session.reentries_used >= 3
                else "session_not_active"
            )
        ticket = self.reentries.issue(session_id, ttl_seconds)
        # Increment use counter UPFRONT so 3 mints (even if not consumed yet)
        # exhausts the budget. This deters interviewers from minting "spares".
        session.reentries_used += 1
        self.sessions.save(session)
        return ticket.token

    def consume(self, raw_token: str) -> InterviewSession:
        """
        Consume a reentry token. Returns the session so the view layer can
        mint a fresh cookie.
        """
        ticket = self.reentries.consume_atomic(raw_token)
        if ticket is None:
            raise ReentryError("reentry_invalid_or_consumed")
        session = self.sessions.get(ticket.session_id)
        if session is None:
            raise ReentryError("session_missing")
        return session
