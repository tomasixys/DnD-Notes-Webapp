# ADR 0002: Campaign roles and capability matrix

Status: accepted

Date: 2026-07-23

## Context

Hosted DnD Notes needs campaign authorization that is small enough to reason
about and complete enough to classify every current API operation. The chosen
campaign roles are `owner`, `member`, and `viewer`.

Campaign roles are application security roles. They are separate from
game-domain concepts such as:

- a character being active for a player;
- a character owning or managing an inventory; and
- a person, faction, or location owning one side of a tag relationship.

Possessing a resource ID, being an inventory owner, or controlling a character
never grants campaign membership.

## Decision

### Roles

- **Owner:** collaborates on shared resources and administers the campaign,
  membership, character assignments, campaign assets, backups, and deletion.
- **Member:** reads and edits campaign-wide shared resources and manages the
  character assigned to their membership.
- **Viewer:** reads campaign-wide shared resources but cannot mutate them.

A campaign may have multiple owners. The last-human-owner and system-custodian
rules are defined in ADR 0003.

Roles are scoped to one campaign. A viewer in one campaign may create a new
campaign and become its owner. Being a system admin is a separate server role,
not a fourth campaign membership role.

### Capabilities, not role comparisons

Authorization code checks named capabilities rather than comparing role
strings or relying on a numeric role order.

Initial campaign capabilities:

- `campaign.read`
- `campaign.update`
- `campaign.delete`
- `campaign.export`
- `membership.read`
- `membership.manage`
- `character.assign`
- `character.self_create`
- `shared_resource.read`
- `shared_resource.write`
- `assigned_character.write`

The centralized policy maps roles to capabilities:

| Capability | Viewer | Member | Owner |
| --- | :---: | :---: | :---: |
| `campaign.read` | Yes | Yes | Yes |
| `campaign.update` | No | No | Yes |
| `campaign.delete` | No | No | Yes |
| `campaign.export` | No | No | Yes |
| `membership.read` | Yes | Yes | Yes |
| `membership.manage` | No | No | Yes |
| `character.assign` | No | No | Yes |
| `character.self_create` | No | Yes | Yes |
| `shared_resource.read` | Yes | Yes | Yes |
| `shared_resource.write` | No | Yes | Yes |
| `assigned_character.write` | No | Yes | Yes |

The viewer role is an edit ceiling. A future resource grant cannot give a
viewer write access without also changing the campaign role.

### Account-level operations

These operations are not governed by a role in an existing campaign:

| Operation | Anonymous | Enabled hosted user | System admin |
| --- | :---: | :---: | :---: |
| Complete an invited first login | With valid invitation | Not applicable | Bootstrap rule or invitation |
| Log in as a known identity | No | Yes | Yes |
| Read/update own account profile | No | Yes | Yes |
| Manage own sessions | No | Yes | Yes |
| Create a new campaign | No | Yes; becomes owner | Yes; becomes owner |
| Import a backup as a new campaign | No | Yes; becomes owner | Yes; becomes owner |
| List campaigns | No | Memberships only | Memberships by default; elevated admin listing is separate |

Backup import currently creates a new campaign. It is therefore a
campaign-creation operation, not permission to mutate an existing campaign.
Any enabled user may import and becomes owner of the new campaign. A future
restore-over-existing operation requires `campaign.update` and
`campaign.export`-equivalent owner authority.

### Campaign administration

| Operation | Viewer | Member | Owner |
| --- | :---: | :---: | :---: |
| Read campaign summary | Yes | Yes | Yes |
| Change name, description, or player-character summary | No | No | Yes |
| Replace/delete campaign image or banner | No | No | Yes |
| Read member display names and roles | Yes | Yes | Yes |
| Read pending invitation addresses | No | No | Yes |
| Invite, revoke invite, or resend invite | No | No | Yes |
| Change a membership role | No | No | Yes |
| Assign/unassign a member's character | No | No | Yes |
| Remove another member | No | No | Yes |
| Leave campaign | Yes | Yes | Yes, subject to last-owner rule |
| Export downloadable campaign backup | No | No | Yes |
| Delete campaign | No | No | Yes |

Owners may promote another member to owner. An owner cannot demote/remove the
last human owner through the normal membership API.

Member-directory responses expose the minimum useful profile. Invitation
emails, password credential data, session information, and account
administration state are owner/admin data, not campaign-directory data.

### Shared campaign resources

The first collaborative release treats these current resource domains as
campaign-wide shared data:

- sessions and session rolls;
- people;
- locations;
- factions;
- tags and relationships;
- inventory metadata, purse, and items;
- campaign statistics; and
- search results derived from shared records.

| Operation | Viewer | Member | Owner |
| --- | :---: | :---: | :---: |
| List/get shared resource | Yes | Yes | Yes |
| Search shared resources | Yes | Yes | Yes |
| Read roll statistics | Yes | Yes | Yes |
| Create shared resource | No | Yes | Yes |
| Update shared resource | No | Yes | Yes |
| Delete shared resource | No | Yes | Yes |
| Create a roll | No | Yes | Yes |
| Delete a session's rolls | No | Yes | Yes |
| Change inventory metadata or purse | No | Yes | Yes |
| Create/update/delete inventory item | No | Yes | Yes |

HTTP method does not determine the capability. In particular,
`POST /api/campaigns/{campaign_id}/search` is a read operation and requires
`shared_resource.read`, not `shared_resource.write`.

Inventory `owner` and `manager` values continue to describe characters in the
game domain. In the campaign-wide phase, they do not restrict application-user
inventory access.

### Characters

Each membership may have at most one assigned character in the first hosted
release. One character may be assigned to at most one active membership at a
time. Owners may leave characters unassigned.

Character summary/profile information is campaign-visible during the initial
sharing phase. Mutation rules are:

| Operation | Viewer | Member | Owner |
| --- | :---: | :---: | :---: |
| Read shared character profile/portrait | Yes | Yes | Yes |
| Read campaign-visible notes/backstory | Yes | Yes | Yes |
| Select own assigned character as active | No | Yes | Yes |
| Update own assigned profile/portrait | No | Yes | Yes |
| Create/update/delete notes for assigned character | No | Yes | Yes |
| Create/update/delete backstory for assigned character | No | Yes | Yes |
| Create character profile | No | If unassigned; create-and-assign own | Yes |
| Update any shared character profile | No | Assigned only | Yes |
| Delete character profile | No | Assigned only | Yes |
| Assign/reassign character to membership | No | No | Yes |

The current global `Campaign.active_character_person_id` becomes
membership-specific state. Character assignment and active selection are
distinct:

- assignment is an owner-controlled authorization/domain association; and
- active selection is a member preference limited to a character assigned to
  that membership.

Member self-creation is atomic and allowed only when the membership has no
assigned character. It creates a new Person plus profile and assigns that
profile to the caller; it cannot convert or claim an existing campaign Person.
Deleting one's assigned profile clears the assignment but preserves the
underlying Person according to the current domain behavior.

Once private records exist, deleting a character container must not cascade
records the actor cannot access. The operation must transfer/quarantine those
records or require explicit elevated recovery authority.

If multiple characters per user becomes necessary later, assignment can move
to a normalized controller table without changing the role capabilities.

Private and restricted character records later add a resource policy below
this campaign-role ceiling. ADR 0004 defines that composition. Campaign
ownership alone will not grant access to another user's private records.

### Assets and downloads

| Operation | Viewer | Member | Owner |
| --- | :---: | :---: | :---: |
| Read campaign-visible image/portrait | Yes | Yes | Yes |
| Replace/delete campaign image/banner | No | No | Yes |
| Replace/delete assigned character portrait | No | Yes | Yes |
| Replace/delete another character portrait | No | No | Yes |
| Download user-facing campaign export | No | No | Yes |

Every asset request also evaluates the visibility of its owning resource.
Knowing an upload path is never a capability.

### System-admin behavior

System admins do not receive automatic campaign memberships. Normal campaign
requests use their actual membership, if any. Administrative access uses an
explicit elevated context that:

- grants the capabilities needed for the named admin operation;
- is recorded in the security audit log;
- does not silently add the admin to the campaign; and
- does not make admin-only campaigns appear in the normal campaign list.

ADR 0003 defines elevation, recovery, deletion, and audit requirements.

### Denial behavior

- Anonymous request to a protected API: `401 Unauthorized`.
- Authenticated non-member request for a campaign or nested resource:
  `404 Not Found`.
- Member request for an existing campaign action outside their capability:
  `403 Forbidden`.
- Member request for a hidden private/restricted resource: `404 Not Found`.
- Stale allowed mutation after concurrency controls exist: `409 Conflict`.

Input validation must happen after the required authentication and campaign
boundary are established when earlier validation could reveal resource
existence.

## Current API classification

This maps the current router surface to the capabilities above. Future routes
must add a classification before registration.

| Current route group | Read capability | Mutation capability |
| --- | --- | --- |
| `GET /api/campaigns` | Authenticated account; membership-filtered list | Not applicable |
| `GET /api/campaigns/{id}` | `campaign.read` | Not applicable |
| `POST /api/campaigns` | Enabled account; creator becomes owner | Not applicable |
| `PUT/DELETE /api/campaigns/{id}` | Not applicable | `campaign.update` / `campaign.delete` |
| `GET /api/campaigns/{id}/backup/export` | Not applicable | `campaign.export` |
| `POST /api/campaigns/backup/import` | Enabled account; importer becomes owner | Not applicable |
| Session CRUD | `shared_resource.read` | `shared_resource.write` |
| People CRUD | `shared_resource.read` | `shared_resource.write` |
| Location CRUD | `shared_resource.read` | `shared_resource.write` |
| Faction CRUD | `shared_resource.read` | `shared_resource.write` |
| Roll statistics/create/delete | `shared_resource.read` | `shared_resource.write` |
| Search `POST` | `shared_resource.read` | Not applicable |
| Inventory get/patch/item CRUD | `shared_resource.read` | `shared_resource.write` |
| Character get/list notes/backstory | `shared_resource.read` plus resource visibility | Not applicable |
| Character profile/portrait/note/backstory mutation | Not applicable | `assigned_character.write` or owner |
| Character self-create | Not applicable | `character.self_create` with unassigned-membership rule |
| Character assignment/reassignment | Not applicable | `character.assign` |
| Protected asset get | Owning resource read policy | Not applicable |

## Consequences

- Shared campaign collaboration stays simple.
- Campaign administration remains owner-only.
- Character control has an explicit server-side association instead of trusting
  a path parameter or client-supplied user ID.
- Viewer support adds policy-matrix tests but not a different architecture.
- Services need an authorized campaign context and named capability checks.
- Route registration needs a test or declaration that detects unclassified API
  routes.
- Future privacy rules restrict the result of campaign capabilities; they do
  not grant permissions beyond the campaign-role ceiling.

## Rejected alternatives

### Owner and member may both administer the campaign

Rejected because membership, backup, campaign deletion, and campaign settings
are the meaningful distinction requested between these roles.

### HTTP verbs directly determine authorization

Rejected because search uses `POST` for a read, imports create a new campaign,
and character mutations require assignment-aware policy.

### Inventory ownership grants application access

Rejected because inventory access currently belongs to fictional character
state, not authenticated users.

### Owners automatically read every future private resource

Rejected because campaign administration and resource privacy are separate
policies. System-admin recovery remains explicitly elevated and audited.
