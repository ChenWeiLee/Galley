"""ImportProblemUseCase tests using a fake repo."""
from __future__ import annotations

from dataclasses import dataclass, field

from domain.entities import Difficulty, Problem
from domain.usecases.import_problem import ImportProblemUseCase


@dataclass
class _FakeProblemRepo:
    saved: list[Problem] = field(default_factory=list)

    def get_by_slug(self, slug):
        for p in self.saved:
            if p.slug == slug:
                return p
        return None

    def list_all(self):
        return list(self.saved)

    def upsert(self, problem):
        self.saved = [p for p in self.saved if p.slug != problem.slug]
        self.saved.append(problem)
        return problem


def test_import_validates_via_entity_invariants():
    repo = _FakeProblemRepo()
    uc = ImportProblemUseCase(repo=repo)

    raw = {
        "slug": "two-sum",
        "title": "Two Sum",
        "statement_md": "Find indices summing to target.",
        "languages": ["python", "javascript"],
        "time_limit_ms": 1500,
        "testcases": [
            {"stdin": "2 7 11 15\n9", "expected_stdout": "0 1", "is_example": True},
            {"stdin": "3 2 4\n6", "expected_stdout": "1 2"},
        ],
    }
    saved = uc.execute(raw)
    assert saved.slug == "two-sum"
    assert len(saved.testcases) == 2
    assert repo.saved[0] is saved


def test_import_rejects_problem_without_example_testcase():
    """Same invariant should fire for both YAML and admin paths (Patch #3)."""
    import pytest

    repo = _FakeProblemRepo()
    uc = ImportProblemUseCase(repo=repo)

    raw = {
        "slug": "bad",
        "title": "Bad",
        "statement_md": "...",
        "languages": ["python"],
        "testcases": [
            {"stdin": "1", "expected_stdout": "1", "is_example": False},
        ],
    }
    with pytest.raises(ValueError, match="example testcase"):
        uc.execute(raw)
    assert repo.saved == []


def test_import_defaults_difficulty_easy_and_zh_blank():
    uc = ImportProblemUseCase(repo=_FakeProblemRepo())
    raw = {
        "slug": "p", "title": "T", "statement_md": ".",
        "languages": ["python"],
        "testcases": [{"stdin": "1", "expected_stdout": "1", "is_example": True}],
    }
    saved = uc.execute(raw)
    assert saved.difficulty is Difficulty.EASY
    assert saved.title_zh == ""
    assert saved.statement_md_zh == ""


def test_import_reads_difficulty_and_zh_fields():
    uc = ImportProblemUseCase(repo=_FakeProblemRepo())
    raw = {
        "slug": "p", "title": "Two Sum", "title_zh": "兩數之和",
        "statement_md": "EN", "statement_md_zh": "中",
        "difficulty": "hard",
        "languages": ["python"],
        "testcases": [{"stdin": "1", "expected_stdout": "1", "is_example": True}],
    }
    saved = uc.execute(raw)
    assert saved.difficulty is Difficulty.HARD
    assert saved.title_zh == "兩數之和"
    assert saved.statement_md_zh == "中"
