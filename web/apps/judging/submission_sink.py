"""
ForcedSubmissionSink — wires AutoSubmit (Step 6) to the real submission flow
(Step 8). At deadline, materialize the latest snapshot as a forced submission
and dispatch it through SubmitCodeUseCase so it gets a verdict.
"""
from __future__ import annotations


class DjangoSubmissionSink:
    def record_forced(self, session_id: str, language: str, source: str) -> None:
        from web.apps.candidate.clock import DjangoServerClock
        from web.apps.candidate.models import InterviewSession
        from web.apps.interviewer.repos import DjangoProblemRepository

        from domain.usecases.submit_code import SubmitCodeUseCase, SubmitError

        from .adapters import Judge0Client
        from .repos import DjangoSubmissionRepository

        try:
            session = InterviewSession.objects.get(id=session_id)
        except InterviewSession.DoesNotExist:
            return

        uc = SubmitCodeUseCase(
            problems=DjangoProblemRepository(),
            submissions=DjangoSubmissionRepository(),
            judge=Judge0Client(),
            clock=DjangoServerClock(),
        )
        try:
            uc.execute(
                session_id=session.id,
                problem_slug=session.problem_slug,
                language=language or "python",
                source_code=source,
                forced=True,
            )
        except SubmitError:
            # If forced submission fails (e.g., empty code with strict
            # invariants), just record nothing — interviewer can see "no
            # forced submission" in the review page.
            return
