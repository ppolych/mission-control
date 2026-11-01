import contextlib
import fcntl
import json
import os
import stat
import time
from .fsio import replace_atomically
from .settings import MAX_STATE_BYTES


def atomic(path, data):
    text = json.dumps(data, indent=2).encode('utf-8')
    if path.name == 'progress.json' and len(text) > MAX_STATE_BYTES:
        raise ValueError('checkpoint write exceeds readable size limit')
    path.parent.mkdir(parents=True, exist_ok=True)
    replace_atomically(path, text)


class LockBusy(OSError):
    """Another cooperating command holds a persistent lock."""


def require_regular_lock_entry(path):
    """Refuse a suspicious lock entry without creating or acquiring the lock."""
    try:
        mode = os.lstat(path).st_mode
    except FileNotFoundError:
        return
    if not stat.S_ISREG(mode):
        raise ValueError('lock entry must be a regular file')


@contextlib.contextmanager
def persistent_lock(path, wait=0):
    """Lock one regular persistent inode; never truncate or wait on a FIFO."""
    flags = os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK
    with os.fdopen(os.open(path, flags, 0o600), 'r+') as lock:
        if not stat.S_ISREG(os.fstat(lock.fileno()).st_mode):
            raise ValueError('lock entry must be a regular file')
        deadline = time.monotonic() + wait
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError as error:
                if time.monotonic() >= deadline:
                    raise LockBusy('lock ' + str(path) + ' is held by another running command; retry after it finishes') from error
                time.sleep(0.02)
        yield lock
