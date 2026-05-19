# interview-judge

Internal coding-interview judge platform. Self-host on company LAN, no third-party SaaS.

> Status: scaffolding (Steps 1-4 of 14). See [project tracking note](../../zettelkasten/4-project/).

## Quickstart

```bash
cp .env.example .env
make up           # docker compose up everything
make migrate
make createsuperuser
make seed         # load 10 starter problems (after Step 4)
```

Services:
- `web` (Daphne ASGI on :8000)
- `scheduler` (django-q2 worker — runs OUTSIDE Daphne by design)
- `db` (Postgres 16, also stores django-q2 jobstore)
- `redis-channels` (Channels layer ONLY)
- `judge0-server`, `judge0-workers`, `redis-judge0`, `db-judge0` (Judge0 self-host)

The two redises (`redis-channels` and `redis-judge0`) **must never be shared** —
sharing couples our real-time observation SLO to Judge0's queue depth.

## Architecture

Two layers only:

```
domain/   pure Python — no Django imports
  entities/   Session, Submission, Problem, values
  ports/      Repository, JudgeClient, Scheduler, LiveBroadcaster, ServerClock (Protocols)
  usecases/   AdmitCandidate, SubmitCode, RecordVerdict, AutoSubmit, ImportProblem, ...

web/      Django project + adapters
  apps/core/         /healthz, middleware
  apps/candidate/    candidate-facing views, consumers, templates
  apps/interviewer/  admin, dashboard, observe consumer
  apps/judging/      Judge0Client adapter, callback view
  apps/scheduling/   DjangoQScheduler adapter
  apps/repos/        Django repository implementations (return ORM models)
```

See `domain/README.md` for the layering rationale (Postgres + Judge0 are fixed by
spec → no DTO mapper layer; repos return ORM-typed models behind Protocol).

## Stage map

| Stage | Step range | Status |
|-------|-----------|--------|
| Skeleton + Domain | 1–2 | in progress |
| Walking skeleton + Problem CRUD | 3–4 | in progress |
| Auth + Scheduler + Live observe | 5–7 | not started |
| Submission + Polish + Soak | 8–14 | not started |

## Acceptance criteria

See `.omx-flow/specs/interview-interview-judge.md` (in zettelkasten). Headline:
**5 consecutive 60-min interviews without incident** is the bar.

## Development

```bash
make test         # unit + integration
make lint         # ruff
make fmt          # ruff format
```

## Layout caveat — iCloud Drive

This repo lives under iCloud Drive. iCloud sync may interact with file locks
during builds. If you see `EBUSY` or stale `.pyc` files, pause sync via the
Finder iCloud icon during long-running test runs.
