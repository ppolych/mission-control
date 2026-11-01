#!/usr/bin/env python3
"""Build mission-control.zip and checksum after disposable install smoke checks."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import shutil
import tempfile
import zipfile
from release_archive import check_manifest, write_archive
from release_publish import PublicationRecoveryError, publication_lock, publish_pair

ROOT = Path(__file__).resolve().parent.parent


def smoke(archive_path):
    with tempfile.TemporaryDirectory(prefix='mission-control-smoke-') as temporary:
        root = Path(temporary)
        with zipfile.ZipFile(archive_path) as archive:
            check_manifest(archive)
            archive.extractall(root)
        skill = root / 'mission-control'
        workspace = root / 'workspace spaces Ελληνικά';workspace.mkdir()
        cli = skill / 'scripts/mission.py'
        contract = workspace / 'input.json'
        contract.write_text(json.dumps({'schema_version': 2, 'mission': 'Packaging smoke',
            'steps': [{'id': 'one', 'verify': [['exit0', 'true']]}]}), encoding='utf-8')
        commands = [('--version',), ('validate', '--contract', str(skill / 'templates/contract.json')),
                    ('init', '--contract', str(contract)), ('repeat', 'record', 'tool', 'argument'),
                    ('start', '--step', 'one'), ('verify', '--step', 'one'), ('finish',)]
        env = dict(os.environ)
        env.pop('NO_PROGRESS_STATE', None)
        env['NO_PROGRESS_THRESHOLD'] = '2'
        env['VERIFY_TIMEOUT'] = '10'
        env['PYTHONDONTWRITEBYTECODE'] = '1'
        for command in commands:
            subprocess.run([sys.executable, str(cli), *command], cwd=workspace, env=env,
                           check=True, capture_output=True, text=True, timeout=30)
        for wrapper in ('verify.sh', 'no_progress.sh'):
            subprocess.run(['bash', str(skill / 'scripts' / wrapper), '--version'],
                           cwd=workspace, env=env, check=True, capture_output=True, timeout=30)
        if ((workspace / 'mission').exists()
                or not (workspace / '.mission/state/progress.json').is_file()
                or not (workspace / '.mission/state/call_hashes.txt').is_file()):
            raise ValueError('Extracted package used the wrong runtime directory')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'mission-control.zip')
    args = parser.parse_args()
    target = args.output.absolute()
    checksum = target.with_suffix('.zip.sha256')
    if target.suffix != '.zip' or target.is_symlink() or checksum.is_symlink():
        raise ValueError('Output must be a regular .zip path with a nonsymlink checksum')
    target.parent.mkdir(parents=True, exist_ok=True)
    with publication_lock(target):
        temporary = Path(tempfile.mkdtemp(prefix='.mission-package-', dir=target.parent))
        retain = False
        try:
            stage = temporary / 'release.zip'
            count = write_archive(ROOT, stage)
            smoke(stage)
            digest = hashlib.sha256(stage.read_bytes()).hexdigest()
            staged_checksum = temporary / 'release.sha256'
            staged_checksum.write_text(digest + '  ' + target.name + '\n', encoding='utf-8')
            publish_pair(stage, staged_checksum, target)
        except PublicationRecoveryError:
            retain = True
            raise
        finally:
            if not retain:
                shutil.rmtree(temporary)
    print(f'{target}: {count} entries; manifest and extracted-install smoke passed')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(2)
