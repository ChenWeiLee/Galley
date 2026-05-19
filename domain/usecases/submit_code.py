"""
SubmitCodeUseCase — dispatches a candidate submission to Judge0.

Split from RecordVerdictUseCase (Architect concern #4 / Plan REV-8): one use
case dispatches; the other consumes the result. Idempotency is the boundary
contract — RecordVerdict tolerates callback + poll arriving for the same
submission and persists exactly one verdict.

This use case does NOT wait for a verdict; it returns the submission_id so the
view layer can return immediately. Verdict arrival happens via callback or
poll fallback (Plan REV-2).
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass

from domain.entities import Language
from domain.ports import ProblemRepository, ServerClock, SubmissionRepository
from domain.ports.judge import JudgeClient, JudgeSubmissionRequest


class SubmitError(Exception):
    """Raised when a submission cannot be dispatched."""


@dataclass
class SubmitCodeUseCase:
    problems: ProblemRepository
    submissions: SubmissionRepository
    judge: JudgeClient
    clock: ServerClock

    def execute(
        self,
        session_id: str,
        problem_slug: str,
        language: str,
        source_code: str,
        forced: bool = False,
    ) -> str:
        problem = self.problems.get_by_slug(problem_slug)
        if problem is None:
            raise SubmitError("problem_missing")
        try:
            lang = Language(language)
        except ValueError as e:
            raise SubmitError(f"unsupported_language:{language}") from e
        if lang not in problem.languages:
            raise SubmitError("language_not_whitelisted")

        sub_id = secrets.token_urlsafe(12)
        # Build the dispatch payload — testcases as (stdin, expected) pairs.
        request = JudgeSubmissionRequest(
            language=lang,
            source_code=source_code,
            testcases=[(tc.stdin, tc.expected_stdout) for tc in problem.testcases],
            time_limit_ms=problem.time_limit_ms,
            memory_limit_kb=problem.memory_limit_kb,
        )
        try:
            tokens = self.judge.submit(request)
        except Exception as e:  # noqa: BLE001
            raise SubmitError(f"judge_dispatch_failed:{e!r}") from e

        # Persist the submission; the SubmissionRepository's `create_pending`
        # method (added by adapter) writes the row + tokens atomically.
        self.submissions.save(
            _PendingSubmission(
                id=sub_id,
                session_id=session_id,
                problem_slug=problem_slug,
                language=language,
                source_code=source_code,
                judge0_tokens=tokens,
                forced=forced,
                submitted_at=self.clock.now(),
            )
        )
        return sub_id


@dataclass
class _PendingSubmission:
    """Lightweight DTO between use case and repo — kept inline to avoid
    a domain entity update; the repo adapter unpacks fields."""

    id: str
    session_id: str
    problem_slug: str
    language: str
    source_code: str
    judge0_tokens: list[str]
    forced: bool
    submitted_at: object
