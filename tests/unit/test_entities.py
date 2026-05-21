"""Unit tests for domain entities — invariants and state transitions."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from domain.entities import (
    Difficulty,
    InterviewSession,
    Judge0Result,
    Language,
    Problem,
    SessionState,
    Submission,
    SubmissionState,
    Testcase,
    TokenTicket,
    Verdict,
)


# ---------------- Problem invariants ----------------


def test_problem_requires_at_least_one_example_testcase():
    with pytest.raises(ValueError, match="example testcase"):
        Problem(
            slug="bad",
            title="Bad",
            statement_md="...",
            languages=[Language.PYTHON],
            testcases=[Testcase(stdin="1", expected_stdout="1")],  # is_example=False
        )


def test_problem_requires_languages():
    with pytest.raises(ValueError, match="at least one language"):
        Problem(
            slug="bad",
            title="Bad",
            statement_md="...",
            languages=[],
            testcases=[Testcase(stdin="1", expected_stdout="1", is_example=True)],
        )


def test_problem_rejects_extreme_time_limit():
    with pytest.raises(ValueError, match="time_limit_ms"):
        Problem(
            slug="bad",
            title="Bad",
            statement_md="...",
            languages=[Language.PYTHON],
            time_limit_ms=99,
            testcases=[Testcase(stdin="1", expected_stdout="1", is_example=True)],
        )


def test_problem_happy_path():
    p = Problem(
        slug="two-sum",
        title="Two Sum",
        statement_md="Find indices.",
        languages=[Language.PYTHON, Language.JAVASCRIPT],
        testcases=[
            Testcase(stdin="2 7 11 15\n9", expected_stdout="0 1", is_example=True),
            Testcase(stdin="3 2 4\n6", expected_stdout="1 2"),
        ],
    )
    assert p.slug == "two-sum"
    assert len(p.testcases) == 2


def test_problem_defaults_zh_blank_and_difficulty_easy():
    p = Problem(
        slug="p", title="P", statement_md=".",
        languages=[Language.PYTHON],
        testcases=[Testcase(stdin="1", expected_stdout="1", is_example=True)],
    )
    assert p.title_zh == ""
    assert p.statement_md_zh == ""
    assert p.difficulty is Difficulty.EASY


def test_problem_accepts_difficulty_and_zh_fields():
    p = Problem(
        slug="p", title="Two Sum", statement_md="EN body",
        languages=[Language.PYTHON],
        testcases=[Testcase(stdin="1", expected_stdout="1", is_example=True)],
        title_zh="兩數之和", statement_md_zh="中文題敘",
        difficulty=Difficulty.MEDIUM,
    )
    assert p.title_zh == "兩數之和"
    assert p.difficulty is Difficulty.MEDIUM


# ---------------- InterviewSession state transitions ----------------


def test_admit_sets_deadline_once_and_transitions_to_active():
    s = InterviewSession(
        id="s1",
        problem_slug="two-sum",
        candidate_label="Alice",
        duration_seconds=3600,
    )
    now = datetime(2026, 5, 10, 12, 0, 0, tzinfo=timezone.utc)
    s.admit(now)
    assert s.state == SessionState.ACTIVE
    assert s.deadline_utc == datetime(2026, 5, 10, 13, 0, 0, tzinfo=timezone.utc)
    assert s.started_at == now


def test_admit_twice_raises():
    s = InterviewSession(
        id="s1", problem_slug="two-sum", candidate_label="Alice", duration_seconds=60
    )
    now = datetime(2026, 5, 10, tzinfo=timezone.utc)
    s.admit(now)
    with pytest.raises(ValueError, match="cannot be admitted"):
        s.admit(now)


def test_remaining_seconds():
    s = InterviewSession(
        id="s1", problem_slug="two-sum", candidate_label="A", duration_seconds=60
    )
    now = datetime(2026, 5, 10, 12, 0, 0, tzinfo=timezone.utc)
    s.admit(now)
    later = datetime(2026, 5, 10, 12, 0, 30, tzinfo=timezone.utc)
    assert s.remaining_seconds(later) == 30


def test_can_reentry_rate_limit():
    s = InterviewSession(
        id="s1", problem_slug="two-sum", candidate_label="A", duration_seconds=60
    )
    s.admit(datetime(2026, 5, 10, tzinfo=timezone.utc))
    assert s.can_reentry()
    s.reentries_used = 3
    assert not s.can_reentry()


def test_freeze_only_from_active():
    s = InterviewSession(
        id="s1", problem_slug="two-sum", candidate_label="A", duration_seconds=60
    )
    with pytest.raises(ValueError):
        s.freeze()  # PENDING → can't freeze


# ---------------- Submission idempotent verdict ----------------


def _judged_result(verdict: Verdict = Verdict.ACCEPTED) -> Judge0Result:
    return Judge0Result(
        raw={},
        verdict=verdict,
        stdout="1",
        stderr=None,
        time_ms=10,
        memory_kb=1024,
    )


def test_submission_record_verdict_idempotent():
    sub = Submission(
        id="sub1",
        session_id="s1",
        language=Language.PYTHON,
        source_code="print(1)",
        submitted_at=datetime(2026, 5, 10, tzinfo=timezone.utc),
    )
    sub.record_verdict(_judged_result(Verdict.ACCEPTED))
    assert sub.state == SubmissionState.JUDGED
    assert sub.verdict() == Verdict.ACCEPTED

    # Duplicate (callback + poll race) — must NOT change state or verdict
    sub.record_verdict(_judged_result(Verdict.WRONG_ANSWER))
    assert sub.verdict() == Verdict.ACCEPTED


def test_submission_rejects_pending_verdict():
    sub = Submission(
        id="sub1",
        session_id="s1",
        language=Language.PYTHON,
        source_code="print(1)",
        submitted_at=datetime(2026, 5, 10, tzinfo=timezone.utc),
    )
    pending = Judge0Result(
        raw={}, verdict=Verdict.PENDING, stdout=None, stderr=None, time_ms=None, memory_kb=None
    )
    with pytest.raises(ValueError, match="non-terminal"):
        sub.record_verdict(pending)


# ---------------- TokenTicket ----------------


def test_token_consumable_only_until_consumed():
    t = TokenTicket(token="abc", session_id="s1", expires_at_iso="2026-05-11T00:00:00Z")
    assert t.is_consumable()
    consumed = TokenTicket(
        token="abc",
        session_id="s1",
        expires_at_iso="2026-05-11T00:00:00Z",
        consumed_at_iso="2026-05-10T13:00:00Z",
    )
    assert not consumed.is_consumable()
