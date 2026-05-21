"""SubmitCodeUseCase + RecordVerdictUseCase unit tests."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

import pytest

from domain.entities import (
    Judge0Result,
    Language,
    Problem,
    Submission as DomainSubmission,
    SubmissionState,
    Testcase,
    Verdict,
)
from domain.ports.judge import JudgeSubmissionRequest
from domain.usecases.record_verdict import RecordVerdictUseCase
from domain.usecases.submit_code import SubmitCodeUseCase, SubmitError


@dataclass
class _FakeProblems:
    by_slug: dict[str, Problem] = field(default_factory=dict)

    def get_by_slug(self, s):
        return self.by_slug.get(s)

    def list_all(self):
        return list(self.by_slug.values())

    def upsert(self, p):
        self.by_slug[p.slug] = p
        return p


@dataclass
class _FakeSubmissions:
    by_id: dict[str, DomainSubmission] = field(default_factory=dict)
    saved_dtos: list = field(default_factory=list)

    def get(self, sid):
        return self.by_id.get(sid)

    def save(self, sub):
        self.saved_dtos.append(sub)
        if isinstance(sub, DomainSubmission):
            self.by_id[sub.id] = sub
        return sub

    def list_for_session(self, sid):
        return [s for s in self.by_id.values() if s.session_id == sid]


@dataclass
class _FakeJudge:
    next_tokens: list[str] = field(default_factory=lambda: ["t1", "t2"])
    submitted: list[JudgeSubmissionRequest] = field(default_factory=list)

    def submit(self, request):
        self.submitted.append(request)
        return list(self.next_tokens)

    def fetch_results(self, tokens):
        return []


@dataclass
class _FakeClock:
    def now(self):
        return datetime(2026, 5, 10, 12, 0, 0, tzinfo=timezone.utc)


@dataclass
class _FakeBroadcaster:
    pushed: list[tuple[str, str, dict]] = field(default_factory=list)

    def push(self, sid, ev, payload):
        self.pushed.append((sid, ev, payload))


def _problem(slug="p1", langs=(Language.PYTHON,)) -> Problem:
    return Problem(
        slug=slug, title="P", statement_md=".", languages=list(langs),
        testcases=[Testcase(stdin="1", expected_stdout="1", is_example=True)],
    )


# ---------------- SubmitCodeUseCase ----------------


def test_submit_dispatches_and_persists_pending():
    problems = _FakeProblems({"p1": _problem()})
    subs = _FakeSubmissions()
    judge = _FakeJudge(next_tokens=["tok-a"])
    uc = SubmitCodeUseCase(problems=problems, submissions=subs,
                           judge=judge, clock=_FakeClock())
    sid = uc.execute("s1", "p1", "python", "print(1)\n")
    assert sid
    assert len(judge.submitted) == 1
    assert subs.saved_dtos and subs.saved_dtos[0].judge0_tokens == ["tok-a"]


def test_submit_unknown_problem_rejected():
    uc = SubmitCodeUseCase(_FakeProblems(), _FakeSubmissions(), _FakeJudge(), _FakeClock())
    with pytest.raises(SubmitError, match="problem_missing"):
        uc.execute("s1", "ghost", "python", "print(1)")


def test_submit_unsupported_language_rejected():
    problems = _FakeProblems({"p1": _problem(langs=(Language.PYTHON,))})
    uc = SubmitCodeUseCase(problems, _FakeSubmissions(), _FakeJudge(), _FakeClock())
    with pytest.raises(SubmitError, match="language_not_whitelisted"):
        uc.execute("s1", "p1", "java", "class A {}")


def test_submit_invalid_language_rejected():
    problems = _FakeProblems({"p1": _problem()})
    uc = SubmitCodeUseCase(problems, _FakeSubmissions(), _FakeJudge(), _FakeClock())
    with pytest.raises(SubmitError, match="unsupported_language"):
        uc.execute("s1", "p1", "brainfuck", "+++")


# ---------------- RecordVerdictUseCase ----------------


def _accepted_result() -> Judge0Result:
    return Judge0Result(raw={}, verdict=Verdict.ACCEPTED, stdout="1\n",
                         stderr=None, time_ms=10, memory_kb=1024)


def _wa_result() -> Judge0Result:
    return Judge0Result(raw={}, verdict=Verdict.WRONG_ANSWER, stdout="2\n",
                         stderr=None, time_ms=10, memory_kb=1024)


def _pending_sub() -> DomainSubmission:
    return DomainSubmission(
        id="sub-1", session_id="s1", language=Language.PYTHON,
        source_code="print(1)\n",
        submitted_at=datetime(2026, 5, 10, tzinfo=timezone.utc),
    )


def test_record_verdict_persists_and_broadcasts():
    sub = _pending_sub()
    subs = _FakeSubmissions({"sub-1": sub})
    bc = _FakeBroadcaster()
    RecordVerdictUseCase(submissions=subs, broadcaster=bc).execute(
        "sub-1", [_accepted_result()]
    )
    assert subs.by_id["sub-1"].state == SubmissionState.JUDGED
    assert subs.by_id["sub-1"].verdict() == Verdict.ACCEPTED
    assert bc.pushed[0][0] == "s1"
    assert bc.pushed[0][1] == "verdict"


def test_record_verdict_idempotent_callback_then_poll():
    """Plan REV-8: callback + poll both fire; second one drops silently."""
    sub = _pending_sub()
    subs = _FakeSubmissions({"sub-1": sub})
    bc = _FakeBroadcaster()
    uc = RecordVerdictUseCase(submissions=subs, broadcaster=bc)
    uc.execute("sub-1", [_accepted_result()])
    # Race: poll fetches different result (shouldn't happen, but harden)
    uc.execute("sub-1", [_wa_result()])
    assert subs.by_id["sub-1"].verdict() == Verdict.ACCEPTED  # unchanged


def test_record_verdict_drops_non_terminal():
    sub = _pending_sub()
    subs = _FakeSubmissions({"sub-1": sub})
    bc = _FakeBroadcaster()
    pending = Judge0Result(raw={}, verdict=Verdict.PENDING, stdout=None,
                           stderr=None, time_ms=None, memory_kb=None)
    RecordVerdictUseCase(submissions=subs, broadcaster=bc).execute(
        "sub-1", [pending, _accepted_result()]
    )
    assert subs.by_id["sub-1"].state == SubmissionState.PENDING
    assert bc.pushed == []


def test_record_verdict_aggregates_worst_verdict_first():
    """If 3 testcases run, ACCEPTED + WRONG_ANSWER + ACCEPTED → WA."""
    sub = _pending_sub()
    subs = _FakeSubmissions({"sub-1": sub})
    bc = _FakeBroadcaster()
    RecordVerdictUseCase(submissions=subs, broadcaster=bc).execute(
        "sub-1", [_accepted_result(), _wa_result(), _accepted_result()]
    )
    assert subs.by_id["sub-1"].verdict() == Verdict.WRONG_ANSWER


def test_per_testcase_hides_stdout_and_expected_for_hidden_cases():
    """Hidden testcases must not leak stdout/expected to candidate; example ones may."""
    sub = _pending_sub()
    subs = _FakeSubmissions({"sub-1": sub})
    bc = _FakeBroadcaster()
    RecordVerdictUseCase(submissions=subs, broadcaster=bc).execute(
        "sub-1",
        [_accepted_result(), _wa_result()],
        example_flags=[True, False],
        example_expected=["1\n", "should-not-leak"],
    )
    rows = subs.by_id["sub-1"].per_testcase_results
    assert len(rows) == 2
    # Example row exposes stdout + expected
    assert rows[0]["is_example"] is True
    assert rows[0]["stdout"] == "1\n"
    assert rows[0]["expected"] == "1\n"
    # Hidden row keeps verdict/time/memory but omits stdout/expected entirely
    assert rows[1]["is_example"] is False
    assert "stdout" not in rows[1]
    assert "expected" not in rows[1]
    assert rows[1]["verdict"] == Verdict.WRONG_ANSWER.value


def test_per_testcase_defaults_when_no_flags_provided():
    """If callback doesn't supply example metadata, every row is treated as hidden."""
    sub = _pending_sub()
    subs = _FakeSubmissions({"sub-1": sub})
    bc = _FakeBroadcaster()
    RecordVerdictUseCase(submissions=subs, broadcaster=bc).execute(
        "sub-1", [_accepted_result()]
    )
    rows = subs.by_id["sub-1"].per_testcase_results
    assert rows[0]["is_example"] is False
    assert "stdout" not in rows[0]
