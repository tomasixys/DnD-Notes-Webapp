# DnD Notes roadmap

Updated: 2026-07-25

DnD Notes is currently a local, single-user application. The completed
milestones below describe the current application; deferred and planned work is
listed separately.

## Completed

### Application storage

- [x] Platform-specific application-data directory
- [x] Persistent SQLite database outside the executable
- [x] Upload directories and relative stored paths
- [x] Stable campaign-image serving

### Campaign images

- [x] Campaign image and banner upload
- [x] Image preview, replacement, and deletion
- [x] Uploaded-file cleanup during resource deletion

### Resource deletion

- [x] Delete support for every implemented entry type
- [x] Campaign cascade deletion
- [x] Related uploaded-file cleanup

### Campaign backup and restore

- [x] ZIP-based campaign export
- [x] JSON campaign data
- [x] Included campaign and character images
- [x] Import with ID remapping
- [x] Tags, relationships, notes, rolls, and inventory round-tripping

### Application packaging

- [x] Frontend compilation from the repository build script
- [x] Compiled frontend served by FastAPI
- [x] PyInstaller folder and single-executable builds

### Character profiles

- [x] Character overview, appearance, notes, and backstory
- [x] Portrait upload
- [x] Active-character selection
- [x] Tags and related entries

### Party inventory

- [x] Default campaign party inventory
- [x] Editable inventory name and description
- [x] Items with quantities, categories, rarities, and monetary values
- [x] Multi-denomination purse and calculated wealth totals
- [x] Active-character ownership and owner/manager access data
- [x] Backup and restore support

### Campaign search

- [x] Campaign-wide search
- [x] Results grouped and filtered by entry type
- [x] Direct links to matching resources
- [x] Character-note and backstory results

### Interactive tags and relationships

- [x] Shared free-form tags
- [x] Typed reference tags
- [x] Linked entry tags
- [x] Clickable typed relationships
- [x] Resolved, unresolved, and ambiguous reference states

## Deferred

- SQLite full-text search
- Inventory item tags
- Multiple inventories per campaign
- User-managed inventory owners and managers
- Inventory location associations

## Planned: hosted multi-user mode

The ordered implementation and security gates are documented in the
[hosted multi-user development plan](docs/hosted-multi-user-plan.md).
The target is a self-contained private-server deployment with local
username/password accounts, PostgreSQL, and protected server filesystem
storage; a third-party identity provider is not required.

- [x] Product rules and threat model
- [x] Server-ready configuration, database, and migrations
- [x] Identity and secure sessions
- [x] Campaign tenancy and authorization
- [x] Authenticated frontend shell
- [x] Protected assets and backups
- [x] Campaign invitations and member management
- [x] Shared and private visibility controls for character notes and backstory
- [x] Concurrent editing and multi-client synchronization
- [ ] Production hosting, operations, and staged rollout
  - [x] Reproducible HTTPS/PostgreSQL/filesystem stack and operator controls
  - [ ] Hosted-alpha deployment and documented restore-drill sign-off
