"""Problem + Testcase models — admin-editable, also hydrated from YAML loader."""
from __future__ import annotations

from django.db import models


class Problem(models.Model):
    slug = models.SlugField(unique=True, max_length=128)
    title = models.CharField(max_length=200)
    statement_md = models.TextField(help_text="Markdown body shown to candidate.")
    languages = models.JSONField(
        default=list,
        help_text='List of language slugs e.g. ["python", "javascript"]',
    )
    time_limit_ms = models.IntegerField(default=2000)
    memory_limit_kb = models.IntegerField(default=262144)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "problems"
        ordering = ["slug"]

    def __str__(self) -> str:
        return f"{self.slug} — {self.title}"


class Testcase(models.Model):
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE, related_name="testcases")
    stdin = models.TextField(blank=True, default="")
    expected_stdout = models.TextField()
    is_example = models.BooleanField(
        default=False,
        help_text="If true, shown to the candidate in the problem statement.",
    )
    weight = models.IntegerField(default=1)

    class Meta:
        db_table = "testcases"
        ordering = ["id"]

    def __str__(self) -> str:
        return f"Testcase(problem={self.problem.slug}, example={self.is_example})"
