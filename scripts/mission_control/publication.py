import datetime, hashlib, json, os


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()


def publish_migration(destination,contract,backups,backup_dir='legacy'):
    """Recover helper-owned staging under a persistent destination lock."""
    import shutil
    from .storage import atomic, persistent_lock
    destination=destination.absolute()
    destination.parent.mkdir(parents=True,exist_ok=True)
    parent=destination.parent.resolve()
    destination=parent/destination.name
    token=digest(str(destination))
    stage=parent/('.mission-migration-'+token+'.stage')
    lock_path=parent/('.mission-migration-'+token+'.lock')
    with persistent_lock(lock_path):
        if os.path.lexists(destination):raise ValueError('destination already exists')
        if os.path.lexists(stage):
            if stage.is_symlink() or not stage.is_dir():raise ValueError('unsafe migration staging entry; inspect manually')
            shutil.rmtree(stage)
        stage.mkdir(mode=0o700)
        try:
            atomic(stage/'contract.json',contract)
            for name,backup in backups.items():atomic(stage/backup_dir/name,backup)
            if os.path.lexists(destination):raise ValueError('destination already exists')
            os.rename(stage,destination)
        finally:
            if stage.exists():shutil.rmtree(stage)

