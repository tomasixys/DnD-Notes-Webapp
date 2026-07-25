import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"
BACKEND_DIR = PROJECT_ROOT / "backend"
BUILD_VENV_DIR = PROJECT_ROOT / ".build-venv"
BUILD_METADATA_DIR = PROJECT_ROOT / "build" / "metadata"


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


def build_python_path() -> Path:
    if sys.platform == "win32":
        return BUILD_VENV_DIR / "Scripts" / "python.exe"
    return BUILD_VENV_DIR / "bin" / "python"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build Vue and package the FastAPI application with PyInstaller."
    )
    parser.add_argument(
        "--skip-install",
        action="store_true",
        help="Reuse existing node_modules and .build-venv dependencies.",
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
    config_path = resolve_build_config(args)
    npm = find_npm()

    if not args.skip_install:
        run([npm, "ci"], cwd=FRONTEND_DIR)

    if not args.skip_type_check:
        run([npm, "run", "type-check"], cwd=FRONTEND_DIR)

    run([npm, "run", "build"], cwd=FRONTEND_DIR)

    frontend_index = FRONTEND_DIR / "dist" / "index.html"
    if not frontend_index.is_file():
        raise RuntimeError(f"Frontend build did not create {frontend_index}")

    python = build_python_path()
    if not python.exists():
        run([sys.executable, "-m", "venv", str(BUILD_VENV_DIR)])

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

    BUILD_METADATA_DIR.mkdir(parents=True, exist_ok=True)
    embedded_profile_path = BUILD_METADATA_DIR / "_embedded_profile.txt"
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
    artifact_name = f"DnDNotes-{args.profile}"

    command = [
        str(python),
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        mode,
        "--name",
        artifact_name,
        "--distpath",
        str(PROJECT_ROOT / "dist"),
        "--workpath",
        str(PROJECT_ROOT / "build" / "pyinstaller"),
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

    executable_suffix = ".exe" if sys.platform == "win32" else ""
    if args.onefile:
        output = (
            PROJECT_ROOT
            / "dist"
            / f"{artifact_name}{executable_suffix}"
        )
    else:
        output = (
            PROJECT_ROOT
            / "dist"
            / artifact_name
            / f"{artifact_name}{executable_suffix}"
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
