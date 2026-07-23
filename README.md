# DnD Notes

DnD Notes is a local campaign-management application for keeping campaign
information, session notes, characters, relationships, rolls, and party
inventory in one place.

The Vue frontend and FastAPI backend are packaged as a single application. In
production, FastAPI serves both the JSON API and the compiled frontend, while
SQLite and uploaded files remain in the operating system's user-data directory.

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

DnD Notes currently runs as a local, single-user application. Authentication
and hosted multi-user collaboration are future roadmap items.

## Technology

- FastAPI, SQLModel, and SQLite
- Vue, Vue Router, TypeScript, and Vite
- PyInstaller for distributable application builds

The backend API is available under `/api`. Uploaded campaign assets are served
under `/api/uploads`.

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

## Documentation

- [Roadmap](ROADMAP.md)
- [Changelog](CHANGELOG.md)
- [Backend architecture](docs/backend-architecture.md)
- [Completed backend refactoring record](docs/archive/backend-refactoring-2026-07.md)
