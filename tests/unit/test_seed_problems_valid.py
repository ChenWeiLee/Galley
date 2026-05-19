"""
All 10 seed YAML problems must validate through ImportProblemUseCase
(domain entity invariants).

This is the unit-test surrogate for `make seed` since `make seed` requires
Postgres + Django. Patch #3: same use case is used by admin save_model,
the YAML loader, and this test — single source of validation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest
import yaml

from domain.entities import Problem
from domain.usecases.import_problem import ImportProblemUseCase

PROBLEMS_DIR = Path(__file__).resolve().parents[2] / "web" / "data" / "problems"


@dataclass
class _FakeRepo:
    saved: list[Problem] = field(default_factory=list)

    def get_by_slug(self, slug):
        return next((p for p in self.saved if p.slug == slug), None)

    def list_all(self):
        return list(self.saved)

    def upsert(self, p):
        self.saved = [x for x in self.saved if x.slug != p.slug]
        self.saved.append(p)
        return p


def test_we_have_at_least_10_seed_problems():
    yamls = list(PROBLEMS_DIR.glob("*.yaml"))
    assert len(yamls) >= 10, f"Found {len(yamls)} seed problems, AC #2 needs ≥10"


@pytest.mark.parametrize(
    "yaml_file",
    sorted(PROBLEMS_DIR.glob("*.yaml")),
    ids=lambda p: p.name,
)
def test_seed_problem_validates(yaml_file: Path):
    raw = yaml.safe_load(yaml_file.read_text())
    repo = _FakeRepo()
    uc = ImportProblemUseCase(repo=repo)
    problem = uc.execute(raw)
    assert problem.slug == raw["slug"]
    # Has at least one example testcase (Problem invariant) — already enforced
    # by entity __post_init__, but assert here for clarity.
    assert any(tc.is_example for tc in problem.testcases)


def test_seed_problems_cover_diverse_categories():
    """
    Spec AC #2: ≥4 distinct categories. We can't tag categories yet (Step 4
    skeleton), so we approximate by topic-keywords in titles/slugs.
    """
    seen: set[str] = set()
    keyword_to_cat = {
        "sum": "arrays",
        "reverse": "strings",
        "fizz": "control_flow",
        "anagram": "strings",
        "fibonacci": "recursion_or_dp",
        "parenth": "stack",
        "binary": "search",
        "bfs": "graph",
        "stack": "stack",
        "frequency": "hashmap",
    }
    for f in PROBLEMS_DIR.glob("*.yaml"):
        raw = yaml.safe_load(f.read_text())
        slug = raw["slug"].lower()
        for kw, cat in keyword_to_cat.items():
            if kw in slug:
                seen.add(cat)
    assert len(seen) >= 4, f"Categories covered: {seen} (need ≥4)"
