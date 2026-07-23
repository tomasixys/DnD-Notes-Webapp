# Backend Refactoring Plan

Status: planned, intentionally deferred from feature pull requests.

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

## Current pressure points

### Campaign backups

`app/routers/campaigns.py` currently owns campaign CRUD as well as backup export,
archive creation, asset collection, backup serialization, archive parsing, ID
remapping, imported asset storage, and restoration of tags and relationships.

Backup behavior is substantial enough to be its own backend feature. Keeping it
inside the campaign CRUD router makes both areas harder to understand and test.

### Shared campaign lookup

Several routers import `verify_campaign` from the campaign router. A router
should not be used as a shared dependency module. This creates unnecessary
coupling and makes import cycles more likely as the application grows.

### Mixed responsibilities

Some route handlers currently perform all of the following:

- HTTP validation and error selection
- database lookup and mutation
- transaction commit or rollback
- file storage operations
- tag and relationship synchronization
- API response construction

The inventory implementation has started separating response composition and
domain conversion from HTTP routing. That is a useful direction, but it should
be applied gradually rather than through a repository-wide rewrite.

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

Prefer request-scoped service classes for resource domains that have several
related database operations. A service instance should receive the SQLModel
session in its constructor and expose domain operations such as resolving,
creating, updating, activating, or synchronizing a resource. Do not create one
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

Domain services may need import-oriented methods that accept a transaction
without committing it. This allows the backup service to compose many resource
operations atomically while keeping the business rules in one place. Those
methods should be real domain operations, not backup-specific copies of route
logic.

## Refactoring sequence

### Refactor track 1: Separate campaign backups and shared dependencies

This should be the first refactoring milestone, but it should be delivered as a
small stack of reviewable pull requests rather than one large movement:

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
- Adding inventory data to campaign backups
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

Move campaign CRUD and character profile operations into focused services.
Separate character notes, backstory, image handling, and activation where their
lifecycle or transaction boundaries differ.

This PR should establish a consistent rule: the service that coordinates a
mutation owns its commit and rollback behavior. Routers should not need to know
which database objects must be flushed in which order.

### PR 3: Normalize API response construction

Replace remaining response dictionaries with explicit API models and named
conversion functions. Keep database-only fields, including canonical copper
values, out of public responses.

Inventory response composition and persistence now live in
`app/services/inventory.py`; the inventory router delegates its aggregate
operations to that service.

### PR 4: Consolidate repeated resource operations

Review people, locations, factions, sessions, and character entries for actual
duplication. Extract shared operations only where the resource semantics and
error behavior are genuinely the same.

Avoid a generic CRUD framework that hides resource-specific behavior such as
tag synchronization, reference refreshes, uploaded assets, or cascade rules.

### PR 5: Standardize mutation responses across every router

Every endpoint that changes database state should return a typed, freshly read
representation that gives the frontend everything affected by the mutation.
The response must be constructed after the mutation has been flushed or
committed, using the same read conversion used by the corresponding GET route.

Apply this contract to campaigns, sessions, people, locations, factions,
characters, notes, backstory, rolls, inventory, and future mutable resources.
The inventory API is the initial example: changing the purse or an item returns
the complete refreshed inventory.

Use the following response rules:

- Creating a top-level resource returns its complete read model.
- Updating a top-level resource returns its complete refreshed read model.
- Mutating a nested resource returns the refreshed aggregate normally displayed
  by the frontend when that aggregate is small, such as an inventory after an
  item or purse mutation.
- When returning an entire aggregate would be excessive, return a typed response
  containing the refreshed resource and any changed summary or parent state.
- Deleting a nested resource returns the refreshed parent aggregate or
  collection required to remove it from the current view.
- Deleting a top-level resource returns a typed deletion response containing its
  identifier and any refreshed parent or collection state the current view
  requires.
- Avoid untyped `{\"deleted\": true}` responses when they force the frontend to
  perform a follow-up fetch to discover the new state.

This is an API behavior change and should not be hidden inside file-movement
refactors. Define the response models and migrate one resource group at a time,
with frontend consumers and route tests updated in the same PR.

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

- Whether campaign backup should include inventories, purse balances, access
  grants, and items in the next backup schema version.
- Whether `/inventory` remains a permanent shortcut for the default campaign
  inventory after multiple inventories are introduced.
- Whether inventory managers and owners require authorization enforcement in
  addition to being represented in the data model.
- Whether service errors need a shared exception hierarchy once more services
  exist.
