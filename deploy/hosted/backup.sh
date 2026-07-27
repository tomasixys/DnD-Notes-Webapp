#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$SCRIPT_DIR"

BACKUP_ROOT=${1:-"$SCRIPT_DIR/backups"}
TIMESTAMP=$(date -u +%Y%m%dT%H%M%SZ)
BACKUP_DIR="$BACKUP_ROOT/$TIMESTAMP"

if [ -e "$BACKUP_DIR" ]; then
  echo "Backup target already exists: $BACKUP_DIR" >&2
  exit 1
fi

mkdir -p "$BACKUP_DIR"

restart_app() {
  docker compose start app >/dev/null 2>&1 || true
}
trap restart_app EXIT INT TERM

echo "Stopping application writes..."
docker compose stop app

echo "Exporting PostgreSQL..."
docker compose exec -T database \
  pg_dump --username dnd_notes --dbname dnd_notes --format custom \
  > "$BACKUP_DIR/database.dump"

echo "Archiving protected filesystem data..."
tar -czf "$BACKUP_DIR/files.tar.gz" -C "$SCRIPT_DIR/data" .

(
  cd "$BACKUP_DIR"
  sha256sum database.dump files.tar.gz > SHA256SUMS
)

restart_app
trap - EXIT INT TERM

echo "Backup completed: $BACKUP_DIR"
