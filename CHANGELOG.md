# Changelog

All notable changes to DnD Notes are documented in this file.

The project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html),
and this changelog follows the structure described by
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- Added strict TOML launch configuration with local and hosted deployment
  validation, safe discovery, and documented example files.
- Added a persisted installation identity and immutable deployment mode;
  administrator credentials remain application-managed rather than config.
- Added embedded local/hosted build profiles, build-time config validation,
  mode-specific artifact names, and packaged executable-specific config files.
- Added explicit Windows/Linux build-target detection, platform-specific build
  environments and artifact names, and clear rejection of cross-compilation.
- Added the initial local-account persistence model for users, password
  credentials, revocable server sessions, and activation/reset tokens.
- Added Argon2id password hashing with automatic parameter upgrades, a
  15-character single-factor password policy, and lock-protected offline
  first-administrator and password-reset commands.
- Added local login/session foundations with generic credential failures,
  bounded account lockout, digest-backed revocable session and CSRF tokens,
  idle/absolute expiry, and secure host-only cookie responses.
- Enabled hosted startup with mounted authentication endpoints, complete
  session/CSRF protection for hosted API and upload paths, and a non-login
  internal identity for local mode.
- Added administrator-issued activation and password-reset tokens, invite-only
  account creation, account tombstoning, keyed source login throttling, and
  persistent security events.
- Added typed SQLite/PostgreSQL database URL and pool settings with
  environment-referenced hosted credentials.
- Added an Alembic current-schema baseline for SQLite and PostgreSQL, a legacy
  SQLite adoption bridge, and disposable-schema PostgreSQL CI coverage.
- Added trusted host/proxy, secure cookie, runtime secret, filesystem, and
  object-storage configuration validation.
- Allowed authenticated network deployments to use an explicit durable server
  filesystem path by default instead of requiring remote object storage.
- Added an exclusive instance lock and a separate offline inspection and
  filesystem campaign-export command.
- Added campaign memberships with owner, member, and viewer roles, centralized
  named capabilities, membership-filtered campaign access, and per-member
  character assignment and active-character state.
- Added last-owner protection, atomic account-deletion transfer to a non-login
  system custodian, orphan recovery, and explicitly reasoned and audited system
  administrator elevation.
- Added startup route auditing so application API routes cannot be registered
  without an authentication or campaign-authorization classification.
- Added an authenticated frontend shell with session bootstrap, hosted login
  and account flows, CSRF-aware API requests, protected routes, centralized
  authorization failures, and user-scoped campaign browser state.
- Added capability-aware campaign, shared-resource, and assigned-character
  controls for owner, member, and viewer memberships.
- Added authorized campaign-image and character-portrait delivery without a
  public uploads mount, using existing database ownership relationships.
- Added byte-decoded image validation with MIME, extension, filename, size,
  pixel, and animation limits, including validation of restored backup images.
- Changed campaign backup export to a direct authorized download whose
  temporary archive is deleted after transfer and expired after interruption.
- Added backup upload, archive-member, expansion, link, duplicate-path, and
  manifest limits.
- Added digest-backed campaign invitations for existing active or
  activation-pending accounts, with replacement, revocation, expiry,
  exact-account redemption, source throttling, and atomic membership creation.
- Added campaign membership and pending-invitation screens, administrator
  account-invitation controls, role changes, member removal and leaving, and
  explicit ownership transfer.
- Added action-specific security audit records for campaign invitations,
  membership role/removal changes, ownership transfer, and campaign deletion.
- Added campaign, restricted, and private visibility for character notes and
  backstory, with distinct creator/access-owner metadata and normalized
  read/write grants for campaign users.
- Added centralized resource policy enforcement across direct note access,
  lists, search, tag references, result counts, and frontend controls.
- Added relationship metadata to tag assignments in preparation for moving
  dedicated entry relationships into the tag system.
- Marked every tag entered through a Tags field as `associated_with`, while
  keeping relationship meaning out of tag-chip labels.
- Replaced person faction/location, location parent, and faction location text
  storage with typed tag relationships.
- Added derived people lists to locations and member lists to factions, with
  links back to the related person entries.
- Added private character profiles backed by People entries, including active
  character selection, portraits, personal notes, and backstory entries.
- Added a default party inventory with editable metadata, item quantities,
  categories, rarities, values, and campaign wealth totals.
- Added a purse with copper, silver, electrum, gold, and platinum balances.
- Added inventory ownership metadata tied to campaign characters.

### Changed

- Changed downloadable campaign exports to exclude private or restricted
  character entries the requesting owner cannot read; imported private data is
  re-owned by the importer without restoring source-server user identifiers.
- Kept offline maintenance exports explicitly elevated and complete rather than
  applying the ordinary user-download privacy filter.
- Isolated identity models, password handling, login, browser sessions,
  authentication dependencies, and account administration in a dedicated
  backend authentication domain.
- Renamed the played-game backend domain from session notes to episodes while
  preserving existing database, HTTP, tag, roll, and backup contracts.
- Split tag parsing, reference resolution, assignments, and read queries into
  focused modules behind a small compatibility facade.
- Consolidated the unreleased database changes into one version 1 to version 2
  migration instead of retaining development-only intermediate versions.
- Organized database migrations as versioned modules with a registry-driven
  runner and an idempotent hook for temporary development migrations.
- Updated campaign backups and search to preserve and understand the new
  relationship-backed fields.
- Migrated existing relationship text values into typed tag assignments while
  retaining unresolved and ambiguous references, then removed the obsolete
  database columns.
- Promoted the character and shared-note schema into the version 2 to version 3
  database migration and restored the development migration hook to a no-op.
- Added the version 3 to version 4 database migration for inventories, access
  grants, purses, currency balances, and items.
- Updated campaign backup import and export to preserve inventory contents,
  balances, and access grants.
- Moved campaign-scoped backend operations into focused services with explicit
  transaction ownership while preserving existing API paths.
- Standardized mutation and deletion responses with explicit API models.
- Updated frontend mutation handling to apply authoritative response data
  locally instead of immediately fetching the same resource again.

### Fixed

- Resolved reference tags now follow renamed resources, update their displayed
  labels, and merge aliases without losing existing tag assignments.
- Person details now refresh immediately after editing, and refreshing a
  resource URL no longer redirects away while its persisted campaign is valid.
- Added campaign search filters and direct results for character notes and
  backstory entries, including entries belonging to former characters.
- Made frontend API failures expose consistent `error` and `message` values,
  including validation failures.
- Made invalid backup imports return a consistent client error without leaving
  a partially created campaign.
- Corrected location deletion to send the selected location ID.

## [0.2.0] - 2026-07-18

### Added

- Added campaign-wide search across sessions, people, locations, and factions.
- Added relevance-ranked search results and a search store that retains the
  latest results while navigating through the application.
- Added URL-based entry selection, allowing individual resources to be opened
  and linked directly by ID.
- Added shared campaign tag definitions and resource tag subscriptions.
- Added typed reference tags for sessions, people, locations, and factions.
- Added passive, resolved, unresolved, and ambiguous tag states.
- Added clickable reference tags that navigate to the linked resource.
- Added structured tag response DTOs while retaining simple string-based tag
  input for create and edit forms.
- Added versioned SQLite migrations, including a pre-migration database backup
  and conversion of legacy JSON tags into passive shared tags.
- Added backend tests for tag parsing, subscriptions, reference resolution,
  deletion handling, migration, API responses, and tag search.

### Changed

- Reworked the application header into a compact navigation bar with the
  selected campaign name as the primary campaign link.
- Moved campaign search into the main navigation and reduced space occupied by
  banner and page-title sections.
- Removed the enlarged dashboard banner and renamed the page to Campaign
  Dashboard, leaving more room for campaign information.
- Made resource page headings more compact and kept title and description on a
  single line where space permits.
- Updated dashboard, resource, roll, and search views to use the denser visual
  design.
- Hid resource-list scrollbars while retaining scrolling behavior.
- Stabilized the page scrollbar gutter so navigation and header elements no
  longer shift between short and long views.
- Updated campaign backup and import handling to work with shared tags.
- Updated campaign search to include the displayed values of assigned tags.
- Typed tag prefixes such as `faction:` and `location:` are now treated as
  input syntax and reference metadata rather than part of the displayed label.

### Fixed

- Redirected users to the Campaign Dashboard when no campaign is selected.
- Corrected session navigation to use database IDs consistently.
- Ensured deleting a referenced resource leaves subscribed tags unresolved
  instead of pointing to a missing entry.

## [0.1.0] - 2026-07-10

### Added

- Added the initial Vue and FastAPI campaign-notes application.
- Added campaign creation, selection, editing, and deletion.
- Added campaign dashboards with campaign descriptions, player-character
  information, images, and banners.
- Added campaign-scoped session notes, people, locations, and factions.
- Added session roll tracking and campaign roll statistics.
- Added image uploads with stable application-data storage and image cleanup.
- Added campaign backup and restore through ZIP archives containing JSON data
  and campaign images.
- Added reusable popup and confirmation components for destructive actions.
- Added SQLite relationships, foreign-key enforcement, cascade deletion, and
  cleanup of campaign-owned records.
- Added a production setup in which FastAPI serves the compiled web frontend.
- Added PyInstaller support for building DnD Notes as a standalone
  application.

### Changed

- Moved persistent databases, uploads, and generated files into the operating
  system's application-data directory.
- Connected the frontend resource views to the backend API.
- Added TypeScript DTOs for data exchanged between the frontend and backend.
- Improved resource actions and button styling across the application.

[Unreleased]: https://github.com/tomasixys/DnD-Notes-Webapp/compare/dndnotes/v0.2.0...HEAD
[0.2.0]: https://github.com/tomasixys/DnD-Notes-Webapp/compare/dndnotes/v0.1.0...dndnotes/v0.2.0
[0.1.0]: https://github.com/tomasixys/DnD-Notes-Webapp/releases/tag/dndnotes/v0.1.0
