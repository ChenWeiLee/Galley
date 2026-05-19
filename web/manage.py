#!/usr/bin/env python
import os
import sys
from pathlib import Path

# Ensure the repo root (parent of `web/`) is on sys.path so `web.*` imports
# resolve regardless of how this script is invoked. When `python web/manage.py`
# is run, Python sets sys.path[0] to `/app/web/` (the script's dir), NOT to the
# cwd — without this insert, `from web.interview_judge.settings import ...`
# fails with ModuleNotFoundError. This was caught by the scheduler container
# crashing on first boot.
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "web.interview_judge.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Did you `pip install -r requirements.txt`?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
