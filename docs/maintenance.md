# Offline maintenance and recovery

Updated: 2026-07-25

`backend/maintenance.py` is a separate, non-web recovery path for operators
with operating-system access. It never starts FastAPI, never changes the
installation mode, and shares the server's exclusive instance lock. Stop the
normal server before using it.

Inspect non-secret installation and campaign summary data:

```powershell
cd backend
..\.venv\Scripts\python.exe maintenance.py `
  --config ..\config\local.example.toml `
  inspect
```

Export one campaign from filesystem-backed storage:

```powershell
..\.venv\Scripts\python.exe maintenance.py `
  --config ..\config\local.example.toml `
  export `
  --campaign-id 1 `
  --output D:\recovery\campaign.backup
```

Inspection is database read-only. Export uses the normal full campaign-backup
serializer, copies the resulting archive to the explicit output path, and
removes its temporary generated archive. It refuses to overwrite an existing
output file.

Object-storage deployments require the infrastructure disaster-recovery
process until protected object access is implemented. The command does not
offer a web authentication bypass.

## Hosted identity setup and recovery

Create the first hosted administrator after configuring the hosted database:

```bash
cd backend
../.venv/bin/python maintenance.py \
  --config ../config/hosted.example.toml \
  create-admin \
  --username keeper
```

Windows uses the same command with its Python path and PowerShell line
continuations:

```powershell
cd backend
..\.venv\Scripts\python.exe maintenance.py `
  --config ..\config\my-hosted.toml `
  create-admin `
  --username keeper
```

The command prompts twice for the password without echoing it. Passwords must
contain at least 15 Unicode characters and at most 1024; there are no
letter/number/symbol composition rules. The resulting database value is an
Argon2id encoded hash with a library-generated salt, never the password.

The first-admin command also creates the installation's non-login system
custodian. It refuses to create another bootstrap administrator while an
enabled login-capable administrator exists.

Reset an existing local account password:

```bash
../.venv/bin/python maintenance.py \
  --config ../config/hosted.example.toml \
  reset-password \
  --username keeper
```

Password reset replaces the Argon2id hash, clears credential failure/lock
state, and revokes every existing session for that user. Neither identity
command accepts a password argument, preventing the password from appearing in
shell history or process listings.

All maintenance commands acquire the same exclusive installation lock as the
normal server. Stop the server before running them.
