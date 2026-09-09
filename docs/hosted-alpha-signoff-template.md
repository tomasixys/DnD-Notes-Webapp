# Optional hosted alpha sign-off

This template is optional reference material for operators who want a formal
release record. It is not a gate for the personal friends-and-family server.

Copy this template into the operator's private records for each environment.
Do not commit addresses, usernames, backup locations, certificate details, or
other deployment-specific information to the source repository.

## Deployment identity

- Date and operator:
- Environment:
- Reviewed Git revision:
- Application image ID:
- PostgreSQL image/version:
- Public origin or LAN test origin:
- Hosted configuration reviewed:

## Automated verification

- [ ] Backend test suite passed, including PostgreSQL migrations.
- [ ] Frontend type-check and production build passed.
- [ ] Dependency audit passed.
- [ ] Secret scan passed.
- [ ] Hosted image and Compose validation passed.
- [ ] `check-health.sh` passed through the configured HTTPS origin.

Evidence or CI run:

## Authorization smoke test

- [ ] Administrator login and logout work.
- [ ] Account activation and password reset links are single-use.
- [ ] Campaign invitation and membership changes work with two test accounts.
- [ ] A non-member cannot enumerate the campaign or retrieve its API records.
- [ ] A member cannot read another member's private notes or backstory.
- [ ] Protected campaign and character images cannot be fetched anonymously.
- [ ] Owner and member campaign exports contain only data visible to the
  exporting user; viewers cannot export.
- [ ] Suspension and global session revocation invalidate active sessions.
- [ ] Orphaned-campaign recovery records an administrative reason.

## Backup and recovery

- Backup timestamp and protected location:
- Backup `source_revision` and `application_image_id`:
- Encryption mechanism and key custodian:
- Retention schedule:
- Restore-drill date:
- [ ] Checksums passed.
- [ ] Protected files extracted successfully.
- [ ] PostgreSQL restored into a disposable database.
- [ ] Required installation and campaign tables were queried successfully.
- [ ] Decryption was tested from the off-host copy.

## Operations and exposure

- [ ] Only intended HTTP/HTTPS ports are published.
- [ ] PostgreSQL and application HTTP ports are private.
- [ ] Real-domain public TLS is configured before internet exposure.
- [ ] Host firewall, router administration, and automatic security updates are configured.
- [ ] External availability, container health, backup age, and disk alerts are active.
- [ ] Secret-rotation and incident-response procedures were reviewed.
- [ ] Rollback image/source revision and schema-compatible recovery path were recorded.

## Decision

- [ ] Approved for owner-only hosted alpha.
- [ ] Approved for internal multi-user collaboration.
- [ ] Not approved; corrective actions are recorded below.

Corrective actions and sign-off:
