# ADR 0003: System administration, deletion, and custody

Status: accepted

Date: 2026-07-23

## Context

DnD Notes needs a root-level administrative capability for support and
recovery, including access to every campaign. At the same time, ordinary
campaign requests should remain membership-scoped, and a human administrator
should not become the permanent database owner of every campaign whose owner
deletes their account.

Account and campaign deletion must not cause accidental loss. Future private
resources also need a defined outcome when their owning account is deleted.

## Decision

### System admin is a server role

`system_admin` is an application-wide role on a login-capable user. It is
separate from the `owner`, `member`, and `viewer` campaign roles.

- A system admin can access and recover every campaign.
- Admin status is granted only through initial bootstrap or an authenticated,
  audited admin operation.
- The application prevents removal, suspension, or deletion of the last
  enabled login-capable system admin unless an offline recovery administrator
  has first been established.
- There is no default root password.
- The non-interactive system custodian is not a system admin and cannot log in.

### Elevation is explicit

A system admin's normal application view uses ordinary membership rules. It
does not automatically list or preload every campaign.

Access outside normal membership uses a dedicated admin operation or an
explicit elevated campaign context. Elevated operations:

- require a current system-admin role;
- require a short reason for destructive, export, identity, or private-data
  operations;
- never create an ordinary campaign membership as a side effect;
- are authorized again on every request;
- are recorded whether they succeed or fail; and
- cannot be enabled through a client-supplied user ID or role claim.

Admin routes live under an explicit administrative API/UI boundary. A normal
campaign route may use an elevated context only when the server established
that context through the admin workflow.

### Security audit events

Security audit events are append-only application records. At minimum they
contain:

- event ID and timestamp;
- actor user ID and current session reference where useful;
- action type;
- campaign and target type/ID where applicable;
- whether access used membership or system-admin elevation;
- operator-supplied reason where required;
- request correlation ID;
- outcome and safe error category; and
- safe request metadata needed for investigation.

They do not contain passwords, password hashes, raw cookies, session tokens,
invitation/reset/recovery tokens, secrets, backup contents, or private note
bodies.

Events are required for:

- admin elevation, including reads of campaigns without membership;
- private/restricted resource access by an admin;
- campaign export or operational recovery export;
- invitations, role changes, member removal, and ownership changes;
- user activation, password reset, suspension, restoration, or deletion;
- campaign soft deletion, restoration, and permanent purge;
- custodian assignment and orphan recovery;
- session revocation and global logout; and
- recovery-mode entry and mutation.

Normal domain edit history is a separate future feature; the security audit log
does not need to duplicate every note edit.

### Multiple owners and the last-owner invariant

A campaign may have multiple human owners.

Normal operations cannot leave a campaign without either:

- at least one enabled human owner; or
- one custodial owner membership plus an `orphaned` campaign state.

An owner who is the last enabled human owner must promote another member before
leaving or voluntarily removing their owner role. Account deletion is the
exception: it invokes custodial transfer atomically so deletion cannot destroy
or strand the campaign.

### System custodian

The installation owns one seeded system-custodian user:

- it has no password credential;
- `can_login` is false;
- it does not receive sessions;
- it is hidden from the ordinary member directory;
- its owner membership is marked custodial; and
- it is used only when a campaign or protected resource would otherwise become
  ownerless.

Custodial ownership is a preservation state, not a person and not a general
authorization bypass.

When an admin assigns a new human owner to an orphaned campaign, one transaction
adds the human owner, removes the custodial campaign membership, clears the
orphaned state, and records the recovery event.

### Account suspension

Suspension is reversible and preferred while ownership or account questions
are being resolved.

Suspending a user:

- prevents new application sessions;
- revokes all existing application sessions;
- retains the disabled credential, memberships, content ownership, and audit
  references;
- does not transfer campaign ownership; and
- is audited.

Other campaign owners may continue administering the campaign. A campaign
whose only human owner is suspended is flagged for admin attention but is not
automatically transferred until deletion or an explicit recovery decision.

### Account deletion

Deletion is a coordinated, transactional workflow rather than direct row
deletion.

Before mutation, the application calculates all affected:

- sessions, password credentials, and account tokens;
- campaign memberships and invitations;
- character assignments;
- solely owned campaigns;
- shared authored records; and
- private/restricted records and grants.

The workflow:

1. requires recent authentication for self-service deletion or explicit
   elevated admin authority;
2. revokes all sessions;
3. disables the password credential and replaces the public username with an
   internal tombstone outside the valid username namespace;
4. revokes unaccepted invitations issued by that account;
5. removes viewer/member memberships and unassigns their characters;
6. removes owner memberships where another enabled human owner remains;
7. adds the custodian and marks the campaign orphaned before removing a sole
   human owner;
8. retains shared campaign records, with authorship pointing to a tombstoned or
   anonymized user as policy permits;
9. transfers private/restricted ownership to the custodian and quarantines it
   from ordinary campaign access pending recovery or purge;
10. marks the user deleted/tombstoned; and
11. records one encompassing event plus campaign-specific custody events.

The initial hosted release preserves data. Legal erasure requirements,
retention periods, and irreversible private-content deletion require a separate
policy before broader public availability.

A deleted account is never reactivated implicitly. A later invitation may use
the former public username, but activation creates a distinct user ID and does
not inherit the deleted account's memberships, private access, or authorship.

### Campaign deletion

Owner-initiated campaign deletion is recoverable:

- require recent authentication and explicit confirmation;
- mark the campaign soft-deleted;
- revoke normal member access and invitations;
- retain database records and protected assets for a configured recovery
  period; and
- allow restoration by an owner or elevated system admin during that period.

Permanent purge is a separate owner/admin operation after the recovery period,
or an explicit immediate purge requiring stronger confirmation. Purge removes
database records and owned assets using the existing transaction/file-cleanup
rules and emits an audit event.

Soft-deleted campaigns do not appear in normal campaign lists, search, asset
access, or exports.

### Lost credential and account restoration

If a user loses their password:

- a system admin may issue an expiring, single-use password-reset token;
- if no administrator can log in, a deployment operator may run the exclusive
  offline password-reset command;
- completing a reset revokes every existing session for the user; and
- a matching display name or email never automatically merges accounts.

Restoring a deleted account is a separate, audited admin operation. The precise
human-verification procedure is operational policy, not an API inference.

## Consequences

- Campaigns survive owner deletion without making a human root account their
  permanent owner.
- Multiple owners reduce the need for administrator intervention.
- Admin access remains available but visible in the audit trail.
- Suspension provides a safe intermediate response before deletion.
- Account and campaign deletion require state machines and recovery UI rather
  than simple `DELETE` statements.
- Tombstones and custody records add retention and privacy-policy work.
- Permanent purge requires database and object-storage lifecycle coordination.

## Rejected alternatives

### Transfer orphaned campaigns directly to a human root user

Rejected because deployments may have multiple or changing administrators, a
human account may itself be deleted, and routine ownership would blur
administrative recovery with campaign membership.

### Admin automatically belongs to every campaign

Rejected because it leaks every campaign into normal lists and weakens the
distinction between collaboration and elevated support access.

### Hard-delete users immediately

Rejected because memberships, authored content, audit history, invitations,
private resources, credential tombstones, and account restoration all require
coordinated handling.

### Delete a campaign immediately with all files

Rejected for hosted mode because accidental deletion would require an
infrastructure restore and affect every collaborator.
