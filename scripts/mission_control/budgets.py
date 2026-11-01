

def step_budget_exhausted(contract,state):
    """True only when a step budget prevents progress and no ready work remains."""
    per_step=contract.get('budget',{}).get('max_attempts_per_step',2)
    exhausted=False
    for step in contract['steps']:
        entry=state['steps'].get(step['id'],{})
        if entry.get('status')=='completed':continue
        if entry.get('status')=='in_progress':return False
        eligible=not entry.get('approval_denied') and (entry.get('needs_revalidation') or entry.get('attempts',0)<per_step)
        if not eligible:exhausted=True
        if eligible and all(state['steps'].get(d,{}).get('status')=='completed'
                            for d in step.get('depends_on',[])):return False
    return exhausted

