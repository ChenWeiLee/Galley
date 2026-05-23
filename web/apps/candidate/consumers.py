"""
Candidate-side WebSocket consumer (Step 7).

Receives `{type: "snapshot", code, language}` messages from Monaco
~every 1.5s. Server persists every Nth snapshot (5s wall-time durability)
and broadcasts to `session:<id>` group so interviewer observers see typing.

Layer-skip note (domain/README.md): we write CodeSnapshot rows directly via
ORM; there are no domain invariants to enforce on append-only event firehoses.
"""
from __future__ import annotations

import json

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.utils import timezone

from web.apps.candidate.cookies import read_session_cookie

from .models import CodeSnapshot, InterviewSession


def _group(session_id: str) -> str:
    return f"session_{session_id}"


class CandidateConsumer(AsyncJsonWebsocketConsumer):
    """
    Connect path: ws://.../ws/candidate/<session_id>/
    Authenticated by signed cookie (read in connect()).
    """

    async def connect(self):
        self.session_id = self.scope["url_route"]["kwargs"]["session_id"]
        cookie_session_id = await sync_to_async(self._read_cookie)()
        if cookie_session_id != self.session_id:
            await self.close(code=4403)
            return
        await self.channel_layer.group_add(_group(self.session_id), self.channel_name)
        await self.accept()
        self._last_persisted_at = None

    def _read_cookie(self) -> str | None:
        # The HTTP cookie is in scope["cookies"] for ASGI WS.
        # Django's signing requires a request-like object; reuse cookies module
        # by faking the minimal interface. Easier: extract value from scope.
        from django.conf import settings
        from django.core import signing

        raw = (self.scope.get("cookies") or {}).get(settings.INTERVIEW_SESSION_COOKIE_NAME)
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

    async def disconnect(self, code):
        if hasattr(self, "session_id"):
            await self.channel_layer.group_discard(_group(self.session_id), self.channel_name)

    async def receive_json(self, content, **kwargs):
        if content.get("type") != "snapshot":
            return
        code = content.get("code", "")
        language = content.get("language", "python")
        await self._maybe_persist(code, language)
        # Always broadcast so observers get sub-second cadence.
        await self.channel_layer.group_send(
            _group(self.session_id),
            {
                "type": "snapshot.broadcast",
                "code": code,
                "language": language,
                "ts": timezone.now().isoformat(),
            },
        )

    @sync_to_async
    def _maybe_persist(self, code: str, language: str) -> None:
        # 5s durability cadence — Architect REV-13 → 12 snapshots/min.
        now = timezone.now()
        if self._last_persisted_at and (now - self._last_persisted_at).total_seconds() < 5:
            return
        try:
            session = InterviewSession.objects.get(id=self.session_id)
        except InterviewSession.DoesNotExist:
            return
        CodeSnapshot.objects.create(session=session, language=language, source_code=code)
        self._last_persisted_at = now

    # Group handler — mirrors snapshots back to the candidate's own socket.
    # Keeps multi-tab consistent if the candidate ever opens 2 windows.
    async def snapshot_broadcast(self, event):
        # Candidate already sent this; no-op to avoid echo loop.
        return


class ObserverConsumer(AsyncJsonWebsocketConsumer):
    """
    Interviewer-side observer. ws://.../ws/observe/<session_id>/

    Authenticated by Django session (interviewer login). For Step 7 we accept
    any logged-in staff user; Step 10 will scope by ownership.
    """

    async def connect(self):
        self.session_id = self.scope["url_route"]["kwargs"]["session_id"]
        user = self.scope.get("user")
        if not user or not user.is_authenticated or not user.is_staff:
            await self.close(code=4403)
            return
        await self.channel_layer.group_add(_group(self.session_id), self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, "session_id"):
            await self.channel_layer.group_discard(_group(self.session_id), self.channel_name)

    async def snapshot_broadcast(self, event):
        await self.send_json({
            "type": "snapshot",
            "code": event["code"],
            "language": event["language"],
            "ts": event["ts"],
        })

    # Step 8 will add a verdict_broadcast handler too; same group, different type.
    async def verdict_broadcast(self, event):
        await self.send_json({
            "type": "verdict",
            "submission_id": event["submission_id"],
            "verdict": event["verdict"],
        })
