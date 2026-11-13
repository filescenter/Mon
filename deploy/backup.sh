#!/usr/bin/env bash
# Daily backup: database dump plus uploaded files, kept for 14 days.
# Run from cron on the server, for example:
#   15 3 * * * /opt/Mon/deploy/backup.sh >> /var/log/siddiqa-backup.log 2>&1
set -euo pipefail

cd "$(dirname "$0")"
target="${BACKUP_DIR:-/var/backups/siddiqa}"
stamp="$(date +%Y-%m-%d_%H%M)"
mkdir -p "$target"

docker compose exec -T db pg_dump -U odoo -Fc siddiqa > "$target/siddiqa_$stamp.dump"
docker compose exec -T odoo tar -czf - -C /var/lib/odoo filestore > "$target/filestore_$stamp.tar.gz"

find "$target" -type f -mtime +14 -delete
echo "$(date -Is) backup written to $target"
