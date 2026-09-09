#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$SCRIPT_DIR"

ORIGIN=${DND_NOTES_HEALTH_ORIGIN:-https://royalen.no}
MAX_BACKUP_AGE_HOURS=${DND_NOTES_MAX_BACKUP_AGE_HOURS:-26}
MIN_FREE_DISK_PERCENT=${DND_NOTES_MIN_FREE_DISK_PERCENT:-10}
BACKUP_ROOT=${DND_NOTES_BACKUP_ROOT:-"$SCRIPT_DIR/backups"}
# Public HTTPS uses the system trust store unless an explicit CA is supplied.
CA_CERTIFICATE=${DND_NOTES_HEALTH_CA_CERTIFICATE:-}
CURL_PLATFORM_OPTION=""
if curl --version | head -n 1 | grep -q Schannel; then
  # Schannel otherwise rejects a private LAN CA when its certificate has no
  # internet-accessible revocation service. Certificate validation stays on.
  CURL_PLATFORM_OPTION="--ssl-no-revoke"
fi

fail() {
  echo "UNHEALTHY: $*" >&2
  exit 1
}

request_status() {
  if [ -f "$CA_CERTIFICATE" ]; then
    curl --silent --show-error --output /dev/null \
      $CURL_PLATFORM_OPTION \
      --cacert "$CA_CERTIFICATE" \
      --write-out '%{http_code}' "$1"
  else
    curl --silent --show-error --output /dev/null \
      $CURL_PLATFORM_OPTION \
      --write-out '%{http_code}' "$1"
  fi
}

for service in database app proxy; do
  container_id=$(docker compose ps -q "$service")
  [ -n "$container_id" ] || fail "$service container is missing"
  state=$(docker inspect --format '{{.State.Status}}' "$container_id")
  [ "$state" = "running" ] || fail "$service container is $state"
done

for service in database app; do
  container_id=$(docker compose ps -q "$service")
  health=$(docker inspect --format '{{.State.Health.Status}}' "$container_id")
  [ "$health" = "healthy" ] || fail "$service container is $health"
done

[ "$(request_status "$ORIGIN/health/live")" = "200" ] \
  || fail "liveness endpoint failed"
[ "$(request_status "$ORIGIN/health/ready")" = "200" ] \
  || fail "readiness endpoint failed"
[ "$(request_status "$ORIGIN/metrics")" = "404" ] \
  || fail "metrics endpoint is externally reachable"

newest_backup=$(
  find "$BACKUP_ROOT" -type f -name SHA256SUMS -print 2>/dev/null \
    | sort | tail -n 1
)
[ -n "$newest_backup" ] || fail "no completed backup was found"

now=$(date +%s)
backup_time=$(date -r "$newest_backup" +%s)
backup_age_hours=$(( (now - backup_time) / 3600 ))
[ "$backup_age_hours" -le "$MAX_BACKUP_AGE_HOURS" ] \
  || fail "newest backup is ${backup_age_hours} hours old"

free_disk_percent=$(
  df -Pk "$SCRIPT_DIR/data" \
    | awk 'NR == 2 { gsub("%", "", $5); print 100 - $5 }'
)
[ -n "$free_disk_percent" ] || fail "could not determine free disk space"
[ "$free_disk_percent" -ge "$MIN_FREE_DISK_PERCENT" ] \
  || fail "only ${free_disk_percent}% disk space remains"

echo "HEALTHY: services, HTTPS, backup age, and disk capacity passed"
