"""
Repository Protocols.

Per `domain/README.md`, implementations may return Django ORM model instances
typed against these Protocols. This is the project's single deliberate
compromise on Clean Architecture — Postgres is fixed by spec.
"""
from __future__ import annotations

from typing import Protocol

from domain.entities import (
    InterviewSession,
    Problem,
    ReentryTicket,
    Submission,
    TokenTicket,
)


class ProblemRepository(Protocol):
    def get_by_slug(self, slug: str) -> Problem | None: ...

    def list_all(self) -> list[Problem]: ...

    def upsert(self, problem: Problem) -> Problem: ...


class SessionRepository(Protocol):
    def get(self, session_id: str) -> InterviewSession | None: ...

    def save(self, session: InterviewSession) -> InterviewSession: ...

    def list_by_interviewer(self, username: str) -> list[InterviewSession]: ...


class SubmissionRepository(Protocol):
    def get(self, submission_id: str) -> Submission | None: ...

    def save(self, submission: Submission) -> Submission: ...

    def list_for_session(self, session_id: str) -> list[Submission]: ...


class TokenRepository(Protocol):
    """
    Token CRUD with single-use semantics.

    `consume_atomic` MUST be implemented with `SELECT ... FOR UPDATE` or an
    equivalent serializable transaction, returning None if the token is already
    consumed or expired (Plan REV-4).
    """

    def issue(self, session_id: str, ttl_seconds: int) -> TokenTicket: ...

    def consume_atomic(self, token: str) -> TokenTicket | None: ...


class ReentryRepository(Protocol):
    """Interviewer-issued reentry tickets, single-use, rate-limited at session level."""

    def issue(self, session_id: str, ttl_seconds: int) -> ReentryTicket: ...

    def consume_atomic(self, token: str) -> ReentryTicket | None: ...
