"""Is a lock file held? Asked through a separate open file description, as another process would."""

import fcntl
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


def lock_is_held(lock_path: Path) -> bool:
    fd = os.open(lock_path, os.O_RDWR)  # a separate open file description
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return True
    else:
        fcntl.flock(fd, fcntl.LOCK_UN)
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
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
        fcntl.flock(fd, fcntl.LOCK_UN)
        return True
