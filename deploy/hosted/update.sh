#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$SCRIPT_DIR"

if [ "$#" -ne 0 ]; then
  echo "Usage: $0" >&2
  echo "Update the source checkout first, then run this script." >&2
  exit 2
fi

echo "Creating a coordinated backup before the update..."
sh "$SCRIPT_DIR/backup.sh"

echo "Pulling the pinned database and proxy images..."
docker compose pull database proxy

echo "Rebuilding the application from the current checkout..."
docker compose build --pull app

echo "Recreating the hosted stack..."
docker compose up -d --remove-orphans
docker compose ps

echo "Running the hosted health check..."
sh "$SCRIPT_DIR/check-health.sh"

echo "Update completed successfully."
