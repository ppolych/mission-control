import hashlib, os, stat
from pathlib import Path
from .settings import MAX_OBSERVED_BYTES


def observe_file(workspace, name):
    """Bounded, nonblocking, no-follow hash observation; never persist bytes."""
    from .contract import relative_path
    relative_path(name)
    directory = None
    fd = None
    try:
        directory = os.open(workspace, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        parts = Path(name).parts
        for part in parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            os.close(directory);directory = child
        fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_OBSERVED_BYTES:
            return {'status': 'unavailable', 'reason': 'not_regular_or_oversized'}
        hasher = hashlib.sha256()
        size = 0
        while True:
            chunk = os.read(fd, min(65536, MAX_OBSERVED_BYTES + 1 - size))
            if not chunk:break
            size += len(chunk)
            if size > MAX_OBSERVED_BYTES:return {'status': 'unavailable', 'reason': 'oversized'}
            hasher.update(chunk)
        after = os.fstat(fd)
        if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            return {'status': 'unavailable', 'reason': 'changed_during_read'}
        return {'status': 'present', 'sha256': hasher.hexdigest(), 'mode': stat.S_IMODE(after.st_mode)}
    except FileNotFoundError:
        return {'status': 'absent'}
    except OSError as error:
        return {'status': 'unavailable', 'reason': type(error).__name__}
    finally:
        if fd is not None:os.close(fd)
        if directory is not None:os.close(directory)


def observations(workspace, names):
    return {name: observe_file(workspace, name) for name in names}


def watched_inputs(contract, step, workspace):
    return observations(workspace, step.get('watch', [])) if contract['schema_version'] == 3 else {}


def readable_observations(values):
    if any(v.get('status') == 'unavailable' for v in values.values()):
        raise ValueError('artifact observation unavailable; inspect before proceeding')

