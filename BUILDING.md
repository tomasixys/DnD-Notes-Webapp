# Building DnD Notes

The production package uses one FastAPI/Uvicorn process. FastAPI serves:

- the JSON API under `/api`
- uploaded campaign files under `/api/uploads`
- the compiled Vue application at `/`
- Vue Router history routes such as `/dashboard` and `/sessions`

This avoids a second web server, a second port, and production CORS
configuration.

## Requirements

- Python 3.10 or newer with `venv` support
- Node.js matching the `engines` field in `frontend/package.json`
- npm

PyInstaller builds are operating-system specific. Build a Windows executable on
Windows.

## Build

From the repository root:

```powershell
python build.py
```

The build script:

1. installs the locked frontend dependencies with `npm ci`;
2. runs the frontend type-check;
3. compiles the Vue frontend;
4. creates or updates `.build-venv`;
5. installs the backend and packaging dependencies; and
6. packages the backend and compiled frontend with PyInstaller.

The default output is an `onedir` bundle:

```text
dist/DnDNotes/DnDNotes.exe
```

The entire `dist/DnDNotes` directory must be distributed together.

For a single executable:

```powershell
python build.py --onefile
```

Output:

```text
dist/DnDNotes.exe
```

The one-file version starts more slowly because PyInstaller extracts bundled
files on launch.

## Build options

Reuse existing `frontend/node_modules` and `.build-venv` dependencies:

```powershell
python build.py --skip-install
```

The required dependencies must already be installed when this option is used.

Skip the Vue and TypeScript check:

```powershell
python build.py --skip-type-check
```

Options can be combined:

```powershell
python build.py --skip-install --skip-type-check --onefile
```

## Running from source with a compiled frontend

Create the root virtual environment and install backend dependencies first, as
described in [README.md](README.md). Then run:

```powershell
cd frontend
npm ci
npm run type-check
npm run build
cd ..\backend
..\.venv\Scripts\python.exe run.py
```

Open `http://127.0.0.1:8000`. The launcher opens it automatically unless it is
started with `--no-browser`.

The launcher also accepts `--host` and `--port`:

```powershell
..\.venv\Scripts\python.exe run.py --host 0.0.0.0 --port 8080 --no-browser
```

## Data location

The database and uploaded files remain outside the source tree and executable
in the platform-specific user-data directory selected by `platformdirs`.
Rebuilding or replacing the executable therefore does not overwrite campaign
data.

On startup, DnD Notes creates the data directory, SQLite database, and upload
directories when they do not already exist. Before a numbered database
migration, it creates a pre-migration backup beside the database.

See [the backend architecture](docs/backend-architecture.md) for the production
process and persistence boundaries.
