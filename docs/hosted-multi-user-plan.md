# Hosted multi-user development plan

Status: Milestones 0-8 implemented; the Milestone 9 private-server baseline is
deployed with live operator testing underway. Wider-rollout hardening remains
optional where noted below.

Updated: 2026-09-09

## Goal

Evolve DnD Notes from a trusted local, single-user application into a hosted
application where authenticated users can safely collaborate in campaigns.
The work should preserve the packaged local application and the existing
campaign backup format wherever practical.

This is not only a login feature. It changes the application's trust boundary,
data ownership, storage, deployment, and conflict behavior. No hosted release
should happen until every API route, uploaded asset, and backup download is
protected by the same campaign-membership rules.

## Recommended first hosted release

The first collaborative release should deliberately stay small:

- Hosted accounts use usernames and passwords managed by the DnD Notes server.
  Passwords are stored only as Argon2id hashes produced by a maintained
  password-hashing library.
- FastAPI exchanges valid local credentials for a server-side application
  session held in a secure, HTTP-only cookie. Authentication tokens are not
  stored in browser local storage.
- Campaign access is granted through explicit `owner`, `member`, and `viewer`
  memberships.
- All existing campaign content is shared with campaign members. Fine-grained
  private notes are added only after the membership boundary is proven, but
  new resource models retain ownership and visibility metadata so the later
  restriction does not require another architectural reset.
- The hosted database is PostgreSQL. The packaged local application may
  continue using SQLite through the same models and service interfaces.
- Hosted uploads use private object storage or an authorized filesystem-backed
  file service on the server. Knowing a file path must not grant access.
- Concurrent edits use optimistic version checks before live synchronization
  is attempted.

The existing active-character and inventory owner/manager fields remain game
domain data. They must not determine whether an application user may read or
modify a campaign.

## Decisions to record before implementation

The following initial product decisions have been accepted. Milestone 0 records
their exact behavior as short architecture decision records:

1. **Authentication:** hosted mode uses accounts and password credentials that
   exist only in the DnD Notes installation. The application owns password
   hashing, login throttling, activation, reset, session revocation, and
   credential security updates. It uses maintained libraries rather than
   custom cryptography.
2. **Deployment profiles:** the build selects either `local` or `hosted`.
   Local mode has no login, uses an internal local user, and may bind only to
   loopback. Hosted mode always requires authentication; there is no production
   runtime switch that can make a hosted build open.
3. **Roles:** campaigns use `owner`, `member`, and read-only `viewer`. The
   viewer role adds policy and matrix tests but no materially different
   authorization architecture. Avoid custom roles until real usage
   demonstrates a need.
4. **Campaign administration:** owners alone change campaign settings and
   images, manage members, and delete campaigns. Owners and members may export
   access-filtered campaign backups. Members may edit campaign-wide shared
   resources and manage their assigned character. Viewers can only read
   campaign-wide shared resources.
5. **Privacy:** start with campaign-wide sharing, while recording resource
   creator/owner and visibility metadata. Add private and restricted resources
   as a separate milestone with explicit grant rules.
6. **Administration and deletion:** one or more local users may have a global
   system-admin role with access to every campaign. A separate,
   non-interactive system-custodian identity receives campaigns that would
   otherwise become ownerless when a user is deleted.
7. **Hosted import/export:** owners and members may export campaign backups
   containing only records the requesting user can read. An explicitly elevated
   system-admin maintenance export remains a separate recovery operation.
   Account, session, invitation, audit, and server-role data are
   never included. The importing user becomes owner of a newly imported
   campaign.

“Campaign administration” above means mutation of the `Campaign` aggregate and
its membership/security settings. It does not mean that ordinary members are
unable to collaborate on campaign-wide shared resources.

## Deployment profiles

The build argument should select a security profile, not contain secrets:

```text
python build.py --profile local --config config/local.toml
python build.py --profile hosted --config config/hosted.toml
```

- `local` is the default for the PyInstaller desktop artifact. The chosen
  profile is embedded in the backend artifact, the server creates/resolves one
  internal local identity, and startup rejects a non-loopback bind address.
- `hosted` permanently enables authentication and authorization enforcement.
  Database credentials, cookie secrets, and origins are still supplied
  securely at runtime; build arguments and frontend environment variables must
  not contain them.
- The backend exposes only safe public configuration to the frontend. The
  frontend may adapt its login UI to the profile, but only backend policy
  determines whether a request is authorized.
- Source development may have an explicit `development` profile with test
  identities. Production startup must reject it.
- The build validates the supplied configuration and copies a distributable
  configuration file or template beside the application. The embedded profile
  is a security ceiling: a hosted artifact rejects `mode = "local"` even on an
  empty database.

This gives separate open and authenticated distributions without allowing a
misconfigured environment variable to turn an internet-facing hosted artifact
into the open local application.

## Configuration lifecycle

Configuration values have different lifetimes and must not all behave like
ordinary editable settings.

### Build constraints

These values describe what the artifact is allowed to do:

- allowed deployment profile: `local` or `hosted`;
- application/version metadata;
- supported database and storage drivers; and
- safe defaults such as the default config-file location.

The build may validate and package these values. It must not contain database
passwords, user passwords, password hashes, session keys, invitation/reset
tokens, or default administrator passwords.

### First-launch bootstrap values

These values are consumed only when initializing a new database:

- deployment mode, which must match the artifact profile;
- an installation ID;
- the local internal user for local mode;
- initial non-secret product defaults.

Initialization creates a single installation record containing at least the
mode, installation ID, initialization time, and bootstrap completion state. On
later launches, the database value is authoritative. If the editable config
requests a different mode, startup fails with a diagnostic instead of changing
the database's trust boundary.

Do not bootstrap a hosted administrator with a shared username/password from
the config file. An offline `create-admin` command requires operating-system
access, acquires the installation lock, securely prompts for the password, and
transactionally creates the first administrator through the normal credential
service. It refuses to create another bootstrap administrator after an
enabled, login-capable administrator exists. Administrators are subsequently
managed through authenticated, audited application operations.

### Runtime settings

These values may be read on every launch and changed without changing the
installation's security identity:

- bind address and port;
- public HTTPS origin;
- logging level and operational limits;
- database connection reference and storage endpoints;
- references to secrets supplied by environment variables, restricted secret
  files, or a deployment secret manager.

Local mode permits configurable ports but rejects non-loopback bind addresses.
Hosted mode validates the public origin, secure cookie settings, and proxy
trust. Changing the database connection may select a different installation,
but the selected database must still pass the stored-mode check.

### Application-managed settings

Users, password credentials, system roles, sessions, campaign memberships,
activation/reset tokens, and invitations live in the database and are changed
through authorized application or administrative operations, not by editing
the launch configuration.

### Recovery access

A hosted installation must never fall back to open local mode merely because
credentials or configuration are unavailable. Provide a separate maintenance
command instead. It should:

- require operating-system access to the server;
- acquire an exclusive installation lock so the hosted service is not running;
- bind only to loopback if it exposes a UI;
- generate an instance-unique, short-lived recovery token;
- audit any database changes; and
- offer read-only inspection/export before mutation or ownership recovery.

For a PostgreSQL/object-storage deployment, recovery may produce an offline
campaign or disaster-recovery export rather than attempting to open the hosted
database in the SQLite desktop application. Changing deployment mode should be
an explicit migration with a verified backup, never a normal launch option.

## Current architecture findings

The current design provides a useful starting point:

- Most resource routers already resolve a `CampaignContext`.
- Domain services consistently filter resources by `campaign_id`.
- Cross-campaign resource IDs generally produce the same response as missing
  IDs.
- Backup import is atomic and uploaded-file cleanup is coordinated with
  database transactions.

The original architecture review identified the following assumptions to
change before hosting. The milestone status notes below record which items have
since been completed:

- `CampaignContext.resolve()` verifies existence, not membership.
- Campaign list, create, update, delete, import, and export accept any caller.
- SQLite configuration, `PRAGMA user_version`, and migration code are tied to
  one local database file.
- `/api/uploads` was mounted as public static content. Campaign images,
  character portraits, and generated campaign backup archives could therefore
  be fetched without authorization.
- `Campaign.active_character_person_id` is global. In a multi-user campaign,
  character selection belongs to a membership or user preference.
- The frontend has no authenticated application bootstrap, route guards,
  session-expiry handling, or CSRF handling.
- Selected campaign state is stored under one global browser key and can leak
  between accounts using the same browser.
- Mutations have no version precondition, so two clients can silently overwrite
  each other's edits.
- The local process model and filesystem storage do not support horizontal
  scaling.

## Security invariants

These rules apply to every milestone:

- The server derives the current user from a verified server-side session.
  Client-provided user IDs are never trusted.
- Every campaign operation resolves an authenticated actor plus either a
  campaign membership or an explicitly elevated system-admin context before it
  reaches domain behavior.
- A non-member receives `404` for a campaign or nested resource so IDs cannot be
  used to enumerate private campaigns. An authenticated member who lacks a
  permitted action may receive `403`.
- Role checks happen on the backend. Hidden or disabled frontend controls are
  only usability features.
- Unsafe cookie-authenticated requests require CSRF protection.
- Session cookies use `HttpOnly`, `Secure`, and an explicit `SameSite` policy;
  sessions rotate after login and sensitive account changes.
- Invitation, reset, and session tokens are random, expiring, revocable, and
  stored only as digests where the application controls their storage.
- Uploaded files and backup downloads go through an authorization check or use
  short-lived signed URLs issued only after that check.
- Logs and audit events never include raw tokens, cookies, secrets, or private
  note bodies.
- System-admin access to a campaign is explicit and audited. Normal background
  requests never silently elevate themselves.
- Authorization behavior is tested as a matrix of anonymous, non-member,
  viewer, member, owner, and system-admin callers.

## Ordered milestones

### Milestone 0 — Product rules and threat model

**Purpose:** decide what is being secured before schema or UI work begins.

Status: complete on 2026-07-23

Deliverables:

- Record the seven decisions above:
  - [x] [ADR 0001: deployment profiles, identity bootstrap, and recovery](decisions/0001-deployment-identity-bootstrap-and-recovery.md)
  - [x] [ADR 0002: campaign roles and capability matrix](decisions/0002-campaign-roles-and-capabilities.md)
  - [x] [ADR 0003: system administration, deletion, and custody](decisions/0003-system-administration-deletion-and-custody.md)
  - [x] [ADR 0004: resource visibility and portable exports](decisions/0004-resource-visibility-and-portable-exports.md)
  - [x] [Hosted threat model, recovery expectations, and release non-goals](security/hosted-threat-model.md)
- Define the role matrix:
  - owner: read and edit shared content, manage the campaign and its members,
    assign characters, import/export, and delete the campaign;
  - member: read and edit shared content and manage the character assigned to
    that membership;
  - viewer: read shared campaign content only.
- Define system-admin elevation, auditing, and the non-interactive custodian
  account. System administrators do not become ordinary campaign members
  merely by inspecting or recovering a campaign.
- Confirm whether a campaign may have multiple owners. Multiple owners are
  recommended; custodial transfer is then needed only when deletion would
  remove the last owner.
- Write abuse cases covering account takeover, ID enumeration, cross-campaign
  access, malicious invitations, CSRF, unsafe uploads, backup disclosure, and
  concurrent overwrites.
- Define hosted account recovery and support expectations.
- Explicitly keep organizations, billing, public share links, custom roles,
  and real-time document co-editing out of the first release.

Exit criteria:

- The product rules are unambiguous enough to turn into authorization tests.
- Local-mode behavior and hosted-mode behavior are both documented.

### Milestone 1 — Server-ready configuration, database, and migrations

**Purpose:** create a stable persistence foundation before identity tables
become production data.

Status: implementation complete; PostgreSQL CI verification pending

Progress:

- [x] Add a strict TOML configuration schema, safe config discovery, local and
  hosted validation, and command-line server overrides.
- [x] Reject non-loopback local binding and incomplete hosted database, origin,
  session, proxy, and storage configuration.
- [x] Persist one installation identity, deployment mode, and initialization
  time; reject later mode changes and hosted adoption of a legacy local
  database.
- [x] Add the installation table through an idempotent development migration.
- [x] Embed and validate the deployment profile in distinctly named build
  artifacts, include the Windows/Linux host platform in artifact names, and
  copy the validated config beside the executable.
- [x] Add database URL, environment-secret reference, engine, pool health, and
  connection recycling settings.
- [x] Add PostgreSQL driver/engine construction.
- [x] Add storage, trusted-proxy, secure-cookie, session-secret, and runtime
  secret-reference settings.
- [x] Adopt an Alembic cross-database baseline with a legacy SQLite adoption
  bridge.
- [x] Add a PostgreSQL integration test and disposable PostgreSQL CI service.
- [x] Add a separate offline maintenance command sharing the server's
  exclusive instance lock.
- CI can run the PostgreSQL integration test when the repository is published,
  but hosted CI sign-off is not required for the private-server scope.

Deliverables:

- Replace hard-coded paths and development origins with validated settings for
  deployment profile, database URL, public origin, trusted proxy behavior,
  cookie settings, storage backend, and secrets.
- Add `--profile local|hosted` to the build and embed the result in the backend
  artifact. Add `--config PATH`, validate the file against the selected profile,
  and give artifacts distinct names or build metadata so their security mode
  is obvious.
- Make local-profile startup reject non-loopback host binding, hosted-profile
  startup reject missing database/session/origin configuration, and production
  startup reject the development profile.
- Add the persisted installation record and first-launch transaction. Test that
  later config edits cannot change mode or replace the installation identity.
- Define a typed configuration schema, validation errors, safe precedence, and
  secret references. Document which values are build constraints, first-launch
  bootstrap values, runtime settings, and application-managed settings.
- Add the loopback-only recovery command as a separately authorized maintenance
  path; do not reuse the normal local-mode bypass.
- Make the database session/engine configuration support both PostgreSQL and
  SQLite.
- Adopt a migration workflow that runs against PostgreSQL and SQLite. Convert
  the current SQLite-only version migrations or create a documented baseline
  transition into the new migration history.
- Add PostgreSQL integration tests in CI while retaining fast SQLite unit
  tests where useful.
- Add transaction and connection-pool settings suitable for a server process.
- Decide how existing desktop campaigns reach hosted mode. Recommended:
  campaign backup import rather than uploading a raw SQLite database.
- Add startup checks that fail clearly when secrets, origins, or production
  storage are unsafe or missing.

Exit criteria:

- A clean database can be created and migrated on both supported engines.
- The existing backend test suite passes against SQLite and the selected
  integration suite passes against PostgreSQL.
- No application service constructs or assumes the path of the database.

### Milestone 2 — Identity and secure sessions

**Purpose:** establish who is making a request, without yet claiming that login
alone grants campaign access.

Status: implementation complete; CI verification pending

Progress:

- [x] Add cross-database user, password credential, account-token, and
  revocable-session models.
- [x] Apply the unreleased identity schema idempotently to both fresh databases
  and databases already stamped at the Milestone 1 portable baseline.
- [x] Add the Argon2id credential service, automatic hash-parameter upgrades,
  system custodian seed, and offline first-admin/password-reset commands.
- [x] Add generic local credential verification, bounded account lockout,
  digest-backed revocable sessions, idle/absolute expiry, session-bound CSRF,
  and login/logout/current-session router foundations.
- [x] Add login/logout/current-session APIs, CSRF enforcement, throttling, and
  complete hosted route protection.
- [x] Add invite-only activation, administrator-issued password reset,
  account tombstoning, keyed source throttling, and persistent security
  events.
- [x] Keep development identities in isolated test fixtures only; production
  has no fixture switch or default credential.

Suggested data model:

- `User`: unique normalized username, optional profile/email, account status,
  global system role, login capability, and timestamps.
- `PasswordCredential`: one-to-one user reference, Argon2id encoded hash,
  password-changed time, and hash-policy version. The encoded hash contains its
  unique salt and parameters.
- `AuthSession`: user, token digest, creation, last use, expiry, revocation,
  and minimal device metadata.
- `AccountToken`: activation/reset purpose, token digest, user, creation,
  expiry, and consumed time.
- One seeded `SystemCustodian`: a `User` with no password credential and
  `can_login = false`, used only to preserve ownership of orphaned campaigns.

Deliverables:

- Implement username/password login, current-session, logout, and
  logout-all-sessions endpoints.
- Add `get_current_user` and `require_current_user` FastAPI dependencies.
- Use a backend-for-frontend flow: the browser holds only the secure application
  session cookie.
- Add CSRF-token issue and validation behavior for unsafe methods.
- Add session expiry, rotation, revocation, disabled-account, and
  password-reset tests.
- Add generic authentication errors, username/account-aware throttling,
  source-aware rate limiting, bounded temporary lockout, and security events.
- Add administrator-created activation and password-reset tokens. Initially
  the administrator may copy activation/reset links to users without email.
- Implement a development identity fixture that cannot be enabled accidentally
  in production.
- Implement the local-mode internal user without exposing a hosted auth bypass.
- Add an offline, lock-protected, securely prompted `create-admin` command.
  Never assign admin to the first web signup or ship a default credential.
- Add an offline password-reset path for recovery when no administrator can
  log in.
- On password change or reset, revoke existing sessions. On account deletion,
  revoke sessions and credentials and retain a tombstoned user row where
  referential integrity or audit history requires it.

Exit criteria:

- Anonymous and authenticated behavior is deterministic across every auth
  endpoint.
- Authentication responses do not reveal whether a username exists.
- No session token is persisted in browser local storage.
- Production startup refuses insecure origin, cookie, or proxy settings.
- Credential hashing, throttling, reset, and session revocation have negative
  and concurrency tests.

### Milestone 3 — Campaign tenancy and authorization

**Status:** completed on 2026-07-25. The resource-specific private visibility
architecture prepared here is now implemented for character notes and
backstory in Milestone 7; the expansion matrix is documented in
[`resource-visibility-migration.md`](resource-visibility-migration.md).

**Purpose:** make membership, rather than possession of an ID, the boundary for
all campaign data.

Suggested data model:

- `CampaignMembership`: unique `(campaign_id, user_id)`, `owner`, `member`, or
  `viewer` role, joined time,
  optional membership-specific active character, and status if needed.
- Optional `AuditEvent`: actor, campaign, event type, target reference,
  timestamp, and safe metadata for security-sensitive operations.

Deliverables:

- Extend or replace `CampaignContext` with an authorized context containing the
  database session, campaign, current user, and membership.
- Require services operating on a campaign to receive that authorized context.
  Avoid service entry points that accept only `db` plus an arbitrary
  `campaign_id`.
- Filter campaign lists by membership.
- Make campaign creation atomically create an owner membership.
- Move active-character selection from `Campaign` to
  `CampaignMembership`. Migrate the existing value to the local/legacy owner.
- Add reusable policy checks such as `require_view`, `require_edit`, and
  `require_owner`; keep the role matrix and system-admin elevation centralized.
- Protect campaign CRUD, every nested router, search, backup import/export, and
  any indirect tag or relationship lookups.
- Enforce the last-owner rule and atomic ownership transfer. When account
  deletion would leave no human owner, transfer ownership to the non-login
  system custodian and flag the campaign for admin recovery.
- Allow system admins to resolve any authorized campaign context, but record
  the elevation and expose campaign recovery through explicit admin workflows
  rather than silently creating memberships.
- Add `created_by_user_id` and a campaign-default visibility value to new
  protectable resource schemas. For existing resource types, prepare a
  migration matrix and add the fields when the privacy policy begins to use
  them.
- Backfill existing local campaigns to one generated local owner in a numbered
  migration.
- Add an automated route audit so a newly registered `/api` route cannot
  silently omit an authentication/authorization classification.

Exit criteria:

- Authorization matrix tests cover every API operation.
- A user cannot list, read, mutate, search, export, or infer another user's
  campaign.
- All existing campaign behavior still passes through a single authoritative
  context and transaction owner.

### Milestone 4 — Authenticated frontend shell

**Status:** completed on 2026-07-25. The frontend now shares one explicit
session bootstrap in local and hosted builds, while local mode retains its
non-login identity and does not expose hosted account-management endpoints.

**Purpose:** make session and authorization state explicit in the client.

Deliverables:

- Add an auth store with `loading`, `anonymous`, `authenticated`, and
  `expired` states.
- Bootstrap `/api/auth/session` before loading campaign data or entering
  protected routes.
- Add login, callback/loading, logout, expired-session, access-denied, and
  account-profile UI.
- Make all API helpers send same-origin credentials and the CSRF token for
  unsafe requests.
- Centralize `401`, `403`, `404`, `409`, and network-failure handling.
- Add route guards that preserve the intended route through login.
- Namespace selected-campaign browser state by user ID, and clear all
  user-scoped client state on logout or account change.
- Use membership capabilities returned by the API to hide or disable
  unauthorized controls, while retaining backend enforcement.

Exit criteria:

- A fresh, expired, revoked, and switched-account session each produce a clean
  UI state with no prior user's campaign data.
- Viewer/member/owner controls match the server role matrix.

### Milestone 5 — Protected assets and backups

**Status:** completed on 2026-07-25 for durable filesystem storage. Campaign
and character database relationships are the authoritative asset ownership
mapping, so no redundant asset table was required. The public uploads mount is
gone, and backup downloads are authorized, one-request responses backed by
temporary files removed after transfer or by hourly expiry cleanup. A future
remote-object adapter may replace these responses with short-lived signed URLs
without changing the authorization boundary.

**Purpose:** close the largest current hosting-specific data leak.

Deliverables:

- Remove the public `/api/uploads` mount for private campaign data.
- Introduce asset records or another ownership mapping that can prove the
  campaign for each stored object.
- Serve local-mode files through an authorized endpoint; use private object
  storage and short-lived signed URLs in hosted mode where practical.
- Authorize campaign images, character portraits, backup exports, replacements,
  and deletions.
- Do not leave generated backup archives indefinitely in a web-readable
  directory. Stream them, use expiring objects, or clean them with a reliable
  lifecycle.
- Validate content type from file bytes, size limits, filenames, archive
  expansion limits, and image decoding behavior.
- Test cross-campaign URLs, stale signed URLs, deleted memberships, replaced
  files, rollback cleanup, and backup expiry.

Exit criteria:

- No stored campaign asset is retrievable solely by knowing or guessing its
  path.
- Backup files expire or are removed and cannot outlive the authorization that
  created their download.

At this point an **owner-only hosted alpha** can be deployed for infrastructure
and security testing. It is not yet the collaborative release.

### Milestone 6 — Invitations and campaign member management

**Status:** completed on 2026-07-25. Campaign membership can now be created
only by accepting a digest-backed invitation issued to an existing active or
activation-pending server account. Owner management, explicit ownership
transfer, exact-account redemption, source throttling, audit records, and the
frontend invitation/member flows are implemented. Email delivery remains
optional and is not part of the self-hosted first release.

**Purpose:** introduce controlled collaboration after the authorization
boundary is proven.

Suggested data model:

- `CampaignInvitation`: campaign, invited local user or activation-pending
  account, intended role, inviter, token digest, expiry,
  acceptance/revocation timestamps, and uniqueness rules.

Deliverables:

- [x] Add owner-only invite, list, resend/replace, revoke, role-change, remove
  member, leave campaign, and transfer-ownership operations.
- [x] Make invitation acceptance one-time, expiring, rate-limited, and atomic with
  membership creation.
- [x] Define behavior when the signed-in account differs from the invited account.
- [x] Prevent removal or demotion of the last owner.
- [x] Add a membership screen and pending-invitation flow.
- [x] Add security audit events for invites, role changes, removals, ownership
  transfers, exports, and campaign deletion.
- [x] Complete the token flow without email; email delivery remains optional.

Exit criteria:

- Two independent users can join one campaign and receive exactly their
  assigned permissions.
- Revocation and role changes affect the next request, not merely the next
  login.

### Milestone 7 — Explicit private visibility

**Status:** completed on 2026-07-25 for character notes and backstory.
Both resource types now use centralized campaign-plus-resource policy,
normalized user grants, filtered search/tag/reference paths, portable
visibility metadata, and access-filtered owner and member exports. Existing and legacy
imported entries remain campaign-visible. Private/restricted imports are
normalized to importer-owned private entries, while explicitly elevated
maintenance exports remain separate from ordinary user downloads.

**Purpose:** add privacy intentionally instead of relying on the old
single-user meaning of “private character.”

Recommended first scope:

- Add `campaign`, `restricted`, and `private` visibility to character notes and
  backstory first.
- Private records have an owning user or membership; campaign owners do not
  automatically read them. System admins can use explicitly elevated, audited
  access.
- Existing content and imported backups default to campaign-visible, unless a
  migration/import rule approved in Milestone 0 says otherwise.

Deliverables:

- [x] Add explicit visibility and owner fields with deletion/transfer
  semantics.
- [x] Represent per-user access with normalized grant rows such as
  `(resource/access-policy, user, permission)`. Do not store arrays or
  comma-separated user IDs in a resource column: they are difficult to
  constrain, index, revoke, cascade, and query safely.
- [x] Keep creator metadata separate from authorization. `created_by_user_id`
  records provenance; visibility, ownership, and grant rows decide access.
- [x] Centralize resource policy evaluation so `campaign`, `private`, and
  `restricted` rules are applied consistently by services.
- [x] Apply visibility filters to direct reads, lists, search, tags,
  relationships, counts, exports, and any aggregate response.
- [x] Change user-facing campaign export to include only records readable by the
  requester. Omit or safely rewrite tags, relationships, references, and assets
  that point to excluded records.
- [x] Keep infrastructure disaster-recovery backups separate from downloadable
  campaign exports. Disaster-recovery backups may contain all encrypted server
  data and are available only through operational admin procedures.
- [x] On import, do not restore source-server user IDs. Campaign-wide records
  remain campaign-wide; requester-owned private records map to the importing
  owner;
  ambiguous restricted grants must be rejected or normalized by an explicitly
  versioned backup rule.
- [x] Prevent metadata leaks through search snippets, unresolved tags, counts,
  error messages, and asset URLs.
- [x] Add visibility controls and clear labeling in the frontend.

Exit criteria:

- Private content cannot be inferred by another member through any API,
  aggregate, search result, backup, or asset endpoint.

### Milestone 8 — Concurrent editing and multi-client synchronization

**Status:** completed on 2026-07-25. Ordinary mutable campaign aggregates now
use optimistic revision checks, while identity, invitations, and memberships
retain their existing purpose-built transactional invariants. Per-recipient
change sequences preserve private-resource visibility and per-client source
markers prevent a browser tab from reporting its own saves as remote changes.

**Purpose:** prevent silent data loss before adding real-time convenience.

Deliverables:

- [x] Add `updated_at` plus an integer version, or an equivalent revision
  token, to mutable aggregates.
- [x] Require the revision on updates/deletes and return `409 Conflict` with
  the current authoritative state when it is stale.
- [x] Add conflict UI offering reload/copy/reapply behavior. Do not silently
  choose a winner for note text.
- [x] Refresh data on window focus and after reconnect.
- [x] Add a lightweight campaign change cursor so clients can poll for
  invalidated resource types. Consider server-sent events or WebSockets only
  after this protocol is correct.
- [x] Test simultaneous edit/edit, edit/delete, membership removal during
  editing, and reconnect after missed changes.

Exit criteria:

- Two users cannot silently overwrite each other's changes.
- A connected client learns about remote changes without a full application
  reload.

Implementation scope:

- Revisions cover campaigns, episodes and rolls, people, locations, factions,
  character profiles, character notes and backstory, and party inventory.
- Stale writes return a structured conflict containing the resource identity,
  expected revision, and current authoritative revision. The client preserves
  the open form, can copy visible draft fields, and reloads only when the user
  chooses.
- Change rows contain no resource content. They are sequenced separately for
  each campaign member, emitted only to users allowed to know about the
  resource, and filtered by the requesting browser-tab identifier.
- The client polls every 15 seconds and immediately on focus, visibility
  restoration, and reconnect. A user-triggered view remount refreshes the
  affected data without reloading the application shell.

### Milestone 9 — Private-server hosting and operations

**Status:** operational implementation completed on 2026-08-05. The local
hosted staging stack passed the full PostgreSQL-enabled backend suite, HTTPS
health checks, a coordinated backup, and a disposable restore drill. Live
operator testing is underway as of 2026-09-08, with verified public-domain TLS,
health endpoints, and initial anonymous-access checks. The operator also
confirmed mobile-data access without certificate warnings, administrator
login/logout, and successful account and campaign invitations with a friend.
The remaining private-server work is a LAN exposure check, scheduling backups
and health checks, and exercising the update procedure. Encrypted off-host
restore, external monitoring, CI review, and formal sign-off are optional for
this friends-and-family deployment.

**Purpose:** keep the private server maintainable and recoverable while it is
reachable from the public internet.

Deliverables:

- [x] Build a reproducible application image and deploy the saved source
  revision. Backups record both the source revision and application image ID.
- [x] Serve the frontend and API from one HTTPS origin behind a correctly
  configured reverse proxy.
- [x] Run PostgreSQL on the same private server by default, while allowing a
  separately operated PostgreSQL service. Store assets in a protected and
  backed-up server filesystem by default, with private object storage as an
  optional future adapter. Document encryption, retention, and restore
  procedures. Current builds fail closed if the reserved object backend is
  selected.
- [x] Add liveness and readiness endpoints that reveal no sensitive state.
- [x] Add structured logs, request correlation IDs, error reporting, security
  events, basic service metrics, and alerts.
- [x] Add an audited admin surface for orphaned-campaign recovery, ownership
  transfer, account suspension/deletion, and global session revocation. Do not
  ship a default root password.
- [x] Add rate limits for authentication, invitations, imports, uploads,
  exports,
  and expensive searches.
- [x] Restrict CORS and trusted hosts to configured production origins.
- [x] Define database and selected asset-storage backup schedules and perform a
  restore drill.
- [x] Run dependency, secret, migration, authorization, and upload-security checks
  in CI.
- [x] Document incident response, password/reset compromise, session revocation,
  data export, account deletion, and rollback.

Original wider-rollout exit criteria (optional for the current private server):

- A staging environment passes the full authorization and migration suites.
- Backup restoration is demonstrated, not merely configured.
- Secrets can be rotated and all user sessions can be revoked.
- The production security checklist is signed off before inviting beta users.

### Live verification record

Checked on 2026-09-08 against the configured public HTTPS origin using Python's
standard-library HTTPS client with its default certificate and hostname
validation. Requests originated on the Linux server, used public DNS, and
carried no login credentials. No application data was changed.

| Check | Result | Evidence |
| --- | --- | --- |
| Public-domain TLS and frontend delivery | Passed | `GET /` returned `200`, HTML content, and the same HTTPS origin with certificate validation enabled. |
| Liveness | Passed | `GET /health/live` returned `200`. |
| Database-backed readiness | Passed | `GET /health/ready` returned `200`. |
| Metrics excluded from the public proxy | Passed | `GET /metrics` returned `404`. |
| Anonymous campaign-list access denied | Passed | `GET /api/campaigns` returned `401`. |

On the same date, the operator confirmed these additional browser checks:

| Check | Result | Evidence |
| --- | --- | --- |
| Independent off-LAN access | Operator-confirmed | Site opens on mobile data without a certificate warning. |
| Administrator login/logout | Operator-confirmed | Operator confirmed the requested login/logout check and reported login working. |
| Account invitation and activation | Operator-confirmed | A friend was invited successfully and became an account available for campaign invitation. |
| Campaign invitation and joining | Operator-confirmed | The friend was invited to the campaign and the operator reported the flow working. |
| Roles and private resources | Operator-confirmed | The operator subsequently reported successful role and private-resource checks. |
| Session revocation | Operator-confirmed | The operator subsequently reported successful session-revocation checks. |

These observations establish successful collaboration, role, privacy, and
session-revocation smoke tests. Invitation single-use behavior was subsequently
operator-confirmed. The complete operator health script, which also checks
backups and disk capacity, has not been verified in this session. Earlier
staging results above are historical evidence, not a fresh test or restore run
against this live deployment. Detailed evidence may optionally be kept using
the [sign-off template](hosted-alpha-signoff-template.md).

Authenticated live verification on 2026-09-08 used the dedicated non-admin
member test account and its assigned test campaign. Credentials remain in the
ignored operator-only specification file and are not recorded here.

| Check | Result | Evidence |
| --- | --- | --- |
| Member login and campaign access | Passed | Login returned `200`; the account resolved as a member with shared-resource read/write and campaign-export capabilities. |
| Shared-resource creation and relationships | Passed | Created clearly labeled test location, faction, person, and session records; subsequent reads resolved the faction/location relationships. |
| Per-member player character | Passed | Created and activated the member's test character; the campaign summary returned that character in `player_character` with matching assigned and active character IDs. |
| Optimistic revision conflict | Passed | A current location update returned `200` and revision 2; a repeat using stale revision 1 returned `409` with the expected reload-before-save response. |
| Access-filtered member export | Passed | Member export returned `200`; the ZIP integrity check passed, schema version 4 parsed, `access_filtered` was true, and the readable test records were present. |
| Pending-invitation inbox read | Passed | The accepted member account could read the pending-invitation endpoint; it returned an empty list as expected after invitation acceptance. |

The test campaign now intentionally contains records prefixed with
`[Codex Test]`. The test character was removed while reproducing LIVE-08, and
replacement-character creation was subsequently operator-confirmed. The API
checks establish the server behavior above; the reported browser workflows
have also been operator-confirmed where recorded below.

Post-merge private-server checks:

- [x] Public-domain certificate validation and frontend response.
- [x] Liveness and database-backed readiness through the HTTPS proxy.
- [x] Anonymous campaign-list denial and public metrics denial.
- [x] Verify access from an independent connection, such as mobile data
  (operator-confirmed).
- [x] Verify administrator login and logout in the live browser
  (operator-confirmed).
- [x] Complete account invitation/activation and campaign invitation/joining
  with a second user (operator-confirmed).
- [x] Verify roles, private resources, invitations, and session revocation with
  live users (operator-confirmed).
- [x] Confirm invitation links are single-use (operator-confirmed).
- [x] Verify a member's access-filtered campaign export against the live server.
- [x] Repeat the reported UI workflows after deploying the fixes, including
  promotion/demotion, invitation actions, per-user character summaries,
  filtered exports, edit conflicts, and replacement-character creation
  (operator-confirmed).
- [x] Confirm the router forwards only ports 80 and 443 and complete the other
  router-administration checks (operator-confirmed).
- [ ] Deploy and verify that a deleted account's former username can be used by
  a newly activated account.
- [ ] Confirm from another LAN device that ports 8000 and 5432 are unreachable.
- [ ] Run and schedule the coordinated backup and five-minute health check.
- [ ] Exercise the backup-first container update script.

Password-reset replay, anonymous protected-file probes, off-host encrypted
copies, external monitoring, CI review, and formal operator sign-off remain
available as optional hardening rather than completion gates for this personal
friends-and-family deployment.

These deployment checks do not block merging the application changes. They
close the operational roadmap after the merged revision is deployed.

### Milestone 10 — Optional wider rollout

**Status:** outside the current personal friends-and-family project scope. The
material below remains as reference if the deployment audience expands later.

**Purpose:** expose risk gradually and use real collaboration patterns to guide
later work.

Rollout gates:

1. Local regression: packaged single-user mode behaves as before.
2. Owner-only hosted alpha: one user per campaign; validate deployment,
   sessions, assets, backups, and recovery.
3. Internal collaboration: invitations and roles with test accounts.
4. Closed beta: a small number of real campaigns, monitored migrations, and a
   documented support path.
5. Broader availability: only after restore drills, security review, conflict
   handling, and privacy behavior have held up under beta usage.

Do not use the beta to discover whether basic tenant isolation works; that is a
pre-beta automated-test requirement.

## Dependency map

```text
Product rules and threat model
        |
        v
Server-ready configuration and persistence
        |
        v
Identity and sessions
        |
        v
Campaign tenancy and authorization
        |
        +----> Authenticated frontend shell
        |
        +----> Protected assets and backups
                    |
                    v
             Owner-only hosted alpha
                    |
                    v
        Invitations and member management
                    |
           +--------+--------+
           v                 v
    Private visibility   Concurrency/sync
           +--------+--------+
                    v
          Production hardening
                    |
                    v
               Closed beta
```

## Verification strategy

Add shared test fixtures for six actors: anonymous, unrelated authenticated
user, viewer, member, owner, and system admin. Also include the non-login system
custodian in deletion and recovery tests. For each API operation, assert the
expected status and whether the database, files, audit events, and response body
changed.

The minimum cross-cutting suite should cover:

- direct-object-reference attempts against every campaign-scoped resource;
- campaign list isolation and nested resource isolation;
- role upgrades, downgrades, revocation, ownership transfer, and last-owner
  protection;
- owner deletion, custodian transfer, admin recovery, and audit trails for
  elevated access;
- CSRF rejection and session expiry/rotation/revocation;
- private file and backup access;
- backup import ownership and exclusion of server identity data;
- private-record omission from search, tags, counts, relationships, and export;
- transaction rollback and orphaned-file cleanup;
- concurrent mutation conflicts;
- SQLite local migrations and PostgreSQL hosted migrations;
- OpenAPI response contracts, frontend type-checking, and production build.

## Major risks and mitigations

- **Authorization added only at routers:** service calls, backup orchestration,
  or future routes could bypass it. Mitigate by making authorized context a
  required service dependency and auditing route coverage.
- **PostgreSQL postponed too long:** SQLite locking and SQLite-specific
  migrations become embedded in hosted features. Complete the persistence
  milestone before production identity data.
- **Public file paths retained:** database authorization would be undermined by
  direct image or backup URLs. Gate every file retrieval.
- **Game roles confused with security roles:** a character marked inventory
  owner is not necessarily an application account owner. Keep these schemas and
  names distinct.
- **Privacy added as a query patch:** indirect paths such as search, tags,
  counts, backups, and images leak metadata. Introduce privacy only with a full
  access-path audit.
- **Real-time work started first:** synchronized clients can still overwrite or
  leak data. Establish authorization and optimistic concurrency before adding
  push transport.
- **Desktop mode becomes a bypass:** local convenience settings must never be
  accepted in hosted mode. Validate the run mode and bind local mode to
  localhost.
- **Editable config changes the trust boundary:** persist installation mode in
  the initialized database, compare it with the artifact and config on every
  launch, and fail closed on disagreement.
- **Bootstrap credentials survive deployment:** do not ship default passwords.
  Use a lock-protected offline command that securely prompts for an
  installation-specific password and refuses unsafe repeat bootstrap.
- **Password implementation becomes custom cryptography:** use a maintained
  Argon2id/password-hashing library, version parameters, and test upgrade
  behavior. Never create a new password-hashing construction.
- **Recovery mode becomes a backdoor:** require operating-system access,
  exclusive maintenance mode, loopback binding, a one-time recovery token, and
  audit logging. Never make it an automatic fallback.
- **Account deletion breaks campaigns:** transfer otherwise-ownerless
  campaigns to the non-login custodian, flag them for recovery, tombstone the
  deleted user where necessary, and preserve referential integrity for authored
  content.
- **A universal admin becomes routine access:** keep admin elevation explicit,
  audited, and separate from normal campaign membership. Use a non-login
  custodian, not a human root account, as the ownership fallback.
- **User-ID lists become embedded ACLs:** JSON, arrays, or comma-separated IDs
  complicate constraints and revocation. Use normalized visibility/owner fields
  and grant rows behind one policy service.

## Current development slice

After merging, the remaining work is the small private-server maintenance
slice:

1. Deploy and verify the deleted-username reuse fix.
2. Confirm from another LAN device that PostgreSQL and application HTTP ports
   are not reachable.
3. Run and schedule the coordinated backup and health-check scripts, then
   exercise the backup-first update script.
4. Capture each issue reported during live use with reproduction steps,
   expected and actual behavior, affected role, and relevant milestone.
   The reported issues are tracked below.
5. Prioritize authorization/privacy failures and data loss, then blocked core
   workflows and usability defects. Verify each fix with a relevant regression
   check and repeat the affected live smoke test after deployment.


## Live testing fixes — 2026-09-08

The operator reported the following issues after validating the initial hosted flows.
These changes are implemented in the working tree. LIVE-04 and LIVE-06 have
now passed authenticated API smoke tests after deployment; the remaining
browser and administrator flows still need live validation. Implementation
tests did not change production data. Subsequent live verification intentionally
added the labeled test-campaign records described in the verification record.

| ID | Report and resulting behavior | Milestone |
| --- | --- | --- |
| LIVE-01 | Align invitation/reset link copy buttons with their input, with wrapping on small screens. | 4 / 6 |
| LIVE-02 | Add audited server-role changes for other active accounts in Administration. Require an admin and a reason, preserve self-protection, and revoke the target's sessions. | 2 / 9 |
| LIVE-03 | Accept or decline a recipient's pending campaign invitation directly in the inbox. Preserve exact-account, expiry, revocation, and single-use checks; existing links remain usable. | 6 |
| LIVE-04 | Show the requesting member's active/assigned character in campaign summaries. Preserve the legacy text fallback for local mode. | 3 / 4 |
| LIVE-05 | Let a server invitee choose username, display name, and password at activation. Keep old invitation links valid and reject username collisions without consuming the invitation. | 2 / 4 |
| LIVE-06 | Allow members as well as owners to export backups filtered by the requester's existing resource visibility. Viewers remain unable to export. | 7 |
| LIVE-07 | Refresh browsing views quietly. Preserve open forms and show remote-change notices only for the resource currently being edited; inventory item/purse events identify the edited resource. | 8 |
| LIVE-08 | Clear active and assigned character state together after character or People deletion, and hydrate campaign permissions during session/login initialization, so direct navigation or a refresh still lets a member create a replacement character. | 3 / 4 |
| LIVE-09 | Replace a deleted account's public identity with an internal tombstone so a newly invited account can reuse the former username without inheriting the deleted account's ID, access, or history. | 2 |

Verification covers backend service regressions, synchronization store tests,
frontend type-check/build, and isolated browser smoke tests. LIVE-09 still
needs post-deployment live validation.
