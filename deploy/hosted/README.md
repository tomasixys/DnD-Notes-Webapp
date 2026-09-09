# Hosted LAN deployment

This stack runs DnD Notes as three containers on one private server:

- the application image, with the hosted security profile embedded;
- PostgreSQL for application and identity data; and
- Caddy for one HTTPS origin using a private local certificate authority.

Campaign images and other protected files remain in `./data` on the server.
PostgreSQL and Caddy state use named Docker volumes. Neither PostgreSQL nor the
application's plain HTTP port is published to the LAN.

## Requirements

- Linux or Docker Desktop with Docker Compose v2;
- TCP ports 80 and 443 available on the server, or alternative ports in
  `.env`;
- a LAN DNS or hosts-file entry mapping `dnd-notes.home.arpa` to the server;
  and
- clients configured to trust Caddy's local root certificate.

The hostname is deliberately shared by `hosted.toml` and `Caddyfile`. To use a
different hostname, replace it in both files before the first launch.

## First launch

From this directory:

```bash
cp .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"
python -c "import secrets; print(secrets.token_hex(32))"
```

Put one generated value in `DND_NOTES_POSTGRES_PASSWORD` and the other in
`DND_NOTES_SESSION_SECRET`. Do not reuse the example values or commit `.env`.
Hexadecimal database passwords are required by this Compose template because
the password is embedded in a PostgreSQL URL.

Build the saved source and initialize the administrator:

```bash
docker compose build
docker compose up -d database
docker compose run --rm app \
  python maintenance.py \
  --config /etc/dnd-notes/hosted.toml \
  create-admin \
  --username keeper
docker compose up -d
docker compose ps
```

The administrator command prompts twice without echoing the password. It
creates no default password and refuses to replace an existing administrator.

Git Bash on Windows automatically rewrites Unix-looking command arguments into
Windows paths. Disable that conversion when passing container paths:

```bash
MSYS_NO_PATHCONV=1 docker compose run --rm app \
  python maintenance.py \
  --config /etc/dnd-notes/hosted.toml \
  create-admin \
  --username keeper
```

PowerShell and a native Linux shell do not need `MSYS_NO_PATHCONV`. The
application's dependency startup runs the one-shot storage initializer before
the maintenance container, so it does not need a separate `docker compose run`
command.

Add this entry to each test client's hosts file, replacing the address:

```text
192.168.1.50 dnd-notes.home.arpa
```

Open `https://dnd-notes.home.arpa`. Before browsers accept the site, export
Caddy's root certificate:

```bash
MSYS_NO_PATHCONV=1 docker compose cp \
  proxy:/data/caddy/pki/authorities/local/root.crt \
  ./dnd-notes-local-root.crt
```

Install that certificate as a trusted root only on devices that should trust
this private server. Protect the exported certificate from substitution while
copying it; compare its SHA-256 fingerprint over a separate trusted channel.
The private CA key remains in the `caddy-data` volume and must never be copied
to client devices.

## Routine operation

### Start after Docker Desktop is stopped

On Windows, start Docker Desktop before starting the application containers:

```bash
docker desktop start
docker desktop status
docker info
docker compose up -d
docker compose ps
```

Wait for Docker Desktop to report that its engine is running before using
Compose. `docker info` must include a `Server` section. If the
`docker desktop` command is unavailable, open **Docker Desktop** from the
Windows Start menu and wait for it to finish starting.

`docker compose stop` stops the DnD Notes containers but leaves Docker Desktop
running. If Docker Desktop itself has been quit or Windows has restarted, use
the complete sequence above.

### Refresh after source changes

The application source and compiled frontend are copied into the image, so
backend, frontend, dependency, or Dockerfile changes require an image rebuild:

```bash
docker compose up -d --build
docker compose ps
docker compose logs --tail 100 app proxy database
```

Startup applies pending database migrations automatically and preserves the
PostgreSQL volume, protected files in `./data`, and Caddy certificate state.
After the application is healthy, refresh `https://dnd-notes.home.arpa` with
`Ctrl+F5` so the browser discards cached frontend assets.

For configuration-only changes:

```bash
# hosted.toml
docker compose restart app

# Caddyfile
docker compose restart proxy

# .env values
docker compose up -d --force-recreate
```

To deliberately update base images and rebuild from them:

```bash
docker compose pull
docker compose build --pull
docker compose up -d
```

For a routine application update, update the source checkout as the normal
server user, then run the bundled update script with the same Docker privileges
used for the rest of the stack:

```bash
git pull --ff-only
cd deploy/hosted
chmod +x update.sh
sudo ./update.sh
```

The script creates a coordinated backup, pulls the pinned PostgreSQL and Caddy
images, rebuilds the application from the current checkout, recreates the
containers, and runs `check-health.sh`. It intentionally does not run
`git pull`, allowing source changes to be reviewed before they are deployed.

Do not use `docker compose down --volumes` or `docker volume prune`; those can
delete PostgreSQL data and Caddy certificate state.

Application request logs contain JSON with a request ID, method, path, status,
duration, and client address. Responses return the same ID in
`X-Request-ID`. Liveness and readiness are available at `/health/live` and
`/health/ready`. Metrics are available only on the internal application
network at `/metrics`; Caddy returns `404` for that path.

After at least one backup exists, run the operator health check manually or
from the host monitor:

```bash
chmod +x check-health.sh
./check-health.sh
```

It fails when a required container is stopped or unhealthy, HTTPS health is
unavailable, `/metrics` is exposed, the newest backup is too old, or free disk
space is too low. The defaults require a backup no older than 26 hours and at
least 10 percent free disk space. Override them through
`DND_NOTES_MAX_BACKUP_AGE_HOURS`, `DND_NOTES_MIN_FREE_DISK_PERCENT`,
`DND_NOTES_BACKUP_ROOT`, and `DND_NOTES_HEALTH_ORIGIN`. Send its nonzero exit
status to the operator's existing alerting system; the application does not
contain an email or paging credential.

System administrators have an **Administration** link in the application for
account suspension/reactivation, password-reset links, per-user or global
session revocation, account deletion, and orphaned-campaign recovery. Every
elevated action requires a reason and creates a security event.

Stop the server before offline identity recovery:

```bash
docker compose stop app
MSYS_NO_PATHCONV=1 docker compose run --rm app \
  python maintenance.py \
  --config /etc/dnd-notes/hosted.toml \
  reset-password \
  --username keeper
docker compose start app
```

If an authenticated administrator session is unavailable during an incident,
revoke every session offline:

```bash
docker compose stop app
MSYS_NO_PATHCONV=1 docker compose run --rm app \
  python maintenance.py \
  --config /etc/dnd-notes/hosted.toml \
  revoke-all-sessions
docker compose start app
```

## Backup and restore drill

Create a coordinated PostgreSQL and protected-file backup:

```bash
chmod +x backup.sh restore-drill.sh
./backup.sh
```

The application is stopped briefly so the database dump and protected files
represent one consistent point. Backup files are created with operator-only
permissions. Each backup includes SHA-256 checksums plus `METADATA` recording
the UTC creation time, source revision, and application image ID.

Demonstrate restoration without touching the live database:

```bash
./restore-drill.sh ./backups/YYYYMMDDTHHMMSSZ
```

The drill verifies checksums, extracts the file archive, restores PostgreSQL
into a disposable database, queries required tables, and removes the
disposable database afterward.

Backups contain private campaign and account data. Copy them to encrypted
operator-controlled storage, restrict access, define a retention period, and
test a restore after application or PostgreSQL upgrades.

For the initial hosted deployment, use this minimum schedule unless the
operator records a stricter one in the sign-off:

- create a coordinated backup every night after expected campaign activity;
- copy it to encrypted storage on another device or service before pruning;
- retain 7 daily, 4 weekly, and 12 monthly recovery points; and
- run a disposable restore drill monthly and before or after every upgrade
  that changes PostgreSQL, migrations, or storage behavior.

On a Linux server, schedule `backup.sh` with a systemd timer or cron from the
repository's `deploy/hosted` directory, and schedule `check-health.sh` at least
every five minutes. For higher-assurance deployments, cron mail, a systemd
`OnFailure` handler, or an external monitor can alert on failure. An encrypted
backup tool such as restic or Borg can provide off-host copies and retention;
do not place raw `database.dump` or `files.tar.gz` files in ordinary
cloud-synchronized folders.

For a small private server where local logging is sufficient, root's crontab
can run both scripts without granting the login user direct Docker access:

```cron
*/5 * * * * cd /home/trc/Projects/dndnotes/deploy/hosted && /bin/sh ./check-health.sh >> /var/log/dnd-notes-health.log 2>&1
15 4 * * * cd /home/trc/Projects/dndnotes/deploy/hosted && /bin/sh ./backup.sh >> /var/log/dnd-notes-backup.log 2>&1
```

Install these with `sudo crontab -e`. Review or rotate the two log files
periodically. The health check requires a completed backup no older than 26
hours, so run `sudo ./backup.sh` once before enabling the five-minute check.

The bundled Compose database is the default. A separately operated PostgreSQL
service is supported through the normal `DND_NOTES_DATABASE_URL` runtime
setting when the application image is deployed with an operator-maintained
Compose override or another container supervisor. Keep TLS, credentials,
network access, database backups, and compatible PostgreSQL upgrades under
that operator's control. The bundled `backup.sh` assumes the Compose
`database` service and must be replaced or adapted when PostgreSQL is external.

## Moving beyond a private LAN

Caddy's internal CA is appropriate for controlled LAN testing. Before exposing
the service to the public internet, use a real domain whose DNS points to the
server and replace `tls internal` with Caddy's normal publicly trusted
certificate flow. Review firewall, router, operating-system update, backup,
monitoring, and incident-response guidance before forwarding port 443.

The operational checklist, monitoring suggestions, secret-rotation sequence,
and incident playbooks are in
[Hosted operations](../../docs/hosted-operations.md).
