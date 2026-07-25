from enum import Enum
from pathlib import Path


EMBEDDED_PROFILE_FILENAME = "_embedded_profile.txt"


class BuildProfileError(RuntimeError):
    """Raised when embedded artifact metadata is missing or invalid."""


class DeploymentMode(str, Enum):
    LOCAL = "local"
    HOSTED = "hosted"


def get_embedded_deployment_mode() -> DeploymentMode:
    profile_path = Path(__file__).with_name(EMBEDDED_PROFILE_FILENAME)
    try:
        raw_profile = profile_path.read_text(encoding="utf-8").strip()
    except OSError as error:
        raise BuildProfileError(
            f"Could not read embedded build profile: {profile_path}"
        ) from error

    try:
        return DeploymentMode(raw_profile)
    except ValueError as error:
        raise BuildProfileError(
            f"Unsupported embedded build profile: {raw_profile!r}"
        ) from error
