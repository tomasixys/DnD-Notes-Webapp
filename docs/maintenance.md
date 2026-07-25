# Offline maintenance and recovery

Updated: 2026-07-23

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
offer ownership mutation or an authentication bypass. Those operations require
the later audited administration workflow.
