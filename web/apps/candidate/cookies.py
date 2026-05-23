"""
Signed-cookie helpers for the durable candidate credential (Plan REV-4).

The cookie carries `session_id` signed with Django's `signing` (TimestampSigner
+ SECRET_KEY-derived HMAC). Its TTL is enforced by `max_age`; a truncated /
forged value fails to verify.

Cookie attributes:
- HttpOnly (no JS access; reduces XSS impact)
- Secure (in prod — gated by DEBUG below)
- SameSite=Lax (lets the candidate click the token URL from email)

TTL choice (REC-6 from Steps 5-10 architect review):
`INTERVIEW_SESSION_COOKIE_MAX_AGE_SECONDS` defaults to 18000 (5h). Plan REV-4
hinted at binding it to `session.freeze_at + 5min`, but that would require
the cookie issuer to know the session's deadline at mint time (currently
true for `set_session_cookie` from `admit`, but not for re-mints inside
`consumers.py`). The fixed 5h ceiling covers the longest planned interview
(60min) + reentries with 4h+ slack, which is safe because: (a) the server
still gates access by `InterviewSession.state == FROZEN`, so a stale cookie
past freeze_at gets a 410 from `session_page` (REC-1 fix), and (b) the
signed payload is just `session_id` — possession after freeze_at conveys
no extra privilege. If you ever need tighter TTL, mint with `max_age=
session.remaining_seconds(now) + 300` at `admit` time instead of the
settings default.
"""
from __future__ import annotations

from django.conf import settings
from django.core import signing
from django.http import HttpRequest, HttpResponse


def set_session_cookie(response: HttpResponse, session_id: str) -> None:
    signed = signing.dumps(session_id, salt="galley.session")
    response.set_cookie(
        key=settings.INTERVIEW_SESSION_COOKIE_NAME,
        value=signed,
        max_age=settings.INTERVIEW_SESSION_COOKIE_MAX_AGE_SECONDS,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="Lax",
    )


def read_session_cookie(request: HttpRequest) -> str | None:
    raw = request.COOKIES.get(settings.INTERVIEW_SESSION_COOKIE_NAME)
    if not raw:
        return None
    try:
        return signing.loads(
            raw,
            salt="galley.session",
            max_age=settings.INTERVIEW_SESSION_COOKIE_MAX_AGE_SECONDS,
        )
    except signing.BadSignature:
        return None


def clear_session_cookie(response: HttpResponse) -> None:
    response.delete_cookie(settings.INTERVIEW_SESSION_COOKIE_NAME)
