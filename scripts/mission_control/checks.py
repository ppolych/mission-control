import os, subprocess
from pathlib import Path


def run_check(check, quiet=False, cwd=None, timeout=None, index=None):
    """Return normalized verification status separately from process status."""
    from .processes import supervised_process
    from .validation import check_args
    check_args(check)
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
            if kind=='grep':cmd=['grep','-q','--',*args]
            elif kind=='exec':cmd=['bash','-o','pipefail','-c',args[0]]
            elif kind=='test':cmd=['test',*args]
            else:cmd=args
            process=supervised_process(cmd,cwd,quiet,limit)
            status=process.returncode
            result['command_exit_status']=status
            result['code']=int(status!=0)
            if status<0:
                result['signal']=-status;result['error_type']='signal'
            elif kind in ('grep','test') and status>1:
                result['code']=2;result['error_type']=kind+'_error'
    except subprocess.TimeoutExpired:
        result['code']=2;result['error_type']='timeout'
    except OSError as error:
        result['code']=2;result['error_type']=type(error).__name__
    details=[] if index is None else ['check '+str(index)]
    if result['error_type']=='timeout':details.append(f'timeout after {limit:g}s')
    elif result['signal']:details.append('signal '+str(result['signal']))
    elif result['error_type'] and result['command_exit_status'] is None:details.append(result['error_type'])
    elif result['code'] and result['command_exit_status'] is not None:details.append('exit '+str(result['command_exit_status']))
    suffix=' ('+', '.join(details)+')' if details else ''
    print(('PASS' if result['code']==0 else 'FAIL')+': '+kind+suffix)
    return result


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

