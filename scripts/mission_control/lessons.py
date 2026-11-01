import os, stat
from pathlib import Path


def lesson_text(root, relative):
    directory=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    fd=None
    try:
        for part in relative.parts[:-1]:
            child=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=directory)
            os.close(directory);directory=child
        fd=os.open(relative.name,os.O_RDONLY|os.O_NONBLOCK|os.O_NOFOLLOW,dir_fd=directory)
        info=os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size>65536:return None
        data=b''
        while len(data)<=65536:
            chunk=os.read(fd,min(8192,65537-len(data)))
            if not chunk:break
            data+=chunk
        if len(data)>65536:return None
        return data.decode('utf-8-sig')
    finally:
        if fd is not None:os.close(fd)
        os.close(directory)


def lessons_search(root,queries,limit,offset,diverse=False):
    from .ranking import diversify
    if not queries or any(not q.strip() for q in queries):raise ValueError('nonblank --query required')
    if not 1<=limit<=50 or not 0<=offset<=1000:raise ValueError('limit must be 1..50 and offset 0..1000')
    if root.is_symlink() or not root.is_dir():raise ValueError('lessons root must be an existing nonsymlink directory')
    matches=[];scanned=0;visited=0;truncated=False;skipped=[]
    for directory,dirs,files in os.walk(root,followlinks=False):
        visited+=1
        if visited>64:truncated=True;break
        dirs[:]=sorted(d for d in dirs if not d.startswith('.') and not (Path(directory)/d).is_symlink())
        for name in sorted(files):
            if name.startswith('.') or not name.endswith('.md'):continue
            scanned+=1
            if scanned>32:truncated=True;break
            relative=(Path(directory)/name).relative_to(root)
            try:text=lesson_text(root,relative)
            except (OSError,UnicodeError):text=None
            if text is None:
                skipped.append(str(relative))
                continue
            for line_number,line in enumerate(text.splitlines(),1):
                if all(q.casefold() in line.casefold() for q in queries):
                    matches.append({'path':str(relative),'line':line_number,'text':line[:500]})
                    if len(matches)>1050:truncated=True;break
            if len(matches)>1050:break
        if truncated:break
    if diverse:
        truncated=truncated or len({item['text'].strip().casefold() for item in matches})>128
        matches=diversify(matches,queries)
    page=matches[offset:offset+limit]
    next_offset=offset+len(page) if offset+len(page)<len(matches) else None
    return {'root':str(root.resolve()),'queries':queries,'matches':page,
            'next_offset':next_offset,'truncated':truncated or bool(skipped) or next_offset is not None,
            'skipped_files':skipped,
            'files_examined':min(scanned,32),'warning':'Historical context only; verify current sources before reuse.'}

