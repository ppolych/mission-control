"""A bounded projection of the complete read-only handoff report."""
from collections import Counter


def compact_handoff(report):
    steps = report['steps']
    counts = dict(Counter(row['status'] for row in steps.values()))
    ready = None
    if not report.get('stop_reason') and not report['active_steps']:
        ready = next((key for key, row in steps.items()
                      if row['suggested_action'] in ('inspect_then_start', 'inspect_then_revalidate')), None)
    selected = list(report['active_steps'])
    if ready is not None:
        selected.append(ready)
    ranked = sorted(steps, key=lambda key: (
        steps[key]['status'] == 'completed',
        steps[key]['suggested_action'] not in ('inspect_recovery', 'wait_for_approval', 'respect_denial')))
    for key in ranked:
        if len(selected) >= 5:
            break
        if key not in selected:
            selected.append(key)
    keys = ('installation', 'mission_directory', 'workspace', 'contract_hash',
            'journal_head', 'active_steps', 'stop_reason', 'goal_review_status', 'next_action', 'reminder')
    result = {key: report[key] for key in keys}
    result.update(compact=True, step_counts=counts, next_ready_step=ready,
                  steps={key: steps[key] for key in selected},
                  omitted_steps=len(steps) - len(selected),
                  pending_approval_count=len(report['pending_approvals']),
                  retry_authorized=False)
    return result
