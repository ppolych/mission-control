import os, signal, subprocess


def supervised_process(cmd,cwd,quiet,timeout):
    process=subprocess.Popen(cmd,cwd=cwd,stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL if quiet else None,stderr=subprocess.DEVNULL if quiet else None,
        start_new_session=True)
    try:
        try:status=process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            try:os.killpg(process.pid,signal.SIGTERM)
            except ProcessLookupError:pass
            try:process.wait(timeout=.2)
            except subprocess.TimeoutExpired:pass
            raise
        return subprocess.CompletedProcess(cmd,status)
    finally:
        # Verification must not leave asynchronous work running after completion.
        try:os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        process.wait()

