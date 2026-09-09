from __future__ import annotations

import os
from pathlib import Path
from types import TracebackType


class InstanceLockError(RuntimeError):
    """Raised when another server or maintenance process owns the instance."""


class InstanceLock:
    def __init__(self, path: Path):
        self.path = path
        self._file = None

    def acquire(self) -> None:
        if self._file is not None:
            return

        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock_file = self.path.open("a+b")
        try:
            lock_file.seek(0, os.SEEK_END)
            if lock_file.tell() == 0:
                lock_file.write(b"\0")
                lock_file.flush()
            lock_file.seek(0)
            self._lock_file(lock_file)
        except OSError as error:
            lock_file.close()
            raise InstanceLockError(
                "Another DnD Notes server or maintenance command is using "
                f"this installation ({self.path})."
            ) from error

        self._file = lock_file

    def release(self) -> None:
        if self._file is None:
            return
        try:
            self._file.seek(0)
            self._unlock_file(self._file)
        finally:
            self._file.close()
            self._file = None

    @staticmethod
    def _lock_file(lock_file) -> None:
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(
                lock_file.fileno(),
                fcntl.LOCK_EX | fcntl.LOCK_NB,
            )

    @staticmethod
    def _unlock_file(lock_file) -> None:
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def __enter__(self) -> "InstanceLock":
        self.acquire()
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.release()
