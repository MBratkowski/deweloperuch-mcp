"""File locks contend across open descriptions and survive state-file I/O."""

import errno
import importlib
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


def test_another_descriptor_cannot_lock_until_the_owner_unlocks(tmp_path: Path) -> None:
    locks = importlib.import_module("deweloperuch_mcp.file_lock")
    path = tmp_path / "lock"
    owner = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    other = os.open(path, os.O_RDWR)
    try:
        locks.lock_file(owner)
        with pytest.raises(BlockingIOError):
            locks.lock_file(other, blocking=False)
        # The lock's identity does not depend on the descriptor's current position.
        os.write(owner, b'{"next_start": 10}')
        locks.unlock_file(owner)
        locks.lock_file(other, blocking=False)
        locks.unlock_file(other)
    finally:
        os.close(owner)
        os.close(other)


def test_windows_lock_resets_the_position_after_state_io(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    locks = importlib.import_module("deweloperuch_mcp.file_lock")
    operations: list[tuple[int, int, int]] = []

    def locking(fd: int, mode: int, size: int) -> None:
        operations.append((os.lseek(fd, 0, os.SEEK_CUR), mode, size))

    monkeypatch.setitem(
        sys.modules, "msvcrt", SimpleNamespace(locking=locking, LK_NBLCK=2, LK_UNLCK=0)
    )
    monkeypatch.setattr(locks, "_WINDOWS", True)
    fd = os.open(tmp_path / "lock", os.O_RDWR | os.O_CREAT, 0o600)
    try:
        os.write(fd, b"old state")
        locks.lock_file(fd)
        os.lseek(fd, 5, os.SEEK_SET)
        locks.unlock_file(fd)
    finally:
        os.close(fd)

    assert operations == [(0, 2, 1), (0, 0, 1)]


def test_windows_contention_is_nonblocking_or_retried_until_free(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    locks = importlib.import_module("deweloperuch_mcp.file_lock")
    held = True
    sleeps: list[float] = []

    def locking(fd: int, mode: int, size: int) -> None:
        if held:
            raise PermissionError(errno.EACCES, "Lock violation")

    def release_after_sleep(seconds: float) -> None:
        nonlocal held
        sleeps.append(seconds)
        held = False

    monkeypatch.setitem(
        sys.modules, "msvcrt", SimpleNamespace(locking=locking, LK_NBLCK=2, LK_UNLCK=0)
    )
    monkeypatch.setattr(locks, "_WINDOWS", True)
    monkeypatch.setattr(locks.time, "sleep", release_after_sleep)
    fd = os.open(tmp_path / "lock", os.O_RDWR | os.O_CREAT, 0o600)
    try:
        with pytest.raises(BlockingIOError):
            locks.lock_file(fd, blocking=False)
        assert sleeps == []
        locks.lock_file(fd)
        assert sleeps == [0.1]
    finally:
        os.close(fd)


def test_windows_io_errors_are_not_treated_as_contention(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    locks = importlib.import_module("deweloperuch_mcp.file_lock")

    def locking(fd: int, mode: int, size: int) -> None:
        raise OSError(errno.EIO, "I/O error")

    monkeypatch.setitem(
        sys.modules, "msvcrt", SimpleNamespace(locking=locking, LK_NBLCK=2, LK_UNLCK=0)
    )
    monkeypatch.setattr(locks, "_WINDOWS", True)
    fd = os.open(tmp_path / "lock", os.O_RDWR | os.O_CREAT, 0o600)
    try:
        with pytest.raises(OSError) as caught:
            locks.lock_file(fd)
        assert caught.value.errno == errno.EIO
    finally:
        os.close(fd)
