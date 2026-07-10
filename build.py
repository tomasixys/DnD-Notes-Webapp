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
    return parser.parse_args()


def main() -> None:
    args = parse_args()
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

    mode = "--onefile" if args.onefile else "--onedir"
    add_data = f"{FRONTEND_DIR / 'dist'}{os.pathsep}app/frontend_dist"

    run(
        [
            str(python),
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            mode,
            "--name",
            "DnDNotes",
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
            "--collect-submodules",
            "uvicorn",
            "--hidden-import",
            "sqlalchemy.dialects.sqlite",
            str(BACKEND_DIR / "run.py"),
        ]
    )

    executable_suffix = ".exe" if sys.platform == "win32" else ""
    if args.onefile:
        output = PROJECT_ROOT / "dist" / f"DnDNotes{executable_suffix}"
    else:
        output = (
            PROJECT_ROOT
            / "dist"
            / "DnDNotes"
            / f"DnDNotes{executable_suffix}"
        )

    print(f"\nBuild complete: {output}")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, subprocess.CalledProcessError) as error:
        print(f"\nBuild failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
