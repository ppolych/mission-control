"""Read-only git calls with a scrubbed environment; never used to change a repository."""
import os

GIT_TIMEOUT_SECONDS = 30


class GitError(ValueError):
    """Git could not answer; callers must not treat this as a clean result."""


def run_git(workspace, *args, ok=(0,)):
    import subprocess
    # A hook sets GIT_DIR and similar variables that would redirect these reads.
    environment = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
    environment['GIT_OPTIONAL_LOCKS'] = '0'
    # core.fsmonitor can name a command to run from repository configuration.
    command = ['git', '-C', str(workspace), '--literal-pathspecs', '-c', 'core.fsmonitor=false',
               '-c', 'status.submoduleSummary=false', *args]
    try:
        result = subprocess.run(command, capture_output=True, env=environment, stdin=subprocess.DEVNULL,
                                timeout=GIT_TIMEOUT_SECONDS)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise GitError('git could not run: ' + type(error).__name__) from error
    if result.returncode not in ok:
        raise GitError('git ' + args[0] + ' failed: ' + os.fsdecode(result.stderr).strip()[:200])
    return result


def text(result):
    return os.fsdecode(result.stdout).strip()


def null_separated(result):
    return [os.fsdecode(item) for item in result.stdout.split(b'\0') if item]


def repository_prefix(workspace):
    """Path of the workspace inside its repository, ending in / unless it is the top."""
    return text(run_git(workspace, 'rev-parse', '--show-prefix'))
