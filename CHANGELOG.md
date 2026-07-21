# Changelog

All notable changes to Campaign Notes are documented in this file.

The project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html),
and this changelog follows the structure described by
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- Added relationship metadata to tag assignments in preparation for moving
  dedicated entry relationships into the tag system.
- Marked every tag entered through a Tags field as `associated_with`, while
  keeping relationship meaning out of tag-chip labels.
- Replaced person faction/location, location parent, and faction location text
  storage with typed tag relationships.
- Added derived people lists to locations and member lists to factions, with
  links back to the related person entries.

### Changed

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

### Fixed

- Resolved reference tags now follow renamed resources, update their displayed
  labels, and merge aliases without losing existing tag assignments.
- Person details now refresh immediately after editing, and refreshing a
  resource URL no longer redirects away while its persisted campaign is valid.

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
- Added PyInstaller support for building Campaign Notes as a standalone
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
