# Backend Refactoring Plan

Status: in progress.

This document records backend cleanup that should be completed in focused,
behavior-preserving pull requests. Refactoring should not be mixed into feature
work unless it is required to implement the feature safely.

The plan applies to every backend router and domain, including campaigns,
sessions, people, locations, factions, characters, character notes, backstory,
rolls, tags, search, inventory, and future resources. The modules named in the
examples below are starting points, not the limit of the refactor.

## Goals

- Keep route modules focused on HTTP input, output, and status codes.
- Move reusable business operations out of route modules.
- Remove imports from one router into another router.
- Give database transactions clear ownership.
- Make write endpoints return enough authoritative, refreshed state for the
  frontend to update without immediately fetching the same resource again.
- Preserve existing URLs, request payloads, response payloads, and backup files
  while code is being reorganized.
- Keep each refactoring pull request small enough to review confidently.

## Progress summary

### Completed

- [x] Introduced `CampaignContext` and campaign-scoped service construction.
- [x] Extracted services for campaigns, backup, people, characters, character
  notes, backstory notes, sessions, rolls, inventory, locations, and factions.
- [x] Moved campaign backup import/export into `CampaignBackupService` and a
  separate router without changing API paths or backup layout.
- [x] Moved backup collection queries and conversion into their domain
  services.
- [x] Extracted campaign-scoped `SearchService` and `TagService` components.
- [x] Removed redundant `campaign_id` handler arguments where
  `get_campaign_context` owns path resolution.
- [x] Made inventory mutations return the refreshed `InventoryRead` aggregate.

### Remaining

- [ ] Move the remaining character image persistence logic out of the router.
- [ ] Replace remaining response dictionaries with explicit API models.
- [ ] Standardize mutation responses and remove compensating frontend GETs.
- [ ] Replace untyped `{"deleted": true}` responses.
- [ ] Complete a final transaction, error, OpenAPI, and frontend-consumer audit.

## Current pressure points

### Campaign backups

Campaign CRUD now delegates to `CampaignService`. Backup export and import
delegate to `CampaignBackupService` and are registered through the separate
`app/routers/campaign_backups.py` router while preserving their existing URLs.
The backup service owns archive creation, asset collection, serialization,
parsing, ID remapping, and the encompassing import transaction.

Backup behavior is substantial enough to be its own backend feature. Keeping it
inside the campaign CRUD router made both areas harder to understand and test.
This pressure point is resolved.

### Shared campaign lookup

Campaign lookup now lives in `app/dependencies/campaigns.py` and
`CampaignContext`. Campaign-scoped routers no longer import lookup behavior from
another router. This pressure point is resolved.

### Mixed responsibilities

Most route handlers now delegate persistence and transaction behavior to
services. The main remaining exception is character image persistence. The
next cross-cutting pressure point is inconsistent mutation responses: several
views still perform a collection GET immediately after a successful mutation.

Inventory and character notes already demonstrate the preferred frontend
behavior by applying authoritative mutation responses locally.

## Intended module boundaries

```text
backend/app/
  dependencies/
    campaigns.py
  routers/
    campaigns.py
    campaign_backups.py
    characters.py
    inventory.py
    ...
  services/
    campaign_context.py
    campaign_backups.py
    campaigns.py
    character_notes.py
    characters.py
    inventory.py
    sessions.py
    people.py
    locations.py
    factions.py
    rolls.py
    ...
```

The exact names can change when each refactor begins. The important boundaries
are:

- `routers`: HTTP-specific behavior, request models, response models, and status
  codes.
- `dependencies`: reusable FastAPI dependencies such as resolving the campaign
  from a path parameter or returning a consistent 404 response.
- `services`: application operations, transaction boundaries, domain
  validation, persistence coordination, and conversion between database and API
  representations.
- `models/api`: explicit transport models rather than ad hoc dictionaries.
- `models/database`: persistence structure and relationships only.

A repository layer is not currently planned. SQLModel queries are simple enough
to remain in services until repetition or testing difficulty demonstrates a
clear need for another abstraction.

## Service structure

Campaign-scoped services receive one resolved `CampaignContext` when they are
constructed. The context contains the request-scoped database session and the
verified campaign model. It is resolved once by a FastAPI dependency, then
shared by composed services. Methods therefore do not repeat `campaign` or
`campaign_id` parameters, and a service instance cannot accidentally cross
campaign boundaries. Application-wide operations such as campaign creation and
backup import establish the context after the new campaign has been flushed.

Prefer request-scoped service classes for resource domains that have several
related database operations. A service instance should receive the SQLModel
campaign context in its constructor and expose domain operations such as
resolving, creating, updating, activating, or synchronizing a resource. Do not
create one
service mechanically for every database table, and do not introduce a generic
CRUD base class.

When one resource builds on another, services should use composition rather
than inheritance. For example, `CharacterService` composes `PersonService`
because a character profile coordinates person operations, but is not a
specialized kind of person service.

Character notes and backstory notes expose separate `CharacterNoteService` and
`BackstoryNoteService` APIs from `app/services/character_notes.py`. They compose
a private shared note implementation because their persistence and tag
lifecycles are identical, while their database models, resource types, and
public return models remain distinct. Callers therefore never pass a model
class or resource-type flag into a generic CRUD service.

`SessionNoteService` owns session numbering, note content, tags, and complete
session backup conversion. It composes `RollService` for the roll records stored
under a session. `RollService` separately owns roll validation and statistics,
so session routes do not absorb roll-specific behavior and roll routes do not
reimplement session-note persistence.

`LocationService` and `FactionService` own their resource CRUD, tags,
relationship synchronization, response conversion, and backup conversion.
Both use the same `CampaignContext`, allowing location parentage and faction
bases to resolve through shared campaign-scoped tags without either service
depending directly on the other.

`SearchService` owns campaign-scoped matching queries, resource projections,
field weighting, relevance calculation, filtering, and result ordering. The
search router resolves the `CampaignContext` and delegates the request without
accessing the database directly.

`TagService` is the campaign-scoped component for database-backed tag values,
structured tag reads, relationships, reverse references, search matching,
synchronization, reference refresh, and deletion cleanup. Its mutation methods
use the `stage_*` convention and never commit, allowing resource services to
retain their transaction boundaries. Stateless tag parsing and formatting
remain pure functions in `app/tags`.

Services that participate in larger operations should distinguish between:

- composable `stage_*` methods that flush generated state and apply all domain
  synchronization without committing; and
- standalone methods that coordinate a complete mutation and own its commit,
  rollback, refresh, and authoritative response construction.

Use explicit method names for these two levels rather than a `commit=True`
argument. A coordinating service such as campaign backup calls the composable
methods and owns the encompassing transaction. Normal resource routes call the
standalone methods. Service objects must not be shared across requests because
their database sessions are request-scoped.

These boundaries should eventually be applied consistently to all routers. A
router that is not explicitly listed in the proposed tree is not exempt; it
should be migrated when a focused PR can do so without mixing unrelated domain
changes.

## Backup service composition

Campaign backup is an orchestration feature, not an alternative implementation
of every resource's persistence rules. The backup service should import and call
the services for the models it exports or restores.

For example, restoring a person, location, faction, session, character note, or
inventory should go through the same domain service used by that resource's
normal API routes. The backup service may coordinate ordering, ID remapping,
archive parsing, and one encompassing transaction, but it should not redefine:

- resource creation or update rules
- validation and normalization
- tag and relationship synchronization
- active-character and ownership behavior
- inventory, purse, or item conversion rules
- file lifecycle rules owned by a domain service

For export, each campaign-scoped domain service should expose a collection
operation that selects every in-scope record, applies deterministic ordering,
and returns its backup API models. The backup coordinator should consume those
lists instead of traversing ORM relationships or repeating per-record
conversion. Archive-only work, such as copying images and assigning their
archive paths, remains with the backup coordinator and is supplied to the
relevant domain service when it builds the backup entries.

Domain services may need import-oriented methods that accept a transaction
without committing it. This allows the backup service to compose many resource
operations atomically while keeping the business rules in one place. Those
methods should be real domain operations, not backup-specific copies of route
logic.

## Refactoring sequence

### Refactor track 1: Separate campaign backups and shared dependencies

This should be the first refactoring milestone, but it should be delivered as a
small stack of reviewable pull requests rather than one large movement:

Implementation status: completed. The router split, campaign context, campaign
service, backup service, and composed resource services are now in place.

1. Move shared campaign resolution out of `app/routers/campaigns.py`, replace
   router-to-router imports, and make no other router changes.
2. Extract the minimum reusable domain service operations needed by backup. Do
   this one domain at a time where combining them would create a large diff.
3. Move the two existing backup endpoints to
   `app/routers/campaign_backups.py` without changing their URLs.
4. Move export construction and import restoration into
   `app/services/campaign_backups.py`.
5. Make the backup service compose the domain services for people, locations,
   factions, sessions, characters, notes, tags, and relationships. If one of
   those services does not exist yet, extract its operation first instead of
   copying the implementation into the backup service.
6. Register the backup router separately in `app/main.py`.
7. Add an API model for the campaign response in a separate PR if doing so would
   otherwise obscure the backup extraction.

Non-goals for this refactor track:

- Changing backup schema versions or archive layout
- Changing inventory backup behavior as part of the structural extraction
- Changing campaign CRUD behavior
- Renaming API paths
- Reformatting unrelated router files
- Introducing generic repositories or CRUD base classes

Required verification:

- Existing backup export/import round-trip tests remain green.
- Imported images, tags, relationships, character notes, backstory, sessions,
  and rolls still round-trip.
- Both backup paths remain in the generated OpenAPI schema.
- Campaign-not-found behavior remains identical across routers.
- Each individual diff contains only the service extraction, dependency move,
  or file movement it is intended to accomplish.

### PR 2: Thin campaign and character routers

Implementation status: mostly completed. Campaign CRUD and character domain
operations use services. Character portrait persistence remains in the router
and should be moved in a focused follow-up.

Move campaign CRUD and character profile operations into focused services.
Separate character notes, backstory, image handling, and activation where their
lifecycle or transaction boundaries differ.

This PR should establish a consistent rule: the service that coordinates a
mutation owns its commit and rollback behavior. Routers should not need to know
which database objects must be flushed in which order.

### PR 3: Normalize API response construction

Implementation status: partially completed. Resource services and inventory
return explicit read models, but campaign and deletion responses still include
ad hoc dictionaries.

Replace remaining response dictionaries with explicit API models and named
conversion functions. Keep database-only fields, including canonical copper
values, out of public responses.

Inventory response composition and persistence now live in
`app/services/inventory.py`; the inventory router delegates its aggregate
operations to that service.

### PR 4: Consolidate repeated resource operations

Implementation status: substantially completed. Resource-specific services
remain separate, while genuinely shared tag and personal-note mechanics are
centralized behind explicit components.

Review people, locations, factions, sessions, and character entries for actual
duplication. Extract shared operations only where the resource semantics and
error behavior are genuinely the same.

Avoid a generic CRUD framework that hides resource-specific behavior such as
tag synchronization, reference refreshes, uploaded assets, or cascade rules.

### PR 5: Standardize mutation responses across every router

Implementation status: planned. Inventory is complete and character-note
create/update/delete already update their view locally, but most top-level
resource views still refetch their collection after mutations.

This track is intentionally split into several PRs because it changes backend
response contracts and frontend state handling together.

#### Response contract decision

Return the smallest authoritative state required to update the active view.
Do not return an entire resource collection after every mutation by default.

- Creating a top-level resource returns its complete read model.
- Updating a top-level resource returns its complete refreshed read model.
- Deleting a resource returns a typed response containing `deleted_id`.
- The frontend inserts, replaces, or removes the affected entry locally and
  applies the same ordering as the corresponding GET collection.
- A nested mutation returns the refreshed aggregate when several displayed
  values change together and the aggregate is reasonably small. Inventory is
  the reference implementation.
- When one mutation changes multiple independently useful view models, return a
  typed response envelope containing those models. Roll statistics are the
  clearest example.
- Return a full collection only for a true bulk operation, server-owned
  reordering, or another case where a local deterministic update is unsafe.
- Read-only endpoints that happen to use `POST`, such as search, are outside
  this mutation contract.

Returning a full collection after every write would simplify individual
frontend handlers, but it would add a collection query and an increasingly
large response to each mutation, couple resource endpoints to one list view,
and still would not provide real synchronization between multiple clients.

#### Current mutation inventory

| Domain | Current backend response | Current frontend behavior | Target |
| --- | --- | --- | --- |
| Campaigns | Create/update return an untyped campaign dictionary; delete returns `{"deleted": true}` | Refetches all campaigns | Typed campaign read model; local upsert/remove |
| People | Create/update return `PersonRead`; delete returns `{"deleted": true}` | Refetches all people | Keep resource responses; typed delete; local upsert/remove |
| Locations | Create/update return `LocationRead`; delete returns `{"deleted": true}` | Refetches all locations | Keep resource responses; typed delete; local upsert/remove |
| Factions | Create/update return `FactionRead`; delete returns `{"deleted": true}` | Refetches all factions | Keep resource responses; typed delete; local upsert/remove |
| Sessions | Create/update return `SessionNoteRead`; delete returns `{"deleted": true}` | Refetches all sessions | Keep resource responses; typed delete; local upsert/remove and session-number ordering |
| Character profiles | Most writes return `CharacterRead`; delete returns `{"deleted": true}` | Mostly uses returned state, with some compensating reloads | Typed delete and explicit handling of active-character side effects |
| Character/backstory notes | Create/update return the note; delete returns `{"deleted": true}` | Already inserts/replaces/removes locally | Add typed delete response; retain local updates |
| Rolls | Create returns both session and campaign stats; delete returns `{"deleted": true}` | Refetches both statistics after create and delete | One shared roll-mutation response for both operations; assign returned stats |
| Inventory | Every mutation returns refreshed `InventoryRead` | Replaces the aggregate locally | Complete; retain as reference implementation |
| Backup import | Returns the created campaign dictionary | Refetches campaigns | Return typed campaign read model and locally insert it |

#### Delivery sequence

##### PR 5a: Shared response models and frontend collection utilities

- Add an explicit campaign read model.
- Add a typed deletion response containing `deleted_id`.
- Add small frontend utilities or store operations for upserting, removing, and
  sorting resources by ID, name, or session number.
- Do not change every endpoint in this PR; establish and test the shared
  contracts first.

##### PR 5b: People, locations, and factions

- Preserve their existing create/update read responses.
- Change deletion to the typed deletion response.
- Replace collection refetches with local upsert/remove operations.
- Preserve case-insensitive name ordering after local changes.
- Test relationship/tag fields in returned resources after writes.

##### PR 5c: Sessions and campaigns

- Migrate campaign dictionaries to the campaign read model.
- Use returned campaign and session resources to update frontend stores.
- Replace session and campaign deletion responses with the typed model.
- Preserve campaign ID ordering and descending session-number ordering.
- Decide whether session mutations need a campaign-summary envelope only if the
  active frontend state consumes `session_count` without reloading the
  dashboard.

##### PR 5d: Characters, notes, and backstory

- Move portrait persistence into the character service before changing its
  mutation contracts.
- Remove redundant character reloads where `CharacterRead` is already returned.
- Add typed character and note deletion responses.
- Review create/activate/delete for active-character, campaign-summary, person,
  and inventory-ownership side effects. Return a typed envelope only for state
  the active frontend store must update immediately.
- Keep note and backstory collection updates local.

##### PR 5e: Rolls and inventory

- Rename or generalize the current roll-create response as a roll-mutation
  response containing both session and campaign statistics.
- Return that response from roll deletion as well as creation.
- Replace the two follow-up statistics GETs with direct response assignment.
- Make no inventory response-shape change; verify it remains the aggregate
  reference implementation.

##### PR 5f: Final mutation audit

- Inspect every `POST`, `PUT`, `PATCH`, and `DELETE` endpoint by semantics;
  exclude read-only POST operations.
- Confirm each database mutation returns an explicit API model.
- Confirm services construct responses after flush or commit using the same
  conversion as GET routes.
- Confirm frontend success handlers do not issue compensating GETs for state
  already present in the mutation response.
- Compare OpenAPI paths and intentionally review all changed response schemas.
- Run backend tests and the frontend production build.

#### Per-PR acceptance criteria

- Backend and frontend changes for a resource group land together.
- Create/update tests verify generated IDs, relationships, tags, timestamps,
  summaries, and other refreshed fields as applicable.
- Delete tests save the created ID, delete it, verify the typed response, and
  verify the record no longer exists.
- Frontend tests or focused code assertions verify local upsert/remove behavior
  and the absence of a compensating GET.
- No endpoint returns a full collection unless the PR documents why local state
  replacement is unsafe.

## Transaction and error guidelines

- A mutation should have one visible transaction boundary.
- Files written before a failed database commit must be removed during rollback.
- Existing files should only be deleted after the replacement database state is
  committed successfully.
- Services should raise a small set of application errors where practical.
- Routers or dependencies should translate application errors into HTTP status
  codes.
- Read-after-write response construction must happen within a transaction state
  where generated IDs, relationships, totals, and timestamps are current.
- A resource belonging to another campaign should normally produce the same 404
  response as a missing resource, avoiding cross-campaign information leakage.

## Review guidelines

- One architectural concern per pull request.
- No endpoint redesign during a file-movement refactor.
- No broad formatting pass alongside structural changes.
- Prefer moving code first; improve the moved implementation in a later commit
  or PR.
- Compare generated OpenAPI paths before and after router changes.
- Require focused regression tests for every extracted service.
- For each write endpoint, test that its response contains the refreshed state
  and that the frontend does not need a compensating GET request.

## Future decisions

The following questions should be answered when the relevant feature work makes
them concrete:

- Whether future backup versions need additional inventory authorization or
  configuration fields beyond the inventories, balances, access grants, and
  items already included.
- Whether `/inventory` remains a permanent shortcut for the default campaign
  inventory after multiple inventories are introduced.
- Whether inventory managers and owners require authorization enforcement in
  addition to being represented in the data model.
- Whether service errors need a shared exception hierarchy once more services
  exist.
