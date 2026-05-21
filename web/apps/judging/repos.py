"""
DjangoSubmissionRepository — implements `domain.ports.SubmissionRepository`.

Returns ORM-typed `Submission` rows. Conversion between `domain.Submission`
dataclass and the ORM happens here.
"""
from __future__ import annotations

from datetime import datetime, timezone

from domain.entities import Judge0Result, Language
from domain.entities import Submission as DomainSubmission
from domain.entities import SubmissionState, Verdict

from .models import Submission as ORMSubmission


class DjangoSubmissionRepository:
    def get(self, submission_id: str) -> DomainSubmission | None:
        try:
            row = ORMSubmission.objects.get(id=submission_id)
        except ORMSubmission.DoesNotExist:
            return None
        return self._to_domain(row)

    def save(self, sub) -> DomainSubmission:
        """Accepts either a domain Submission OR the inline _PendingSubmission DTO."""
        # REC-3 fix: discriminate by type, not by hasattr (which silently
        # broke when fields were added/renamed). The inline DTO is anything
        # that isn't a DomainSubmission.
        if not isinstance(sub, DomainSubmission):
            ORMSubmission.objects.update_or_create(
                id=sub.id,
                defaults=dict(
                    session_id=sub.session_id,
                    problem_slug=sub.problem_slug,
                    language=sub.language,
                    source_code=sub.source_code,
                    judge0_tokens=sub.judge0_tokens,
                    forced=getattr(sub, "forced", False),
                    state=ORMSubmission.STATE_PENDING,
                ),
            )
            return self.get(sub.id)

        # Full domain entity (verdict update)
        defaults = dict(
            language=sub.language.value,
            source_code=sub.source_code,
            judge0_tokens=sub.judge0_tokens,
            forced=sub.forced,
            state=sub.state.value,
            per_testcase_results=getattr(sub, "per_testcase_results", []) or [],
        )
        if sub.result is not None:
            defaults.update(
                verdict=sub.result.verdict.value,
                stdout=sub.result.stdout or "",
                stderr=sub.result.stderr or "",
                time_ms=sub.result.time_ms,
                memory_kb=sub.result.memory_kb,
            )
        ORMSubmission.objects.update_or_create(
            id=sub.id, defaults={**defaults, "session_id": sub.session_id}
        )
        return self.get(sub.id)

    def list_for_session(self, session_id: str) -> list[DomainSubmission]:
        rows = ORMSubmission.objects.filter(session_id=session_id).order_by("-submitted_at")
        return [self._to_domain(r) for r in rows]

    @staticmethod
    def _to_domain(row: ORMSubmission) -> DomainSubmission:
        result = None
        if row.state == ORMSubmission.STATE_JUDGED and row.verdict:
            result = Judge0Result(
                raw={},
                verdict=Verdict(row.verdict),
                stdout=row.stdout or None,
                stderr=row.stderr or None,
                time_ms=row.time_ms,
                memory_kb=row.memory_kb,
            )
        # REC-2 fix: raise on unknown language so data drift (e.g. a deprecated
        # language removed from the enum) surfaces immediately instead of silently
        # rewriting every record's language to Python on read.
        return DomainSubmission(
            id=row.id,
            session_id=row.session_id,
            language=Language(row.language),
            source_code=row.source_code,
            submitted_at=row.submitted_at or datetime.now(timezone.utc),
            state=SubmissionState(row.state),
            judge0_tokens=list(row.judge0_tokens or []),
            result=result,
            forced=row.forced,
        )
