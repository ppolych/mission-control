"""Command-line definition for the Mission Control controller."""
import argparse

COMMAND_GROUPS = (
    ('Lifecycle', ('validate', 'init', 'start', 'red', 'test-first-note', 'assess', 'verify', 'block', 'stop', 'resume',
                   'criterion-review', 'finish', 'goal-review')),
    ('Controlled mode', ('approve', 'deny')),
    ('Recovery and revision', ('recovery', 'recover', 'revision-diff', 'revise', 'migrate', 'scope-note')),
    ('Read-only reports', ('status', 'history', 'coverage', 'metrics', 'handoff', 'evidence-audit',
                           'diagnose', 'gate', 'impact', 'lessons-search', 'lesson-audit', 'store-read',
                           'service-status')),
    ('Auxiliary stores', ('store-publish', 'service-probe', 'service-record',
                          'analysis-key', 'cache-save', 'cache-check')),
)
COMMANDS = [command for _, group in COMMAND_GROUPS for command in group]
FLAGS = (
    ('--mission', {'default': '.mission', 'help': 'mission directory (default: .mission)'}),
    ('--contract', {'help': 'contract file for validate, init, revise or revision-diff'}),
    ('--step', {'help': 'step ID from the contract'}),
    ('--destination', {'help': 'new directory for migrate or revise'}),
    ('--reason', {'help': 'stop label, block diagnosis or revision reason'}),
    ('--context', {'default': 'default', 'help': 'tactic label used by repeat-failure detection'}),
    ('--check', {'type': int, 'help': 'zero-based index of a manual check for assess'}),
    ('--verdict', {'choices': ['pass', 'fail', 'supported', 'unmet', 'unverified'],
                   'help': 'assess: pass/fail/unverified; goal-review: pass/fail; '
                           'criterion-review: supported/unmet/unverified'}),
    ('--rationale', {'help': 'evidence-based reason; required to resume a human_abort stop'}),
    ('--revalidate', {'action': 'store_true', 'help': 'start for checks only; do not repeat work'}),
    ('--already-satisfied', {'action': 'store_true',
                             'help': 'verify, strict only: the requested state already existed; needs --rationale'}),
    ('--workspace', {'help': 'workspace to pin at init (default: current directory)'}),
    ('--digest', {'help': 'digest from the current approval request or recovery report'}),
    ('--criterion', {'help': 'acceptance ID for criterion-review'}),
    ('--evidence-ref', {'action': 'append', 'help': 'file:RELATIVE_PATH or check:STEP:INDEX'}),
    ('--resolution', {'choices': ['completed', 'not_applied', 'applied_incorrect', 'partial', 'unknown'],
                      'help': 'Allowed resolution after inspection: completed (checks only), '
                              'not_applied (nothing happened; new attempt), applied_incorrect '
                              '(failed verification; new corrective attempt), partial or unknown '
                              '(stay blocked)'}),
    ('--path', {'help': 'observed workspace-relative path for scope-note'}),
    ('--disposition', {'choices': ['mine', 'not_mine', 'unknown'],
                       'help': 'scope-note: a recorded statement about an observed path, not proof'}),
    ('--commit', {'help': 'gate: commit to compare with the recorded evidence'}),
    ('--lessons-root', {'help': 'known lessons directory to search'}),
    ('--query', {'action': 'append', 'help': 'search or analysis query'}),
    ('--limit', {'type': int, 'default': 10, 'help': 'maximum search results'}),
    ('--offset', {'type': int, 'default': 0, 'help': 'search results to skip'}),
    ('--diverse', {'action': 'store_true', 'help': 'prefer nonredundant search results'}),
    ('--store', {'help': 'shared store file'}),
    ('--content', {'help': 'file holding content to publish'}),
    ('--base-hash', {'help': 'store digest read before editing'}),
    ('--health-file', {'help': 'service health record file'}),
    ('--service', {'help': 'service name'}),
    ('--outcome', {'choices': ['success', 'transient', 'terminal'], 'help': 'observed service outcome'}),
    ('--http-status', {'type': int, 'help': 'derive the outcome from an HTTP status'}),
    ('--retry-after', {'type': float, 'help': 'seconds the service asked to wait'}),
    ('--source-root', {'help': 'source directory for impact or analysis commands'}),
    ('--symbol', {'help': 'symbol to locate with impact'}),
    ('--evidence-kind', {'action': 'append', 'help': 'proof type declared by a criterion review'}),
    ('--record', {'help': 'lesson record file for lesson-audit'}),
    ('--as-of', {'help': 'ISO timestamp for lesson-audit'}),
    ('--policy', {'help': 'analysis policy label'}),
    ('--input', {'action': 'append', 'help': 'declared analysis input path'}),
    ('--cache', {'help': 'analysis cache file'}),
    ('--report', {'help': 'derived report file for cache-save'}),
    ('--redacted', {'action': 'store_true', 'help': 'assert the cached report holds no raw payloads'}),
    ('--max-age', {'type': int, 'default': 86400, 'help': 'cache age limit in seconds'}),
    ('--compact', {'action': 'store_true', 'help': 'handoff only: at most five step rows'}),
)


def build_parser():
    groups = '\n'.join(f'  {name}: {", ".join(commands)}' for name, commands in COMMAND_GROUPS)
    epilog = ('Commands:\n' + groups + '\n\n'
              'Normal flow: validate, init, start, work, assess, verify, criterion-review, finish, goal-review.\n'
              'Exit codes: 0 success; 1 refusal, check failure or exhausted work; '
              '2 invalid input or transition; 3 waiting for a controlled-step decision.\n'
              'Wrappers: verify.sh runs ad hoc checks; no_progress.sh records repeated calls.\n'
              'VERIFY_TIMEOUT sets the default check timeout (60 seconds); step verify_timeout overrides it.\n'
              'See references/commands-lifecycle.md and the other command references.')
    parser = argparse.ArgumentParser(prog='mission.py', epilog=epilog,
                                     formatter_class=argparse.RawDescriptionHelpFormatter,
                                     usage='%(prog)s COMMAND [options]')
    parser.add_argument('command', choices=COMMANDS, metavar='COMMAND', help='see the command list below')
    for name, options in FLAGS:
        parser.add_argument(name, **options)
    return parser


def reject_misplaced_flags(args):
    if args.compact and args.command != 'handoff':
        raise ValueError('--compact is only for handoff')
    if args.already_satisfied and args.command != 'verify':
        raise ValueError('--already-satisfied is only for verify')
    if args.commit and args.command != 'gate':
        raise ValueError('--commit is only for gate')
    if args.digest and args.command not in ('approve', 'deny', 'recover'):
        raise ValueError('--digest is only for approve, deny or recover')
    if args.contract and args.command not in ('init', 'validate', 'revise', 'revision-diff'):
        raise ValueError('--contract is only for init, validate or revision commands; lifecycle uses the stored contract')
    if args.workspace and args.command not in ('init', 'resume'):
        raise ValueError('--workspace is only for init or legacy resume')
    if args.command == 'assess' and args.verdict not in ('pass', 'fail', 'unverified'):
        raise ValueError('assess requires pass, fail or unverified')
    if args.command == 'goal-review' and args.verdict not in ('pass', 'fail'):
        raise ValueError('goal-review requires pass or fail')
    if args.command == 'criterion-review' and args.verdict not in ('supported', 'unmet', 'unverified'):
        raise ValueError('criterion-review requires supported, unmet or unverified')
    if args.command == 'recover' and not args.resolution:
        raise ValueError('recover requires --resolution')
