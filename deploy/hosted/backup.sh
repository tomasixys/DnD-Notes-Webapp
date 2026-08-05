#!/usr/bin/env sh
set -eu
umask 077

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

SOURCE_REVISION=$(
  git -C "$SCRIPT_DIR/../.." rev-parse --verify HEAD 2>/dev/null \
    || printf '%s' "unknown"
)
APP_IMAGE_ID=$(
  docker compose images -q app 2>/dev/null | head -n 1 \
    || printf '%s' "unknown"
)

{
  echo "created_at_utc=$TIMESTAMP"
  echo "source_revision=$SOURCE_REVISION"
  echo "application_image_id=${APP_IMAGE_ID:-unknown}"
} > "$BACKUP_DIR/METADATA"

(
  cd "$BACKUP_DIR"
  sha256sum database.dump files.tar.gz METADATA > SHA256SUMS
)

restart_app
trap - EXIT INT TERM

echo "Backup completed: $BACKUP_DIR"
