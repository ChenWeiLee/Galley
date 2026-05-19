"""JudgeClient port — wraps Judge0 (or future replacement)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from domain.entities import Judge0Result, Language


@dataclass(frozen=True)
class JudgeSubmissionRequest:
    """One unit of work for the judge: source + testcases."""

    language: Language
    source_code: str
    testcases: list[tuple[str, str]]  # (stdin, expected_stdout)
    time_limit_ms: int
    memory_limit_kb: int


class JudgeClient(Protocol):
    """
    Black-box judge interface (Plan Principle 2).

    The adapter at `web/apps/judging/adapters.py` is the ONLY code that knows
    Judge0's payload shape, language IDs, base64 encoding, and status enum.
    Use cases speak this Protocol exclusively.
    """

    def submit(self, request: JudgeSubmissionRequest) -> list[str]:
        """Dispatch the batch; return one Judge0 token per testcase."""
        ...

    def fetch_results(self, tokens: list[str]) -> list[Judge0Result]:
        """Pull current verdicts (used by the poll fallback in Plan REV-2)."""
        ...
