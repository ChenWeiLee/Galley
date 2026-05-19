"""
Repository implementations for candidate flow.

Per Plan REV-6, repos return Django ORM models — but the conversion to/from
domain entities happens in the adapter, not the use case. Domain stays pure.
"""
from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from domain.entities import InterviewSession as DomainSession
from domain.entities import ReentryTicket
from domain.entities import SessionState
from domain.entities import TokenTicket

from .models import InterviewSession, ReentryToken, Token


class DjangoSessionRepository:
    def get(self, session_id: str) -> DomainSession | None:
        try:
            row = InterviewSession.objects.get(id=session_id)
        except InterviewSession.DoesNotExist:
            return None
        return self._to_domain(row)

    def save(self, session: DomainSession) -> DomainSession:
        InterviewSession.objects.filter(id=session.id).update(
            state=session.state.value,
            deadline_utc=session.deadline_utc,
            started_at=session.started_at,
            reentries_used=session.reentries_used,
        )
        return session

    def list_by_interviewer(self, username: str) -> list[DomainSession]:
        return [
            self._to_domain(row)
            for row in InterviewSession.objects.filter(interviewer_username=username)
        ]

    def create(
        self,
        problem_slug: str,
        candidate_label: str,
        duration_seconds: int,
        interviewer_username: str,
    ) -> DomainSession:
        row = InterviewSession.objects.create(
            problem_slug=problem_slug,
            candidate_label=candidate_label,
            duration_seconds=duration_seconds,
            interviewer_username=interviewer_username,
        )
        return self._to_domain(row)

    @staticmethod
    def _to_domain(row: InterviewSession) -> DomainSession:
        return DomainSession(
            id=row.id,
            problem_slug=row.problem_slug,
            candidate_label=row.candidate_label,
            duration_seconds=row.duration_seconds,
            deadline_utc=row.deadline_utc,
            state=SessionState(row.state),
            started_at=row.started_at,
            interviewer_username=row.interviewer_username,
            reentries_used=row.reentries_used,
        )


class DjangoTokenRepository:
    def issue(self, session_id: str, ttl_seconds: int) -> TokenTicket:
        expires = timezone.now() + timedelta(seconds=ttl_seconds)
        row = Token.objects.create(session_id=session_id, expires_at=expires)
        return TokenTicket(
            token=row.token,
            session_id=row.session_id,
            expires_at_iso=row.expires_at.isoformat(),
        )

    @transaction.atomic
    def consume_atomic(self, token: str) -> TokenTicket | None:
        """
        SELECT FOR UPDATE — single-use guarantee under concurrent hits.
        """
        try:
            row = Token.objects.select_for_update().get(token=token)
        except Token.DoesNotExist:
            return None
        if not row.is_consumable():
            return None
        row.consumed_at = timezone.now()
        row.save(update_fields=["consumed_at"])
        return TokenTicket(
            token=row.token,
            session_id=row.session_id,
            expires_at_iso=row.expires_at.isoformat(),
            consumed_at_iso=row.consumed_at.isoformat(),
        )


class DjangoReentryRepository:
    def issue(self, session_id: str, ttl_seconds: int, issued_by: str = "") -> ReentryTicket:
        expires = timezone.now() + timedelta(seconds=ttl_seconds)
        row = ReentryToken.objects.create(
            session_id=session_id, expires_at=expires, issued_by=issued_by
        )
        return ReentryTicket(
            token=row.token,
            session_id=row.session_id,
            expires_at_iso=row.expires_at.isoformat(),
        )

    @transaction.atomic
    def consume_atomic(self, token: str) -> ReentryTicket | None:
        try:
            row = ReentryToken.objects.select_for_update().get(token=token)
        except ReentryToken.DoesNotExist:
            return None
        if not row.is_consumable():
            return None
        row.consumed_at = timezone.now()
        row.save(update_fields=["consumed_at"])
        return ReentryTicket(
            token=row.token,
            session_id=row.session_id,
            expires_at_iso=row.expires_at.isoformat(),
            consumed_at_iso=row.consumed_at.isoformat(),
        )
