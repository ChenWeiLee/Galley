"""
`python manage.py import_problems <dir-or-file ...>`

Patch #3: routes ALL writes through `ImportProblemUseCase` so admin and
YAML paths share the same validation.
"""
from __future__ import annotations

from pathlib import Path

import yaml
from django.core.management.base import BaseCommand, CommandError

from domain.usecases.import_problem import ImportProblemUseCase

from web.apps.interviewer.repos import DjangoProblemRepository


class Command(BaseCommand):
    help = "Import problems from YAML files (or a directory of them)."

    def add_arguments(self, parser):
        parser.add_argument(
            "paths", nargs="+", help="YAML files or directories containing *.yaml"
        )

    def handle(self, *args, **options):
        paths = [Path(p) for p in options["paths"]]
        files: list[Path] = []
        for p in paths:
            if p.is_dir():
                files.extend(sorted(p.glob("*.yaml")))
                files.extend(sorted(p.glob("*.yml")))
            elif p.is_file():
                files.append(p)
            else:
                raise CommandError(f"Path not found: {p}")

        if not files:
            self.stdout.write(self.style.WARNING("No YAML files found."))
            return

        repo = DjangoProblemRepository()
        uc = ImportProblemUseCase(repo=repo)
        ok, failed = 0, 0
        for f in files:
            try:
                raw = yaml.safe_load(f.read_text())
                problem = uc.execute(raw)
                self.stdout.write(self.style.SUCCESS(f"  ✓ {problem.slug} ({f.name})"))
                ok += 1
            except Exception as e:  # noqa: BLE001
                self.stdout.write(self.style.ERROR(f"  ✗ {f.name}: {e}"))
                failed += 1

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(f"Imported {ok} problem(s).")
            + (self.style.ERROR(f" {failed} failed.") if failed else "")
        )
