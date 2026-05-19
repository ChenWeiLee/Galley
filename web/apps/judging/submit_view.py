"""
Real submission view (Step 8).

Replaces the walking-skeleton submit endpoint for cookie-authenticated
candidates. The walking skeleton at `/skeleton/...` stays — it's the
no-auth diagnostic path.

POST /api/sessions/<id>/submit  body: {language, source_code}
"""
from __future__ import annotations

import json

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from domain.usecases.submit_code import SubmitCodeUseCase, SubmitError

from web.apps.candidate.clock import DjangoServerClock
from web.apps.candidate.cookies import read_session_cookie
from web.apps.candidate.models import InterviewSession

from .adapters import Judge0Client
from .repos import DjangoSubmissionRepository


def _submit_uc() -> SubmitCodeUseCase:
    from web.apps.interviewer.repos import DjangoProblemRepository

    return SubmitCodeUseCase(
        problems=DjangoProblemRepository(),
        submissions=DjangoSubmissionRepository(),
        judge=Judge0Client(),
        clock=DjangoServerClock(),
    )


@csrf_exempt  # candidate page is its own surface; CSRF via signed cookie
def submit(request: HttpRequest, session_id: str) -> JsonResponse:
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)
    cookie_id = read_session_cookie(request)
    if cookie_id != session_id:
        return JsonResponse({"error": "forbidden"}, status=403)
    try:
        session = InterviewSession.objects.get(id=session_id)
    except InterviewSession.DoesNotExist:
        return JsonResponse({"error": "not_found"}, status=404)
    if session.state == InterviewSession.STATE_FROZEN:
        return JsonResponse({"error": "session_frozen"}, status=409)

    payload = json.loads(request.body)
    language = payload.get("language", "python")
    source = payload.get("source_code", "")

    try:
        sub_id = _submit_uc().execute(
            session_id=session.id,
            problem_slug=session.problem_slug,
            language=language,
            source_code=source,
        )
    except SubmitError as e:
        return JsonResponse({"error": str(e)}, status=400)

    return JsonResponse({"submission_id": sub_id, "state": "pending"})
