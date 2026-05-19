"""AdmitCandidateUseCase tests with fake repos + fake clock."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import pytest

from domain.entities import InterviewSession, SessionState, TokenTicket
from domain.usecases.admit_candidate import AdmissionError, AdmitCandidateUseCase


@dataclass
class _FakeClock:
    t: datetime

    def now(self) -> datetime:
        return self.t


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
class _FakeTokenRepo:
    """Tokens: token → (session_id, consumed?)."""
    tokens: dict[str, tuple[str, bool]] = field(default_factory=dict)

    def issue(self, session_id, ttl_seconds):
        raise NotImplementedError

    def consume_atomic(self, token):
        if token not in self.tokens:
            return None
        sid, consumed = self.tokens[token]
        if consumed:
            return None
        self.tokens[token] = (sid, True)
        return TokenTicket(
            token=token,
            session_id=sid,
            expires_at_iso="2100-01-01T00:00:00Z",
            consumed_at_iso="2026-05-10T12:00:00Z",
        )


@dataclass
class _FakeScheduler:
    scheduled: list = field(default_factory=list)

    def schedule_at(self, key, run_at, callable_path, payload):
        self.scheduled.append((key, run_at, callable_path, payload))

    def cancel(self, key):
        self.scheduled = [s for s in self.scheduled if s[0] != key]


def _setup():
    now = datetime(2026, 5, 10, 12, 0, 0, tzinfo=timezone.utc)
    sessions = _FakeSessionRepo({
        "s1": InterviewSession(
            id="s1", problem_slug="two-sum", candidate_label="Alice",
            duration_seconds=3600,
        )
    })
    tokens = _FakeTokenRepo({"good-token": ("s1", False)})
    sched = _FakeScheduler()
    uc = AdmitCandidateUseCase(
        sessions=sessions, tokens=tokens, clock=_FakeClock(now), scheduler=sched,
    )
    return uc, sessions, tokens, now, sched


def test_first_hit_admits_and_sets_deadline():
    uc, sessions, _, now, _ = _setup()
    s = uc.execute("good-token")
    assert s.state == SessionState.ACTIVE
    assert s.deadline_utc == now + timedelta(seconds=3600)
    assert sessions.sessions["s1"].state == SessionState.ACTIVE


def test_first_hit_schedules_auto_submit():
    """Patch #2 + REV-1: scheduler.schedule_at MUST be called with deadline_utc."""
    uc, sessions, _, now, sched = _setup()
    s = uc.execute("good-token")
    assert len(sched.scheduled) == 1
    key, run_at, callable_path, payload = sched.scheduled[0]
    assert key == f"auto_submit:{s.id}"
    assert run_at == s.deadline_utc
    assert callable_path == "web.apps.scheduling.adapters.auto_submit_task"
    assert payload == {"args": [s.id]}


def test_replay_token_rejected():
    uc, _, _, _, _ = _setup()
    uc.execute("good-token")
    with pytest.raises(AdmissionError, match="token_invalid_or_consumed"):
        uc.execute("good-token")


def test_unknown_token_rejected():
    uc, _, _, _, _ = _setup()
    with pytest.raises(AdmissionError, match="token_invalid_or_consumed"):
        uc.execute("bogus")


def test_admit_after_freeze_rejected():
    uc, sessions, tokens, _, _ = _setup()
    sessions.sessions["s1"].state = SessionState.FROZEN
    tokens.tokens["another"] = ("s1", False)
    with pytest.raises(AdmissionError, match="session_already_finished"):
        uc.execute("another")


def test_token_for_already_active_session_idempotent():
    """If session is ACTIVE (e.g. interviewer accidentally re-issued a token
    that got consumed for an already-running session), return the active
    session without erroring."""
    uc, sessions, tokens, now, sched = _setup()
    sessions.sessions["s1"].admit(now)  # ACTIVE
    tokens.tokens["t2"] = ("s1", False)
    s = uc.execute("t2")
    assert s.state == SessionState.ACTIVE
    # Already ACTIVE — should NOT re-schedule (scheduler stays empty).
    assert sched.scheduled == []
