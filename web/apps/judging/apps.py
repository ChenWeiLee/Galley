from django.apps import AppConfig


class JudgingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "web.apps.judging"
    label = "judging"

    def ready(self):
        # BUG-2 fix: register the poll-fallback recurring task.
        # Idempotent — only inserts if not already present, so app reloads
        # don't duplicate the schedule row.
        # Late import: django-q2 models aren't importable until apps are ready.
        import os
        import sys

        # Skip during test collection / migrations to keep the registration
        # side-effect out of unrelated commands.
        skip_cmds = {"migrate", "makemigrations", "test", "collectstatic",
                     "shell", "createsuperuser", "import_problems"}
        if any(arg in sys.argv for arg in skip_cmds):
            return
        if os.environ.get("INTERVIEW_JUDGE_SKIP_QSCHEDULE") == "1":
            return

        try:
            from django.db.utils import OperationalError, ProgrammingError
            from django_q.models import Schedule
            from django_q.tasks import schedule

            try:
                if not Schedule.objects.filter(name="poll_pending_submissions").exists():
                    schedule(
                        "web.apps.judging.callback.poll_pending_submissions",
                        name="poll_pending_submissions",
                        schedule_type=Schedule.MINUTES,
                        minutes=1,  # django-q2 minimum granularity for non-cron schedules
                        repeats=-1,
                    )
            except (OperationalError, ProgrammingError):
                # DB not ready yet (e.g. first boot before migrations). The
                # scheduler container's later AppConfig.ready() call will retry.
                pass
        except Exception:  # noqa: BLE001
            # Never let scheduler registration block app startup.
            pass
