"""
Submission model — minimal for walking skeleton.

Step 8 will add HMAC for callback, full status lifecycle, idempotency keys.
"""
from __future__ import annotations

from django.db import models


class Submission(models.Model):
    STATE_PENDING = "pending"
    STATE_JUDGED = "judged"
    STATE_FAILED = "failed"
    STATE_CHOICES = [
        (STATE_PENDING, "Pending"),
        (STATE_JUDGED, "Judged"),
        (STATE_FAILED, "Failed"),
    ]

    id = models.CharField(primary_key=True, max_length=64)
    session_id = models.CharField(max_length=32, blank=True, default="", db_index=True)
    problem_slug = models.CharField(max_length=128)
    language = models.CharField(max_length=32)
    source_code = models.TextField()
    submitted_at = models.DateTimeField(auto_now_add=True)
    state = models.CharField(max_length=16, choices=STATE_CHOICES, default=STATE_PENDING)
    judge0_tokens = models.JSONField(default=list)
    verdict = models.CharField(max_length=32, blank=True, default="")
    stdout = models.TextField(blank=True, default="")
    stderr = models.TextField(blank=True, default="")
    time_ms = models.IntegerField(null=True, blank=True)
    memory_kb = models.IntegerField(null=True, blank=True)
    forced = models.BooleanField(default=False)

    class Meta:
        db_table = "submissions"
        indexes = [
            models.Index(fields=["state", "submitted_at"]),
            models.Index(fields=["session_id", "-submitted_at"]),
        ]

    def __str__(self) -> str:
        return f"Submission({self.id}, {self.state}, {self.verdict or '-'})"
