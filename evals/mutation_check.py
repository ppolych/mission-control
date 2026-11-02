#!/usr/bin/env python3
"""Break one safety invariant at a time in a scratch copy; the test suite must notice."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = 'scripts/mission_control/'
# name, file, original text, replacement. Each must be caught by at least one test.
MUTANTS = (
    ('approval_always_valid', 'approvals.py', "return record.get('digest') == approval_digest(contract, step, state.get('workspace'))", 'return True'),
    ('digest_ignores_workspace', 'approvals.py', "'step_id': step['id'], 'workspace': workspace}", "'step_id': step['id']}"),
    ('receipt_always_current', 'coverage.py', "if entry.get('status') != 'completed':return False", "return entry.get('status') == 'completed'"),
    ('journal_ignores_state', 'journal.py', "if events[-1]['state_hash'] != state_fingerprint(state):raise ValueError('checkpoint differs from committed journal state')", 'pass'),
    ('lock_follows_symlink', 'storage.py', 'os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK', 'os.O_RDWR | os.O_CREAT | os.O_NONBLOCK'),
    ('no_process_group_kill', 'processes.py', 'try:os.killpg(process.pid,signal.SIGKILL)', 'try:pass'),
    ('attempts_not_counted', 'lifecycle_start.py', "state['attempts'] += 1", 'pass'),
    ('denial_can_be_resumed', 'lifecycle_stop.py', "if entry.get('approval_denied'):\n            continue", 'if False:\n            continue'),
    ('recovery_gate_removed', 'lifecycle_start.py', "raise ValueError('inspect recovery report and reconcile before retry or revalidation')", 'pass'),
    ('observation_follows_symlink', 'observations.py', 'fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)', 'fd = os.open(parts[-1], os.O_RDONLY | os.O_NONBLOCK, dir_fd=directory)'),
    ('tree_follows_symlinks', 'observations.py', 'info = item.stat(follow_symlinks=False)', 'info = item.stat(follow_symlinks=True)'),
    ('goal_pass_ignores_evidence', 'lifecycle_stop.py', "raise ValueError('acceptance evidence changed; cannot record a passing goal review')", 'pass'),
    ('circuit_never_opens', 'services.py', "if len(record['failures'])>=3 or record['until'] or retry_after:", 'if False:'),
    ('unknown_fields_allowed', 'contract.py', "    if names:\n        raise ValueError('unknown contract fields", "    if False:\n        raise ValueError('unknown contract fields"),
    ('stale_failure_accepted', 'recovery.py', "if not entry.get('failed_verification'):", 'if False:'),
    ('corrective_retry_ignores_network', 'recovery.py', "if report['external_result'] != 'not_declared' or not step['effects']['reversible']:", "if step['effects']['external_actions'] or not step['effects']['reversible']:"),
    ('tree_limit_after_full_read', 'observations.py', "                if count > MAX_TREE_ENTRIES:\n                    raise OverflowError('directory_too_large')\n                items.append(item)", "                items.append(item)\n        if count > MAX_TREE_ENTRIES:\n            raise OverflowError('directory_too_large')"),
    ('next_action_ignores_stop', 'next_action.py', "    if stop:\n", "    if False:\n"),
    ('no_change_proof', 'discipline.py', "if step['effects']['writes'] and not changed:", 'if False:'),
    ('already_satisfied_ignores_change', 'discipline.py', "        if changed:\n            raise ValueError('--already-satisfied refused", "        if False:\n            raise ValueError('--already-satisfied refused"),
    ('manual_evidence_unlabelled', 'discipline.py', "return {'evidence_basis': MANUAL_LABEL, 'manual_only_reason': step['manual_only']['reason']}", "return {'evidence_basis': 'automated'}"),
    ('behavior_accepts_assessment', 'discipline.py', "isinstance(checks[int(index)], list)", 'True'),
    ('first_baseline_overwritten', 'lifecycle_start.py', "entry.setdefault('first_effect_baseline', entry['effect_baseline'])", "entry['first_effect_baseline'] = entry['effect_baseline']"),
    ('red_accepts_a_pass', 'test_first.py', '    if status == 0:\n', '    if False:\n'),
    ('red_ignores_failure_reason', 'test_first.py', 'if pattern is not None and not re.search(pattern, output):', 'if False:'),
    ('red_after_implementation', 'test_first.py', "if started and 'red' not in entry:", 'if False:'),
    ('verify_ignores_test_change', 'test_first.py', "if observations(workspace, step['test_first']['test_paths']) != red['test_digests']:", 'if False:'),
    ('note_confirms_red', 'test_first.py', "return {'red_green': 'unconfirmed', 'test_first_notes': notes}", "return {'red_green': 'confirmed', 'test_first_notes': notes}"),
    ('scope_ignores_changes', 'scope_check.py', "if start['paths'].get(name) == end['paths'].get(name) and not in_commit:", 'if True:'),
    ('dedicated_never_refuses', 'scope_check.py', "if names and contract.get('workspace_isolation') == 'dedicated':", 'if False:'),
    ('note_outlives_content', 'scope_check.py', "return record['status'] if path_digest(workspace, name) == record['digest'] else 'open'", "return record['status']"),
    ('unknown_closes_observation', 'scope_check.py', "'unknown': 'open'}", "'unknown': 'stated_not_mine'}"),
    ('scope_path_limit_removed', 'scope_check.py', 'if len(items) > MAX_SCOPE_PATHS:', 'if False:'),
    ('fsmonitor_allowed', 'git_read.py', "'--literal-pathspecs', '-c', 'core.fsmonitor=false',", "'--literal-pathspecs',"),
    ('git_environment_kept', 'git_read.py', "environment = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}", 'environment = dict(os.environ)'),
    ('repeat_without_lock', 'cli_aux.py', "with persistent_lock(path.with_name(path.name + '.lock'), wait=REPEAT_LOCK_WAIT_SECONDS):", 'if True:'),
)
# A second identical check guards these, so one removal changes no behavior.
EQUIVALENT = {
    'store_compare_and_swap': 'store.py rechecks the same base hash just before replacing the file',
    'cache_alias_resolve': 'cache.py also rejects aliases with samefile',
    'lock_file_type': 'fdopen already refuses a FIFO lock as not seekable before the regular-file check',
}


def tracked_files():
    names = subprocess.run(['git', 'ls-files', '--cached', '--others', '--exclude-standard'], cwd=ROOT,
                           capture_output=True, text=True, check=True).stdout.splitlines()
    return [name for name in names if (ROOT / name).is_file()]


def run_mutant(mutant, names):
    name, relative, original, replacement = mutant
    with tempfile.TemporaryDirectory() as temporary:
        copy = Path(temporary) / 'repo'
        for item in names:
            target = copy / item
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / item, target)
        path = copy / PACKAGE / relative
        text = path.read_text(encoding='utf-8')
        if text.count(original) != 1:
            return name, 'not_applied', 'expected one match, found ' + str(text.count(original))
        path.write_text(text.replace(original, replacement), encoding='utf-8')
        environment = {key: value for key, value in os.environ.items() if key != 'MISSION_RANDOM_SEEDS'}
        result = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-f'], cwd=copy,
                                capture_output=True, text=True, env=environment)
        if result.returncode == 0:
            return name, 'survived', ''
        caught = [line for line in result.stderr.splitlines() if line.startswith(('FAIL:', 'ERROR:'))]
        return name, 'caught', caught[0] if caught else 'nonzero exit'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--jobs', type=int, default=min(4, os.cpu_count() or 1))
    parser.add_argument('--only', action='append', help='run only this mutant; repeatable')
    args = parser.parse_args()
    known = {mutant[0] for mutant in MUTANTS}
    unknown = sorted(set(args.only or ()) - known)
    if unknown:
        parser.error('unknown mutant: ' + ', '.join(unknown))
    selected = [mutant for mutant in MUTANTS if not args.only or mutant[0] in args.only]
    names = tracked_files()
    with ThreadPoolExecutor(args.jobs) as pool:
        results = list(pool.map(lambda mutant: run_mutant(mutant, names), selected))
    for name, outcome, detail in results:
        print(f'{outcome:12} {name}  {detail[:90]}')
    for name, reason in EQUIVALENT.items():
        print(f'{"equivalent":12} {name}  {reason}')
    bad = [name for name, outcome, _ in results if outcome != 'caught']
    print(f'{len(results) - len(bad)} of {len(results)} caught')
    return int(bool(bad))


if __name__ == '__main__':
    sys.exit(main())
