import hashlib
from .fsio import read_bounded, replace_atomically
from .settings import MAX_SMALL_FILE_BYTES


def store_snapshot(path):
    from .publication import digest
    try:
        data, mode = read_bounded(path, MAX_SMALL_FILE_BYTES)
    except FileNotFoundError:
        return {'base_hash': 'absent', 'bytes': 0}, None
    data.decode('utf-8-sig')
    return {'base_hash': digest({'sha256': hashlib.sha256(data).hexdigest(), 'mode': mode}), 'bytes': len(data)}, mode


def publish_store(path, content, base_hash):
    from .publication import digest
    from .storage import persistent_lock
    data, _ = read_bounded(content, MAX_SMALL_FILE_BYTES)
    data.decode('utf-8-sig')
    path = path.absolute()
    path.parent.mkdir(parents=True, exist_ok=True)
    with persistent_lock(path.parent / ('.mission-store-' + digest(path.name) + '.lock')):
        snapshot, mode = store_snapshot(path)
        if snapshot['base_hash'] != base_hash:
            raise ValueError('store changed since review; reread and merge without overwriting')
        def unchanged():
            if store_snapshot(path)[0]['base_hash'] != base_hash:
                raise ValueError('store changed while staging')
        replace_atomically(path, data, mode, unchanged)
    return store_snapshot(path)[0]
