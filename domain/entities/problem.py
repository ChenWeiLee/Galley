"""Problem + Testcase entities."""
from __future__ import annotations

from dataclasses import dataclass, field

from .values import Difficulty, Language


@dataclass
class Testcase:
    """One input/expected-output pair for a problem."""

    __test__ = False  # tell pytest not to collect this dataclass as a test class

    stdin: str
    expected_stdout: str
    is_example: bool = False  # examples shown in the problem statement
    weight: int = 1  # for partial-credit scoring (currently unused — pass/fail)

    def __post_init__(self) -> None:
        if self.weight < 1:
            raise ValueError("Testcase.weight must be >= 1")


@dataclass
class Problem:
    """
    A coding problem.

    Invariants enforced here so they can't be bypassed by the YAML loader OR
    the Django Admin (both write paths share `ImportProblemUseCase`, Patch #3).
    """

    slug: str
    title: str
    statement_md: str  # markdown body
    languages: list[Language]  # whitelist for this problem
    time_limit_ms: int = 2000
    memory_limit_kb: int = 262144  # 256 MB
    testcases: list[Testcase] = field(default_factory=list)
    title_zh: str = ""
    statement_md_zh: str = ""
    difficulty: Difficulty = Difficulty.EASY

    def __post_init__(self) -> None:
        if not self.slug:
            raise ValueError("Problem.slug is required")
        if not self.languages:
            raise ValueError("Problem must whitelist at least one language")
        if not any(tc.is_example for tc in self.testcases):
            raise ValueError(
                "Problem must include at least one example testcase "
                "(is_example=True) so the candidate sees an input format"
            )
        if self.time_limit_ms < 100 or self.time_limit_ms > 10_000:
            raise ValueError(
                "Problem.time_limit_ms must be in [100, 10000] — Judge0 max is ~15s"
            )
