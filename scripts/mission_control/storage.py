import contextlib, fcntl, json, os, stat, tempfile
from .settings import MAX_STATE_BYTES


def atomic(path,data):
    if path.name=='progress.json' and len(json.dumps(data,indent=2).encode('utf-8'))>MAX_STATE_BYTES:
        raise ValueError('checkpoint write exceeds readable size limit')
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8',newline='\n') as f:json.dump(data,f,indent=2);f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
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
def persistent_lock(path):
    """Lock one regular persistent inode; never truncate or wait on a FIFO."""
    flags = os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK
    with os.fdopen(os.open(path, flags, 0o600), 'r+') as lock:
        if not stat.S_ISREG(os.fstat(lock.fileno()).st_mode):
            raise ValueError('lock entry must be a regular file')
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise LockBusy('lock ' + str(path) + ' is held by another running command; retry after it finishes') from error
        yield lock

