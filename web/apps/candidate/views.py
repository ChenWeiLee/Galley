"""
Candidate-flow views (Step 5).

- /t/<token>/   first hit consumes the admission ticket; sets cookie; redirects
- /enter/<reentry_token>/   interviewer-minted recovery; sets cookie; redirects
- /session/    candidate's coding page (cookie-protected)
- /api/sessions/<id>/remaining   countdown re-anchor (Step 6 will populate)
"""
from __future__ import annotations

from django.http import Http404, HttpRequest, HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.urls import reverse

from domain.usecases.admit_candidate import AdmissionError, AdmitCandidateUseCase
from domain.usecases.reentry import ReentryError, ReentryUseCase

from web.apps.scheduling.adapters import DjangoQScheduler

from .clock import DjangoServerClock
from .cookies import read_session_cookie, set_session_cookie
from .models import InterviewSession
from .repos import DjangoReentryRepository, DjangoSessionRepository, DjangoTokenRepository


def _admit_uc() -> AdmitCandidateUseCase:
    # BUG-1 fix: scheduler is a required dataclass field; missing it crashes
    # the entire token-consume path on first hit.
    return AdmitCandidateUseCase(
        sessions=DjangoSessionRepository(),
        tokens=DjangoTokenRepository(),
        clock=DjangoServerClock(),
        scheduler=DjangoQScheduler(),
    )


def _reentry_uc() -> ReentryUseCase:
    return ReentryUseCase(
        sessions=DjangoSessionRepository(),
        reentries=DjangoReentryRepository(),
    )


def consume_token(request: HttpRequest, token: str) -> HttpResponse:
    """First-hit: consume admission token → cookie → redirect to /session/."""
    try:
        session = _admit_uc().execute(token)
    except AdmissionError as e:
        # 410 Gone is correct for "consumed/expired"; 404 for unknown.
        if str(e) == "session_missing":
            raise Http404("session not found")
        return render(request, "candidate/admission_failed.html", {"reason": str(e)},
                      status=410)

    response = HttpResponseRedirect(reverse("candidate:session_page"))
    set_session_cookie(response, session.id)
    return response


def consume_reentry(request: HttpRequest, token: str) -> HttpResponse:
    """Recovery hit: consume reentry token → cookie → redirect."""
    try:
        session = _reentry_uc().consume(token)
    except ReentryError as e:
        return render(request, "candidate/admission_failed.html", {"reason": str(e)},
                      status=410)
    response = HttpResponseRedirect(reverse("candidate:session_page"))
    set_session_cookie(response, session.id)
    return response


def session_page(request: HttpRequest) -> HttpResponse:
    """
    Candidate coding page. Reads cookie, loads session, renders Monaco UI
    + the problem's markdown statement rendered to HTML.
    """
    import markdown as md
    from web.apps.interviewer.models import Problem

    session_id = read_session_cookie(request)
    if not session_id:
        return render(request, "candidate/admission_failed.html",
                      {"reason": "no_cookie"}, status=401)
    try:
        session = InterviewSession.objects.get(id=session_id)
    except InterviewSession.DoesNotExist:
        return render(request, "candidate/admission_failed.html",
                      {"reason": "session_missing"}, status=410)
    if session.state == InterviewSession.STATE_FROZEN:
        return render(request, "candidate/admission_failed.html",
                      {"reason": "time_up"}, status=410)

    problem = Problem.objects.filter(slug=session.problem_slug).first()
    problem_html = ""
    if problem and problem.statement_md:
        problem_html = md.markdown(
            problem.statement_md,
            extensions=["fenced_code", "tables", "sane_lists"],
        )

    return render(
        request,
        "candidate/session.html",
        {
            "session": session,
            "problem": problem,
            "problem_html": problem_html,
            "remaining_seconds": (
                int((session.deadline_utc - DjangoServerClock().now()).total_seconds())
                if session.deadline_utc
                else session.duration_seconds
            ),
        },
    )


def last_snapshot(request: HttpRequest, session_id: str) -> JsonResponse:
    """
    Step 7 reconnect helper.

    On WS reconnect the client fetches its own last persisted snapshot to
    re-anchor the editor (cadence: every 5s = ≤7.5s loss window).
    """
    cookie_id = read_session_cookie(request)
    if cookie_id != session_id:
        return JsonResponse({"error": "forbidden"}, status=403)
    from .models import CodeSnapshot
    row = (
        CodeSnapshot.objects.filter(session_id=session_id)
        .order_by("-captured_at")
        .first()
    )
    if row is None:
        return JsonResponse({"language": None, "source_code": ""})
    return JsonResponse(
        {"language": row.language, "source_code": row.source_code,
         "captured_at": row.captured_at.isoformat()}
    )


def session_remaining(request: HttpRequest, session_id: str) -> JsonResponse:
    """
    Step 6 / Patch #2 — countdown re-anchor. Browser polls every 5s.
    Authoritative: returns deadline_utc - clock.now() with state.
    """
    cookie_id = read_session_cookie(request)
    if cookie_id != session_id:
        return JsonResponse({"error": "forbidden"}, status=403)
    try:
        s = InterviewSession.objects.get(id=session_id)
    except InterviewSession.DoesNotExist:
        return JsonResponse({"error": "not_found"}, status=404)
    if s.deadline_utc is None:
        return JsonResponse({"remaining_seconds": s.duration_seconds, "state": s.state})
    remaining = int((s.deadline_utc - DjangoServerClock().now()).total_seconds())
    return JsonResponse({"remaining_seconds": max(remaining, 0), "state": s.state})
