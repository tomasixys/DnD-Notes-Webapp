# Backend architecture

This document describes the current backend structure and the conventions that
new backend work should preserve. The completed implementation plan is retained
in the [July 2026 backend refactoring record](archive/backend-refactoring-2026-07.md).

## Runtime

DnD Notes uses one FastAPI/Uvicorn process in production. It serves:

- the JSON API under `/api`;
- uploaded campaign files under `/api/uploads`;
- the compiled Vue frontend at `/`; and
- Vue Router history routes through the frontend catch-all.

`app/application.py` constructs the application, registers every API router
before mounting the frontend catch-all, and owns startup initialization.
`app/main.py` is the ASGI compatibility entry point. The typed launcher in
`backend/run.py` validates configuration before constructing the application.

## Package boundaries

```text
backend/app/
  auth/               Local identity, credentials, login, and browser sessions
  dependencies/       Reusable FastAPI request dependencies
  migrations/         Ordered SQLite schema migrations
  models/
    api/               Explicit request, response, and backup models
    database/          SQLModel persistence models and relationships
    enums/             Shared domain enumerations
  routers/             HTTP paths, inputs, outputs, and status codes
  services/            Domain operations and transaction coordination
  tags/                Stateless parsing plus focused tag query helpers
  application.py       FastAPI construction and startup lifecycle
  app_paths.py         Platform-specific persistent paths
  config.py            Typed launch configuration and deployment validation
  file_storage.py      Shared validation and filesystem primitives
  frontend.py          Compiled-frontend mounting and history fallback
```

### Routers

Routers should remain thin. They:

- declare paths, methods, status codes, and response models;
- resolve request dependencies;
- pass validated input to a service; and
- translate domain failures into HTTP responses where necessary.

Routers should not import operations from other routers or own reusable database
logic.

### Dependencies and campaign context

`app/dependencies/campaigns.py` resolves campaign path parameters and returns a
consistent not-found response.

Campaign-scoped services receive one request-scoped `CampaignContext` containing
the database session and verified campaign. Service methods therefore do not
repeat `campaign` or `campaign_id` parameters, and one service instance cannot
accidentally operate across campaign boundaries.

Application-wide operations, such as campaign creation and backup import, use
the database session directly until a new campaign has been flushed and a
context can be established.

### Services

Services own application behavior, domain validation, persistence coordination,
response conversion, and transaction boundaries. A service should represent a
cohesive resource domain or orchestration feature, not mechanically mirror
every database table.

Services use composition instead of inheritance:

- `CharacterService` composes person operations because a character profile is
  backed by a person.
- `CharacterNoteService` and `BackstoryNoteService` share private note
  mechanics while preserving separate models and public APIs.
- `EpisodeService` owns played-game notes and composes `RollService` for rolls
  stored beneath an episode.
- `CampaignBackupService` composes domain services instead of reimplementing
  their rules.
- `LocationService` and `FactionService` coordinate relationship-backed tags
  through the shared campaign context.
- `SearchService` owns campaign-scoped matching, weighting, filtering, and
  result ordering.
- `TagService` owns database-backed tag synchronization, relationships, reverse
  references, search matching, refresh, and deletion cleanup.

Stateless tag parsing and formatting remain pure functions in `app/tags`.

### Episode terminology and compatibility

`Episode` is the backend domain term for one played game and its notes/rolls.
This avoids collisions with SQLModel database `Session` objects and
authentication `AuthSession` records.

Existing compatibility boundaries deliberately keep their released names:

- the database table remains `sessionnote`, with `session_id` roll foreign keys;
- HTTP routes remain under `/api/campaigns/{campaign_id}/sessions`;
- request/response fields retain `session_number`, `session_id`,
  `session_stats`, and `session_count`;
- tag resources continue to serialize as `"session"`; and
- campaign backups continue to serialize their episode collection as
  `sessions`.

Those names may change only through an explicit API, database, or backup-schema
migration. New internal backend code should otherwise use `Episode`.

## Transactions

A complete mutation has one visible transaction owner.

- A standalone service operation owns commit, rollback, refresh, and response
  construction.
- A composable `stage_*` operation flushes and synchronizes state without
  committing, allowing a coordinating service to retain the transaction.
- Read-after-write responses are constructed only after generated IDs,
  relationships, totals, and timestamps are current.
- A resource from another campaign normally produces the same not-found result
  as a missing resource.

### Uploaded files

`file_storage.py` provides shared validation, safe paths, and filesystem
operations. The resource service owns the surrounding database transaction and
file lifecycle:

- newly written files are removed when the database mutation fails;
- replaced files are removed only after the replacement state commits; and
- deletion cleanup targets only files owned by the affected resource.

## API models and mutation responses

Public transport models live in `app/models/api`; database models do not double
as ad hoc response dictionaries.

Mutations return the smallest authoritative state needed by active consumers:

- top-level creation and updates return the complete refreshed read model;
- top-level deletion returns a typed response containing `deleted_id`;
- a small nested aggregate may be returned when several displayed values change
  together, as inventory mutations do with `InventoryRead`;
- a typed envelope may contain multiple independently useful models, as roll
  mutations do with session and campaign statistics; and
- full collections are reserved for true bulk operations or server-owned
  ordering that cannot be updated safely on the client.

The frontend applies returned state locally and preserves the ordering used by
the corresponding collection endpoint. It should not immediately issue a
compensating GET for data already present in a mutation response.

Every API operation must declare an explicit success-response schema. Frontend
API failures consistently expose `error` and `message`, including validation
errors.

## Campaign backups

Campaign backup is an orchestration feature. `CampaignBackupService` owns
archive parsing, asset collection, serialization, ID remapping, operation
ordering, and the encompassing import transaction.

Resource rules remain in their domain services. Those services provide:

- deterministically ordered collection conversion for export; and
- composable import operations that participate in the backup transaction
  without committing independently.

Backup import must be atomic. Invalid archives return a client error without
leaving a partially created campaign or orphaned imported files.

Changing the backup schema or archive layout requires explicit compatibility
planning and migration tests.

## Persistence and migrations

SQLite data and uploads live in the platform-specific user-data directory
selected by `platformdirs`, outside the executable and source tree.

The engine is configured lazily during application startup from typed settings.
Local mode defaults to the platform data-directory SQLite file; hosted
configuration references a PostgreSQL URL through an environment variable.
Request dependencies resolve the initialized engine rather than importing a
hard-coded global connection.

Every initialized database has one `Installation` row. It records the
installation identity, deployment mode, and initialization time. Startup
rejects a requested mode that differs from the stored mode. User accounts and
administrator credentials are separate application-managed records.

Hosted local identity is an independent application domain under `app/auth`.
Its persistence state is split across `User`, `PasswordCredential`,
`AuthSession`, `AccountToken`, `LoginThrottle`, and `SecurityEvent`. Password
operations go through
`auth/passwords.py`, which delegates hashing and verification to
`argon2-cffi`, upgrades hashes after successful verification when parameters
change, and revokes server-side sessions during password reset. Offline
administrator creation and password reset use the same authentication-domain
services while holding the installation lock.

The authentication foundation issues independent random session and CSRF
tokens. Only SHA-256 token digests are persisted. Sessions have renewable idle
expiry, an absolute expiry ceiling, explicit revocation, and account-state
checks. Authentication request dependencies and routes remain inside the same
domain package; resource services do not import password or login mechanics.
The authentication router returns the session token only in a host-only,
secure, HTTP-only cookie and returns the session-bound CSRF token in the
response body. Hosted mode mounts these routes and protects every other API
path, including uploaded files, with session authentication and CSRF checks
for unsafe methods. Local mode seeds one non-login internal user instead of
exposing a hosted authentication bypass.

System administrators create pending accounts through one-time activation
tokens and may issue one-time password-reset tokens. Raw account tokens are
returned once for the administrator to share and only their SHA-256 digests
are stored. Password resets revoke existing sessions. Account deletion removes
the credential, revokes sessions and active account tokens, and retains a
tombstoned user row.

Login defenses combine username/account lockout with a keyed, source-aware
throttle. The source key is an HMAC derived from the runtime session secret, so
throttle and security-event rows do not retain a raw network address.
Pre-installation databases containing campaigns can be claimed only by local
mode; moving desktop data into hosted mode remains an explicit import process.

Alembic in `app/migrations/portable` owns the cross-database migration history.
Its first revision is a current-schema baseline used to create empty SQLite and
PostgreSQL databases.

The original numbered SQLite migrations remain as an adoption bridge. An
existing SQLite database is backed up, upgraded through legacy schema version
4 plus the final development hook, and stamped at the Alembic baseline in the
same startup operation. A non-empty PostgreSQL database without Alembic history
is rejected and requires an explicit reviewed adoption process.

PostgreSQL integration tests create a unique temporary schema and remove only
that generated schema. CI runs them against a disposable PostgreSQL service.

Normal startup holds an exclusive instance lock. The separate offline
maintenance command uses the same lock for non-secret inspection and
filesystem-backed campaign export.

## Verification expectations

Backend changes should include focused regression tests for their domain.
Cross-cutting API or architecture changes should additionally verify:

- campaign scoping and not-found behavior;
- commit, rollback, and uploaded-file cleanup;
- backup import/export round-tripping;
- tag and relationship synchronization;
- explicit OpenAPI response schemas;
- authoritative mutation responses;
- frontend type-checking; and
- the production frontend build.

Run the backend tests and frontend type-check using the commands in the root
[README](../README.md).

