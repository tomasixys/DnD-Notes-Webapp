# DnD Notes

DnD Notes is a local campaign-management application for keeping campaign
information, session notes, characters, relationships, rolls, and party
inventory in one place.

The Vue frontend and FastAPI backend are packaged as a single application.
FastAPI serves both the JSON API and compiled frontend. Local mode uses SQLite
and the operating system's application-data directory; hosted mode uses
PostgreSQL and an explicitly configured protected filesystem directory.

## Features

- Create, select, edit, back up, restore, and delete campaigns.
- Record session notes and session-specific dice rolls and statistics.
- Track people, locations, factions, and typed relationships between them.
- Create private character profiles with portraits, notes, and backstory.
- Manage a party inventory with item quantities, categories, rarity, values,
  and a multi-denomination purse.
- Add free-form and typed reference tags that link related entries.
- Search campaign resources, including character notes and backstory.
- Link directly to individual resources through their URLs.
- Invite existing server accounts into campaigns and manage member roles.

DnD Notes supports the established local single-user mode and an authenticated
server mode for private hosting. Server mode
keeps application-managed user accounts, PostgreSQL data, and protected files
under the operator's control. Campaign membership and resource authorization
are enforced across the API and reflected in the authenticated frontend.
Campaign images, portraits, and backup downloads are protected by those same
membership boundaries. Controlled campaign invitations, one-time account
activation, role changes, removal, leaving, and ownership transfer are
available without requiring an email provider. Character notes and backstory
support campaign-wide, restricted, and private visibility.

## Technology

- FastAPI, SQLModel, SQLite, and PostgreSQL
- Vue, Vue Router, TypeScript, and Vite
- PyInstaller for host-native Windows and Linux application builds

The backend API is available under `/api`. Campaign assets are available only
through authorized, campaign-scoped API routes; the storage directory is never
mounted as public static content.

## Development setup

Requirements:

- Python 3.10 or newer with `venv` support
- Node.js matching the `engines` field in `frontend/package.json`
- npm

From the repository root on Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
cd frontend
npm ci
cd ..
```

Start the backend:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --app-dir backend
```

Or use the typed configuration launcher:

```powershell
cd backend
..\.venv\Scripts\python.exe run.py --config ..\config\local.example.toml
cd ..
```

In a second terminal, start the frontend:

```powershell
cd frontend
npm run dev
```

Open `http://localhost:5173`. During development, the frontend sends API
requests to the backend at `http://localhost:8000`.

The shared [VS Code task template](vscode-tasks-template.md) provides equivalent
setup, development, verification, and packaging tasks.

## Verification

Run the frontend type-check:

```powershell
cd frontend
npm run type-check
```

The backend test runner is a development-only dependency and is not included in
the packaged application's runtime requirements:

```powershell
.\.venv\Scripts\python.exe -m pip install pytest
cd backend
..\.venv\Scripts\python.exe -m pytest -q
```

## Building

See [BUILDING.md](BUILDING.md) for distributable builds, single-file builds,
source launches with a compiled frontend, and data-location details.

For an authenticated LAN server with PostgreSQL, protected local file storage,
and HTTPS, use the [hosted deployment stack](deploy/hosted/README.md). You do
not need to build a desktop executable for that deployment.

## Documentation

- [Roadmap](ROADMAP.md)
- [Hosted multi-user development plan](docs/hosted-multi-user-plan.md)
- [Application configuration](docs/configuration.md)
- [Offline maintenance and recovery](docs/maintenance.md)
- [Hosted operations and incident response](docs/hosted-operations.md)
- [Changelog](CHANGELOG.md)
- [Backend architecture](docs/backend-architecture.md)
- [Completed backend refactoring record](docs/archive/backend-refactoring-2026-07.md)
