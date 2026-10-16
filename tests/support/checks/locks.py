"""Is a lock file held? Asked through a separate open file description, as another process would."""

import os
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from deweloperuch_mcp.file_lock import lock_file, unlock_file


def lock_is_held(lock_path: Path) -> bool:
    fd = os.open(lock_path, os.O_RDWR)  # a separate open file description
    try:
        lock_file(fd, blocking=False)
    except BlockingIOError:
        return True
    else:
        unlock_file(fd)
        return False
    finally:
        os.close(fd)


@contextmanager
def other_descriptor(path: Path) -> Iterator[int]:
    """A separate open file description, as another process would have."""
    fd = os.open(path, os.O_RDWR)
    try:
        yield fd
    finally:
        os.close(fd)


def lock_is_free(path: Path) -> bool:
    with other_descriptor(path) as fd:
        try:
            lock_file(fd, blocking=False)
        except BlockingIOError:
            return False
        unlock_file(fd)
        return True


@contextmanager
def held_lock(path: Path, *, release_after: float = 3.0) -> Iterator[None]:
    """Hold another descriptor's lock, with a timed release to bound a broken wait.

    Timer and cleanup share one release: Windows rejects unlocking an unlocked region.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        lock_file(fd)
        held = True
        guard = threading.Lock()

        def release() -> None:
            nonlocal held
            with guard:
                if held:
                    unlock_file(fd)
                    held = False

        releaser = threading.Timer(release_after, release)
        releaser.start()
        try:
            yield
        finally:
            releaser.cancel()
            releaser.join()
            release()
    finally:
        os.close(fd)
