"""
ImportProblemUseCase — the SINGLE write path for problems (Patch #3).

Used by:
- `web/apps/interviewer/admin.py` ProblemAdmin.save_model — interviewer UI
- `web/manage.py import_problems <dir>` — engineer YAML loader

Both go through here so Problem invariants enforced in
`domain.entities.Problem.__post_init__` apply equally to both paths.
"""
from __future__ import annotations

from dataclasses import dataclass

from domain.entities import Difficulty, Language, Problem, Testcase
from domain.ports import ProblemRepository


@dataclass
class ImportProblemUseCase:
    repo: ProblemRepository

    def execute(self, raw: dict) -> Problem:
        """
        Validate and persist a problem from a raw dict (YAML-decoded or admin-form).

        Shape:
        ```
        slug: "two-sum"
        difficulty: easy
        title: "Two Sum"
        title_zh: "兩數之和"
        statement_md: "..."
        statement_md_zh: "..."   # optional 繁中 markdown
        languages: ["python", "javascript"]
        time_limit_ms: 2000
        memory_limit_kb: 262144
        testcases:
          - stdin: "..."
            expected_stdout: "..."
            is_example: true
            weight: 1
        ```
        """
        problem = Problem(
            slug=raw["slug"],
            title=raw["title"],
            title_zh=raw.get("title_zh", ""),
            statement_md=raw["statement_md"],
            statement_md_zh=raw.get("statement_md_zh", ""),
            difficulty=Difficulty(raw.get("difficulty", "easy")),
            languages=[Language(lang) for lang in raw["languages"]],
            time_limit_ms=raw.get("time_limit_ms", 2000),
            memory_limit_kb=raw.get("memory_limit_kb", 262144),
            testcases=[
                Testcase(
                    stdin=tc["stdin"],
                    expected_stdout=tc["expected_stdout"],
                    is_example=tc.get("is_example", False),
                    weight=tc.get("weight", 1),
                )
                for tc in raw["testcases"]
            ],
        )
        # Problem.__post_init__ already validated. Just persist.
        return self.repo.upsert(problem)
