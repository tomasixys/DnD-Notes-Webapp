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

`app/main.py` registers every API router before mounting the frontend catch-all.
Application startup initializes storage and applies database migrations.

## Package boundaries

```text
backend/app/
  dependencies/       Reusable FastAPI request dependencies
  migrations/         Ordered SQLite schema migrations
  models/
    api/               Explicit request, response, and backup models
    database/          SQLModel persistence models and relationships
    enums/             Shared domain enumerations
  routers/             HTTP paths, inputs, outputs, and status codes
  services/            Domain operations and transaction coordination
  tags/                Stateless parsing plus focused tag query helpers
  app_paths.py         Platform-specific persistent paths
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
- `SessionNoteService` composes `RollService` for rolls stored beneath a
  session.
- `CampaignBackupService` composes domain services instead of reimplementing
  their rules.
- `LocationService` and `FactionService` coordinate relationship-backed tags
  through the shared campaign context.
- `SearchService` owns campaign-scoped matching, weighting, filtering, and
  result ordering.
- `TagService` owns database-backed tag synchronization, relationships, reverse
  references, search matching, refresh, and deletion cleanup.

Stateless tag parsing and formatting remain pure functions in `app/tags`.

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

Numbered migration modules are registered in `app/migrations/runner.py`.
Before migrating an older database, the runner creates a pre-migration backup.
The development migration hook is unversioned and must remain idempotent; its
work is promoted into a numbered migration before release.

The current schema version is 4.

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

