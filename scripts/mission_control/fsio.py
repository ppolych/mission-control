"""Shared bounded, no-follow file reads and durable atomic replacement."""
import fcntl
import os
import stat


def open_directory_chain(root, parts):
    """Open root and each directory in parts without following symlinks; the caller closes it."""
    directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in parts:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            os.close(directory)
            directory = child
    except BaseException:
        os.close(directory)
        raise
    return directory


def read_bounded(path, cap):
    """Read a regular file without following it, refusing oversized or changing files."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > cap:
            raise ValueError('file is not regular or exceeds read limit')
        data = b''
        while len(data) <= cap:
            part = os.read(fd, min(65536, cap + 1 - len(data)))
            if not part:
                break
            data += part
        after = os.fstat(fd)
        if len(data) > cap:
            raise ValueError('file exceeds read limit')
        if (info.st_size, info.st_mtime_ns, info.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise ValueError('file changed during read')
        return data, stat.S_IMODE(after.st_mode)
    finally:
        os.close(fd)


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


def replace_atomically(path, data, mode=None, before_replace=None):
    """Publish bytes through a synced temporary file, then sync the directory."""
    import tempfile
    fd, temporary = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            if mode is not None:
                os.fchmod(stream.fileno(), mode)
            stream.write(data)
            stream.flush()
            sync_file(stream.fileno())
        if before_replace is not None:
            before_replace()
        os.replace(temporary, path)
        sync_directory(path.parent)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
