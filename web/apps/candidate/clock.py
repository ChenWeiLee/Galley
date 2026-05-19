"""
ServerClock implementation (Patch #2).

Single, sanctioned wall-clock reader for the project. The web layer reads
time here; domain code never does.
"""
from __future__ import annotations

from datetime import datetime

from django.utils import timezone


class DjangoServerClock:
    """Production ServerClock — uses Django's timezone-aware `now()`."""

    def now(self) -> datetime:
        return timezone.now()
