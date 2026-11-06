"""Name the next lifecycle command from recorded state; the hint never grants authority."""

DEFAULT_MISSION = '.mission'


def _report(action, argv, note, root, step=None, requires_user=False):
    command = list(argv)
    if command and root is not None and str(root) != DEFAULT_MISSION:
        command += ['--mission', str(root)]
    return {'action': action, 'step': step, 'argv': command, 'note': note, 'requires_user': requires_user,
            'advisory': True, 'retry_authorized': False}


def _active_step(contract, state, root):
    from .guidance import step_guidance
    for step in contract['steps']:
        if state['steps'].get(step['id'], {}).get('status') != 'in_progress':
            continue
        identifier = step['id']
        from .test_first import needs_red
        if needs_red(contract, step, state['steps'][identifier]):
            return _report('red', ['red', '--step', identifier],
                           'Write the test, then show it fails before implementing. test-first-note records why not.', root, identifier)
        guidance = step_guidance(contract, state, step, True)
        pending = guidance['missing_assessments'] + guidance['unverified_assessments']
        if pending:
            argv = ['assess', '--step', identifier, '--check', str(pending[0]), '--verdict', 'VERDICT', '--rationale', 'TEXT']
            return _report('assess', argv, 'Inspect the actual result, then record an evidence-based verdict.', root, identifier)
        return _report('verify', ['verify', '--step', identifier], 'Finish the work first; verify runs the declared checks.', root, identifier)
    return None


def _open_step(contract, state, root):
    from .guidance import step_guidance
    for step in contract['steps']:
        identifier = step['id']
        action = step_guidance(contract, state, step, False)['suggested_action']
        if action == 'inspect_recovery':
            return _report('inspect_recovery', ['recovery', '--step', identifier],
                           'Inspect files and external outcomes before any retry.', root, identifier)
        if action == 'wait_for_approval':
            digest = state['steps'][identifier]['approval_request']['digest']
            argv = ['approve', '--step', identifier, '--digest', digest, '--rationale', 'TEXT']
            return _report('wait_for_user_decision', argv,
                           "Show the request and wait. Run approve or deny only with the user's explicit reply.",
                           root, identifier, requires_user=True)
        if action == 'inspect_then_revalidate':
            return _report('revalidate', ['start', '--step', identifier, '--revalidate'],
                           'Run checks only; do not repeat the work.', root, identifier)
        if action == 'inspect_then_start':
            return _report('start', ['start', '--step', identifier],
                           'Inspect the current workspace first. Exit 3 means a user decision is required.', root, identifier)
    return None


def _review_step(contract, state, root):
    reviews = state.get('acceptance_reviews', {})
    for item in contract.get('acceptance', []) if contract['schema_version'] == 3 else []:
        if reviews.get(item['id'], {}).get('verdict') != 'supported':
            argv = ['criterion-review', '--criterion', item['id'], '--verdict', 'VERDICT', '--rationale', 'TEXT',
                    '--evidence-ref', 'check:STEP:INDEX']
            for kind in item.get('evidence_kinds', []):
                argv += ['--evidence-kind', kind]
            return _report('criterion_review', argv, 'Inspect `coverage`, then record what the evidence shows.', root)
    return None


def next_action(contract, state, root=None):
    from .reports import goal_review_status
    stop = state.get('stop_reason')
    if stop == 'done_verified':
        if goal_review_status(state) == 'missing':
            return _report('goal_review', ['goal-review', '--verdict', 'VERDICT', '--rationale', 'TEXT'],
                           'Compare the combined outcome with the original goal.', root)
        open_paths = sorted(name for name, record in state.get('scope_observations', {}).items() if record.get('status') == 'open')
        if open_paths:
            argv = ['scope-note', '--path', open_paths[0], '--disposition', 'mine|not_mine|unknown', '--rationale', 'TEXT']
            return _report('scope_note', argv, 'Inspect the observed change, then record a statement; it is not proof.', root)
        note = 'Report the final label, evidence and unresolved work.'
        unconfirmed = [name for name, entry in state['steps'].items()
                       if (entry.get('discipline_outcome') or {}).get('red_green') == 'unconfirmed']
        if unconfirmed:
            note += ' Name each step whose test did not fail first, and why: unconfirmed red/green: ' + ', '.join(unconfirmed) + '.'
        if goal_review_status(state) == 'pass' and contract.get('discipline') == 'strict':
            note += ' Before any push, commit the result and run gate --commit SHA; it is read-only and proves content, not authorship.'
        return _report('report_outcome', [], note, root)
    if stop:
        return _report('inspect_stop_reason', [], 'Stopped as ' + stop + '. Report it; resume only when the user asks.',
                       root, requires_user=True)
    found = _active_step(contract, state, root) or _open_step(contract, state, root)
    if found:
        return found
    if all(state['steps'].get(step['id'], {}).get('status') == 'completed' for step in contract['steps']):
        if contract['schema_version'] == 3:
            from .coverage import stale_steps
            stale = stale_steps(contract, state)
            if stale:
                return _report('revalidate', ['start', '--step', stale[0], '--revalidate'],
                               'A later step changed its files: rerun its checks, then review its criteria again.', root, stale[0])
        return _review_step(contract, state, root) or _report('finish', ['finish'], 'Finish checks current coverage.', root)
    return _report('ask_user', [], 'No step can run: inspect denials, budgets and dependencies, then report them.',
                   root, requires_user=True)


def print_hint(contract, state, root):
    """Stdout stays stable for parsers; the hint goes to stderr."""
    import shlex
    import sys
    report = next_action(contract, state, root)
    target = shlex.join(report['argv']) if report['argv'] else 'no command (' + report['action'] + ')'
    print('next (advisory): ' + target + ' -- ' + report['note'], file=sys.stderr)
