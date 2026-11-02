from pathlib import Path
from .lifecycle_rules import STEP_STATUSES, STOP_REASONS


def check_args(check):
    if not isinstance(check,list) or not check or not all(isinstance(x,str) for x in check):
        raise ValueError('check must be a nonempty string argv array')
    if any('\x00' in arg for arg in check):raise ValueError('check arguments cannot contain NUL')
    kind,*args=check
    arity={'file':1,'not_file':1,'grep':2,'exec':1}
    if kind not in (*arity,'exit0','test'):raise ValueError('unknown check: '+kind)
    if kind in arity and len(args)!=arity[kind]:raise ValueError('invalid check arity: '+kind)
    if kind in ('exit0','test') and not args:raise ValueError('missing command or expression')
    if kind=='exit0' and not args[0]:raise ValueError('empty executable')
    if kind in ('file','not_file','grep') and not args[-1]:raise ValueError('empty filesystem path')


def validate(c):
    from .approvals import validate_policy
    from .contract import validate_advanced
    if not isinstance(c,dict) or type(c.get('schema_version')) is not int or c['schema_version'] not in (2,3):
        raise ValueError('expected schema_version 2 or 3 object; migrate legacy contracts')
    if not isinstance(c.get('mission'),str) or not c['mission'].strip():raise ValueError('mission required')
    steps=c.get('steps')
    if not isinstance(steps,list) or not steps:raise ValueError('steps must be nonempty array')
    validate_policy(c)
    ids=[]
    for step in steps:
        if not isinstance(step,dict) or not isinstance(step.get('id'),str) or not step['id']:raise ValueError('invalid step identifier')
        ids.append(step['id'])
        if not isinstance(step.get('description',''),str):raise ValueError('invalid description')
        deps=step.get('depends_on',[])
        if not isinstance(deps,list) or not all(isinstance(d,str) for d in deps):raise ValueError('dependencies must be string array')
        if 'verify_timeout' in step:
            limit=step['verify_timeout']
            if type(limit) not in (int,float) or not 0<limit<=86400:raise ValueError('verify_timeout must be 1..86400 seconds')
        checks=step.get('verify')
        if not isinstance(checks,list) or not checks:raise ValueError('verify must be nonempty array')
        for check in checks:
            if isinstance(check,dict):
                if set(check)!={'manual'} or not isinstance(check['manual'],str) or not check['manual'].strip():raise ValueError('invalid manual criterion')
            else:check_args(check)
    if len(ids)!=len(set(ids)):raise ValueError('duplicate step identifiers')
    # Kahn traversal avoids Python recursion limits on long valid missions.
    remaining={step['id']:set(step.get('depends_on',[])) for step in steps}
    followers={identifier:[] for identifier in ids}
    for identifier,deps in remaining.items():
        for dep in deps:
            if dep not in followers:raise ValueError('unknown dependency: '+dep)
            followers[dep].append(identifier)
    ready=[identifier for identifier,deps in remaining.items() if not deps]
    visited=0
    while ready:
        identifier=ready.pop();visited+=1
        for child in followers[identifier]:
            remaining[child].remove(identifier)
            if not remaining[child]:ready.append(child)
    if visited!=len(ids):raise ValueError('dependency cycle')
    budget=c.get('budget',{})
    if not isinstance(budget,dict) or set(budget)-{'max_attempts_per_step','max_iterations','no_progress_threshold'}:raise ValueError('invalid budget keys')
    for v in budget.values():
        if type(v)!=int or v<1:raise ValueError('budgets must be positive integers')
    if 'constraints' in c and (not isinstance(c['constraints'],list) or not all(isinstance(x,str) for x in c['constraints'])):
        raise ValueError('constraints must be string array')
    validate_advanced(c)
    from .discipline import validate_discipline
    validate_discipline(c)


def validate_step_records(entry):
    """Stored records reach reports, so their element types must be checked here."""
    def records(values):
        if not all(isinstance(item,dict) for item in values):raise ValueError('invalid checkpoint evidence record')
    records(entry.get('evidence',[]))
    records(entry.get('history',[]))
    for record in entry.get('history',[]):
        if not isinstance(record.get('evidence',[]),list) or not isinstance(record.get('manual',{}),dict):
            raise ValueError('invalid checkpoint history record')
        records(record.get('evidence',[]))
    if not isinstance(entry.get('recovery_history',[]),list):raise ValueError('invalid recovery history')
    records(entry['recovery_history'] if 'recovery_history' in entry else [])
    for key in ('effect_baseline','input_baseline','verified_artifacts'):
        values=entry.get(key,{})
        if not isinstance(values,dict) or not all(isinstance(item,dict) for item in values.values()):
            raise ValueError('invalid checkpoint observation record')


def validate_state(state,contract):
    """Reject malformed local state before lifecycle operations can mutate it."""
    from .approvals import validate_approval_state
    from .revisions import validate_advanced_state
    def counter(value):return type(value)==int and value>=0
    if not isinstance(state,dict) or not isinstance(state.get('steps'),dict) or not counter(state.get('attempts')):
        raise ValueError('invalid checkpoint structure or attempt count')
    ids={step['id'] for step in contract['steps']}
    if set(state['steps'])-ids:raise ValueError('unknown checkpoint step')
    active=0
    for entry in state['steps'].values():
        if not isinstance(entry,dict):raise ValueError('invalid checkpoint step')
        if entry.get('status','pending') not in STEP_STATUSES:raise ValueError('invalid step status')
        active+=entry.get('status')=='in_progress'
        for key in ('attempts','revalidations'):
            if not counter(entry.get(key,0)):raise ValueError('invalid step counter')
        for key in ('manual','failures'):
            if not isinstance(entry.get(key,{}),dict):raise ValueError('invalid checkpoint mapping')
        if any(not counter(n) for n in entry.get('failures',{}).values()):raise ValueError('invalid failure count')
        for key in ('history','evidence'):
            if not isinstance(entry.get(key,[]),list):raise ValueError('invalid checkpoint evidence')
        for key in ('needs_revalidation','revalidating','budget_exhausted','failed_verification'):
            if key in entry and type(entry[key])!=bool:raise ValueError('invalid checkpoint flag')
        validate_step_records(entry)
        for assessment in entry.get('manual',{}).values():
            if (not isinstance(assessment,dict) or assessment.get('verdict') not in ('pass','fail','unverified')
                    or not isinstance(assessment.get('rationale'),str) or not assessment['rationale'].strip()):
                raise ValueError('invalid stored assessment')
    if not isinstance(state.get('goal_review_history',[]),list):raise ValueError('invalid goal review history')
    reviews=state.get('goal_review_history',[])+([state['goal_review']] if 'goal_review' in state else [])
    for review in reviews:
        if (not isinstance(review,dict) or review.get('verdict') not in ('pass','fail')
                or not isinstance(review.get('rationale'),str) or not review['rationale'].strip()):
            raise ValueError('invalid goal review')
    if active>1:raise ValueError('multiple active steps in checkpoint')
    if state.get('stop_reason') not in (None,*STOP_REASONS):
        raise ValueError('invalid stop reason')
    if 'workspace' in state and (not isinstance(state['workspace'],str) or not Path(state['workspace']).is_absolute()):
        raise ValueError('invalid stored workspace')
    validate_approval_state(state,contract)
    validate_advanced_state(state,contract)

