# Building DnD Notes

The production package uses one FastAPI/Uvicorn process. FastAPI serves:

- the JSON API under `/api`
- uploaded campaign files under `/api/uploads`
- the compiled Vue application at `/`
- Vue Router history routes such as `/dashboard` and `/sessions`

This avoids a second web server, a second port, and production CORS configuration.

## Requirements

- Python with `venv` support
- Node.js matching the `engines` field in `frontend/package.json`
- npm

PyInstaller builds are operating-system specific. Build the Windows executable on Windows.

## Build

From the repository root:

```powershell
python build.py
```

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

The one-file version starts more slowly because PyInstaller extracts bundled files on launch.

To rebuild without reinstalling dependencies:

```powershell
python build.py --skip-install
```

## Running from source with a compiled frontend

```powershell
cd frontend
npm ci
npm run build
cd ..\backend
python run.py
```

Open `http://127.0.0.1:8000`. The launcher opens it automatically unless started with `--no-browser`.

## Data location

The database and uploaded files remain outside the executable in the platform-specific user data directory already selected by `platformdirs`. Rebuilding or replacing the executable therefore does not overwrite campaign data.
