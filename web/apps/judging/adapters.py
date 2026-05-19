"""
Judge0 client adapter (Patch #1 option a).

This is the REAL Judge0 client. The walking skeleton (Step 3) uses it with
hardcoded URLs; Step 8 builds proper submission flow on top of the same
adapter — no throwaway code.

This file is the ONLY place that knows:
- Judge0 status enum (id 1-14) → our Verdict mapping
- base64 encoding of source/stdin/expected_stdout
- Judge0 batch API shape
- Language ID lookup table
"""
from __future__ import annotations

import base64
from typing import Any

import httpx
from django.conf import settings

from domain.entities import Judge0Result, Verdict
from domain.ports.judge import JudgeClient, JudgeSubmissionRequest

# Subset of Judge0 language IDs (1.13.x). Verify against your Judge0's /languages.
LANGUAGE_IDS: dict[str, int] = {
    "python": 71,  # Python 3.8.1
    "javascript": 63,  # Node.js 12.14.0
    "typescript": 74,  # TypeScript 3.7.4
    "java": 62,  # OpenJDK 13.0.1
    "go": 60,  # Go 1.13.5
    "cpp": 54,  # C++ (GCC 9.2.0)
    "csharp": 51,  # C# (Mono 6.6.0.161)
}

# Judge0 status id → our Verdict
STATUS_TO_VERDICT: dict[int, Verdict] = {
    1: Verdict.PENDING,  # In Queue
    2: Verdict.PENDING,  # Processing
    3: Verdict.ACCEPTED,
    4: Verdict.WRONG_ANSWER,
    5: Verdict.TIME_LIMIT_EXCEEDED,
    6: Verdict.COMPILE_ERROR,
    7: Verdict.RUNTIME_ERROR,  # SIGSEGV
    8: Verdict.RUNTIME_ERROR,  # SIGXFSZ
    9: Verdict.RUNTIME_ERROR,  # SIGFPE
    10: Verdict.RUNTIME_ERROR,  # SIGABRT
    11: Verdict.RUNTIME_ERROR,  # NZEC
    12: Verdict.RUNTIME_ERROR,  # Other
    13: Verdict.INTERNAL_ERROR,
    14: Verdict.MEMORY_LIMIT_EXCEEDED,
}


def _b64(s: str) -> str:
    return base64.b64encode(s.encode("utf-8")).decode("ascii")


def _b64d(s: str | None) -> str | None:
    if s is None:
        return None
    try:
        return base64.b64decode(s).decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return s


class Judge0Client(JudgeClient):
    """
    Concrete adapter implementing the JudgeClient port.

    `base_url` defaults to settings.JUDGE0_BASE_URL but can be overridden for
    integration tests pointing at a different Judge0 instance.
    """

    def __init__(self, base_url: str | None = None, callback_base_url: str | None = None):
        self.base_url = base_url or settings.JUDGE0_BASE_URL
        self.callback_base_url = callback_base_url or settings.JUDGE0_CALLBACK_BASE_URL

    def submit(self, request: JudgeSubmissionRequest) -> list[str]:
        if request.language.value not in LANGUAGE_IDS:
            raise ValueError(f"Unsupported language: {request.language.value}")
        language_id = LANGUAGE_IDS[request.language.value]

        submissions = [
            {
                "language_id": language_id,
                "source_code": _b64(request.source_code),
                "stdin": _b64(stdin),
                "expected_output": _b64(expected),
                "cpu_time_limit": request.time_limit_ms / 1000,
                "memory_limit": request.memory_limit_kb,
                # Walking skeleton: callback wired in Step 8. For now we POLL.
                # Step 8 will set callback_url here, e.g.:
                # "callback_url": f"{self.callback_base_url}/judge0/callback",
            }
            for stdin, expected in request.testcases
        ]

        with httpx.Client(timeout=10.0) as client:
            r = client.post(
                f"{self.base_url}/submissions/batch",
                params={"base64_encoded": "true", "wait": "false"},
                json={"submissions": submissions},
            )
            r.raise_for_status()
            data = r.json()
            return [item["token"] for item in data]

    def fetch_results(self, tokens: list[str]) -> list[Judge0Result]:
        if not tokens:
            return []
        with httpx.Client(timeout=10.0) as client:
            r = client.get(
                f"{self.base_url}/submissions/batch",
                params={
                    "tokens": ",".join(tokens),
                    "base64_encoded": "true",
                    "fields": "token,status,stdout,stderr,compile_output,time,memory",
                },
            )
            r.raise_for_status()
            items = r.json().get("submissions", [])
            return [self._map_to_result(item) for item in items]

    def _map_to_result(self, item: dict[str, Any]) -> Judge0Result:
        status_id = item.get("status", {}).get("id", 13)
        verdict = STATUS_TO_VERDICT.get(status_id, Verdict.INTERNAL_ERROR)
        time_str = item.get("time")
        time_ms = int(float(time_str) * 1000) if time_str else None
        return Judge0Result(
            raw=item,
            verdict=verdict,
            stdout=_b64d(item.get("stdout")),
            stderr=_b64d(item.get("stderr")) or _b64d(item.get("compile_output")),
            time_ms=time_ms,
            memory_kb=item.get("memory"),
        )
