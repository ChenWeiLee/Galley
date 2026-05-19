"""
Signed-cookie helpers for the durable candidate credential (Plan REV-4).

The cookie carries `session_id` signed with Django's `signing` (TimestampSigner
+ SECRET_KEY-derived HMAC). Its TTL is enforced by `max_age`; a truncated /
forged value fails to verify.

Cookie attributes:
- HttpOnly (no JS access; reduces XSS impact)
- Secure (in prod — gated by DEBUG below)
- SameSite=Lax (lets the candidate click the token URL from email)
"""
from __future__ import annotations

from django.conf import settings
from django.core import signing
from django.http import HttpRequest, HttpResponse


def set_session_cookie(response: HttpResponse, session_id: str) -> None:
    signed = signing.dumps(session_id, salt="interview-judge.session")
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
            salt="interview-judge.session",
            max_age=settings.INTERVIEW_SESSION_COOKIE_MAX_AGE_SECONDS,
        )
    except signing.BadSignature:
        return None


def clear_session_cookie(response: HttpResponse) -> None:
    response.delete_cookie(settings.INTERVIEW_SESSION_COOKIE_NAME)
