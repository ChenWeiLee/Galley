"""
Candidate-flow ORM models.

InterviewSession + Token + ReentryToken: the token-vs-cookie separation
(Plan REV-4) lives here. CodeSnapshot lands in Step 7.
"""
from __future__ import annotations

import secrets
from django.db import models
from django.utils import timezone


def _new_token() -> str:
    return secrets.token_urlsafe(32)


def _new_session_id() -> str:
    return secrets.token_urlsafe(12)


class InterviewSession(models.Model):
    STATE_PENDING = "pending"
    STATE_ACTIVE = "active"
    STATE_FROZEN = "frozen"
    STATE_REVIEWED = "reviewed"
    STATE_CHOICES = [
        (STATE_PENDING, "Pending"),
        (STATE_ACTIVE, "Active"),
        (STATE_FROZEN, "Frozen"),
        (STATE_REVIEWED, "Reviewed"),
    ]

    id = models.CharField(primary_key=True, max_length=32, default=_new_session_id)
    problem_slug = models.SlugField(max_length=128)  # FK by slug, not by id
    candidate_label = models.CharField(max_length=200)
    interviewer_username = models.CharField(max_length=150, blank=True, default="")
    duration_seconds = models.IntegerField()  # set at creation, immutable

    # Patch #2 — single source of time. Set ONCE on admit, never reassigned.
    deadline_utc = models.DateTimeField(null=True, blank=True, db_index=True)
    started_at = models.DateTimeField(null=True, blank=True)

    state = models.CharField(max_length=16, choices=STATE_CHOICES, default=STATE_PENDING)
    reentries_used = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "interview_sessions"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["state", "deadline_utc"])]

    def __str__(self) -> str:
        return f"Session({self.id}, {self.problem_slug}, {self.candidate_label}, {self.state})"


class Token(models.Model):
    """
    Single-use admission ticket (Plan REV-4).

    Once `consumed_at` is set, the row's purpose is audit-only — the cookie is
    the durable credential.
    """

    token = models.CharField(primary_key=True, max_length=64, default=_new_token)
    session = models.ForeignKey(
        InterviewSession, on_delete=models.CASCADE, related_name="tokens"
    )
    expires_at = models.DateTimeField(db_index=True)
    consumed_at = models.DateTimeField(null=True, blank=True)
    consumer_ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        db_table = "admission_tokens"

    def is_consumable(self, now=None) -> bool:
        now = now or timezone.now()
        return self.consumed_at is None and self.expires_at > now


class ReentryToken(models.Model):
    """
    Interviewer-issued recovery token (Plan REV-4). Rate-limited to
    3 per session at the use-case layer.
    """

    token = models.CharField(primary_key=True, max_length=64, default=_new_token)
    session = models.ForeignKey(
        InterviewSession, on_delete=models.CASCADE, related_name="reentries"
    )
    issued_by = models.CharField(max_length=150)  # interviewer username
    expires_at = models.DateTimeField(db_index=True)
    consumed_at = models.DateTimeField(null=True, blank=True)
    consumer_ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        db_table = "reentry_tokens"

    def is_consumable(self, now=None) -> bool:
        now = now or timezone.now()
        return self.consumed_at is None and self.expires_at > now


class CodeSnapshot(models.Model):
    """
    Periodic candidate-code snapshots (Step 7).

    Cadence: client sends every 1.5s; server persists every 5s (12/min) per
    Plan §5 Step 7 + Patch refinement. AutoSubmit at deadline reads the
    latest snapshot if no candidate-initiated submission exists.

    Layer-skip exception (domain/README.md): no domain invariants on snapshots,
    so the Channels consumer writes via the ORM directly without a use case.
    """

    session = models.ForeignKey(
        InterviewSession, on_delete=models.CASCADE, related_name="snapshots"
    )
    language = models.CharField(max_length=32)
    source_code = models.TextField(blank=True, default="")
    captured_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "code_snapshots"
        ordering = ["-captured_at"]
        indexes = [models.Index(fields=["session", "-captured_at"])]


class AntiCheatEvent(models.Model):
    """
    Append-only anti-cheat event log (Step 9, Plan §5).

    Layer-skip exception #1 in domain/README.md: no domain invariants — direct
    ORM write via the view. Stored:
      - type: "visibility_change" | "blur" | "paste" | "copy" | "tab_count"
      - byte_len: paste/copy byte count (NOT content — privacy)
      - meta: optional JSON for type-specific extras

    Interviewer reviews this timeline at session-end. NEVER blocks the candidate.
    """

    EVENT_TYPES = [
        ("visibility_change", "Visibility change"),
        ("blur", "Blur (window/tab lost focus)"),
        ("paste", "Paste"),
        ("copy", "Copy"),
        ("tab_count", "Tab-switch counter snapshot"),
    ]

    session = models.ForeignKey(
        InterviewSession, on_delete=models.CASCADE, related_name="anticheat_events"
    )
    event_type = models.CharField(max_length=32, choices=EVENT_TYPES)
    byte_len = models.IntegerField(null=True, blank=True)
    meta = models.JSONField(default=dict, blank=True)
    captured_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "anticheat_events"
        ordering = ["-captured_at"]
        indexes = [models.Index(fields=["session", "-captured_at"])]

