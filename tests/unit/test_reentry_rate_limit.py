"""ReentryUseCase rate-limit tests (Plan REV-4: max 3 per session)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

import pytest

from domain.entities import InterviewSession, ReentryTicket, SessionState
from domain.usecases.reentry import ReentryError, ReentryUseCase


@dataclass
class _FakeSessionRepo:
    sessions: dict[str, InterviewSession] = field(default_factory=dict)

    def get(self, sid):
        return self.sessions.get(sid)

    def save(self, s):
        self.sessions[s.id] = s
        return s

    def list_by_interviewer(self, u):
        return []


@dataclass
class _FakeReentryRepo:
    issued: int = 0
    tickets: dict[str, tuple[str, bool]] = field(default_factory=dict)

    def issue(self, session_id, ttl_seconds):
        self.issued += 1
        token = f"r-{self.issued}"
        self.tickets[token] = (session_id, False)
        return ReentryTicket(
            token=token, session_id=session_id, expires_at_iso="2100-01-01T00:00:00Z"
        )

    def consume_atomic(self, token):
        if token not in self.tickets:
            return None
        sid, consumed = self.tickets[token]
        if consumed:
            return None
        self.tickets[token] = (sid, True)
        return ReentryTicket(
            token=token,
            session_id=sid,
            expires_at_iso="2100-01-01T00:00:00Z",
            consumed_at_iso="2026-05-10T13:00:00Z",
        )


def _active_session(reentries: int = 0) -> InterviewSession:
    s = InterviewSession(id="s1", problem_slug="x", candidate_label="A", duration_seconds=60)
    s.admit(datetime(2026, 5, 10, tzinfo=timezone.utc))
    s.reentries_used = reentries
    return s


def test_mint_increments_counter():
    sessions = _FakeSessionRepo({"s1": _active_session(0)})
    uc = ReentryUseCase(sessions=sessions, reentries=_FakeReentryRepo())
    uc.mint("s1")
    assert sessions.sessions["s1"].reentries_used == 1


def test_fourth_mint_rejected():
    sessions = _FakeSessionRepo({"s1": _active_session(3)})
    uc = ReentryUseCase(sessions=sessions, reentries=_FakeReentryRepo())
    with pytest.raises(ReentryError, match="reentry_limit_exhausted"):
        uc.mint("s1")


def test_three_mints_then_fourth_blocked():
    sessions = _FakeSessionRepo({"s1": _active_session(0)})
    uc = ReentryUseCase(sessions=sessions, reentries=_FakeReentryRepo())
    uc.mint("s1")
    uc.mint("s1")
    uc.mint("s1")
    assert sessions.sessions["s1"].reentries_used == 3
    with pytest.raises(ReentryError, match="reentry_limit_exhausted"):
        uc.mint("s1")


def test_mint_on_pending_session_rejected():
    """Cannot reentry before admit (session_not_active)."""
    s = InterviewSession(id="s1", problem_slug="x", candidate_label="A", duration_seconds=60)
    sessions = _FakeSessionRepo({"s1": s})
    uc = ReentryUseCase(sessions=sessions, reentries=_FakeReentryRepo())
    with pytest.raises(ReentryError, match="session_not_active"):
        uc.mint("s1")


def test_consume_replay_rejected():
    sessions = _FakeSessionRepo({"s1": _active_session(0)})
    rr = _FakeReentryRepo()
    uc = ReentryUseCase(sessions=sessions, reentries=rr)
    token = uc.mint("s1")
    uc.consume(token)
    with pytest.raises(ReentryError, match="reentry_invalid_or_consumed"):
        uc.consume(token)


def test_consume_unknown_rejected():
    sessions = _FakeSessionRepo({"s1": _active_session(0)})
    uc = ReentryUseCase(sessions=sessions, reentries=_FakeReentryRepo())
    with pytest.raises(ReentryError, match="reentry_invalid_or_consumed"):
        uc.consume("nope")
