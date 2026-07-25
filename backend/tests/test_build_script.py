import importlib.util
import unittest
from pathlib import Path


BUILD_SCRIPT = Path(__file__).resolve().parents[2] / "build.py"
SPEC = importlib.util.spec_from_file_location("dnd_notes_build", BUILD_SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Could not load build script: {BUILD_SCRIPT}")
build = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build)


class BuildTargetTests(unittest.TestCase):
    def test_windows_target_uses_windows_paths_and_suffix(self):
        target = build.resolve_build_target(platform_name="win32")

        self.assertEqual("windows", target.name)
        self.assertEqual(".exe", target.executable_suffix)
        self.assertEqual(
            (
                build.PROJECT_ROOT
                / ".build-venv-windows"
                / "Scripts"
                / "python.exe"
            ),
            build.build_python_path(target),
        )
        self.assertEqual(
            "DnDNotes-hosted-windows",
            build.artifact_name("hosted", target),
        )

    def test_linux_target_uses_linux_paths_and_no_suffix(self):
        target = build.resolve_build_target(platform_name="linux")

        self.assertEqual("linux", target.name)
        self.assertEqual("", target.executable_suffix)
        self.assertEqual(
            (
                build.PROJECT_ROOT
                / ".build-venv-linux"
                / "bin"
                / "python"
            ),
            build.build_python_path(target),
        )
        self.assertEqual(
            "DnDNotes-local-linux",
            build.artifact_name("local", target),
        )

    def test_explicit_target_must_match_build_host(self):
        with self.assertRaisesRegex(RuntimeError, "does not cross-compile"):
            build.resolve_build_target(
                "linux",
                platform_name="win32",
            )

    def test_unsupported_build_host_fails_clearly(self):
        with self.assertRaisesRegex(
            RuntimeError,
            "supported only on Windows and Linux",
        ):
            build.resolve_build_target(platform_name="darwin")


if __name__ == "__main__":
    unittest.main()
