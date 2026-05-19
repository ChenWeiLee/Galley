#!/bin/sh
# Daily pg_dump → host-bind-mounted volume. Keeps last 14 days.
#
# Mounted at /backup inside the container (see docker-compose.yml).
# Host path: ./ops/backup/dumps/ (relative to repo root).
set -e

STAMP=$(date -u +"%Y%m%dT%H%M%SZ")
OUT="/backup/dumps/interview_judge-${STAMP}.sql.gz"

mkdir -p /backup/dumps

PGPASSWORD="${POSTGRES_PASSWORD}" pg_dump \
    -h "${POSTGRES_HOST}" -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" \
    --no-owner --no-privileges \
    | gzip -9 > "${OUT}"

echo "wrote ${OUT}"

# Retention: 14 days
find /backup/dumps -name "interview_judge-*.sql.gz" -mtime +14 -delete

echo "retention pass complete"
