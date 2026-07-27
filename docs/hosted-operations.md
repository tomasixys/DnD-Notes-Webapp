# Hosted operations and incident response

Updated: 2026-07-27

This runbook covers the supported single-server hosted deployment in
[`deploy/hosted`](../deploy/hosted/README.md). It is suitable for controlled
LAN testing and is the baseline before any internet port forwarding.

## Operating boundary

- Caddy is the only service published from the container network.
- The application and PostgreSQL ports are not exposed to the LAN.
- PostgreSQL state, protected campaign files, and Caddy's private CA state are
  durable and must all survive container replacement.
- The `.env` file, database backups, file archives, and Caddy CA private key
  are secrets. Restrict them to server operators and never commit them.
- The supported stack runs one application process. Its request limits and
  in-memory service metrics reset when that process restarts.

## Preflight and hosted-alpha checklist

Before inviting another user:

1. Pin the deployment to a reviewed Git commit and save that revision.
2. Generate unique PostgreSQL and application secrets.
3. Build the image and create the initial administrator offline.
4. Confirm only the intended HTTP/HTTPS ports are listening on the host.
5. Trust the Caddy root certificate on test clients over a trusted transfer.
6. Confirm `/health/live` and `/health/ready` return `200` through HTTPS.
7. Confirm `/metrics` returns `404` through Caddy.
8. Test login, logout, invitation activation, campaign membership, private
   notes, uploads, and an authorized campaign export with two test accounts.
9. Confirm an unrelated account cannot enumerate or retrieve the test
   campaign, private notes, images, or backup.
10. Run `backup.sh`, copy the result to encrypted operator-controlled storage,
    and run `restore-drill.sh` against that exact backup.
11. Record the tested commit, date, operator, backup location, and restore
    result. Do not mark the hosted milestone complete without this record.

## Monitoring

Use `docker compose ps` as the first status view. The application container
health check calls readiness, which includes a database query. A simple host
monitor should alert when any container is unhealthy/restarting, HTTPS is
unreachable, disk space is low, or the newest successful backup exceeds the
chosen maximum age.

Application logs are compact JSON and include `request_id`, method, path,
status, duration, and client address. Caddy also emits JSON access logs.
Correlate a client-visible `X-Request-ID` with application logs:

```bash
docker compose logs app | grep REQUEST_ID
```

Prometheus-format counters are available at `http://app:8000/metrics` only
inside the Compose network. If a collector is added, keep that endpoint on a
private monitoring network and alert on readiness failure, sustained `5xx`
growth, abnormal `401`/`403`/`429` growth, restart loops, database capacity,
and storage capacity.

Review recent persistent security events from an operator shell:

```bash
docker compose exec -T database psql \
  --username dnd_notes \
  --dbname dnd_notes \
  --command "SELECT created_at, event_type, actor_user_id, user_id, campaign_id, outcome, reason FROM security_event ORDER BY created_at DESC LIMIT 100;"
```

## Routine upgrades and rollback

1. Save the current Git commit and image ID.
2. Create and verify a coordinated backup.
3. Build the candidate image from a reviewed commit.
4. Run the automated backend, frontend, PostgreSQL migration, and image checks.
5. Deploy with `docker compose up -d` and watch readiness and logs.
6. Perform login, campaign read/write, upload, and export smoke tests.

For application rollback, redeploy the previously saved source/image only when
its schema is compatible with the current database. If a migration is not
backward compatible, stop the stack and restore both the PostgreSQL dump and
file archive from the coordinated pre-upgrade backup. Never restore only one
side of that pair.

## Secret rotation

PostgreSQL password rotation requires a maintenance window:

1. Create and verify a backup.
2. Stop the application.
3. Change the database role password in PostgreSQL.
4. Update `DND_NOTES_POSTGRES_PASSWORD` in `.env`.
5. Recreate the application container and verify readiness.

Rotate `DND_NOTES_SESSION_SECRET` by changing `.env` and recreating the
application container. This secret keys privacy-preserving source digests; its
rotation does **not** revoke existing login tokens. Use the Administration
page's global revocation first, or run the offline
`revoke-all-sessions` command while the application is stopped.

If the Caddy CA private key may be compromised, remove public access, replace
the Caddy state only after recording the impact, restart Caddy to establish a
new private CA, and securely redistribute its new root certificate. Remove the
old root from every client.

## Incident playbooks

### Suspected account or password compromise

1. Suspend the account in Administration; this revokes its sessions.
2. Inspect security events and request logs using request IDs.
3. Issue a one-time password-reset link through a separate trusted channel.
4. Reactivate the account only after the operator verifies the user.
5. If scope is uncertain, revoke all sessions and require everyone to sign in.

### Administrator unavailable or compromised

1. Stop the application to acquire exclusive maintenance access.
2. Run `revoke-all-sessions`.
3. Run `reset-password --username ADMIN`.
4. Rotate relevant secrets and restart the application.
5. Review security events, memberships, exports, and account-status changes.

### Suspected data exposure

1. Remove external reachability without deleting containers or logs.
2. Revoke all sessions.
3. Preserve logs, the affected image ID/commit, configuration, and a
   coordinated forensic backup.
4. Determine affected accounts, campaigns, private records, files, and backup
   exports from security events and request logs.
5. Restore or recover ownership through Administration only with a recorded
   reason.

### Account deletion and campaign custody

Deleting an account tombstones it. Any otherwise ownerless campaign is moved
to the non-login system custodian and placed in the recovery queue; it is not
deleted. Assign a verified active user as the new owner from Administration.
Full campaign import/export remains the current portability boundary.

## Internet exposure gate

LAN success is not permission to port-forward the current private certificate.
Before internet exposure, use a real domain and publicly trusted TLS, patch the
host automatically, restrict the firewall, secure router administration,
configure off-host encrypted backups, add external availability/disk alerts,
and repeat the authorization and restore checklist. Keep PostgreSQL and the
application HTTP port private.
