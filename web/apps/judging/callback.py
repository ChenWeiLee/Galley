"""
Judge0 callback view + poll-fallback task (Step 8).

Callback URL: `/judge0/callback?submission_id=<id>`
Auth: shared HMAC secret in `X-Auth-Token` header (configured via
`JUDGE0_CALLBACK_HMAC_SECRET` and `CALLBACK_GLOBAL_HEADERS` on Judge0).

Idempotency: callback + poll arriving for the same submission resolves to
exactly one verdict (RecordVerdictUseCase + Submission entity invariant).
"""
from __future__ import annotations

import hmac
import json

from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from domain.usecases.record_verdict import RecordVerdictError, RecordVerdictUseCase

from web.apps.interviewer.broadcaster import ChannelsBroadcaster

from .adapters import Judge0Client
from .models import Submission
from .repos import DjangoSubmissionRepository


def _record_uc() -> RecordVerdictUseCase:
    return RecordVerdictUseCase(
        submissions=DjangoSubmissionRepository(),
        broadcaster=ChannelsBroadcaster(),
    )


def _example_metadata_for(sub: Submission) -> tuple[list[bool], list[str]]:
    """Look up the problem and return (is_example_flags, expected_stdouts) so
    RecordVerdictUseCase can decorate per-testcase rows with diagnostic data
    for the example testcases only."""
    from web.apps.interviewer.models import Problem

    p = Problem.objects.filter(slug=sub.problem_slug).first()
    if not p:
        return [], []
    flags = []
    expected = []
    for tc in p.testcases.all():
        flags.append(bool(tc.is_example))
        expected.append(tc.expected_stdout)
    return flags, expected


@csrf_exempt
def judge0_callback(request: HttpRequest) -> JsonResponse:
    """Judge0 hits this when a submission finishes."""
    if request.method != "PUT" and request.method != "POST":
        return JsonResponse({"error": "PUT/POST only"}, status=405)

    expected = settings.JUDGE0_CALLBACK_HMAC_SECRET
    received = request.headers.get("X-Auth-Token", "")
    if not expected or not hmac.compare_digest(expected, received):
        return JsonResponse({"error": "unauthorized"}, status=401)

    submission_id = request.GET.get("submission_id", "")
    if not submission_id:
        return JsonResponse({"error": "missing submission_id"}, status=400)

    sub = Submission.objects.filter(id=submission_id).first()
    if sub is None:
        return JsonResponse({"error": "submission not found"}, status=404)

    if not sub.judge0_tokens:
        return JsonResponse({"error": "no judge tokens"}, status=400)
    results = Judge0Client().fetch_results(sub.judge0_tokens)
    flags, expected_stdouts = _example_metadata_for(sub)

    try:
        _record_uc().execute(submission_id, results, flags, expected_stdouts)
    except RecordVerdictError as e:
        return JsonResponse({"error": str(e)}, status=404)
    return JsonResponse({"status": "recorded"})


def poll_pending_submissions() -> int:
    """
    django-q2 scheduled task — every 5s, finds PENDING submissions older than
    5s and pulls verdicts from Judge0. The poll-fallback path proven in Step 3.

    Idempotent: callbacks may have already resolved the submission; the
    Submission entity drops the duplicate.
    """
    from datetime import timedelta

    from django.utils import timezone

    cutoff = timezone.now() - timedelta(seconds=5)
    pending = Submission.objects.filter(state=Submission.STATE_PENDING,
                                        submitted_at__lte=cutoff)
    resolved = 0
    client = Judge0Client()
    uc = _record_uc()
    for sub in pending:
        if not sub.judge0_tokens:
            continue
        try:
            results = client.fetch_results(sub.judge0_tokens)
        except Exception:  # noqa: BLE001
            continue
        if not all(r.is_terminal() for r in results):
            continue
        flags, expected_stdouts = _example_metadata_for(sub)
        try:
            uc.execute(sub.id, results, flags, expected_stdouts)
            resolved += 1
        except RecordVerdictError:
            continue
    return resolved
