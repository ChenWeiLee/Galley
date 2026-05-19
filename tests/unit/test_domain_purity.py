"""
Domain-purity test.

`domain/` MUST NOT import Django, httpx, channels, django-q, or any framework.
This test scans every .py file under `domain/` and fails if it sees a forbidden
import. This is the cheapest enforcement of the "two-layer" architecture
(Plan REV-6).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

DOMAIN_DIR = Path(__file__).resolve().parents[2] / "domain"
FORBIDDEN = (
    "django",
    "httpx",
    "channels",
    "django_q",
    "rest_framework",
    "asgiref",  # comes with Django, also forbidden
)


def _domain_py_files() -> list[Path]:
    return [p for p in DOMAIN_DIR.rglob("*.py") if p.is_file()]


@pytest.mark.parametrize("py_file", _domain_py_files(), ids=lambda p: p.name)
def test_no_framework_imports_in_domain(py_file: Path) -> None:
    """No `import django` / `from django...` etc. inside domain/."""
    text = py_file.read_text()
    for forbidden in FORBIDDEN:
        # Match `import X` or `from X` at start of a line (after whitespace)
        pattern = re.compile(rf"^\s*(import|from)\s+{re.escape(forbidden)}", re.MULTILINE)
        match = pattern.search(text)
        assert match is None, (
            f"{py_file.relative_to(DOMAIN_DIR.parent)} imports forbidden module "
            f"'{forbidden}'. domain/ must stay framework-free (see domain/README.md)."
        )


def test_no_walltime_calls_in_domain() -> None:
    """
    `domain/` must use ServerClock, not datetime.now() / time.time() (Patch #2).

    We allow:
    - `datetime.now` import in test files (these are NOT in domain)
    - The literal string 'now' as a parameter name
    """
    bad_patterns = (
        re.compile(r"datetime\.now\("),
        re.compile(r"datetime\.utcnow\("),
        re.compile(r"time\.time\("),
    )
    for py_file in _domain_py_files():
        text = py_file.read_text()
        for pat in bad_patterns:
            assert not pat.search(text), (
                f"{py_file.name} reads wall clock directly. Use ServerClock port instead."
            )
