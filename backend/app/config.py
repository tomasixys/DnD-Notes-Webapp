from __future__ import annotations

import ipaddress
import os
import re
import sys
from enum import Enum
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from app.build_profile import (
    BuildProfileError,
    DeploymentMode,
    get_embedded_deployment_mode,
)

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


CONFIG_PATH_ENV = "DND_NOTES_CONFIG"
DEFAULT_CONFIG_FILENAME = "dnd-notes.toml"
SECRET_REFERENCE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")


class ConfigurationError(RuntimeError):
    """Raised when application configuration cannot be loaded safely."""


class StrictSettingsModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InstallationSettings(StrictSettingsModel):
    mode: DeploymentMode = DeploymentMode.LOCAL


class StorageBackend(str, Enum):
    FILESYSTEM = "filesystem"
    OBJECT = "object"


class SameSitePolicy(str, Enum):
    LAX = "lax"
    STRICT = "strict"


class DatabaseSettings(StrictSettingsModel):
    url: str | None = None
    url_env: str | None = None
    echo: bool = False
    pool_pre_ping: bool = True
    pool_recycle_seconds: int = Field(default=1800, ge=0)

    @field_validator("url")
    @classmethod
    def normalize_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("database.url cannot be empty")
        return value

    @field_validator("url_env")
    @classmethod
    def validate_url_reference(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not SECRET_REFERENCE_PATTERN.fullmatch(value):
            raise ValueError(
                "database.url_env must name an uppercase environment variable"
            )
        return value

    @model_validator(mode="after")
    def validate_url_source(self) -> "DatabaseSettings":
        if self.url is not None and self.url_env is not None:
            raise ValueError(
                "database requires at most one of url or url_env"
            )
        return self


class ServerSettings(StrictSettingsModel):
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    public_origin: str | None = None
    open_browser: bool = True
    trusted_hosts: list[str] = Field(
        default_factory=lambda: [
            "localhost",
            "127.0.0.1",
            "[::1]",
            "testserver",
        ]
    )
    proxy_headers: bool = False
    trusted_proxies: list[str] = Field(default_factory=list)

    @field_validator("host")
    @classmethod
    def normalize_host(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("server.host cannot be empty")
        return value

    @field_validator("public_origin")
    @classmethod
    def validate_public_origin(cls, value: str | None) -> str | None:
        if value is None:
            return None

        value = value.strip().rstrip("/")
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError(
                "server.public_origin must be an HTTP(S) origin "
                "without credentials, path query, or fragment"
            )
        if parsed.path not in {"", "/"}:
            raise ValueError(
                "server.public_origin must not contain a path"
            )
        return value

    @field_validator("trusted_hosts")
    @classmethod
    def validate_trusted_hosts(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        for value in values:
            value = value.strip().lower()
            if (
                not value
                or "://" in value
                or "/" in value
                or any(character.isspace() for character in value)
            ):
                raise ValueError(
                    "server.trusted_hosts entries must be hostnames only"
                )
            if value not in normalized:
                normalized.append(value)
        if not normalized:
            raise ValueError("server.trusted_hosts cannot be empty")
        return normalized

    @field_validator("trusted_proxies")
    @classmethod
    def validate_trusted_proxies(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        for value in values:
            value = value.strip()
            try:
                network = ipaddress.ip_network(value, strict=False)
            except ValueError as error:
                raise ValueError(
                    "server.trusted_proxies entries must be IP addresses "
                    "or CIDR networks"
                ) from error
            canonical = str(network)
            if canonical not in normalized:
                normalized.append(canonical)
        return normalized

    @model_validator(mode="after")
    def validate_proxy_settings(self) -> "ServerSettings":
        if self.proxy_headers and not self.trusted_proxies:
            raise ValueError(
                "server.proxy_headers requires at least one trusted proxy"
            )
        if not self.proxy_headers and self.trusted_proxies:
            raise ValueError(
                "server.trusted_proxies requires proxy_headers = true"
            )
        return self


class StorageSettings(StrictSettingsModel):
    backend: StorageBackend = StorageBackend.FILESYSTEM
    path: Path | None = None
    endpoint: str | None = None
    bucket: str | None = None
    region: str | None = None
    access_key_env: str | None = None
    secret_key_env: str | None = None

    @field_validator("path")
    @classmethod
    def validate_filesystem_path(
        cls,
        value: Path | None,
    ) -> Path | None:
        if value is None:
            return None
        value = value.expanduser()
        if not value.is_absolute():
            raise ValueError("storage.path must be absolute")
        return value

    @field_validator("endpoint", "bucket", "region")
    @classmethod
    def normalize_object_value(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("storage values cannot be empty")
        return value

    @field_validator("access_key_env", "secret_key_env")
    @classmethod
    def validate_secret_reference(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not SECRET_REFERENCE_PATTERN.fullmatch(value):
            raise ValueError(
                "storage secret references must name uppercase "
                "environment variables"
            )
        return value

    @model_validator(mode="after")
    def validate_backend_settings(self) -> "StorageSettings":
        object_values = (
            self.endpoint,
            self.bucket,
            self.region,
            self.access_key_env,
            self.secret_key_env,
        )
        if self.backend is StorageBackend.FILESYSTEM:
            if any(value is not None for value in object_values):
                raise ValueError(
                    "filesystem storage cannot configure object settings"
                )
            return self

        if self.path is not None:
            raise ValueError("object storage cannot configure storage.path")
        required = {
            "endpoint": self.endpoint,
            "bucket": self.bucket,
            "access_key_env": self.access_key_env,
            "secret_key_env": self.secret_key_env,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(
                "object storage requires " + ", ".join(missing)
            )
        parsed_endpoint = urlsplit(self.endpoint or "")
        if (
            parsed_endpoint.scheme != "https"
            or not parsed_endpoint.netloc
            or parsed_endpoint.username is not None
            or parsed_endpoint.password is not None
            or parsed_endpoint.path not in {"", "/"}
            or parsed_endpoint.query
            or parsed_endpoint.fragment
        ):
            raise ValueError(
                "storage.endpoint must be an HTTPS origin"
            )
        return self


class SecuritySettings(StrictSettingsModel):
    session_secret_env: str | None = None
    cookie_name: str = "__Host-dnd_notes_session"
    cookie_secure: bool = True
    cookie_samesite: SameSitePolicy = SameSitePolicy.LAX
    session_lifetime_minutes: int = Field(
        default=720,
        ge=5,
        le=43200,
    )
    session_absolute_lifetime_minutes: int = Field(
        default=10080,
        ge=5,
        le=129600,
    )
    login_failure_limit: int = Field(default=5, ge=3, le=20)
    login_initial_lock_seconds: int = Field(
        default=30,
        ge=1,
        le=3600,
    )
    login_maximum_lock_seconds: int = Field(
        default=900,
        ge=1,
        le=86400,
    )
    login_source_failure_limit: int = Field(
        default=20,
        ge=5,
        le=1000,
    )
    login_source_window_seconds: int = Field(
        default=300,
        ge=10,
        le=86400,
    )
    login_source_lock_seconds: int = Field(
        default=300,
        ge=10,
        le=86400,
    )
    activation_token_lifetime_minutes: int = Field(
        default=10080,
        ge=5,
        le=43200,
    )
    password_reset_token_lifetime_minutes: int = Field(
        default=60,
        ge=5,
        le=1440,
    )
    campaign_invitation_lifetime_minutes: int = Field(
        default=10080,
        ge=5,
        le=43200,
    )
    invitation_failure_limit: int = Field(default=10, ge=3, le=100)
    invitation_failure_window_seconds: int = Field(
        default=300,
        ge=10,
        le=86400,
    )
    invitation_lock_seconds: int = Field(
        default=300,
        ge=10,
        le=86400,
    )

    @field_validator("session_secret_env")
    @classmethod
    def validate_session_secret_reference(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not SECRET_REFERENCE_PATTERN.fullmatch(value):
            raise ValueError(
                "security.session_secret_env must name an uppercase "
                "environment variable"
            )
        return value

    @field_validator("cookie_name")
    @classmethod
    def validate_cookie_name(cls, value: str) -> str:
        value = value.strip()
        if not value or any(
            character.isspace() or character in ";,"
            for character in value
        ):
            raise ValueError("security.cookie_name is invalid")
        return value

    @model_validator(mode="after")
    def validate_security_lifetimes(self) -> "SecuritySettings":
        if (
            self.session_absolute_lifetime_minutes
            < self.session_lifetime_minutes
        ):
            raise ValueError(
                "security.session_absolute_lifetime_minutes cannot be "
                "shorter than session_lifetime_minutes"
            )
        if (
            self.login_maximum_lock_seconds
            < self.login_initial_lock_seconds
        ):
            raise ValueError(
                "security.login_maximum_lock_seconds cannot be shorter "
                "than login_initial_lock_seconds"
            )
        return self


class RequestLimitSettings(StrictSettingsModel):
    enabled: bool = True
    search_per_minute: int = Field(default=60, ge=1, le=10000)
    upload_per_minute: int = Field(default=20, ge=1, le=10000)
    import_per_minute: int = Field(default=5, ge=1, le=10000)
    export_per_minute: int = Field(default=10, ge=1, le=10000)


class ApplicationSettings(StrictSettingsModel):
    installation: InstallationSettings = Field(
        default_factory=InstallationSettings
    )
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    server: ServerSettings = Field(default_factory=ServerSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    request_limits: RequestLimitSettings = Field(
        default_factory=RequestLimitSettings
    )

    @model_validator(mode="after")
    def validate_deployment_mode(self) -> "ApplicationSettings":
        if self.installation.mode is DeploymentMode.LOCAL:
            if not is_loopback_host(self.server.host):
                raise ValueError(
                    "local mode requires server.host to be a loopback "
                    "address"
                )
            if self.storage.backend is not StorageBackend.FILESYSTEM:
                raise ValueError(
                    "local mode currently requires filesystem storage"
                )
            return self

        if self.server.public_origin is None:
            raise ValueError(
                "hosted mode requires server.public_origin"
            )
        if not self.server.public_origin.startswith("https://"):
            raise ValueError(
                "hosted mode requires an HTTPS server.public_origin"
            )
        if self.server.open_browser:
            raise ValueError(
                "hosted mode requires server.open_browser = false"
            )
        if self.database.url_env is None:
            raise ValueError(
                "hosted mode requires database.url_env so credentials are "
                "provided at runtime"
            )
        if "*" in self.server.trusted_hosts:
            raise ValueError(
                "hosted mode cannot trust every Host header"
            )
        if (
            self.storage.backend is StorageBackend.FILESYSTEM
            and self.storage.path is None
        ):
            raise ValueError(
                "hosted filesystem storage requires an explicit "
                "absolute storage.path"
            )
        if self.security.session_secret_env is None:
            raise ValueError(
                "hosted mode requires security.session_secret_env"
            )
        if not self.security.cookie_secure:
            raise ValueError(
                "hosted mode requires secure session cookies"
            )
        if not self.security.cookie_name.startswith("__Host-"):
            raise ValueError(
                "hosted mode session cookie must use the __Host- prefix"
            )
        return self


def is_loopback_host(host: str) -> bool:
    normalized = host.strip().strip("[]").lower()
    if normalized == "localhost":
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def find_default_config_path() -> Path | None:
    configured_path = os.environ.get(CONFIG_PATH_ENV)
    if configured_path:
        return Path(configured_path).expanduser()

    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        executable = Path(sys.executable).resolve()
        candidates.extend(
            (
                executable.with_suffix(".toml"),
                executable.parent / DEFAULT_CONFIG_FILENAME,
            )
        )
    candidates.append(Path.cwd() / DEFAULT_CONFIG_FILENAME)

    return next((path for path in candidates if path.is_file()), None)


def load_application_settings(
    config_path: str | Path | None = None,
) -> ApplicationSettings:
    path = (
        Path(config_path).expanduser()
        if config_path is not None
        else find_default_config_path()
    )
    if path is None:
        return ApplicationSettings()
    if not path.is_file():
        raise ConfigurationError(
            f"Configuration file does not exist: {path}"
        )

    try:
        with path.open("rb") as config_file:
            raw_settings = tomllib.load(config_file)
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise ConfigurationError(
            f"Could not read configuration file {path}: {error}"
        ) from error

    try:
        return ApplicationSettings.model_validate(raw_settings)
    except ValidationError as error:
        raise ConfigurationError(
            f"Invalid configuration in {path}:\n{error}"
        ) from error


def validate_build_profile(
    settings: ApplicationSettings,
    build_profile: DeploymentMode | str | None = None,
) -> ApplicationSettings:
    try:
        expected_mode = (
            DeploymentMode(build_profile)
            if build_profile is not None
            else get_embedded_deployment_mode()
        )
    except (BuildProfileError, ValueError) as error:
        raise ConfigurationError(str(error)) from error

    configured_mode = settings.installation.mode
    if configured_mode is not expected_mode:
        raise ConfigurationError(
            f"Build profile is '{expected_mode.value}' but configuration "
            f"requests '{configured_mode.value}'. Use an artifact built for "
            "the requested deployment mode."
        )
    if settings.storage.backend is StorageBackend.OBJECT:
        raise ConfigurationError(
            "Object storage is reserved for a future storage adapter. "
            "Use storage.backend = 'filesystem' for current builds."
        )
    return settings


def load_runtime_settings(
    config_path: str | Path | None = None,
) -> ApplicationSettings:
    settings = validate_build_profile(
        load_application_settings(config_path)
    )
    validate_runtime_secrets(settings)
    return settings


def validate_runtime_secrets(settings: ApplicationSettings) -> None:
    if settings.installation.mode is DeploymentMode.LOCAL:
        return

    references: dict[str, str | None] = {
        "database URL": settings.database.url_env,
        "session secret": settings.security.session_secret_env,
    }
    if settings.storage.backend is StorageBackend.OBJECT:
        references.update(
            {
                "object-storage access key": (
                    settings.storage.access_key_env
                ),
                "object-storage secret key": (
                    settings.storage.secret_key_env
                ),
            }
        )
    for label, environment_name in references.items():
        if environment_name is None:
            raise ConfigurationError(
                f"Hosted {label} reference is not configured"
            )
        value = os.environ.get(environment_name)
        if value is None or not value.strip():
            raise ConfigurationError(
                f"Hosted {label} environment variable "
                f"{environment_name!r} is not set"
            )

    session_secret_name = settings.security.session_secret_env
    session_secret = os.environ.get(session_secret_name or "", "")
    if len(session_secret.encode("utf-8")) < 32:
        raise ConfigurationError(
            "Hosted session secret must contain at least 32 bytes"
        )


def apply_server_overrides(
    settings: ApplicationSettings,
    *,
    host: str | None = None,
    port: int | None = None,
    open_browser: bool | None = None,
) -> ApplicationSettings:
    raw_settings = settings.model_dump(mode="python")
    server = raw_settings["server"]
    if host is not None:
        server["host"] = host
    if port is not None:
        server["port"] = port
    if open_browser is not None:
        server["open_browser"] = open_browser
    try:
        return ApplicationSettings.model_validate(raw_settings)
    except ValidationError as error:
        raise ConfigurationError(
            f"Invalid command-line server override:\n{error}"
        ) from error
