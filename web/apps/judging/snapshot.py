"""
SnapshotSource — Step 7 implementation.

Reads the latest CodeSnapshot row for a session. Used by AutoSubmitUseCase
at deadline_utc to materialize a forced submission from the candidate's last
durable snapshot.
"""
from __future__ import annotations

from web.apps.candidate.models import CodeSnapshot


class SnapshotSource:
    def latest_code(self, session_id: str) -> tuple[str, str] | None:
        row = (
            CodeSnapshot.objects.filter(session_id=session_id)
            .order_by("-captured_at")
            .first()
        )
        if row is None:
            return None
        return (row.language, row.source_code)
