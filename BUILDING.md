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

PyInstaller builds are operating-system specific. Build the Windows artifact
on Windows and the Linux artifact on Linux. The build detects the host by
default and keeps platform artifacts and build environments separate.

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

On Windows, the default output is an `onedir` bundle:

```text
dist/DnDNotes-local-windows/DnDNotes-local-windows.exe
dist/DnDNotes-local-windows/DnDNotes-local-windows.toml
```

On Linux:

```text
dist/DnDNotes-local-linux/DnDNotes-local-linux
dist/DnDNotes-local-linux/DnDNotes-local-linux.toml
```

The entire platform-specific directory must be distributed together.

For a single executable:

```powershell
python build.py --onefile
```

Windows output:

```text
dist/DnDNotes-local-windows.exe
dist/DnDNotes-local-windows.toml
```

Linux output:

```text
dist/DnDNotes-local-linux
dist/DnDNotes-local-linux.toml
```

The one-file version starts more slowly because PyInstaller extracts bundled
files on launch.

## Build options

### Target operating system

The default `--target auto` selects the operating system running the build:

```powershell
# Windows
python build.py --target windows
```

```bash
# Linux
python build.py --target linux
```

An explicit target is a safety check, not a cross-compiler. Asking for
`--target linux` on Windows or `--target windows` on Linux fails before
installing or building anything. To produce both artifacts, run the same source
revision once on each operating system. Their `-windows` and `-linux` names
prevent one artifact from overwriting the other when collected into the same
`dist` directory.

Dependencies are stored in `.build-venv-windows` or `.build-venv-linux`, so a
workspace used from both operating systems does not reuse an incompatible
virtual environment.

The default artifact embeds the `local` security profile and validates
`config/local.example.toml`. An explicit local configuration may be supplied:

```powershell
python build.py --profile local --config .\config\my-local.toml
```

A hosted build requires an explicit hosted configuration:

```powershell
python build.py --profile hosted --config .\config\my-hosted.toml
```

This produces a distinctly named `DnDNotes-hosted-windows` or
`DnDNotes-hosted-linux` artifact with an embedded hosted profile. Profile
mismatch is a startup error. Hosted startup remains disabled until
authentication and authorization are implemented.

The packaged backend includes the portable Alembic migration environment.
Normal startup creates or upgrades the selected SQLite/PostgreSQL database;
legacy desktop SQLite databases are backed up and adopted into that history.

Reuse existing `frontend/node_modules` and the current platform's
`.build-venv-*` dependencies:

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
..\.venv\Scripts\python.exe run.py --host 127.0.0.1 --port 8080 --no-browser
```

The typed TOML launcher also accepts `--config`. Local mode rejects
non-loopback bind addresses; external binding remains available only to a
future hosted profile with authentication enabled.

```powershell
..\.venv\Scripts\python.exe run.py `
  --config ..\config\local.example.toml `
  --port 8080
```

See [application configuration](docs/configuration.md) for discovery,
validation, and first-launch installation behavior.

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
