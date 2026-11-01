"""Deterministic source archives with an embedded file manifest."""
import hashlib
from pathlib import Path
import stat
import zipfile

ROOT_FILES = ('VERSION', 'SKILL.md', 'README.md', 'AGENTS.md', 'CHANGELOG.md', '.gitignore', '.gitattributes')
DIRECTORIES = ('scripts', 'references', 'templates', 'tests', 'evals')


def source_files(root):
    paths = [root / name for name in ROOT_FILES]
    for name in DIRECTORIES:
        for path in (root / name).rglob('*'):
            parts = path.relative_to(root).parts
            if any(part.startswith('.') or part == '__pycache__' for part in parts):
                continue
            if path.is_symlink():
                raise ValueError('Refusing release source symlink: ' + str(path))
            if (path.is_file() and path.suffix not in ('.pyc', '.pyo', '.zip')
                    and not path.name.endswith('.zip.sha256')):
                paths.append(path)
    if any(path.is_symlink() or not path.is_file() for path in paths):
        raise ValueError('Release requires regular source files')
    return sorted(paths)


def write_archive(root, destination):
    entries = []
    manifest = []
    for path in source_files(root):
        name = path.relative_to(root).as_posix()
        data = path.read_bytes()
        entries.append((name, data, stat.S_IMODE(path.stat().st_mode)))
        manifest.append(hashlib.sha256(data).hexdigest() + '  ' + name)
    entries.append(('MANIFEST.sha256', ('\n'.join(manifest) + '\n').encode(), 0o644))
    with zipfile.ZipFile(destination, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data, mode in entries:
            info = zipfile.ZipInfo('mission-control/' + name, (1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | mode) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data, compresslevel=9)
    return len(entries)


def check_manifest(archive):
    if archive.testzip() is not None:
        raise ValueError('Corrupt release ZIP')
    manifest = archive.read('mission-control/MANIFEST.sha256').decode('utf-8')
    for line in manifest.splitlines():
        expected, name = line.split('  ', 1)
        if hashlib.sha256(archive.read('mission-control/' + name)).hexdigest() != expected:
            raise ValueError('Release manifest mismatch: ' + name)
