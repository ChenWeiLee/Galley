"""
RecordVerdictUseCase — idempotent verdict ingestion (Plan REV-8).

Receives verdicts via either:
- Judge0 callback (primary path, low latency)
- Poll fallback (durability path; survives callback unreachable)

Idempotency: once a Submission has a terminal verdict, subsequent calls are
no-ops. Implemented inside `Submission.record_verdict` (entity invariant).

After persisting, broadcasts a `verdict` event to the session group so
interviewer observers update without polling.
"""
from __future__ import annotations

from dataclasses import dataclass

from domain.entities import Judge0Result
from domain.ports import LiveBroadcaster, SubmissionRepository


class RecordVerdictError(Exception):
    pass


@dataclass
class RecordVerdictUseCase:
    submissions: SubmissionRepository
    broadcaster: LiveBroadcaster

    def execute(
        self,
        submission_id: str,
        judge_results: list[Judge0Result],
        example_flags: list[bool] | None = None,
        example_expected: list[str] | None = None,
    ) -> None:
        """
        Record per-testcase results + aggregated verdict.

        `example_flags[i]` indicates whether testcase i was tagged is_example;
        when True the candidate already saw its stdin/expected, so the
        per-testcase row may include stdout + expected for diagnostic display.
        Hidden testcases never expose stdout/expected to candidates.
        """
        sub = self.submissions.get(submission_id)
        if sub is None:
            raise RecordVerdictError("submission_missing")

        all_terminal = all(r.is_terminal() for r in judge_results)
        if not all_terminal:
            return  # poll fallback retries

        # Build per-testcase result list. Always include verdict/time/memory.
        # For example testcases (or accepted ones at example_flags==None) we
        # also include stdout + expected for diagnostic display in the UI.
        per_testcase: list[dict] = []
        example_flags = example_flags or [False] * len(judge_results)
        example_expected = example_expected or [""] * len(judge_results)
        for i, r in enumerate(judge_results):
            entry = {
                "idx": i,
                "verdict": r.verdict.value,
                "time_ms": r.time_ms,
                "memory_kb": r.memory_kb,
                "is_example": bool(example_flags[i]) if i < len(example_flags) else False,
            }
            if entry["is_example"]:
                entry["stdout"] = r.stdout or ""
                entry["expected"] = (example_expected[i] if i < len(example_expected) else "")
            per_testcase.append(entry)
        sub.per_testcase_results = per_testcase

        # Aggregate verdict: any non-Accepted wins (worst-of).
        worst = next((r for r in judge_results if not r.is_accepted()),
                     judge_results[0] if judge_results else None)
        if worst is None:
            return

        sub.record_verdict(worst)
        self.submissions.save(sub)

        self.broadcaster.push(
            sub.session_id,
            "verdict",
            {"submission_id": sub.id, "verdict": sub.verdict().value},
        )
