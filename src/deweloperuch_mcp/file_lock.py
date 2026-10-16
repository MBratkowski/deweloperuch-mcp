"""Exclusive inter-process file locks, using only the standard library.

POSIX uses ``flock``. Windows locks byte zero with ``msvcrt`` (also beyond EOF),
so acquiring a fresh lock never writes or truncates the shared limiter state.
Every unlock returns to byte zero: state I/O moves the descriptor's position.
Windows' blocking CRT mode gives up after ten attempts, so we poll its immediate
mode instead. Closing the descriptor, including process death, releases the lock.
"""

import errno
import importlib
import os
import sys
import time

_WINDOWS = sys.platform == "win32"
_POLL = 0.1


def lock_file(fd: int, *, blocking: bool = True) -> None:
    """Hold an exclusive lock; nonblocking contention raises ``BlockingIOError``."""
    if not _WINDOWS:
        fcntl = importlib.import_module("fcntl")

        fcntl.flock(fd, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        return
    while True:
        try:
            _try_windows_lock(fd)
            return
        except BlockingIOError:
            if not blocking:
                raise
            time.sleep(_POLL)


def unlock_file(fd: int) -> None:
    """Release the lock held by ``fd`` after any state-file reads or writes."""
    if _WINDOWS:
        # Its typed attributes exist only on Windows; recon still imports on POSIX.
        msvcrt = importlib.import_module("msvcrt")

        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
    else:
        fcntl = importlib.import_module("fcntl")

        fcntl.flock(fd, fcntl.LOCK_UN)


def _try_windows_lock(fd: int) -> None:
    msvcrt = importlib.import_module("msvcrt")

    os.lseek(fd, 0, os.SEEK_SET)
    try:
        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
    except OSError as err:
        if err.errno in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
            raise BlockingIOError(err.errno, err.strerror) from err
        raise
