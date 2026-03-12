#!/bin/bash
# Database backup script for SPIP PostgreSQL database.
# Run manually or schedule via cron.
#
# Usage:
#   ./scripts/backup_db.sh
#   Or via Docker: docker compose exec db sh /backup.sh
#
# Recommended cron schedule (daily at 2 AM):
#   0 2 * * * /path/to/spip/scripts/backup_db.sh >> /var/log/spip-backup.log 2>&1

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/var/backups/spip}"
POSTGRES_DB="${POSTGRES_DB:-spip_db}"
POSTGRES_USER="${POSTGRES_USER:-spip_user}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/spip_db_${TIMESTAMP}.sql.gz"

mkdir -p "${BACKUP_DIR}"

echo "[$(date)] Starting SPIP database backup..."

# Run pg_dump inside the db container (or directly if PostgreSQL client is available)
docker compose exec -T db pg_dump \
    -U "${POSTGRES_USER}" \
    -d "${POSTGRES_DB}" \
    --no-password \
    --clean \
    --if-exists \
    --format=plain \
    | gzip > "${BACKUP_FILE}"

echo "[$(date)] Backup written to: ${BACKUP_FILE}"

# Remove backups older than RETENTION_DAYS
find "${BACKUP_DIR}" -name "spip_db_*.sql.gz" -mtime "+${RETENTION_DAYS}" -delete
echo "[$(date)] Cleaned up backups older than ${RETENTION_DAYS} days."

echo "[$(date)] Backup complete."

# ── Restore instructions ──────────────────────────────────────────────────
# To restore:
#   gunzip -c /var/backups/spip/spip_db_YYYYMMDD_HHMMSS.sql.gz | \
#     docker compose exec -T db psql -U spip_user -d spip_db
