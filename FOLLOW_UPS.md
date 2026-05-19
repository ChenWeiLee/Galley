# Follow-ups before Step 11 (soak harness)

Last updated: 2026-05-11 after Steps 5-10 architect review.

## Required (blocking Step 11 soak)

- [ ] **Generate and commit initial migrations** (still open from Steps 1-4 review)
      Run inside the `web` container once compose is up:
      ```bash
      docker compose exec web python web/manage.py makemigrations \
          interviewer judging candidate
      git add web/apps/*/migrations/0001_initial.py
      git commit -m "chore(interview-judge): commit initial migrations"
      ```
      Without these, `make up` won't be reproducible. The `candidate` app has
      4 models (InterviewSession, Token, ReentryToken, CodeSnapshot,
      AntiCheatEvent), `judging` has 1 (Submission), `interviewer` has 2
      (Problem, Testcase).

## Fixed in Steps 5-10 close (already in code)

- [x] **BUG-1**: `_admit_uc()` now passes `scheduler=DjangoQScheduler()`.
      Candidate token consume path no longer crashes on first hit.
- [x] **BUG-2**: `poll_pending_submissions` registered as recurring django-q2
      task in `JudgingConfig.ready()` (1-min cadence, idempotent insert).
      Step 8 poll fallback is now live, not dead code.
- [x] **REC-1**: `session_page` now returns "time_up" admission_failed.html
      (HTTP 410) when `session.state == FROZEN`. No UX confusion at deadline.
- [x] **transaction.atomic on ProblemAdmin.save_related** (from prior review).
- [x] **qmonitor healthcheck**: replaced `qmonitor --once` (flag may not
      exist) with a `django_q.models.Stat` heartbeat probe in compose.

## Recommended (non-blocking)

These were noted by the Steps 5-10 architect but defer cleanly:

- [ ] **REC-2**: `web/apps/judging/repos.py:_to_domain` silently falls back
      to `Language.PYTHON` on unknown values. Should `raise` so data drift
      surfaces.
- [ ] **REC-3**: `_PendingSubmission` discriminator in `repos.save()` uses
      `hasattr(sub, "result")` — fragile to future renames. Split into
      `save_pending()` + `save_judged()` or add explicit marker class attr.
- [ ] **REC-4** (Step 12 already planned): `interviewer/review.html` snapshot
      replay slider hand-rolls JSON in template. Move to API endpoint.
- [ ] **REC-5**: `scheduling/adapters.py:36` `repeats=-1` comment is
      misleading (Schedule.ONCE makes it one-shot; `repeats` is ignored).
- [ ] **REC-6**: `INTERVIEW_SESSION_COOKIE_MAX_AGE_SECONDS=18000` (5h) is a
      fixed default not bound to `freeze_at + 5min` from Plan REV-4.
      Defensible but document in `cookies.py`.

## Trivially deferred

- Step 12 polish: nginx + pg_dump + final compose hardening.
- Step 13: re-soak after fixes.
- Step 14: pilot with friendly internal candidate.

## Untested in this environment

- `docker compose up` against a real Docker daemon.
- `/healthz` and `/readyz` runtime behavior.
- `make seed` against a real Postgres.
- Walking skeleton e2e (Monaco → Judge0 → verdict).
- WebSocket reconnect chaos (kill redis-channels mid-session).
- Auto-submit chaos (kill web 30s before freeze_at, verify scheduler fires).

These verifications run when you bring up the stack for the first time.
