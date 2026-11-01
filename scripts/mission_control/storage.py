import contextlib, fcntl, json, os, stat, tempfile, time
from .settings import MAX_STATE_BYTES


def sync_file(fd):
    os.fsync(fd)
    # macOS fsync leaves data in the drive cache; F_FULLFSYNC flushes it.
    if hasattr(fcntl, 'F_FULLFSYNC'):
        try:
            fcntl.fcntl(fd, fcntl.F_FULLFSYNC)
        except OSError:
            pass


def sync_directory(path):
    """Make a completed rename durable; some filesystems cannot sync directories."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def atomic(path,data):
    if path.name=='progress.json' and len(json.dumps(data,indent=2).encode('utf-8'))>MAX_STATE_BYTES:
        raise ValueError('checkpoint write exceeds readable size limit')
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8',newline='\n') as f:
            json.dump(data,f,indent=2)
            f.flush()
            sync_file(f.fileno())
        os.replace(tmp,path)
        sync_directory(path.parent)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)


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

