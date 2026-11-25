import os, subprocess
from pathlib import Path


MISSING_TEXT={'file':lambda args:args[0]+' missing','not_file':lambda args:args[0]+' exists',
              'grep':lambda args:'pattern not found in '+args[1],'not_grep':lambda args:'pattern found in '+args[1]}


def run_check(check, quiet=False, cwd=None, timeout=None, index=None, grade=False, require_tests=False):
    """Return normalized verification status separately from process status.

    grade adds what the check proved (validation_tier); require_tests fails a passing
    test command that ran no tests or whose summary could not be read."""
    from .processes import supervised_process
    from .validation import check_args
    from . import validation_tier
    check_args(check)
    capture=grade and validation_tier.argv_tier(check)==validation_tier.ASSERTIONS
    output=''
    kind,*args=check
    result={'code':0,'command_exit_status':None,'signal':None,'error_type':None}
    limit=float(os.environ.get('VERIFY_TIMEOUT','60')) if timeout is None else float(timeout)
    try:
        if kind in ('file','not_file'):
            path=Path(cwd or Path.cwd())/args[0]
            if kind=='file':ok=path.exists()
            else:
                try:path.lstat()
                except (FileNotFoundError,NotADirectoryError):ok=True
                else:ok=False
            result['code']=int(not ok)
        else:
            if kind in ('grep','not_grep'):cmd=['grep','-q','--',*args]
            elif kind=='exec':cmd=['bash','-o','pipefail','-c',args[0]]
            elif kind=='test':cmd=['test',*args]
            else:cmd=args
            if capture:status,output=run_captured(cmd,cwd,limit)
            else:status=supervised_process(cmd,cwd,quiet,limit).returncode
            result['command_exit_status']=status
            result['code']=int(status!=0)
            if kind=='not_grep' and status in (0,1):result['code']=1-status
            if status<0:
                result['signal']=-status;result['error_type']='signal'
            elif kind in ('grep','not_grep','test') and status>1:
                result['code']=2;result['error_type']=kind+'_error'
    except subprocess.TimeoutExpired:
        result['code']=2;result['error_type']='timeout'
    except OSError as error:
        result['code']=2;result['error_type']=type(error).__name__
    explanation=None
    if grade:
        result['grade']=validation_tier.grade(check,output)
        if require_tests and result['code']==0:
            explanation=validation_tier.shortfall(result['grade'])
            if explanation:
                result['code']=1;result['error_type']='tests_not_counted'
    details=[] if index is None else ['check '+str(index)]
    if grade and validation_tier.describe(result['grade']):details.append(validation_tier.describe(result['grade']))
    if result['code']==1 and kind in MISSING_TEXT:details.append(MISSING_TEXT[kind](args))
    if result['error_type']=='timeout':details.append(f'timeout after {limit:g}s')
    elif result['signal']:details.append('signal '+str(result['signal']))
    elif result['error_type'] and result['command_exit_status'] is None:details.append(result['error_type'])
    elif result['code'] and result['command_exit_status'] and not explanation:details.append('exit '+str(result['command_exit_status']))
    suffix=' ('+', '.join(details)+')' if details else ''
    print(('PASS' if result['code']==0 else 'FAIL')+': '+kind+suffix)
    if explanation:print('  '+explanation)
    return result


def run_captured(cmd,cwd,limit):
    """Run with output drained through a pipe; only the tail, where runners print their summary, is kept in memory."""
    import threading
    from .processes import supervised_process
    from .validation_tier import TAIL_BYTES
    read_end,write_end=os.pipe()
    tail=bytearray()
    def drain():
        with os.fdopen(read_end,'rb') as stream:
            for chunk in iter(lambda:stream.read(65536),b''):
                tail.extend(chunk)
                del tail[:-TAIL_BYTES]
    reader=threading.Thread(target=drain,daemon=True)
    reader.start()
    try:
        status=supervised_process(cmd,cwd,False,limit,output=write_end).returncode
    finally:
        os.close(write_end)
        reader.join(timeout=5)
    return status,bytes(tail).decode('utf-8','replace')


def verify(args, quiet=False, cwd=None, split=False):
    from .validation import check_args
    # Contracts supply one argv array; only the wrapper has separators.
    groups=[list(args)]
    if split:
        groups=[[]]
        for arg in args:
            if arg=='--':groups.append([])
            else:groups[-1].append(arg)
    for group in groups:check_args(group)
    for group in groups:
        result=run_check(group,quiet=quiet,cwd=cwd)
        if result['code']:return result['code']
    return 0

