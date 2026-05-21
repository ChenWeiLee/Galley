"""Submission — one judge attempt within a session."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from .values import Judge0Result, Language, Verdict


class SubmissionState(str, Enum):
    PENDING = "pending"  # dispatched to Judge0, no verdict yet
    JUDGED = "judged"  # verdict received via callback or poll
    FAILED = "failed"  # internal error, never got a verdict


@dataclass
class Submission:
    """
    One submission attempt.

    Once a Submission has `state == JUDGED`, the verdict is final — never
    overwritten. This invariant is what makes "callback + poll arriving for
    same submission" safe (Plan REV-8 idempotency key = `(submission_id, judge0_token)`).
    """

    id: str
    session_id: str
    language: Language
    source_code: str
    submitted_at: datetime
    state: SubmissionState = SubmissionState.PENDING
    judge0_tokens: list[str] = field(default_factory=list)  # one token per testcase
    result: Judge0Result | None = None
    forced: bool = False  # True if auto-submit at deadline (vs candidate-initiated)
    per_testcase_results: list[dict] = field(default_factory=list)

    def record_verdict(self, result: Judge0Result) -> None:
        """Idempotent verdict recording. Once JUDGED, never re-records."""
        if self.state == SubmissionState.JUDGED:
            # Already final — drop the duplicate (callback + poll race).
            return
        if not result.is_terminal():
            raise ValueError(
                f"Submission {self.id} cannot be JUDGED with non-terminal verdict "
                f"{result.verdict.value}"
            )
        self.result = result
        self.state = SubmissionState.JUDGED

    def verdict(self) -> Verdict:
        if self.result is None:
            return Verdict.PENDING
        return self.result.verdict
