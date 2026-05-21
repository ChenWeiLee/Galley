"""
Walking-skeleton views (Step 3, Patch #1 option a).

`/skeleton/<slug>` serves a Monaco editor for one hardcoded problem.
`/skeleton/submit` dispatches to Judge0 via the real Judge0Client adapter.
`/api/submissions/<id>` polls the submission status (poll fallback proven here).

NO auth, NO token, NO cookie at this stage. Step 5 layers admission;
Step 8 layers proper submission flow on top of these views.
"""
from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone

from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

from domain.entities import Language
from domain.ports.judge import JudgeSubmissionRequest

from .adapters import Judge0Client
from .models import Submission

# Hardcoded skeleton problem — replaced by DB-backed problems in Step 4.
SKELETON_PROBLEM = {
    "slug": "hello-1",
    "title": "Skeleton: print 1",
    "statement": (
        "Write a program that prints the integer `1` followed by a newline.\n\n"
        "**Example**\n\nInput: (none)  \nOutput: `1`"
    ),
    "languages": ["python", "javascript"],
    "time_limit_ms": 2000,
    "memory_limit_kb": 262144,
    "testcases": [("", "1\n")],
}


def skeleton_page(request: HttpRequest, slug: str) -> "JsonResponse | object":
    """Render the candidate Monaco coding page for the hardcoded problem."""
    if slug != SKELETON_PROBLEM["slug"]:
        return JsonResponse({"error": "unknown skeleton slug"}, status=404)
    return render(request, "judging/skeleton.html", {"problem": SKELETON_PROBLEM})


# TODO Step 8: replace @csrf_exempt with token-bound CSRF check once
# token admission lands. The walking skeleton has no auth at all by design.
@csrf_exempt
def skeleton_submit(request: HttpRequest) -> JsonResponse:
    """
    Dispatch a submission to Judge0 and store a Submission row.

    Returns the submission id; the page polls /api/submissions/<id> until
    state != pending.
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    payload = json.loads(request.body)
    language = payload.get("language", "python")
    source = payload.get("source_code", "")

    if language not in SKELETON_PROBLEM["languages"]:
        return JsonResponse({"error": "language not whitelisted"}, status=400)

    sub_id = secrets.token_urlsafe(12)
    sub = Submission.objects.create(
        id=sub_id,
        problem_slug=SKELETON_PROBLEM["slug"],
        language=language,
        source_code=source,
        state=Submission.STATE_PENDING,
        judge0_tokens=[],
    )

    judge = Judge0Client()
    req = JudgeSubmissionRequest(
        language=Language(language),
        source_code=source,
        testcases=SKELETON_PROBLEM["testcases"],
        time_limit_ms=SKELETON_PROBLEM["time_limit_ms"],
        memory_limit_kb=SKELETON_PROBLEM["memory_limit_kb"],
    )
    try:
        tokens = judge.submit(req)
    except Exception as e:  # noqa: BLE001
        sub.state = Submission.STATE_FAILED
        sub.stderr = f"submit error: {e!r}"
        sub.save(update_fields=["state", "stderr"])
        return JsonResponse({"id": sub_id, "state": "failed", "error": str(e)}, status=502)

    sub.judge0_tokens = tokens
    sub.save(update_fields=["judge0_tokens"])
    return JsonResponse({"id": sub_id, "state": sub.state})


def submission_status(request: HttpRequest, sub_id: str) -> JsonResponse:
    """
    Poll for verdict (Plan REV-2 fallback path).

    Step 8 adds Judge0 callback as the primary path; this endpoint stays as
    the durability fallback.
    """
    try:
        sub = Submission.objects.get(id=sub_id)
    except Submission.DoesNotExist:
        return JsonResponse({"error": "not found"}, status=404)

    if sub.state == Submission.STATE_PENDING and sub.judge0_tokens:
        try:
            results = Judge0Client().fetch_results(sub.judge0_tokens)
        except Exception as e:  # noqa: BLE001
            return JsonResponse(
                {"id": sub_id, "state": sub.state, "fetch_error": str(e)}, status=200
            )
        all_terminal = all(r.is_terminal() for r in results)
        if all_terminal and results:
            terminal = next((r for r in results if not r.is_accepted()), results[0])
            sub.state = Submission.STATE_JUDGED
            sub.verdict = terminal.verdict.value
            sub.stdout = terminal.stdout or ""
            sub.stderr = terminal.stderr or ""
            sub.time_ms = terminal.time_ms
            sub.memory_kb = terminal.memory_kb
            # Real submission flow goes through RecordVerdictUseCase, which
            # populates per_testcase_results. Skeleton is single-testcase, so
            # we shim a synthetic entry here for UI consistency.
            sub.per_testcase_results = [{
                "idx": i,
                "verdict": r.verdict.value,
                "time_ms": r.time_ms,
                "memory_kb": r.memory_kb,
                "is_example": True,
                "stdout": r.stdout or "",
                "expected": SKELETON_PROBLEM["testcases"][i][1]
                            if i < len(SKELETON_PROBLEM["testcases"]) else "",
            } for i, r in enumerate(results)]
            sub.save()

    return JsonResponse(
        {
            "id": sub.id,
            "state": sub.state,
            "verdict": sub.verdict,
            "stdout": sub.stdout,
            "stderr": sub.stderr,
            "time_ms": sub.time_ms,
            "memory_kb": sub.memory_kb,
            "per_testcase_results": sub.per_testcase_results or [],
            "polled_at": datetime.now(timezone.utc).isoformat(),
        }
    )
