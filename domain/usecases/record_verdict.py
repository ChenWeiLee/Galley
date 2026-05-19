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

    def execute(self, submission_id: str, judge_results: list[Judge0Result]) -> None:
        sub = self.submissions.get(submission_id)
        if sub is None:
            raise RecordVerdictError("submission_missing")

        # Aggregate: any non-terminal → still pending. All terminal → use
        # the worst (any non-Accepted dominates).
        all_terminal = all(r.is_terminal() for r in judge_results)
        if not all_terminal:
            return  # caller will retry (poll fallback handles)

        worst = next((r for r in judge_results if not r.is_accepted()),
                     judge_results[0] if judge_results else None)
        if worst is None:
            return

        # Idempotent: Submission.record_verdict drops the call if already JUDGED.
        sub.record_verdict(worst)
        self.submissions.save(sub)

        self.broadcaster.push(
            sub.session_id,
            "verdict",
            {"submission_id": sub.id, "verdict": sub.verdict().value},
        )
