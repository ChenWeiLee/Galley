# `domain/` — pure-Python core

This package contains entities, value objects, ports (Protocols), and use cases.
**No Django, httpx, channels, or any framework imports inside `domain/`.**

## Layering rationale (Plan REV-6)

This project uses **two layers**, not four. The Postgres database and Judge0
sandbox are fixed by spec (Constraints), so a DTO mapper layer between domain
entities and ORM rows would be ceremony for a swap-out we are not allowed to make.

Repository ports therefore return **Django ORM model instances** behind a
`Protocol` contract. The Protocol enforces *what methods exist*; the model itself
is the value being passed around. This is intentional, and it is the project's
single deliberate compromise on Clean Architecture.

```
domain/             ← pure Python, framework-free
  entities/         data classes representing problem-domain objects
  ports/            Protocols — what use cases require from the outside world
  usecases/         orchestration logic
                    (uses ports, never imports adapters)
  values/           opaque value objects (e.g. Judge0Result wraps Judge0 JSON
                    so use cases never read its status enum)

web/                ← Django + adapter implementations
  apps/repos/       ORM-backed Repository implementations
  apps/judging/     Judge0Client (httpx-based) implementing JudgeClient port
  apps/scheduling/  DjangoQScheduler implementing Scheduler port
  apps/interviewer/ Channels consumer implementing LiveBroadcaster port
```

## Deliberate layer-skip exceptions

Two adapters are allowed to bypass the use-case layer because they are
append-only event firehoses with **no domain invariants**:

1. **Anti-cheat events** (Plan REV-8). `POST /events` writes directly to the
   `AntiCheatEvent` table via the repo. No `RecordAntiCheatEventUseCase`. We log
   the type, byte count, and timestamp; the interviewer reads the timeline at
   review time. There is nothing for a use case to enforce.

2. **Code snapshots** during live observe (Plan §5 Step 7). The Channels
   consumer persists every snapshot directly. Snapshots are by definition
   already-happened keystrokes; there is no validation that could prevent them
   from being recorded.

Every other write goes through a use case. The two exceptions above MUST be
the only ones.

## ServerClock contract (Patch #2)

`domain/ports/clock.py` defines `ServerClock` as the single source of time.

- The session's `deadline_utc` is set **once** when the session starts, by reading
  `clock.now() + duration`.
- Both the auto-submit scheduler job and the candidate's countdown read
  `deadline_utc` — **never** their own wall clocks.
- The browser polls `GET /api/sessions/<id>/remaining` every 5 seconds to
  re-anchor its countdown display. Local clocks drift; the server's doesn't.
- AC #4.2 timer drift is measured as `submission.created_at - session.deadline_utc`.

## Forbidden patterns

- `import django` or `from django.*` anywhere under `domain/`.
- `import httpx` or any HTTP client inside `domain/`. Outbound HTTP goes
  through `JudgeClient` port.
- Reading wall clock via `datetime.now()` or `time.time()`. Use the
  `ServerClock` port.
- In-process schedulers (APScheduler, threading.Timer, asyncio.sleep+task).
  Use the `Scheduler` port; the only allowed implementation is the django-q2
  worker running in its own container.
