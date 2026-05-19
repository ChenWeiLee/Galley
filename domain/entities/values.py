"""
Value objects — immutable, identity-less.

`Judge0Result` is opaque (Plan REV-8): use cases never read Judge0's raw
status enum. They ask the value object questions like `is_accepted()` or
`is_compile_error()` and the value object hides Judge0's id-based status.
This means swapping Judge0 for piston/HustOJ later doesn't ripple into use cases.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Verdict(str, Enum):
    """The verdict our domain cares about. Mapped from Judge0 by the adapter."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    WRONG_ANSWER = "wrong_answer"
    TIME_LIMIT_EXCEEDED = "tle"
    MEMORY_LIMIT_EXCEEDED = "mle"
    RUNTIME_ERROR = "runtime_error"
    COMPILE_ERROR = "compile_error"
    INTERNAL_ERROR = "internal_error"


class Language(str, Enum):
    """Subset of Judge0 languages we support. See Plan §3.4 — 5-7 mainstream."""

    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    JAVA = "java"
    GO = "go"
    CPP = "cpp"
    CSHARP = "csharp"


@dataclass(frozen=True)
class Judge0Result:
    """
    Opaque wrapper over a Judge0 submission result.

    Constructed by the adapter (`web/apps/judging/adapters.py`); domain code
    never reads `.raw` directly. Use the boolean predicates instead.
    """

    raw: dict  # the JSON Judge0 returned, unmolested
    verdict: Verdict
    stdout: str | None
    stderr: str | None
    time_ms: int | None
    memory_kb: int | None

    def is_accepted(self) -> bool:
        return self.verdict == Verdict.ACCEPTED

    def is_compile_error(self) -> bool:
        return self.verdict == Verdict.COMPILE_ERROR

    def is_runtime_error(self) -> bool:
        return self.verdict == Verdict.RUNTIME_ERROR

    def is_terminal(self) -> bool:
        return self.verdict != Verdict.PENDING


@dataclass(frozen=True)
class TokenTicket:
    """
    A single-use admission ticket.

    NOT a credential — once consumed, the candidate is given an
    `interview_session` cookie that survives reload (Plan REV-4). The
    ticket itself is dead after first hit and never re-accepted.
    """

    token: str  # urlsafe random, 32 bytes
    session_id: str
    expires_at_iso: str
    consumed_at_iso: str | None = None

    def is_consumable(self) -> bool:
        return self.consumed_at_iso is None
