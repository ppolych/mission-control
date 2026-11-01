"""Read-only continuation hints; never confer execution authority."""
from pathlib import Path
from .settings import VERSION


def installation_identity():
    from .cache import engine_fingerprint
    return {'version': VERSION,
            'cli': str(Path(__file__).resolve().parents[1] / 'mission.py'),
            'engine_fingerprint': engine_fingerprint()}


def step_guidance(contract, state, step, active_step_present=None):
    from .budgets import attempts_per_step, mission_attempts
    entry = state['steps'].get(step['id'], {})
    status = entry.get('status', 'pending')
    dependencies = [name for name in step.get('depends_on', [])
                    if state['steps'].get(name, {}).get('status') != 'completed']
    missing = [i for i, check in enumerate(step['verify'])
               if isinstance(check, dict) and str(i) not in entry.get('manual', {})]
    unresolved = [i for i in range(len(step['verify']))
                  if entry.get('manual', {}).get(str(i), {}).get('verdict') == 'unverified']
    if entry.get('approval_denied'):
        action = 'respect_denial'
    elif state.get('stop_reason'):
        action = 'inspect_stop_reason'
    elif entry.get('recovery_required'):
        action = 'inspect_recovery'
    elif status == 'awaiting_approval':
        action = 'wait_for_approval'
    elif status == 'in_progress':
        action = 'assess' if missing or unresolved else 'verify'
    elif status == 'completed':
        action = 'inspect_goal_coverage'
    elif dependencies:
        action = 'complete_dependencies'
    elif (active_step_present if active_step_present is not None else
          any(value.get('status') == 'in_progress' for value in state['steps'].values())):
        action = 'complete_active_step'
    elif entry.get('needs_revalidation'):
        action = 'inspect_then_revalidate'
    elif (entry.get('budget_exhausted')
          or entry.get('attempts', 0) >= attempts_per_step(contract)
          or state['attempts'] >= mission_attempts(contract)):
        action = 'inspect_budget'
    else:
        action = 'inspect_then_start'
    return {'missing_assessments': missing, 'unverified_assessments': sorted(unresolved),
            'blocked_dependencies': dependencies, 'suggested_action': action,
            'retry_authorized': False}
