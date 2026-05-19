"""
AdmitCandidateUseCase — token consumption (Plan REV-4).

Token = single-use admission ticket. Cookie = durable credential.

Flow:
1. Atomically consume the token (SELECT FOR UPDATE — handled by adapter).
2. Load the session.
3. If session is PENDING, transition to ACTIVE (sets `deadline_utc` once
   from `clock.now() + duration` per Patch #2).
4. Return the session_id; the view-layer mints the signed cookie.

The original admission token is NEVER re-accepted. Reload uses the cookie;
recovery from cookie loss uses interviewer-issued ReentryTicket.
"""
from __future__ import annotations

from dataclasses import dataclass

from domain.entities import InterviewSession, SessionState
from domain.ports import Scheduler, ServerClock, SessionRepository, TokenRepository


class AdmissionError(Exception):
    """Raised when a token cannot be consumed (already used, expired, missing)."""


@dataclass
class AdmitCandidateUseCase:
    sessions: SessionRepository
    tokens: TokenRepository
    clock: ServerClock
    scheduler: Scheduler

    def execute(self, raw_token: str) -> InterviewSession:
        ticket = self.tokens.consume_atomic(raw_token)
        if ticket is None:
            raise AdmissionError("token_invalid_or_consumed")

        session = self.sessions.get(ticket.session_id)
        if session is None:
            raise AdmissionError("session_missing")

        if session.state == SessionState.PENDING:
            session.admit(self.clock.now())
            self.sessions.save(session)
            # Patch #2 / Plan REV-1: schedule auto-submit at deadline_utc in
            # the SEPARATE scheduler container. A Daphne restart can NOT lose
            # this job — it lives in the Postgres jobstore.
            self.scheduler.schedule_at(
                key=f"auto_submit:{session.id}",
                run_at=session.deadline_utc,
                callable_path="web.apps.scheduling.adapters.auto_submit_task",
                payload={"args": [session.id]},
            )
        elif session.state in (SessionState.FROZEN, SessionState.REVIEWED):
            raise AdmissionError("session_already_finished")
        # ACTIVE → admin's accidental re-issue of token consumed it but session
        # already started; treat as idempotent: return the active session.

        return session
