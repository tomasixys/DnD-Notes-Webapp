#!/usr/bin/env sh
set -eu

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 BACKUP_DIRECTORY" >&2
  exit 2
fi

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
BACKUP_DIR=$(CDPATH= cd -- "$1" && pwd)
cd "$SCRIPT_DIR"

if [ ! -f "$BACKUP_DIR/database.dump" ] \
  || [ ! -f "$BACKUP_DIR/files.tar.gz" ] \
  || [ ! -f "$BACKUP_DIR/SHA256SUMS" ]; then
  echo "Backup directory is incomplete: $BACKUP_DIR" >&2
  exit 1
fi

(
  cd "$BACKUP_DIR"
  sha256sum --check SHA256SUMS
)

RESTORE_DATABASE="dnd_notes_restore_$(date -u +%Y%m%d%H%M%S)"
RESTORE_FILES=$(mktemp -d)

cleanup() {
  rm -rf -- "$RESTORE_FILES"
  docker compose exec -T database \
    dropdb --username dnd_notes --if-exists "$RESTORE_DATABASE" \
    >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

echo "Validating and extracting protected files..."
tar -xzf "$BACKUP_DIR/files.tar.gz" -C "$RESTORE_FILES"

echo "Restoring PostgreSQL into disposable database $RESTORE_DATABASE..."
docker compose exec -T database \
  createdb --username dnd_notes "$RESTORE_DATABASE"
docker compose exec -T database \
  pg_restore \
  --username dnd_notes \
  --dbname "$RESTORE_DATABASE" \
  --exit-on-error \
  < "$BACKUP_DIR/database.dump"

docker compose exec -T database \
  psql \
  --username dnd_notes \
  --dbname "$RESTORE_DATABASE" \
  --set ON_ERROR_STOP=1 \
  --command "SELECT COUNT(*) AS installations FROM installation;" \
  --command "SELECT COUNT(*) AS campaigns FROM campaign;"

echo "Restore drill succeeded. The disposable database will be removed."
