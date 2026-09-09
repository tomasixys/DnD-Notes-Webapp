# ADR 0001: Deployment profiles, local identity, bootstrap, and recovery

Status: accepted

Date: 2026-07-23

Updated: 2026-07-25

## Context

DnD Notes currently trusts every caller because it runs as a local desktop
application. The hosted application will run on a private, usually single-node
Linux server and may be reachable from the public internet. The application,
PostgreSQL database, and protected file storage may all live on that server.

The hosted application needs:

- accounts that exist only in the DnD Notes installation;
- password authentication without a third-party identity provider;
- campaign authorization, protected assets, and auditable administration;
- a first-launch method for creating the first system administrator;
- invite-only or administrator-created users during the initial rollout;
- editable operational settings such as the bind address and port; and
- recovery when credentials or application configuration are unavailable.

An editable configuration file must not be able to weaken an initialized
hosted database into unauthenticated local mode. A build artifact or example
config must not contain a default administrator password.

## Decision

### Separate artifact profiles

The build produces artifacts with an embedded `local` or `hosted` profile:

```text
python build.py --profile local --config config/local.toml
python build.py --profile hosted --config config/hosted.toml
```

The supplied config file is validated during the build and distributed as a
config file or template beside the application. The embedded profile is a
security ceiling:

- a local artifact supports only local mode;
- a hosted artifact supports only hosted mode; and
- source development may use an explicit development profile that production
  startup rejects.

The frontend may use safe public profile information to choose its login UI.
Only the backend profile and authorization policy decide whether a request is
allowed.

### Configuration has explicit lifetimes

| Class | Examples | Lifetime |
| --- | --- | --- |
| Build constraint | Allowed profile and supported drivers | Embedded in the artifact |
| First launch | Installation mode and installation ID | Persisted when the database is initialized |
| Runtime | Bind address, port, public origin, database and secret references | Read and validated on every launch |
| Application-managed | Users, password credentials, roles, sessions, invitations | Persisted in the database |

Passwords, session secrets, reset tokens, and invitation tokens are never
embedded in an artifact or stored directly in the distributable configuration
file.

### Installation state is persisted

First launch creates a singleton installation record containing at least:

- a unique installation ID;
- the initialized deployment mode;
- initialization time; and
- a schema/config compatibility version where needed.

The first launch requires:

```text
artifact profile == requested config mode
```

Every later launch requires:

```text
artifact profile == requested config mode == database installation mode
```

A mismatch fails closed. Changing deployment mode is an explicit migration
with a verified backup, not a normal config edit.

Local mode may use SQLite and filesystem storage. Hosted mode uses PostgreSQL
and may use protected filesystem storage on the same server or private object
storage. The storage backend is independent of whether authentication is
enabled.

### Identity behavior depends on the profile

Local mode:

- performs no login flow;
- creates or resolves one internal local user;
- grants that identity the required ownership and administrative capabilities;
  and
- cannot bind the normal application server to a non-loopback address.

Hosted mode:

- authenticates a local DnD Notes username and password;
- stores only a salted password hash produced by a maintained Argon2id
  implementation;
- creates a server-side application session after credential and account-state
  validation;
- never accepts the local internal identity or a development identity; and
- never falls back to open local mode after an authentication failure.

Password hash parameters are versioned and may be upgraded after a successful
login. Passwords, password hashes, session tokens, reset tokens, and invitation
tokens are not written to application logs.

### The first hosted administrator is created through local setup

DnD Notes does not ship or read a default system-admin password. The first
administrator is created using an offline command that requires operating
system access to the server:

```text
dnd-notes create-admin
```

The command:

1. acquires the installation lock and refuses to run beside the hosted service;
2. validates that the selected database belongs to a hosted installation;
3. securely prompts for a username and password without echoing the password;
4. validates the username and password policy;
5. hashes the password using the same application credential service;
6. transactionally creates the user and grants the system-admin role; and
7. refuses to create another bootstrap administrator after an enabled,
   login-capable administrator exists.

Later administrators are added or removed through authenticated and audited
application operations. The system custodian remains a separate
non-interactive user with no credential and no login capability. It receives
ownership only when account deletion would otherwise leave a campaign
ownerless.

### Hosted user creation begins as administrator-controlled

The initial release does not provide public registration.

- A system administrator creates a disabled or activation-pending user and a
  one-time activation token.
- The token is random, expiring, single-use, and stored only as a digest.
- Redeeming it lets the intended user select their local username and password.
- One transaction activates the user, consumes the token, and creates the
  application session.
- Campaign owners may invite an existing user to a campaign. If account
  invitation is later delegated to owners, the same activation-token workflow
  is used.
- Unknown usernames submitted to login never create user records.

An initial implementation may omit email delivery and let the administrator
copy the activation link to the user over a separate channel. Adding
self-service registration later changes admission policy, not the credential
or session model.

### Password recovery begins as an operator-assisted workflow

The first release does not require an email service. A system administrator can
issue a one-time password-reset token, and an operator with server access can
run an offline reset command if no administrator can log in. Resetting a
password revokes the user's existing sessions and is audited.

Security questions, reversible password encryption, disclosure of the existing
password, and recovery through unauthenticated local mode are not supported.

### Recovery is separate from local mode

A hosted installation never automatically falls back to open local mode.
Recovery is an explicit maintenance command that:

- requires operating-system access to the server;
- acquires an exclusive installation lock;
- refuses non-loopback network binding;
- generates an instance-unique, short-lived recovery token if it exposes a UI;
- defaults to read-only inspection or export;
- audits mutations and ownership recovery; and
- cannot run concurrently with the normal hosted service.

For PostgreSQL and filesystem/object-storage deployments, recovery may produce
an offline campaign or disaster-recovery export. Importing that export into a
local installation is a migration, not a mode toggle.

## Consequences

Positive consequences:

- User accounts and credentials remain on the private DnD Notes server.
- The application has no runtime dependency on an external identity provider.
- A config edit cannot disable authentication for an initialized hosted
  database.
- Local desktop use remains simple and does not require an account.
- Invite-only admission controls the initial rollout.
- Runtime port and storage settings remain configurable where safe.

Costs and constraints:

- DnD Notes owns password hashing, authentication throttling, credential
  reset, session revocation, and related security updates.
- The build, startup, and migration systems must understand installation
  profile compatibility.
- Operators need documented first-admin, reset, backup, and recovery
  procedures.
- Separate local and hosted artifacts must be built and tested.
- A hosted-to-local move requires export/import rather than a config change.

## Rejected alternatives

### Managed or social OpenID Connect is required

Rejected because the target installation is self-contained and its accounts
must exist only on the private server. A self-hosted identity provider could be
added later as an optional integration, but it is unnecessary operational
complexity for the first release.

### Config file is the only source of deployment mode

Rejected because changing or mounting the wrong file could expose hosted data
without authentication.

### Shared default administrator credentials

Rejected because a credential in source, a build artifact, or a config file is
likely to be copied and reused. The offline setup command creates an
installation-specific credential instead.

### First successful hosted login becomes administrator

Rejected because scanners or concurrent setup attempts could grant the highest
privilege to the wrong user.

### Hosted mode falls back to local after credential loss

Rejected because an authentication problem must not silently remove the
application's authentication requirement.

### Store passwords with reversible encryption or a fast digest

Rejected because disclosure of the database or encryption key would expose
credentials to inexpensive offline guessing or direct recovery. Passwords use
an adaptive, memory-hard password hash.

## Follow-up work

- [ADR 0002: Campaign roles and capability matrix](0002-campaign-roles-and-capabilities.md)
- [ADR 0003: System administration, deletion, and custody](0003-system-administration-deletion-and-custody.md)
- [ADR 0004: Resource visibility and portable exports](0004-resource-visibility-and-portable-exports.md)
- [Hosted threat model](../security/hosted-threat-model.md)

Milestone 1 establishes the deployment and persistence foundation. Milestone 2
implements password credentials, sessions, activation, throttling, and
operator-assisted recovery.

## References

- [OWASP Password Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)
- [OWASP Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)
- [RFC 9106: Argon2 Memory-Hard Function](https://www.rfc-editor.org/rfc/rfc9106.html)
- [MITRE CWE-1393: Use of Default Password](https://cwe.mitre.org/data/definitions/1393.html)
