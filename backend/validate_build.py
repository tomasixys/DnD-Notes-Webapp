import argparse
from pathlib import Path

from app.build_profile import DeploymentMode
from app.config import (
    ConfigurationError,
    load_application_settings,
    validate_build_profile,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate a DnD Notes build configuration."
    )
    parser.add_argument(
        "--profile",
        choices=[mode.value for mode in DeploymentMode],
        required=True,
    )
    parser.add_argument("--config", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = load_application_settings(args.config)
    validate_build_profile(settings, args.profile)
    print(
        f"Validated {args.profile} build configuration: "
        f"{args.config.resolve()}"
    )


if __name__ == "__main__":
    try:
        main()
    except ConfigurationError as error:
        raise SystemExit(f"Configuration error: {error}") from error
