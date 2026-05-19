# ops — deployment & runbook

Self-host single-machine deployment via `docker compose`. No K8s, no cloud.

## First-time bring-up

```bash
# 1. Configure secrets
cp .env.example .env
# Edit .env — at minimum change:
#   DJANGO_SECRET_KEY
#   POSTGRES_PASSWORD
#   JUDGE0_CALLBACK_HMAC_SECRET
#   DJANGO_ALLOWED_HOSTS  (add your host's actual hostname/IP)

# 2. Bring up the stack
make up

# 3. One-time Django setup (the only thing that's not idempotent on first boot)
docker compose exec web python web/manage.py makemigrations interviewer judging candidate
docker compose exec web python web/manage.py migrate
docker compose exec web python web/manage.py createsuperuser   # this is your interviewer
docker compose exec web python web/manage.py collectstatic --noinput

# 4. Seed problems
make seed

# 5. Smoke-test
curl http://localhost/healthz                 # via nginx
curl http://localhost:8000/readyz             # direct to Daphne; all checks should be "ok"
```

After this, `docker compose up -d` brings everything back without any manual steps.

## Daily life

```bash
make logs            # tail web + scheduler
docker compose ps    # all services healthy?
make test            # 81 unit tests, ~0.1s
```

## Backups

The `pgdump` service runs `pg_dump.sh` at 03:00 UTC daily into
`./ops/backup/dumps/`, gzipped, 14-day retention. To verify:

```bash
docker compose exec pgdump /backup/pg_dump.sh   # manual run
ls -lh ops/backup/dumps/
```

To restore a backup into a clean stack:

```bash
docker compose down -v   # WIPES THE DB. ALWAYS BACK UP BEFORE THIS.
docker compose up -d db
gunzip -c ops/backup/dumps/interview_judge-20260518T030000Z.sql.gz \
    | docker compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
docker compose up -d
```

## Network topology

- **nginx** exposes port 80 to the LAN.
- **web (Daphne)** is reachable only via the compose internal network from nginx.
- **judge0-server** exposes 2358 to the LAN for debug / direct API use.
  In production behind a firewall, you can remove that port mapping;
  callbacks travel inside the compose network only.
- **redis-channels** and **redis-judge0** are NEVER exposed to the host.

If you're putting this behind a corporate firewall or Tailscale subnet,
terminate TLS at that edge, not at this nginx. nginx here is plain HTTP.

## TLS

This stack does NOT terminate TLS. Three reasonable options:

1. **Tailscale subnet router** + Tailscale HTTPS (free, easiest)
2. Office firewall doing TLS termination → forward HTTP to this host
3. `caddy` in front of `nginx` if you really want certbot on-host

Pick one. None require code changes.

## Incident response

### Judge0 callback URL unreachable
- Symptom: submissions stay in `pending` for >10s
- Mitigation: poll fallback is already wired (`JudgingConfig.ready()` registers
  `poll_pending_submissions` every 1 min). Verdicts arrive within 60s.
- Long-term fix: confirm `JUDGE0_CALLBACK_BASE_URL` env var is reachable from
  `judge0-server` container. Default is `http://web:8000` which works inside the
  default compose network.

### Scheduler container down
- Symptom: countdown displays correctly, but no auto-submit fires at deadline.
- Recovery: `docker compose up -d scheduler`. Job survives in Postgres
  jobstore — re-armed on next worker startup.
- Detection: nightly check on `django_q.models.Schedule` (Step 11 soak harness
  covers this).

### Database backup verification
- Quarterly: pick a recent dump, restore it into a throwaway stack, confirm
  a session can be reviewed. Don't ship to production without a verified
  restore path.

## Decommission / wipe

```bash
docker compose down -v        # destroys ALL data including Judge0
rm -rf ops/backup/dumps/*     # destroys backups too
```

Use with care.
