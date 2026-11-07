"""Say whether a commit is what the recorded evidence covers; never a sandbox or a proof of authorship."""
import json

from .git_read import GitError, null_separated, repository_prefix, run_git, text

DOES_NOT_CERTIFY = (
    'Checks are not rerun; this relies on the recorded verification.',
    'Quality of the work or of the tests is not judged.',
    'A local mission does not prove who wrote a commit: certification covers content, not who wrote it.',
    'Local hooks can be bypassed; this is not a sandbox.')
MISMATCH_DETAIL = 'Commit content differs from the verified receipt; git filters or line-ending conversion can also cause this.'
UNPROVABLE = {'directory': 'unverified_directory', 'metadata': 'unverified_metadata_only'}


def capture_base(workspace):
    try:
        head = text(run_git(workspace, 'rev-parse', '--verify', '-q', 'HEAD', ok=(0, 1)))
    except GitError as error:
        return {'status': 'unavailable', 'reason': str(error)}
    return {'status': 'commit', 'commit': head} if head else {'status': 'empty'}


def begin_mission(contract, state, workspace, root):
    """Record the starting commit; a revision keeps its parent's base and unresolved observations."""
    from .scope_check import covered
    from .settings import MAX_STATE_BYTES
    from .store import read_bounded
    parent_path = root / 'lineage/parent-progress.json'
    if not parent_path.exists():
        state['mission_base'] = capture_base(workspace)
        return
    parent = json.loads(read_bounded(parent_path, MAX_STATE_BYTES)[0].decode('utf-8-sig'))
    state['mission_base'] = parent.get('mission_base', capture_base(workspace))
    lineage = set(parent.get('lineage_writes', []))
    parent_contract_path = root / 'lineage/parent-contract.json'
    if parent_contract_path.exists():
        parent_contract = json.loads(read_bounded(parent_contract_path, MAX_STATE_BYTES)[0].decode('utf-8-sig'))
        for step in parent_contract.get('steps', []):
            if parent.get('steps', {}).get(step['id'], {}).get('attempts', 0) > 0:
                lineage.update(step.get('effects', {}).get('writes', []))
    if lineage:
        state['lineage_writes'] = sorted(lineage)
    writes = declared_writes(contract)
    kept = {name: record for name, record in parent.get('scope_observations', {}).items() if not covered(name, writes)}
    if kept:
        state['scope_observations'] = kept


def declared_writes(contract):
    return sorted({name for step in contract['steps'] for name in step['effects']['writes']})


def declared_uncommitted(contract):
    return {name for step in contract['steps'] for name in step['effects'].get('uncommitted', [])}


def latest_receipts(contract, state):
    """The most recent verification of each path decides, because later steps can rewrite it."""
    receipts = {}
    for step in contract['steps']:
        entry = state['steps'].get(step['id'], {})
        evidence = entry.get('evidence') or [{}]
        when = evidence[-1].get('timestamp', '')
        for name, value in entry.get('verified_artifacts', {}).items():
            if name not in receipts or when >= receipts[name][0]:
                receipts[name] = (when, value)
    return {name: value for name, (_, value) in receipts.items()}


def tree_entry(workspace, commit, full_path):
    """Return (mode, object) or None, refusing to look through a link in any parent."""
    parts = full_path.split('/')
    for depth in range(1, len(parts) + 1):
        partial = '/'.join(parts[:depth])
        output = null_separated(run_git(workspace, 'ls-tree', '-z', '--full-tree', commit, '--', partial))
        if not output:
            return None
        mode, _, identity = output[0].split('\t')[0].split(' ')
        if mode in ('120000', '160000') or depth == len(parts):
            return mode, identity
    return None


def blob_result(workspace, identity, mode, receipt):
    import hashlib
    from .settings import MAX_OBSERVED_BYTES
    size = int(text(run_git(workspace, 'cat-file', '-s', identity)))
    if size > MAX_OBSERVED_BYTES:
        return 'unverified_oversized'
    content = run_git(workspace, 'cat-file', 'blob', identity).stdout
    executable = mode == '100755'
    same = hashlib.sha256(content).hexdigest() == receipt['sha256'] and executable == bool(receipt['mode'] & 0o100)
    return 'content_match' if same else 'content_mismatch'


def absent_result(workspace, name):
    ignored = run_git(workspace, 'check-ignore', '-q', '--', name, ok=(0, 1), literal=False).returncode == 0
    return 'ignored_not_in_commit' if ignored else 'not_in_commit'


def artifact_result(workspace, prefix, commit, name, receipt, uncommitted):
    """Exactly one result per declared path; only what the receipt can prove may pass."""
    entry = tree_entry(workspace, commit, prefix + name)
    if entry and entry[0] == '120000':
        return 'unverified_symlink'
    if entry and entry[0] == '160000':
        return 'unverified_gitlink'
    if name in uncommitted:
        return 'unexpected_in_commit' if entry else 'out_of_commit_not_certified'
    if not receipt or receipt.get('status') not in ('present', 'absent'):
        return 'missing_receipt'
    if receipt['status'] == 'absent':
        return 'content_mismatch' if entry else 'deletion_match'
    if receipt.get('kind') in UNPROVABLE:
        return UNPROVABLE[receipt['kind']]
    if not entry:
        return absent_result(workspace, name)
    if entry[0] not in ('100644', '100755'):
        return 'content_mismatch'
    return blob_result(workspace, entry[1], entry[0], receipt)


PASSING_ARTIFACTS = ('content_match', 'deletion_match', 'out_of_commit_not_certified')


def resolve_commit(workspace, value):
    if value.startswith('-'):
        raise ValueError('--commit must name a commit')
    run_git(workspace, 'cat-file', '-e', value)
    return text(run_git(workspace, 'rev-parse', '--verify', '-q', value + '^{commit}', ok=(0, 1))) or None


def pushed_range_problems(contract, state, workspace, commit, prefix, remote_sha):
    """A push may carry only commits after the base; the base itself must already be on the remote."""
    base = state.get('mission_base', {})
    if base.get('status') != 'commit':
        return []
    start = base['commit']
    if not remote_sha.strip('0'):
        if not text(run_git(workspace, 'for-each-ref', '--count=1', 'refs/remotes')):
            empty = text(run_git(workspace, 'hash-object', '-t', 'tree', '--stdin'))
            names = null_separated(run_git(workspace, 'diff', '--name-only', '-z', '--no-renames', '--no-ext-diff', empty, commit))
            return no_change_problems(contract, state, names, prefix)
        if text(run_git(workspace, 'for-each-ref', '--count=1', '--contains', start, 'refs/remotes')):
            return []
    elif run_git(workspace, 'cat-file', '-e', remote_sha + '^{commit}', ok=(0, 1, 128)).returncode:
        return [{'reason': 'remote_commit_unknown', 'detail': 'The remote commit is not available here, so the pushed range cannot be judged.'}]
    elif not run_git(workspace, 'merge-base', '--is-ancestor', start, remote_sha, ok=(0, 1)).returncode:
        return []
    return [{'reason': 'commits_before_mission', 'base': start,
             'detail': 'This push carries the recorded base or earlier commits, which were made before the mission began.'}]


def no_change_problems(contract, state, names, prefix):
    """A path a no-change step claims was already satisfied cannot also be new since the base."""
    from .scope_check import covered
    changed, unchanged = set(), set()
    for step in contract['steps']:
        outcome = state['steps'].get(step['id'], {}).get('discipline_outcome', {}).get('outcome')
        (unchanged if outcome == 'no_change' else changed).update(step['effects']['writes'])
    # A revision inherits writes whose work started in a parent mission under the same base.
    changed.update(state.get('lineage_writes', []))
    paths = sorted(name for name in names if name.startswith(prefix) and covered(name[len(prefix):], unchanged)
                   and not covered(name[len(prefix):], changed))
    if paths:
        return [{'reason': 'no_change_step_changed_path', 'paths': paths, 'ownership': 'unverified',
                 'detail': 'A step recorded no change, but these paths differ from the recorded base, and no step of this '
                           'mission or a parent revision started work on them, so the work predates its verification.'}]
    return []


def range_problems(contract, state, workspace, commit, prefix, root):
    from .scope_check import covered, excluded, mission_relative
    base = state.get('mission_base', {})
    if base.get('status') == 'commit':
        start = base['commit']
        run_git(workspace, 'cat-file', '-e', start + '^{commit}')
        if run_git(workspace, 'merge-base', '--is-ancestor', start, commit, ok=(0, 1)).returncode:
            return [{'reason': 'base_not_ancestor', 'detail': 'The recorded base is not an ancestor of this commit.'}]
    elif base.get('status') == 'empty':
        start = text(run_git(workspace, 'hash-object', '-t', 'tree', '--stdin'))
    else:
        return [{'reason': 'no_base', 'detail': 'No starting commit was recorded for this mission.'}]
    names = null_separated(run_git(workspace, 'diff', '--name-only', '-z', '--no-renames', '--no-ext-diff', start, commit))
    writes = declared_writes(contract)
    mission = mission_relative(root, workspace)
    problems = no_change_problems(contract, state, names, prefix)
    outside = []
    for name in names:
        relative = name[len(prefix):] if name.startswith(prefix) else None
        if relative is None or not (covered(relative, writes) or excluded(relative, mission)):
            outside.append(name)
    if outside:
        problems.append({'reason': 'outside_scope', 'paths': sorted(outside), 'ownership': 'unverified',
                         'detail': 'Paths changed since the recorded base are not declared writes; who changed them is unknown. '
                                   'Do not drop a needed file to pass: report the result as not certified, or declare the '
                                   'path as a write through revise and verify it in the new mission.'})
    return problems


def scope_summary(contract, state):
    missing = {}
    for step in contract['steps']:
        check = state['steps'].get(step['id'], {}).get('scope_check')
        if not check:
            missing[step['id']] = 'no scope check recorded'
        elif check.get('status') != 'performed':
            missing[step['id']] = check.get('reason', 'not performed')
    if missing:
        return {'status': 'not_performed', 'steps': missing,
                'notice': 'Scope was not fully observed; absence of observations here means nothing.'}
    return {'status': 'performed', 'notice': 'Observed through git only; not a sandbox.'}


def mission_problems(contract, state):
    from .approvals import validate_approval_workspace
    from .coverage import coverage_report
    from .scope_check import scope_report
    problems = []
    if state.get('stop_reason') != 'done_verified':
        problems.append({'reason': 'not_done_verified', 'detail': 'stop_reason is ' + str(state.get('stop_reason'))})
    if state.get('goal_review', {}).get('verdict') != 'pass':
        problems.append({'reason': 'goal_review_not_passed', 'detail': 'A passing goal review is required.'})
    validate_approval_workspace(state)
    if not coverage_report(contract, state)['all_supported']:
        problems.append({'reason': 'coverage_not_current', 'detail': 'Acceptance coverage is unmet, unverified or stale.'})
    unresolved = scope_report(contract, state)['open']
    if unresolved:
        problems.append({'reason': 'open_scope_observation', 'paths': unresolved, 'ownership': 'unverified',
                         'detail': 'Inspect them and record scope-note, or publish a revision. A note is a statement, not proof.'})
    return problems


def step_labels(contract, state):
    labels = {}
    for step in contract['steps']:
        outcome = state['steps'].get(step['id'], {}).get('discipline_outcome')
        if outcome:
            labels[step['id']] = {key: outcome[key] for key in ('outcome', 'evidence_basis', 'red_green', 'test_first_exempt') if key in outcome}
    return labels


def base_report(certified, result, problems, **extra):
    return dict({'certified': certified, 'result': result, 'not_certified': problems,
                 'does_not_certify': list(DOES_NOT_CERTIFY)}, **extra)


def no_mission_report():
    return base_report(False, 'not_certified', [{'reason': 'no_mission', 'detail': 'No initialized mission was found.'}],
                       scope_check={'status': 'not_performed'})


def gate_report(contract, state, commit_value, root, remote_sha=None):
    """Return (exit code, report); exit 2 comes from raised errors, never from a refusal."""
    from .discipline import is_strict
    if not is_strict(contract):
        return 1, base_report(False, 'not_certified', [{'reason': 'discipline_not_strict', 'detail': 'gate needs discipline: strict.'}],
                              scope_check={'status': 'not_performed'})
    problems = mission_problems(contract, state)
    scope = scope_summary(contract, state)
    labels = step_labels(contract, state)
    if commit_value is None:
        return (int(bool(problems)), base_report(False, 'not_certified' if problems else 'mission_state_only', problems, scope_check=scope,
                                                 step_labels=labels, not_evaluated=['commit_content', 'commit_range']))
    workspace = state['workspace']
    prefix = repository_prefix(workspace)
    commit = resolve_commit(workspace, commit_value)
    if commit is None:
        problems.append({'reason': 'not_a_commit', 'detail': commit_value + ' does not resolve to a commit.'})
        return 1, base_report(False, 'not_certified', problems, scope_check=scope, step_labels=labels)
    if scope['status'] != 'performed':
        problems.append({'reason': 'scope_check_not_performed', 'steps': scope['steps'],
                         'detail': 'The scope check did not complete, so it cannot count as passed.'})
    problems.extend(range_problems(contract, state, workspace, commit, prefix, root))
    if remote_sha is not None:
        problems.extend(pushed_range_problems(contract, state, workspace, commit, prefix, remote_sha))
    receipts = latest_receipts(contract, state)
    uncommitted = declared_uncommitted(contract)
    artifacts = []
    for name in declared_writes(contract):
        result = artifact_result(workspace, prefix, commit, name, receipts.get(name), uncommitted)
        item = {'path': name, 'result': result}
        if result == 'content_mismatch':
            item['detail'] = MISMATCH_DETAIL
        artifacts.append(item)
        if result not in PASSING_ARTIFACTS:
            problems.append({'reason': result, 'path': name})
    certified = not problems
    return int(not certified), base_report(
        certified, 'certified' if certified else 'not_certified', problems, commit=commit, artifacts=artifacts, scope_check=scope,
        step_labels=labels, out_of_commit_not_certified=[item['path'] for item in artifacts if item['result'] == 'out_of_commit_not_certified'])
