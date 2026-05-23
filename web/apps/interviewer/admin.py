"""
Django admin for Problem + Testcase.

WRITE PATH ASYMMETRY (Patch #3 / Plan REV-8):
    `ProblemAdmin.save_model` routes saves through `ImportProblemUseCase` so
    invariants enforced in `domain.entities.Problem.__post_init__` apply equally
    to admin saves AND to the YAML loader. Read paths use ORM directly via
    `DjangoProblemRepository.get_by_slug`/`list_all`.

    This is intentional. Documented in `domain/README.md`. See ADR in
    `.omx-flow/plans/plan-galley.md`.
"""
from __future__ import annotations

from django.contrib import admin
from django.db import transaction

from domain.usecases.import_problem import ImportProblemUseCase

from .models import Problem, Testcase
from .repos import DjangoProblemRepository


class TestcaseInline(admin.TabularInline):
    model = Testcase
    extra = 1
    fields = ("stdin", "expected_stdout", "is_example", "weight")


@admin.register(Problem)
class ProblemAdmin(admin.ModelAdmin):
    list_display = ("slug", "title", "languages_display", "time_limit_ms", "updated_at")
    search_fields = ("slug", "title")
    inlines = [TestcaseInline]
    fields = (
        "slug",
        "title",
        "statement_md",
        "languages",
        "time_limit_ms",
        "memory_limit_kb",
    )

    @admin.display(description="languages")
    def languages_display(self, obj: Problem) -> str:
        return ", ".join(obj.languages or [])

    # save_model is intentionally inherited (does the bulk write).
    # Validation happens in save_related, wrapped in a transaction so that a
    # failed invariant rolls back the Problem row + Testcases together.

    @transaction.atomic
    def save_related(self, request, form, formsets, change):
        """
        Patch #3 + Architect-fix: route admin saves through ImportProblemUseCase
        AND wrap the whole save+validate in a transaction.

        Order of events Django imposes:
        1. `save_model` (super class) commits the Problem row.
        2. `save_related` (this method) saves the inline Testcases via super().
        3. We re-run ImportProblemUseCase. If domain invariants fail, the
           ValueError propagates and `transaction.atomic` rolls back BOTH the
           Problem row and the Testcases. The interviewer sees the admin
           error page and the DB stays clean.

        The slight inefficiency (super() saves rows that may roll back) is
        worth the simplicity. Step 5 may add pre-validation against the form
        data to skip the doomed write entirely.
        """
        super().save_related(request, form, formsets, change)
        instance = form.instance
        raw = {
            "slug": instance.slug,
            "title": instance.title,
            "statement_md": instance.statement_md,
            "languages": instance.languages or [],
            "time_limit_ms": instance.time_limit_ms,
            "memory_limit_kb": instance.memory_limit_kb,
            "testcases": [
                {
                    "stdin": tc.stdin,
                    "expected_stdout": tc.expected_stdout,
                    "is_example": tc.is_example,
                    "weight": tc.weight,
                }
                for tc in instance.testcases.all()
            ],
        }
        # If this raises, @transaction.atomic rolls back super().save_related
        # AND the upstream save_model write. Net effect: invalid data never
        # reaches the DB.
        ImportProblemUseCase(repo=DjangoProblemRepository()).execute(raw)
