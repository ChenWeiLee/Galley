"""Problem + Testcase models — admin-editable, also hydrated from YAML loader."""
from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _


class Problem(models.Model):
    DIFFICULTY_EASY = "easy"
    DIFFICULTY_MEDIUM = "medium"
    DIFFICULTY_HARD = "hard"
    DIFFICULTY_CHOICES = [
        (DIFFICULTY_EASY, "Easy"),
        (DIFFICULTY_MEDIUM, "Medium"),
        (DIFFICULTY_HARD, "Hard"),
    ]

    slug = models.SlugField(unique=True, max_length=128)
    title = models.CharField(max_length=200, help_text="Canonical English title.")
    title_zh = models.CharField(max_length=200, blank=True, default="",
                                help_text="Optional traditional Chinese title.")
    statement_md = models.TextField(help_text="Markdown statement (English).")
    statement_md_zh = models.TextField(blank=True, default="",
                                        help_text="Optional 繁中 markdown statement.")
    difficulty = models.CharField(
        max_length=10, choices=DIFFICULTY_CHOICES, default=DIFFICULTY_EASY,
        db_index=True,
    )
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
        ordering = ["difficulty", "slug"]
        verbose_name = _("Problem")
        verbose_name_plural = _("Problems")

    def __str__(self) -> str:
        return f"[{self.difficulty}] {self.slug} — {self.title}"

    def localized_title(self, lang: str) -> str:
        if lang and lang.startswith("zh") and self.title_zh:
            return self.title_zh
        return self.title

    def localized_statement(self, lang: str) -> str:
        if lang and lang.startswith("zh") and self.statement_md_zh:
            return self.statement_md_zh
        return self.statement_md


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
        verbose_name = _("Testcase")
        verbose_name_plural = _("Testcases")

    def __str__(self) -> str:
        return f"Testcase(problem={self.problem.slug}, example={self.is_example})"
