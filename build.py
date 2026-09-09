import argparse
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"
BACKEND_DIR = PROJECT_ROOT / "backend"
BUILD_METADATA_DIR = PROJECT_ROOT / "build" / "metadata"


@dataclass(frozen=True)
class BuildTarget:
    name: str
    executable_suffix: str
    venv_python_parts: tuple[str, ...]


BUILD_TARGETS = {
    "win32": BuildTarget(
        name="windows",
        executable_suffix=".exe",
        venv_python_parts=("Scripts", "python.exe"),
    ),
    "linux": BuildTarget(
        name="linux",
        executable_suffix="",
        venv_python_parts=("bin", "python"),
    ),
}


def run(command: list[str], *, cwd: Path = PROJECT_ROOT) -> None:
    print(f"\n> {' '.join(str(part) for part in command)}")
    subprocess.run(command, cwd=cwd, check=True)


def find_npm() -> str:
    for command in ("npm.cmd", "npm"):
        path = shutil.which(command)
        if path:
            return path

    raise RuntimeError(
        "npm was not found. Install a Node.js version supported by frontend/package.json."
    )


def resolve_build_target(
    requested: str = "auto",
    *,
    platform_name: str | None = None,
) -> BuildTarget:
    host_platform = platform_name or sys.platform
    target = BUILD_TARGETS.get(host_platform)
    if target is None:
        raise RuntimeError(
            "DnD Notes builds are supported only on Windows and Linux. "
            f"Current Python platform: {host_platform!r}."
        )
    if requested != "auto" and requested != target.name:
        raise RuntimeError(
            f"Cannot build the {requested} target on {target.name}. "
            "PyInstaller does not cross-compile; run this build on the "
            f"{requested} operating system."
        )
    return target


def build_venv_dir(target: BuildTarget) -> Path:
    return PROJECT_ROOT / f".build-venv-{target.name}"


def build_python_path(target: BuildTarget) -> Path:
    return build_venv_dir(target).joinpath(*target.venv_python_parts)


def artifact_name(profile: str, target: BuildTarget) -> str:
    return f"DnDNotes-{profile}-{target.name}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build Vue and package the FastAPI application with PyInstaller."
    )
    parser.add_argument(
        "--skip-install",
        action="store_true",
        help=(
            "Reuse existing node_modules and the platform-specific "
            ".build-venv-* dependencies."
        ),
    )
    parser.add_argument(
        "--skip-type-check",
        action="store_true",
        help="Skip vue-tsc before compiling the frontend.",
    )
    parser.add_argument(
        "--onefile",
        action="store_true",
        help="Produce one executable. Default is a faster-starting distributable folder.",
    )
    parser.add_argument(
        "--profile",
        choices=("local", "hosted"),
        default="local",
        help="Embed the local or hosted security profile. Default: local.",
    )
    parser.add_argument(
        "--target",
        choices=("auto", "windows", "linux"),
        default="auto",
        help=(
            "Build for the current host OS. An explicit target verifies the "
            "host but does not enable cross-compilation. Default: auto."
        ),
    )
    parser.add_argument(
        "--config",
        type=Path,
        help=(
            "Configuration to validate and copy beside the artifact. "
            "Required for hosted builds."
        ),
    )
    return parser.parse_args()


def resolve_build_config(args: argparse.Namespace) -> Path:
    if args.config is not None:
        config_path = args.config.expanduser().resolve()
    elif args.profile == "local":
        config_path = PROJECT_ROOT / "config" / "local.example.toml"
    else:
        raise RuntimeError("Hosted builds require --config PATH")

    if not config_path.is_file():
        raise RuntimeError(
            f"Build configuration does not exist: {config_path}"
        )
    return config_path


def main() -> None:
    args = parse_args()
    target = resolve_build_target(args.target)
    config_path = resolve_build_config(args)
    npm = find_npm()
    print(f"Building DnD Notes for {target.name}.")

    if not args.skip_install:
        run([npm, "ci"], cwd=FRONTEND_DIR)

    if not args.skip_type_check:
        run([npm, "run", "type-check"], cwd=FRONTEND_DIR)

    run([npm, "run", "build"], cwd=FRONTEND_DIR)

    frontend_index = FRONTEND_DIR / "dist" / "index.html"
    if not frontend_index.is_file():
        raise RuntimeError(f"Frontend build did not create {frontend_index}")

    venv_dir = build_venv_dir(target)
    python = build_python_path(target)
    if not python.exists():
        run([sys.executable, "-m", "venv", str(venv_dir)])

    if not args.skip_install:
        run([str(python), "-m", "pip", "install", "--upgrade", "pip"])
        run(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "-r",
                str(BACKEND_DIR / "requirements.txt"),
            ]
        )

    run(
        [
            str(python),
            str(BACKEND_DIR / "validate_build.py"),
            "--profile",
            args.profile,
            "--config",
            str(config_path),
        ],
        cwd=BACKEND_DIR,
    )

    target_metadata_dir = BUILD_METADATA_DIR / target.name
    target_metadata_dir.mkdir(parents=True, exist_ok=True)
    embedded_profile_path = target_metadata_dir / "_embedded_profile.txt"
    embedded_profile_path.write_text(
        f"{args.profile}\n",
        encoding="utf-8",
    )

    mode = "--onefile" if args.onefile else "--onedir"
    add_data = f"{FRONTEND_DIR / 'dist'}{os.pathsep}app/frontend_dist"
    add_profile = f"{embedded_profile_path}{os.pathsep}app"
    portable_migrations = (
        BACKEND_DIR / "app" / "migrations" / "portable"
    )
    add_migrations = (
        f"{portable_migrations}"
        f"{os.pathsep}app/migrations/portable"
    )
    output_name = artifact_name(args.profile, target)

    command = [
        str(python),
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        mode,
        "--name",
        output_name,
        "--distpath",
        str(PROJECT_ROOT / "dist"),
        "--workpath",
        str(PROJECT_ROOT / "build" / "pyinstaller" / target.name),
        "--specpath",
        str(PROJECT_ROOT / "build"),
        "--paths",
        str(BACKEND_DIR),
        "--add-data",
        add_data,
        "--add-data",
        add_profile,
        "--add-data",
        add_migrations,
        "--collect-submodules",
        "uvicorn",
        "--collect-submodules",
        "alembic",
        "--hidden-import",
        "sqlalchemy.dialects.sqlite",
    ]
    if args.profile == "hosted":
        command.extend(
            [
                "--collect-submodules",
                "psycopg",
                "--hidden-import",
                "sqlalchemy.dialects.postgresql.psycopg",
            ]
        )
    command.append(str(BACKEND_DIR / "run.py"))
    run(command)

    if args.onefile:
        output = (
            PROJECT_ROOT
            / "dist"
            / f"{output_name}{target.executable_suffix}"
        )
    else:
        output = (
            PROJECT_ROOT
            / "dist"
            / output_name
            / f"{output_name}{target.executable_suffix}"
        )

    packaged_config = output.with_suffix(".toml")
    shutil.copy2(config_path, packaged_config)

    print(f"\nBuild complete: {output}")
    print(f"Packaged configuration: {packaged_config}")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, subprocess.CalledProcessError) as error:
        print(f"\nBuild failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
