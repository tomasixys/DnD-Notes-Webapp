# ADR 0004: Resource visibility and portable exports

Status: accepted

Date: 2026-07-23

## Context

The first hosted release will share current campaign content across the
campaign. Later releases need private and explicitly shared records, especially
for character notes and backstory. The first release should preserve a clean
path to those restrictions without prematurely building a field-level ACL
system.

Campaign exports currently round-trip the complete campaign. Once some records
are hidden, an owner-initiated downloadable export must not disclose records
that owner cannot read.

## Decision

### Campaign role is the permission ceiling

Authorization composes two policies:

```text
effective access = campaign role capability intersect resource access policy
```

- Campaign membership is always required, except for explicit audited
  system-admin elevation.
- Resource policy can remove access granted by a campaign role.
- Resource policy cannot grant a capability above the campaign role.
- A `viewer` remains read-only even if a future resource grant contains
  `write`.
- A campaign `owner` does not automatically read another user's private or
  restricted resource.
- An elevated system admin can access any resource, and the access is audited.

### Visibility values

Protectable resources support:

- `campaign`: every current campaign member may read; member/owner mutation
  follows ADR 0002;
- `private`: only the resource access owner may read or mutate, subject to
  campaign membership and role ceiling; and
- `restricted`: the resource access owner plus explicit user grants may read or
  mutate, subject to campaign membership and role ceiling.

The first collaborative release uses `campaign` visibility for all current
data. The first restricted implementation targets character notes and
backstory before expanding to other resource types.

### Creator, access owner, and grants are distinct

Protectable resources conceptually record:

- `created_by_user_id`: provenance, not an authorization decision;
- `visibility`;
- `access_owner_user_id`: the user who controls private/restricted access; and
- normalized grants for explicitly shared restricted records.

A grant identifies an access policy/resource, a user, and `read` or `write`
permission. User IDs are not stored as JSON arrays, delimited text, or other
multi-value resource columns.

Implementation may use resource-specific grant tables or a normalized reusable
access-policy table, provided that it preserves:

- referential integrity;
- indexed user/resource lookups;
- uniqueness of one effective grant per user;
- cascading or transactional cleanup;
- campaign consistency between resource, policy, and grantee; and
- one centralized policy-evaluation interface for domain services.

`created_by_user_id` may remain a tombstone/anonymized reference after account
deletion. `access_owner_user_id` participates in the custodial transfer rules
from ADR 0003.

### Policy changes

- The access owner may change visibility and manage grants if their campaign
  role permits mutation of that resource.
- An assigned character controller may own and manage their character's
  private/restricted notes.
- Campaign owners administer campaign-wide resources but cannot grant
  themselves access to another user's private data.
- System admins may recover or change resource policy only through an elevated,
  reason-bearing, audited operation.
- Removing a user's campaign membership immediately makes all grants in that
  campaign ineffective. The grants may be removed transactionally or retained
  only as inactive audit/recovery state.
- Transferring access ownership is explicit and audited.

Existing records default to `campaign`. Import and migration never infer
private ownership merely from the old global active-character field.

### No indirect disclosure

Resource policy applies to every path by which information can be inferred:

- direct get/list operations;
- search matches, snippets, filters, and result counts;
- tags, reverse references, and relationships;
- rollups, statistics, dashboard counts, and “recent” lists;
- character and inventory aggregates;
- uploaded assets and signed download URLs;
- change feeds and synchronization events;
- downloadable exports; and
- validation/error messages.

When a related target is not visible, the API omits the relationship or returns
the same result as a missing target. It does not reveal a title, type, owner,
count, or “private item exists” placeholder.

Free-form text that an authorized user can read is not automatically redacted
merely because it mentions another resource. Structured references and
metadata are filtered.

### Downloadable campaign exports

Before restricted resources exist:

- only a campaign owner or elevated system admin may request an export;
- the owner export contains the complete campaign because all records are
  campaign-visible; and
- accounts, memberships, invitations, sessions, audit events, server roles,
  and password credential data are excluded.

After restricted resources exist:

- the ordinary campaign export remains owner-initiated;
- records are filtered by the requesting owner's effective read access;
- private records belonging to another member are excluded;
- restricted records without a read grant for the requester are excluded;
- assets are included only when their owning resource is included;
- structured relationships, tags, and references to excluded records are
  omitted or rewritten according to the versioned backup schema; and
- aggregate values are recalculated from included records where needed.

The export manifest records that it is access-filtered and identifies the
backup schema version. It does not include the source user's server identity.

### Import semantics

Import always creates a new campaign and makes the importing user its owner.
It never restores source-server users, memberships, invitations, system roles,
sessions, or audit events.

For included records:

- `campaign` remains `campaign`;
- requester-owned `private` becomes `private` and is owned by the importer;
- `restricted` becomes `private` and is owned by the importer unless a future
  portable principal/grant format is explicitly versioned; and
- creator provenance that cannot be safely mapped becomes absent or an
  archive-local display attribution, never an application user ID.

This least-privilege normalization prevents an imported archive from granting
access to unrelated users who happen to have matching IDs or email addresses.

Older backup schemas without visibility metadata import all records as
`campaign`, preserving their original single-user semantics.

### Operational disaster-recovery backups

Infrastructure backups are separate from user-downloadable campaign exports.
They may contain the complete encrypted database and private object storage,
including records no campaign owner can read.

Operational backups:

- are accessible only through deployment/maintenance authorization;
- are encrypted and retention-controlled;
- are never served from a campaign asset URL;
- do not use the requesting campaign owner's visibility filter; and
- require audited recovery procedures for restore or content extraction.

An elevated admin export of all campaign content is a recovery operation, not
an ordinary owner export.

## Consequences

- Initial collaboration remains campaign-wide and simple.
- Adding privacy later does not require changing campaign roles.
- Every query/aggregate service must accept the same resource-access policy.
- Search, tags, backups, and assets require explicit privacy regression tests.
- Export round-tripping becomes conditional once hidden records exist.
- Restricted grants are portable only after a deliberate cross-installation
  identity design; initial imports safely reduce them to importer-private.
- Campaign owners cannot use backup export to bypass member privacy.

## Rejected alternatives

### Store allowed user IDs in one resource field

Rejected because arrays/JSON/delimited IDs make foreign keys, uniqueness,
revocation, indexing, campaign validation, and cascades difficult to enforce.

### Campaign owner always overrides resource privacy

Rejected because backup and administrative ownership should not silently
disclose member-private content.

### Export the full campaign regardless of requester access

Rejected because downloadable backups would become a privacy bypass as soon as
restricted records exist.

### Restore grants by matching email addresses

Rejected because email is not a stable cross-installation identity key and the
archive must not grant access accidentally.
