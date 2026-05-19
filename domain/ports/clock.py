"""
ServerClock — single source of time (Patch #2 / Plan REV-2).

The session's `deadline_utc` is computed once at admission, from
`clock.now() + duration`. Never read wall clocks elsewhere — auto-submit jobs,
countdown displays, and AC #4.2 drift measurement all reference `deadline_utc`.

The browser, of course, has its own clock; we treat it as untrusted and
re-anchor it via `GET /api/sessions/<id>/remaining` every 5 seconds.
"""
from __future__ import annotations

from datetime import datetime
from typing import Protocol


class ServerClock(Protocol):
    """The only sanctioned source of time inside `domain/`."""

    def now(self) -> datetime:
        """Return the current UTC time."""
        ...
