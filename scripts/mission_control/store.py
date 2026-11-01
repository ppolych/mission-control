import hashlib, os, stat, tempfile


def read_bounded(path, cap):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        info=os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size>cap:raise ValueError('file is not regular or exceeds read limit')
        data=b''
        while len(data)<=cap:
            part=os.read(fd,min(65536,cap+1-len(data)))
            if not part:break
            data+=part
        after=os.fstat(fd)
        if len(data)>cap:raise ValueError('file exceeds read limit')
        if (info.st_size,info.st_mtime_ns,info.st_ctime_ns)!=(after.st_size,after.st_mtime_ns,after.st_ctime_ns):raise ValueError('file changed during read')
        return data,stat.S_IMODE(after.st_mode)
    finally:os.close(fd)


def store_snapshot(path):
    from .publication import digest
    try:data,mode=read_bounded(path,65536)
    except FileNotFoundError:return {'base_hash':'absent','bytes':0},None
    data.decode('utf-8-sig')
    return {'base_hash':digest({'sha256':hashlib.sha256(data).hexdigest(),'mode':mode}),'bytes':len(data)},mode


def publish_store(path,content,base_hash):
    from .publication import digest
    from .storage import persistent_lock
    data,_=read_bounded(content,65536);data.decode('utf-8-sig')
    path=path.absolute();path.parent.mkdir(parents=True,exist_ok=True)
    with persistent_lock(path.parent/('.mission-store-'+digest(path.name)+'.lock')):
        snapshot,mode=store_snapshot(path)
        if snapshot['base_hash']!=base_hash:raise ValueError('store changed since review; reread and merge without overwriting')
        fd,tmp=tempfile.mkstemp(dir=path.parent)
        try:
            with os.fdopen(fd,'wb') as stream:
                if mode is not None:os.fchmod(stream.fileno(),mode)
                stream.write(data);stream.flush();os.fsync(stream.fileno())
            if store_snapshot(path)[0]['base_hash']!=base_hash:raise ValueError('store changed while staging')
            os.replace(tmp,path)
        finally:
            if os.path.exists(tmp):os.unlink(tmp)
    return store_snapshot(path)[0]

