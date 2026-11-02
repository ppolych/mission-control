"""Optional strict discipline: stronger step outcomes for contracts that declare it."""

MANUAL_LABEL = 'manual_evidence_only: agent assessment, not automated verification'
EXEMPT_KINDS = ('docs', 'config', 'exploratory', 'low_impact', 'not_reproducible', 'not_applicable')
AUTOMATED_KINDS = {'behavior', 'integration'}
TRIVIAL_EXECUTABLES = {'true', ':', '/bin/true', '/usr/bin/true'}
TRIVIAL_SCRIPTS = {'true', ':', 'exit 0'}
STRICT_STEP_FIELDS = {'test_first', 'test_first_exempt', 'manual_only'}
SHELLS = {'sh', 'bash', 'zsh', 'dash', '/bin/sh', '/bin/bash', '/bin/zsh', '/bin/dash'}


def is_strict(contract):
    return contract.get('schema_version') == 3 and contract.get('discipline') == 'strict'


def is_trivial_check(check):
    """A finite list of always-true commands; passing it says nothing about check quality."""
    kind, *args = check
    if kind == 'exec':
        return args[0].strip() in TRIVIAL_SCRIPTS
    if kind == 'test':
        return len(args) == 1
    if kind != 'exit0':
        return False
    if len(args) == 1:
        return args[0] in TRIVIAL_EXECUTABLES
    return len(args) == 3 and args[0] in SHELLS and args[1] == '-c' and args[2].strip() in TRIVIAL_SCRIPTS


def nonblank(value):
    return isinstance(value, str) and bool(value.strip())


def validate_draft_fields(contract):
    """Field values only new drafts must meet; frozen contracts are not rechecked."""
    if 'discipline' in contract and contract['schema_version'] != 3:
        raise ValueError('discipline requires schema_version 3')
    if 'discipline' in contract and contract['discipline'] != 'strict':
        raise ValueError('discipline must be "strict" when present')
    if 'discipline' not in contract:
        for step in contract['steps']:
            found = STRICT_STEP_FIELDS & set(step)
            if found:
                raise ValueError(step['id'] + ': ' + ', '.join(sorted(found)) + ' requires discipline: strict')


def validate_exemption(step):
    value = step['test_first_exempt']
    if (not isinstance(value, dict) or set(value) != {'kind', 'reason'} or value['kind'] not in EXEMPT_KINDS
            or not nonblank(value['reason'])):
        raise ValueError(step['id'] + ': test_first_exempt needs kind (' + ', '.join(EXEMPT_KINDS) + ') and a nonblank reason')


def validate_manual_only(step):
    automated = [check for check in step['verify'] if isinstance(check, list)]
    if 'manual_only' in step:
        value = step['manual_only']
        if not isinstance(value, dict) or set(value) != {'reason'} or not nonblank(value['reason']):
            raise ValueError(step['id'] + ': manual_only needs a nonblank reason why no automated check is possible')
        if automated:
            raise ValueError(step['id'] + ': manual_only contradicts an automated check; remove one of them')
    elif not automated:
        raise ValueError(step['id'] + ': a step with only manual checks must declare manual_only with its reason')


def validate_discipline(contract):
    """Structural strict rules; a contract without the field is left exactly as before."""
    if not is_strict(contract):
        return
    from .test_first import validate_test_first
    for step in contract['steps']:
        for check in step['verify']:
            if isinstance(check, list) and is_trivial_check(check):
                raise ValueError(step['id'] + ': trivially true check is not evidence: ' + ' '.join(check))
        validate_manual_only(step)
        if 'test_first_exempt' in step:
            validate_exemption(step)
        validate_test_first(step)
        if step['effects']['writes'] and not {'test_first', 'test_first_exempt'} & set(step):
            raise ValueError(step['id'] + ': a step that writes must declare test_first or test_first_exempt')


def changed_writes(step, entry, workspace):
    """Declared writes that differ from the baseline of the first attempt."""
    from .observations import artifact_observations
    baseline = entry.get('first_effect_baseline', entry.get('effect_baseline', {}))
    current = artifact_observations(workspace, step['effects']['writes'])
    return sorted(name for name, observed in current.items() if baseline.get(name) != observed)


def evidence_basis(step):
    if 'manual_only' in step:
        return {'evidence_basis': MANUAL_LABEL, 'manual_only_reason': step['manual_only']['reason']}
    return {'evidence_basis': 'automated'}


def step_outcome(contract, state, step, entry, args):
    """Refuse an unproven outcome before checks run; return what verification records."""
    claimed = getattr(args, 'already_satisfied', False)
    if not is_strict(contract):
        if claimed:
            raise ValueError('--already-satisfied requires discipline: strict')
        return None
    if entry.get('revalidating'):
        if claimed:
            raise ValueError('--already-satisfied does not apply to checks-only revalidation')
        return None
    changed = changed_writes(step, entry, state['workspace'])
    result = evidence_basis(step)
    if 'test_first_exempt' in step:
        result['test_first_exempt'] = step['test_first_exempt']
    if claimed:
        if not nonblank(args.rationale):
            raise ValueError('--already-satisfied requires a nonblank --rationale')
        if changed:
            raise ValueError('--already-satisfied refused: declared writes changed: ' + ', '.join(changed))
        if 'test_first' in step:
            result['red_green'] = 'not_applicable_no_change'
        return dict(result, outcome='no_change', rationale=args.rationale)
    if step['effects']['writes'] and not changed:
        raise ValueError('no declared write changed since this step began; do the work, or if the requested state '
                         'already exists use verify --already-satisfied --rationale TEXT')
    if 'test_first' in step:
        from .test_first import red_green_status
        result.update(red_green_status(step, entry, state['workspace']))
    return dict(result, outcome='changed' if changed else 'no_declared_writes')


def require_automated_evidence(contract, step_by_id, kinds, refs):
    """Behavior and integration claims must point at a check the controller ran."""
    if not is_strict(contract) or not AUTOMATED_KINDS & set(kinds):
        return
    for ref in refs:
        if ref.startswith('check:'):
            identifier, index = ref[6:].rsplit(':', 1)
            checks = step_by_id[identifier]['verify'] if identifier in step_by_id else []
            if index.isdigit() and int(index) < len(checks) and isinstance(checks[int(index)], list):
                return
    raise ValueError('behavior or integration evidence needs a check:STEP:INDEX reference to an automated check; '
                     'an assessment or file reference is not automated evidence')


def print_outcome(entry):
    import sys
    outcome = entry.get('discipline_outcome')
    if outcome and outcome['evidence_basis'] != 'automated':
        print(outcome['evidence_basis'] + ' (' + outcome['manual_only_reason'] + ')', file=sys.stderr)


def validate_discipline_state(state):
    for entry in state['steps'].values():
        for key in ('discipline_outcome', 'first_effect_baseline', 'red'):
            if key in entry and not isinstance(entry[key], dict):
                raise ValueError('invalid checkpoint discipline record: ' + key)
