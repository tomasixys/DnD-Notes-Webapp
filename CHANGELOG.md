# Changelog

All notable changes to DnD Notes are documented in this file.

The project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html),
and this changelog follows the structure described by
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- Added Changelog and Known Issues pages to the account menu.
- Users can report issues from inside the application and track their status.
  Reports remain private until an administrator acknowledges and publishes
  them as known issues.
- Added an account-menu notification badge for pending campaign invitations,
  changelog updates, server-role changes, and issue reports awaiting
  administrator review.

### Changed

- Resolved and rejected issue reports now move out of the active administrator
  queue into a separate closed-report history, where they can still be reopened.
- Sessions are now sorted and numbered by their played date. New sessions
  default to today's date, and adding an older session places it correctly in
  the timeline without renumbering stored records.
- Rolls are now kept separate for each player account instead of being mixed
  together. Players see their own roll history and can compare it with
  read-only summary statistics from other players.

### Fixed

- Scrolling past the end of a long resource list now continues scrolling the
  main page naturally.

## [1.0.0] - 2026-09-11

### Added

- Added the hosted, multi-user version of DnD Notes with invite-only accounts,
  secure sign-in, password recovery, and persistent browser sessions.
- Added campaign owners, members, and viewers, along with campaign invitations,
  member management, character assignments, and ownership transfer.
- Added private character profiles with portraits, active-character selection,
  personal notes, and backstory entries. Notes and backstories can be private,
  restricted to selected users, or shared with the campaign.
- Added a party inventory with item quantities, categories, rarities, values,
  character ownership, campaign wealth totals, and a multi-currency purse.
- Added richer relationships between people, factions, and locations. Related
  people and faction members are shown automatically and link back to their
  entries.
- Added search support for character notes and backstories, including entries
  belonging to former characters.
- Added protection against conflicting edits from multiple tabs or devices.
  Remote-change notices preserve open forms and let users refresh when ready.
- Added an administration console for account status, password resets, session
  revocation, account deletion, administrator roles, and orphaned campaigns.
- Added a private-server Docker deployment with HTTPS, health checks,
  coordinated backups, restore checks, and a backup-first update command.

### Changed

- Moved account actions into the account menu and campaign member management
  into the Campaign Dashboard.
- Campaign backups downloaded by users now respect private and restricted note
  visibility. Members can export the campaign data they are allowed to see.
- Reference tags now represent relationships between entries and power derived
  lists such as a location's people and a faction's members.

### Fixed

- Remote-change notifications no longer interrupt unrelated browsing or report
  a tab's own successful edits as external changes.
- Deleting an active character no longer prevents that player from creating a
  replacement character.
- Character notes and backstories no longer load twice or briefly redirect
  away while opening an entry.
- Deleted usernames can be reused for new accounts without losing historical
  ownership and audit information.
- Renamed resources now update their reference tags without losing existing
  tag assignments.
- Direct resource links remain open after a refresh, and edited person details
  update immediately.
- Invalid backup imports no longer leave behind a partially created campaign.

## [0.2.0] - 2026-07-18

### Added

- Added campaign-wide search across sessions, people, locations, and factions.
- Added direct links to individual entries.
- Added shared campaign tags and clickable reference tags for sessions, people,
  locations, and factions.

### Changed

- Reworked the header, dashboard, and resource pages into a more compact layout
  that leaves more room for campaign content.
- Campaign search and backups now include shared tags.

### Fixed

- Opening the application without a selected campaign now leads to the Campaign
  Dashboard.
- Session links now consistently open the correct session.
- Deleting a referenced resource now leaves a clearly unresolved tag instead
  of a broken link.

## [0.1.0] - 2026-07-10

### Added

- Added the initial DnD Notes application with campaign creation and dashboards.
- Added campaign-scoped session notes, people, locations, and factions.
- Added session roll tracking and campaign roll statistics.
- Added image uploads and campaign backup and restore through ZIP archives.
- Added a standalone application build for local use.

[Unreleased]: https://github.com/tomasixys/DnD-Notes-Webapp/compare/dndnotes/v1.0.0...HEAD
[1.0.0]: https://github.com/tomasixys/DnD-Notes-Webapp/compare/dndnotes/v0.2.0...dndnotes/v1.0.0
[0.2.0]: https://github.com/tomasixys/DnD-Notes-Webapp/compare/dndnotes/v0.1.0...dndnotes/v0.2.0
[0.1.0]: https://github.com/tomasixys/DnD-Notes-Webapp/releases/tag/dndnotes/v0.1.0
