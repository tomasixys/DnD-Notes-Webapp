# Application configuration

Updated: 2026-07-25

DnD Notes reads typed TOML configuration. Unknown fields and invalid
combinations fail startup rather than being ignored.

The configuration foundation includes embedded build profiles, persisted
installation mode, database-engine settings, and protected filesystem
storage. Hosted mode includes application-managed authentication and campaign
authorization.

## Build profile

Every packaged artifact embeds either `local` or `hosted`. Runtime
configuration must request the same mode; a configuration file cannot turn a
local artifact into a hosted server or turn a hosted artifact into an open
local application.

Source launches embed `local`. Build with:

```powershell
python build.py --profile local
python build.py --profile hosted --config .\config\my-hosted.toml
```

The build validates the configuration before packaging and gives the artifact
a mode- and platform-specific name. It also copies the configuration beside
the executable using the executable name, such as
`DnDNotes-local-windows.toml` or `DnDNotes-local-linux.toml`.

## Configuration discovery

The launcher selects configuration in this order:

1. `--config PATH`;
2. the path named by `DND_NOTES_CONFIG`;
3. a TOML file matching the frozen executable name, such as
   `DnDNotes-local-linux.toml`;
4. `dnd-notes.toml` beside a frozen executable;
5. `dnd-notes.toml` in the current working directory; or
6. safe local defaults when no file exists.

Command-line `--host`, `--port`, and `--no-browser` override the loaded server
section and are revalidated against the deployment mode.

Examples are available at:

- [Local configuration](../config/local.example.toml)
- [Recommended hosted configuration with server filesystem storage](../config/hosted.example.toml)
- [Reserved object-storage configuration shape](../config/hosted-object.example.toml)

Run from source:

```powershell
cd backend
..\.venv\Scripts\python.exe run.py --config ..\config\local.example.toml
```

## Schema

### Installation

```toml
[installation]
mode = "local" # local or hosted
```

Mode is a first-launch value. The database stores it in a singleton
installation record. Later launches require the requested mode to match the
database; changing the file cannot change a hosted database into local mode.

An existing database containing campaigns but no installation record is
treated as a legacy local database. It cannot be claimed directly by hosted
mode.

### Database

Local mode uses the platform-specific SQLite database by default:

```toml
[database]
echo = false
pool_pre_ping = true
```

An explicit local SQLite URL is also accepted:

```toml
url = "sqlite:///D:/path/to/notes.db"
```

Hosted mode requires a PostgreSQL URL supplied through an environment
variable, keeping credentials out of TOML and artifacts:

```toml
[database]
url_env = "DND_NOTES_DATABASE_URL"
pool_pre_ping = true
pool_recycle_seconds = 1800
```

The referenced environment variable must contain a
`postgresql+psycopg://...` URL. Alembic creates the same current-schema
baseline on empty SQLite and PostgreSQL databases. Existing SQLite databases
first run the legacy version upgrader and are then stamped into the portable
history. A non-empty PostgreSQL database without Alembic history is rejected
instead of being adopted implicitly.

### Storage

Local mode uses filesystem storage, defaulting to the application data
directory:

```toml
[storage]
backend = "filesystem"
# path = "D:/path/to/dnd-notes-data"
```

Hosted mode describes an authenticated, network-exposed server; it does not
require cloud infrastructure. A single server may keep uploads on its own
filesystem using an explicit durable absolute path:

```toml
[storage]
backend = "filesystem"
path = "/srv/dnd-notes/data"
```

The path should be outside the source tree and executable, included in server
backups, and accessible only to the application service account and operators.

The object-storage configuration shape is reserved for a future adapter:

```toml
[storage]
backend = "object"
endpoint = "https://objects.example.com"
bucket = "dnd-notes"
region = "eu-north-1"
access_key_env = "DND_NOTES_STORAGE_ACCESS_KEY"
secret_key_env = "DND_NOTES_STORAGE_SECRET_KEY"
```

Current builds reject `backend = "object"` explicitly, so selecting it cannot
silently fall back to the local filesystem. When an object adapter is added,
the same campaign authorization boundary can issue short-lived signed URLs or
stream private objects. Until then, `filesystem` is the supported backend for
both local and hosted deployments.

Filesystem assets are never mounted as a public static directory. Campaign
images, banners, and character portraits are served by authorized API routes
that check campaign access first. Backup exports are direct, authorized
downloads from a transient directory and are removed after transfer, with
hourly cleanup for expired remnants of interrupted responses.

### Security

Hosted configuration requires secure, host-prefixed cookie settings and a
session secret reference:

```toml
[security]
session_secret_env = "DND_NOTES_SESSION_SECRET"
cookie_name = "__Host-dnd_notes_session"
cookie_secure = true
cookie_samesite = "lax"
session_lifetime_minutes = 720
session_absolute_lifetime_minutes = 10080
login_failure_limit = 5
login_initial_lock_seconds = 30
login_maximum_lock_seconds = 900
login_source_failure_limit = 20
login_source_window_seconds = 300
login_source_lock_seconds = 300
activation_token_lifetime_minutes = 10080
password_reset_token_lifetime_minutes = 60
```

The referenced session secret must contain at least 32 bytes. Runtime startup
also requires a non-empty database URL environment variable.

`session_lifetime_minutes` is the renewable idle timeout.
`session_absolute_lifetime_minutes` is the non-renewable ceiling and cannot be
shorter. Failed passwords increment an account counter; after
`login_failure_limit`, the lock begins at `login_initial_lock_seconds` and
increases up to `login_maximum_lock_seconds`. Source-aware request throttling
counts failures within `login_source_window_seconds`, blocks the keyed source
digest at `login_source_failure_limit`, and releases it after
`login_source_lock_seconds`. Raw source addresses are not stored in throttle
or security-event records.

Activation tokens default to seven days and password-reset tokens to one hour.
Both are single-use, stored only as SHA-256 digests, and replaced when an
administrator issues a newer token for the same account and purpose.

### Server

```toml
[server]
host = "127.0.0.1"
port = 8000
open_browser = true
trusted_hosts = ["localhost", "127.0.0.1", "[::1]"]
```

- `port` must be from 1 through 65535.
- Local mode accepts only `localhost` or an IP loopback address.
- Hosted mode requires `open_browser = false`.
- Hosted mode additionally requires one HTTPS origin with no path, query, user
  information, or fragment:

```toml
public_origin = "https://notes.example.com"
```

When running behind a reverse proxy, forwarded headers are accepted only from
explicit IP addresses or CIDR networks:

```toml
trusted_hosts = ["notes.example.com"]
proxy_headers = true
trusted_proxies = ["127.0.0.1"]
```

Hosted mode rejects wildcard trusted hosts.

A public IP address can be used in `public_origin` and `trusted_hosts`, but
password login and secure session cookies still require HTTPS. Port forwarding
alone does not provide transport security; use a TLS-terminating reverse proxy
and a certificate valid for the public origin.

### Initial administrator

The initial administrator is deliberately absent from TOML. Use the offline
`create-admin` maintenance command, which requires operating-system access,
acquires the exclusive installation lock, and securely prompts for the
password. Builds, example configs, environment variables, and command history
must not contain a default administrator password. See
[offline maintenance and recovery](maintenance.md).

## Persisted installation state

The singleton installation row records:

- generated installation ID;
- `local` or `hosted` mode;
- initialization time.

Mode mismatch is a startup error. A future hosted/local conversion must use an
explicit migration or export/import workflow.

## Hosted security consumers

Hosted mode consumes the deployment, cookie, password, session, throttling,
and token settings. Hosted API paths require authentication, while campaign
resources and files additionally require campaign-level authorization.
Persisted application users and administrators remain application-managed
state rather than configuration.
