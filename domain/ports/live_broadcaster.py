"""
LiveBroadcaster port — pushes events to a session's observers.

Implemented by `web/apps/interviewer/consumers.py` as a Channels group_send
adapter. Domain stays Channels-agnostic so we could swap to SSE later
without touching use cases.
"""
from __future__ import annotations

from typing import Protocol


class LiveBroadcaster(Protocol):
    """Push an event to all observers of a session (interviewer dashboards)."""

    def push(self, session_id: str, event_type: str, payload: dict) -> None: ...
