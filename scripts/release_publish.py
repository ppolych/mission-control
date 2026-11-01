"""Cooperative package publication with rollback for handled replacement failures."""
import os
from pathlib import Path
import shutil
import stat
from mission_control.storage import persistent_lock


class PublicationRecoveryError(OSError):
    """Publication failed and backups must remain available to the operator."""


def publication_lock(target):
    return persistent_lock(target.with_name('.' + target.name + '.publish.lock'))


def publish_pair(archive, checksum, target):
    """Caller holds publication_lock; crash-atomic pairing is not promised."""
    target_checksum = target.with_suffix('.zip.sha256')
    destinations = (target, target_checksum)
    stages = (archive, checksum)
    backups = []
    for index, destination in enumerate(destinations):
        if destination.is_symlink():
            raise ValueError('Publication destination must not be a symlink')
        backup = None
        if destination.exists():
            info = destination.stat()
            if not stat.S_ISREG(info.st_mode):
                raise ValueError('Publication destination must be a regular file')
            backup = archive.parent / ('previous-' + str(index))
            shutil.copy2(destination, backup)
            os.chmod(stages[index], stat.S_IMODE(info.st_mode))
        backups.append(backup)
    replaced = []
    try:
        for stage, destination, backup in zip(stages, destinations, backups):
            os.replace(stage, destination)
            replaced.append((destination, backup))
    except BaseException:
        try:
            for destination, backup in reversed(replaced):
                if backup is None:
                    destination.unlink()
                else:
                    os.replace(backup, destination)
        except OSError as error:
            raise PublicationRecoveryError('Rollback failed; recovery files retained at ' +
                                           str(archive.parent)) from error
        raise
