"""
Anti-cheat event capture endpoint (Step 9).

POST /api/sessions/<id>/events  body: {type, byte_len?, meta?}

Layer-skip note (domain/README.md): direct repo write, no use case. Append-only,
no invariants, no business rules — recording-not-blocking by design.

Privacy: never stores paste/copy content; only byte_len.
"""
from __future__ import annotations

import json

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .cookies import read_session_cookie
from .models import AntiCheatEvent, InterviewSession

ALLOWED_TYPES = {"visibility_change", "blur", "paste", "copy", "tab_count"}


@csrf_exempt
def post_event(request: HttpRequest, session_id: str) -> JsonResponse:
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)
    cookie_id = read_session_cookie(request)
    if cookie_id != session_id:
        return JsonResponse({"error": "forbidden"}, status=403)
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid json"}, status=400)

    event_type = payload.get("type")
    if event_type not in ALLOWED_TYPES:
        # Unknown event type → ignore silently (don't help adversaries probe)
        return JsonResponse({"status": "ignored"})

    try:
        session = InterviewSession.objects.get(id=session_id)
    except InterviewSession.DoesNotExist:
        return JsonResponse({"error": "not_found"}, status=404)

    AntiCheatEvent.objects.create(
        session=session,
        event_type=event_type,
        byte_len=payload.get("byte_len"),
        meta=payload.get("meta") or {},
    )
    return JsonResponse({"status": "logged"})
