"""Budget defaults and the exhaustion rule."""
DEFAULT_MAX_ATTEMPTS_PER_STEP = 2
DEFAULT_NO_PROGRESS_THRESHOLD = 2


def attempts_per_step(contract):
    return contract.get('budget', {}).get('max_attempts_per_step', DEFAULT_MAX_ATTEMPTS_PER_STEP)


def no_progress_threshold(contract):
    return contract.get('budget', {}).get('no_progress_threshold', DEFAULT_NO_PROGRESS_THRESHOLD)


def mission_attempts(contract):
    return contract.get('budget', {}).get('max_iterations', max(10, 3 * len(contract['steps'])))


def step_budget_exhausted(contract, state):
    """True only when a step budget prevents progress and no ready work remains."""
    per_step = attempts_per_step(contract)
    exhausted = False
    for step in contract['steps']:
        entry = state['steps'].get(step['id'], {})
        if entry.get('status') == 'completed':
            continue
        if entry.get('status') == 'in_progress':
            return False
        eligible = not entry.get('approval_denied') and (entry.get('needs_revalidation') or entry.get('attempts', 0) < per_step)
        if not eligible:
            exhausted = True
        if eligible and all(state['steps'].get(name, {}).get('status') == 'completed' for name in step.get('depends_on', [])):
            return False
    return exhausted
