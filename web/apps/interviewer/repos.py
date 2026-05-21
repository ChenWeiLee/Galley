"""
DjangoProblemRepository — implements `domain.ports.ProblemRepository`.

Returns Django ORM model instances (Plan REV-6: Postgres is fixed by spec, no
DTO mapper layer). Conversion between domain.Problem dataclass and the ORM
model happens here, in the adapter, not in the use case.
"""
from __future__ import annotations

from django.db import transaction

from domain.entities import Difficulty as DomainDifficulty
from domain.entities import Language as DomainLanguage
from domain.entities import Problem as DomainProblem
from domain.entities import Testcase as DomainTestcase

from .models import Problem as ProblemModel
from .models import Testcase as TestcaseModel


class DjangoProblemRepository:
    """Concrete repository — read paths use ORM, write path goes through use case."""

    def get_by_slug(self, slug: str) -> DomainProblem | None:
        try:
            row = ProblemModel.objects.prefetch_related("testcases").get(slug=slug)
        except ProblemModel.DoesNotExist:
            return None
        return self._to_domain(row)

    def list_all(self) -> list[DomainProblem]:
        rows = ProblemModel.objects.prefetch_related("testcases").all()
        return [self._to_domain(r) for r in rows]

    @transaction.atomic
    def upsert(self, problem: DomainProblem) -> DomainProblem:
        row, _ = ProblemModel.objects.update_or_create(
            slug=problem.slug,
            defaults=dict(
                title=problem.title,
                title_zh=problem.title_zh,
                statement_md=problem.statement_md,
                statement_md_zh=problem.statement_md_zh,
                difficulty=problem.difficulty.value,
                languages=[lang.value for lang in problem.languages],
                time_limit_ms=problem.time_limit_ms,
                memory_limit_kb=problem.memory_limit_kb,
            ),
        )
        # Replace testcases atomically (simpler than diffing for now).
        row.testcases.all().delete()
        TestcaseModel.objects.bulk_create(
            [
                TestcaseModel(
                    problem=row,
                    stdin=tc.stdin,
                    expected_stdout=tc.expected_stdout,
                    is_example=tc.is_example,
                    weight=tc.weight,
                )
                for tc in problem.testcases
            ]
        )
        return self._to_domain(
            ProblemModel.objects.prefetch_related("testcases").get(pk=row.pk)
        )

    @staticmethod
    def _to_domain(row: ProblemModel) -> DomainProblem:
        return DomainProblem(
            slug=row.slug,
            title=row.title,
            title_zh=row.title_zh or "",
            statement_md=row.statement_md,
            statement_md_zh=row.statement_md_zh or "",
            difficulty=DomainDifficulty(row.difficulty or "easy"),
            languages=[DomainLanguage(lang) for lang in row.languages],
            time_limit_ms=row.time_limit_ms,
            memory_limit_kb=row.memory_limit_kb,
            testcases=[
                DomainTestcase(
                    stdin=tc.stdin,
                    expected_stdout=tc.expected_stdout,
                    is_example=tc.is_example,
                    weight=tc.weight,
                )
                for tc in row.testcases.all()
            ],
        )
