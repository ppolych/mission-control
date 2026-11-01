import hashlib
import json
import os
from pathlib import Path
import stat
from .fsio import open_directory_chain
from .settings import MAX_OBSERVED_BYTES, MAX_TREE_DEPTH, MAX_TREE_ENTRIES


def observe_file(workspace, name):
    """Bounded, nonblocking, no-follow hash observation; never persist bytes."""
    from .contract import relative_path
    relative_path(name)
    directory = None
    fd = None
    try:
        parts = Path(name).parts
        directory = open_directory_chain(workspace, parts[:-1])
        fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_OBSERVED_BYTES:
            return {'status': 'unavailable', 'reason': 'not_regular_or_oversized'}
        hasher = hashlib.sha256()
        size = 0
        while True:
            chunk = os.read(fd, min(65536, MAX_OBSERVED_BYTES + 1 - size))
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_OBSERVED_BYTES:
                return {'status': 'unavailable', 'reason': 'oversized'}
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
        if fd is not None:
            os.close(fd)
        if directory is not None:
            os.close(directory)


def observe_tree(directory, parent, name):
    """Hash no-follow metadata for a declared output directory; never read file bytes."""
    hasher = hashlib.sha256()
    count = 0
    def walk(fd, prefix, depth):
        nonlocal count
        if depth > MAX_TREE_DEPTH:
            raise OverflowError('directory_too_deep')
        items = []
        with os.scandir(fd) as entries:
            for item in entries:
                # Apply the limit while reading, so a huge directory is never loaded whole.
                count += 1
                if count > MAX_TREE_ENTRIES:
                    raise OverflowError('directory_too_large')
                items.append(item)
        for item in sorted(items, key=lambda entry: entry.name):
            info = item.stat(follow_symlinks=False)
            path = prefix + item.name
            hasher.update(json.dumps([path, info.st_mode, info.st_size, info.st_mtime_ns]).encode())
            if stat.S_ISDIR(info.st_mode):
                child = os.open(item.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                try:
                    walk(child, path + '/', depth + 1)
                finally:
                    os.close(child)
    root = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
    try:
        walk(root, '', 0)
    finally:
        os.close(root)
    return {'status': 'present', 'kind': 'directory', 'entries': count,
            'manifest': hasher.hexdigest(), 'mode': stat.S_IMODE(parent.st_mode)}


def observe_artifact(workspace, name):
    """Observe a declared output: exact hash when possible, else weaker metadata."""
    value = observe_file(workspace, name)
    if value.get('reason') not in ('not_regular_or_oversized', 'oversized'):
        return value
    parts = Path(name).parts
    directory = None
    try:
        directory = open_directory_chain(workspace, parts[:-1])
        info = os.stat(parts[-1], dir_fd=directory, follow_symlinks=False)
        if stat.S_ISDIR(info.st_mode):
            return observe_tree(directory, info, parts[-1])
        if stat.S_ISREG(info.st_mode):
            return {'status': 'present', 'kind': 'metadata', 'size': info.st_size, 'mtime_ns': info.st_mtime_ns,
                    'ctime_ns': info.st_ctime_ns, 'mode': stat.S_IMODE(info.st_mode)}
        return value
    except OverflowError as error:
        return {'status': 'unavailable', 'reason': str(error)}
    except FileNotFoundError:
        return {'status': 'absent'}
    except OSError as error:
        return {'status': 'unavailable', 'reason': type(error).__name__}
    finally:
        if directory is not None:
            os.close(directory)


def observations(workspace, names):
    return {name: observe_file(workspace, name) for name in names}


def artifact_observations(workspace, names):
    return {name: observe_artifact(workspace, name) for name in names}


def watched_inputs(contract, step, workspace):
    return observations(workspace, step.get('watch', [])) if contract['schema_version'] == 3 else {}


def readable_observations(values):
    unavailable = [name + ' (' + str(v.get('reason')) + ')' for name, v in values.items() if v.get('status') == 'unavailable']
    if unavailable:
        raise ValueError('artifact observation unavailable: ' + ', '.join(sorted(unavailable))
                         + '; inspect it, or publish a contract revision declaring observable paths')

