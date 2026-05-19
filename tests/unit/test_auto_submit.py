"""AutoSubmitUseCase tests."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from domain.entities import InterviewSession, SessionState
from domain.usecases.auto_submit import AutoSubmitUseCase


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
class _FakeSnapshots:
    by_session: dict[str, tuple[str, str]] = field(default_factory=dict)

    def latest_code(self, sid):
        return self.by_session.get(sid)


@dataclass
class _FakeSink:
    forced: list[tuple[str, str, str]] = field(default_factory=list)

    def record_forced(self, sid, lang, src):
        self.forced.append((sid, lang, src))


def _active_session() -> InterviewSession:
    s = InterviewSession(id="s1", problem_slug="x", candidate_label="A", duration_seconds=60)
    s.admit(datetime(2026, 5, 10, tzinfo=timezone.utc))
    return s


def test_active_session_freezes_and_records_latest_snapshot():
    sessions = _FakeSessionRepo({"s1": _active_session()})
    snapshots = _FakeSnapshots({"s1": ("python", "print(42)\n")})
    sink = _FakeSink()
    AutoSubmitUseCase(sessions=sessions, snapshots=snapshots, sink=sink).execute("s1")
    assert sessions.sessions["s1"].state == SessionState.FROZEN
    assert sink.forced == [("s1", "python", "print(42)\n")]


def test_active_session_with_no_snapshot_records_empty():
    sessions = _FakeSessionRepo({"s1": _active_session()})
    sink = _FakeSink()
    AutoSubmitUseCase(sessions=sessions, snapshots=_FakeSnapshots(), sink=sink).execute("s1")
    assert sessions.sessions["s1"].state == SessionState.FROZEN
    assert sink.forced == [("s1", "python", "")]


def test_already_frozen_is_idempotent():
    """Scheduler may retry — re-firing must not double-record or double-freeze."""
    s = _active_session()
    s.freeze()
    sessions = _FakeSessionRepo({"s1": s})
    sink = _FakeSink()
    AutoSubmitUseCase(sessions=sessions, snapshots=_FakeSnapshots(), sink=sink).execute("s1")
    assert sessions.sessions["s1"].state == SessionState.FROZEN
    assert sink.forced == []  # nothing recorded


def test_pending_session_no_op():
    """Scheduler shouldn't be armed before admit, but if it fires, do nothing."""
    s = InterviewSession(id="s1", problem_slug="x", candidate_label="A", duration_seconds=60)
    sessions = _FakeSessionRepo({"s1": s})
    sink = _FakeSink()
    AutoSubmitUseCase(sessions=sessions, snapshots=_FakeSnapshots(), sink=sink).execute("s1")
    assert sessions.sessions["s1"].state == SessionState.PENDING
    assert sink.forced == []


def test_missing_session_no_error():
    sessions = _FakeSessionRepo()
    sink = _FakeSink()
    result = AutoSubmitUseCase(
        sessions=sessions, snapshots=_FakeSnapshots(), sink=sink
    ).execute("ghost")
    assert result is None
    assert sink.forced == []
