# Follow-ups before Step 11 (soak harness)

Last updated: 2026-05-21 after autopilot cleanup pass (commits e9995fe, 57f85d2).

## Required (blocking Step 11 soak)

- [x] **Generate and commit initial migrations** — done. `0001_initial` for all
      three apps (interviewer / judging / candidate) is in tree, and the two
      `0002` follow-ups (per_testcase_results, difficulty+i18n) committed in
      e9995fe. `docker compose exec -T web python web/manage.py showmigrations`
      reports `[X]` across the board.

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

## Recommended (non-blocking) — all closed 2026-05-21 in commit 57f85d2

- [x] **REC-2**: `_to_domain` now calls `Language(row.language)` directly;
      unknown values raise `ValueError` so data drift surfaces immediately
      instead of being silently rewritten to Python on read.
- [x] **REC-3**: switched discriminator to `isinstance(sub, DomainSubmission)`
      — sharp positive type check, no longer fooled if either DTO grows or
      loses fields.
- [x] **REC-4**: new endpoint `interviewer:review_snapshots_json` serves the
      replay frames as JSON; `review.html` fetches via `await fetch(...)`
      instead of injecting hand-rolled JSON. Template no longer depends on
      `escapejs|stringformat` to round-trip source code.
- [x] **REC-5**: kept `repeats=-1` for explicitness, replaced the wrong
      "one-shot" comment with one explaining that `schedule_type=Schedule.ONCE`
      makes `repeats` a no-op (and pointing at `judging/apps.py` where
      `repeats=-1` IS load-bearing for the recurring poll task).
- [x] **REC-6**: `cookies.py` module docstring now documents the 5h ceiling
      rationale (signed payload only carries `session_id`; server-side FROZEN
      gate makes post-deadline possession harmless) and notes how to bind
      `max_age` to `session.remaining_seconds() + 300` at admit time if a
      tighter TTL is ever wanted.

## Trivially deferred

- Step 12 polish: nginx + pg_dump + final compose hardening.
- Step 13: re-soak after fixes.
- Step 14: pilot with friendly internal candidate.

## Tested 2026-05-21 against live `docker compose up` stack (up ~41h)

- [x] `docker compose up` healthy — web/scheduler/db/redis-channels/judge0/pgdump all running
- [x] `/healthz` → 200
- [x] `/readyz` → 200 (Judge0 `/about` reachable from web container)
- [x] `/dashboard/` → 302 (login redirect, expected)
- [x] New `interviewer:review_snapshots_json` URL resolves
- [x] `python -c "from web.apps.judging.repos import DjangoSubmissionRepository"` clean import after REC-2/3 changes
- [x] All 0001 + 0002 migrations applied (`showmigrations` all `[X]`)

## Still untested — needs explicit go-ahead

- `make seed` against the running Postgres (data may already be seeded; check before re-running).
- Walking-skeleton e2e through the browser (Monaco → submit → Judge0 → verdict).
- WebSocket reconnect chaos (`docker compose kill redis-channels`).
- Auto-submit chaos (`docker compose kill -s 9 web` 30s before `freeze_at`).
- Step 13 full `run_5x60_with_chaos.py` soak — needs Playwright install +
  interviewer credentials + 5h budget + willingness to bounce the running
  stack via `docker compose kill -s 9 web`.
