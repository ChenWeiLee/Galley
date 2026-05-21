"""
Interviewer dashboard views (Step 10).

Routes:
- /dashboard            session list + "Create session" form
- /dashboard/create     POST: create session, issue token, return URL
- /dashboard/<id>/reentry   POST: mint reentry link (rate-limited 3/session)
- /dashboard/<id>/observe   live observe page (uses Step 7 ObserverConsumer)
- /dashboard/<id>/review    post-interview review (submissions + events + snapshots)
"""
from __future__ import annotations

from datetime import timedelta

from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

from domain.usecases.reentry import ReentryError, ReentryUseCase

from web.apps.candidate.models import (
    AntiCheatEvent,
    CodeSnapshot,
    InterviewSession,
    Token,
)
from web.apps.candidate.repos import (
    DjangoReentryRepository,
    DjangoSessionRepository,
)
from web.apps.judging.models import Submission

from .models import Problem


def _is_staff(u) -> bool:
    return u.is_authenticated and u.is_staff


staff_required = user_passes_test(_is_staff)


@login_required
@staff_required
def dashboard(request: HttpRequest) -> HttpResponse:
    sessions = InterviewSession.objects.filter(
        interviewer_username=request.user.username
    ).order_by("-created_at")[:50]
    problems = Problem.objects.all().order_by("slug")
    return render(
        request,
        "interviewer/dashboard.html",
        {"sessions": sessions, "problems": problems},
    )


@login_required
@staff_required
def create_session(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)
    problem_slug = request.POST.get("problem_slug", "").strip()
    candidate_label = request.POST.get("candidate_label", "").strip() or "candidate"
    duration_min = int(request.POST.get("duration_minutes", "60"))

    if not Problem.objects.filter(slug=problem_slug).exists():
        return JsonResponse({"error": "unknown problem"}, status=400)
    if duration_min < 1 or duration_min > 240:
        return JsonResponse({"error": "duration must be 1..240 minutes"}, status=400)

    sessions_repo = DjangoSessionRepository()
    session = sessions_repo.create(
        problem_slug=problem_slug,
        candidate_label=candidate_label,
        duration_seconds=duration_min * 60,
        interviewer_username=request.user.username,
    )
    # Issue admission token (24h TTL).
    token = Token.objects.create(
        session_id=session.id,
        expires_at=timezone.now() + timedelta(hours=24),
    )
    token_url = request.build_absolute_uri(
        reverse("candidate:consume_token", args=[token.token])
    )
    return JsonResponse({
        "session_id": session.id,
        "token_url": token_url,
        "expires_at": token.expires_at.isoformat(),
    })


@login_required
@staff_required
def mint_reentry(request: HttpRequest, session_id: str) -> HttpResponse:
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)
    try:
        session = InterviewSession.objects.get(id=session_id)
    except InterviewSession.DoesNotExist:
        raise Http404
    if session.interviewer_username != request.user.username:
        return JsonResponse({"error": "forbidden"}, status=403)

    uc = ReentryUseCase(
        sessions=DjangoSessionRepository(),
        reentries=DjangoReentryRepository(),
    )
    try:
        token = uc.mint(session_id)
    except ReentryError as e:
        return JsonResponse({"error": str(e)}, status=409)
    reentry_url = request.build_absolute_uri(
        reverse("candidate:consume_reentry", args=[token])
    )
    return JsonResponse({"reentry_url": reentry_url})


@login_required
@staff_required
def observe(request: HttpRequest, session_id: str) -> HttpResponse:
    try:
        session = InterviewSession.objects.get(id=session_id)
    except InterviewSession.DoesNotExist:
        raise Http404
    if session.interviewer_username != request.user.username:
        return HttpResponseRedirect(reverse("interviewer:dashboard"))
    return render(request, "interviewer/observe.html", {"session": session})


@login_required
@staff_required
def review(request: HttpRequest, session_id: str) -> HttpResponse:
    try:
        session = InterviewSession.objects.get(id=session_id)
    except InterviewSession.DoesNotExist:
        raise Http404
    if session.interviewer_username != request.user.username:
        return HttpResponseRedirect(reverse("interviewer:dashboard"))
    submissions = Submission.objects.filter(session_id=session_id).order_by("-submitted_at")
    events = AntiCheatEvent.objects.filter(session=session).order_by("captured_at")
    snapshots = CodeSnapshot.objects.filter(session=session).order_by("captured_at")
    return render(
        request,
        "interviewer/review.html",
        {
            "session": session,
            "submissions": submissions,
            "events": events,
            "snapshot_count": snapshots.count(),
        },
    )


@login_required
@staff_required
def review_snapshots_json(request: HttpRequest, session_id: str) -> JsonResponse:
    """REC-4 fix: snapshot replay data served as a real JSON endpoint instead
    of hand-rolled in the template. The replay slider in review.html fetches
    this once, so escaping bugs in template JSON (\\u2028, backticks, etc.)
    can't break the page."""
    try:
        session = InterviewSession.objects.get(id=session_id)
    except InterviewSession.DoesNotExist:
        raise Http404
    if session.interviewer_username != request.user.username:
        return JsonResponse({"error": "forbidden"}, status=403)
    rows = (
        CodeSnapshot.objects
        .filter(session=session)
        .order_by("captured_at")
        .values("captured_at", "language", "source_code")
    )
    return JsonResponse({
        "session_id": session_id,
        "snapshots": [
            {
                "t": s["captured_at"].isoformat(),
                "lang": s["language"],
                "code": s["source_code"] or "",
            }
            for s in rows
        ],
    })
