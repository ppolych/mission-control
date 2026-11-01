import datetime


def evidence_kinds(value):
    from .contract import text_list
    text_list(value,'evidence kinds')
    if set(value)-{'existence','content','behavior','integration','manual'}:raise ValueError('unknown evidence kind')
    return value


def evidence_audit(contract,state):
    from .coverage import coverage_report
    from .traceability import traceability_report
    from .contract_index import requirement_steps
    index=requirement_steps(contract)
    report=coverage_report(contract,state,index)
    rows=[]
    for criterion in report['criteria']:
        declared=(criterion.get('review') or {}).get('evidence_kinds',[])
        missing=sorted(set(criterion.get('evidence_kinds',[]))-set(declared))
        gaps=[]
        if missing:gaps.append('missing_expected_kind')
        if criterion['status']!='supported':gaps.append('missing_unmet_or_stale_review')
        rows.append({'criterion':criterion['id'],'required_kinds':criterion.get('evidence_kinds',[]),
            'declared_kinds':declared,'missing_kinds':missing,'coverage_status':criterion['status'],
            'gaps':gaps,'sufficient':not gaps})
    return {'criteria':rows,'all_sufficient':all(row['sufficient'] for row in rows),
            'traceability':traceability_report(contract,index),
            'advisory_only':True,'warning':'Kinds are reviewer declarations, not automatic semantic proof. No score or approval is granted.'}


def diagnose_report(contract,state):
    from .guidance import installation_identity, step_guidance
    active_step_present=any(entry.get('status')=='in_progress' for entry in state['steps'].values())
    rows=[]
    for step in contract['steps']:
        entry=state['steps'].get(step['id'],{})
        failure=next((item for item in entry.get('evidence',[]) if item.get('code')),None)
        kind='unknown';disposition='inspect_evidence';next_check='Inspect current step evidence and unmet requirement.'
        if entry.get('approval_denied'):
            kind='user_denied';disposition='respect_denial';next_check='No retry in this revision; review scope with the user.'
        elif entry.get('status')=='awaiting_approval':
            kind='policy_blocked';disposition='wait_for_decision';next_check='Present current approval request; do not self-approve.'
        elif failure:
            error=failure.get('error_type')
            if error=='FileNotFoundError':kind='command_unavailable';next_check='Inspect executable availability and the declared command.'
            elif error=='PermissionError':kind='environment_or_policy_blocked';next_check='Inspect host permissions; do not bypass them.'
            elif error=='timeout':kind='execution_timeout';next_check='Inspect external outcomes; timeout does not prove not applied.'
            elif error=='signal':kind='signal_termination'
            elif error:kind='execution_error'
            else:
                identity=failure.get('identity',[])
                kind='manual_unmet' if isinstance(identity,dict) else 'evidence_missing' if identity and identity[0]=='file' else 'command_failed'
            disposition='replan_first'
        elif entry.get('status')=='completed':kind='no_recorded_failure';disposition='inspect_goal_coverage'
        elif entry.get('status')=='in_progress':kind='incomplete_input_or_work';disposition='complete_active_attempt'
        if entry.get('recovery_required') and not entry.get('approval_denied'):
            disposition='inspect_recovery_first';next_check='Obtain current recovery report; reconcile observed outcome before retry.'
        rows.append({'step':step['id'],'kind':kind,'disposition':disposition,
                     'check':failure.get('check') if failure else None,'next_check':next_check,
                     'retry_authorized':False, **step_guidance(contract,state,step,active_step_present)})
    return {'installation':installation_identity(), 'steps':rows,'advisory_only':True,
            'warning':'Classification uses recorded facts; no stderr parsing, automatic diagnosis, approval or retry.'}


def aware_time(value):
    if not isinstance(value,str):raise ValueError('timezone-aware ISO timestamp required')
    parsed=datetime.datetime.fromisoformat(value.replace('Z','+00:00'))
    if parsed.tzinfo is None:raise ValueError('timestamp needs timezone')
    return parsed


def lesson_audit(record,as_of=None):
    if not isinstance(record,dict) or not all(isinstance(record.get(k),str) and record[k].strip() for k in ('lesson_id','context','statement')):
        raise ValueError('lesson needs id, context and statement')
    entries=record.get('evidence')
    if not isinstance(entries,list) or len(entries)>256:raise ValueError('invalid lesson evidence')
    effects={'supports':0,'weakens':0,'contradicts':0,'stales':0};ids=set()
    for item in entries:
        if (not isinstance(item,dict) or item.get('effect') not in effects
                or not all(isinstance(item.get(k),str) and item[k].strip() for k in ('id','source_ref'))):
            raise ValueError('invalid lesson evidence reference')
        if item['id'] in ids:raise ValueError('duplicate lesson evidence ID')
        ids.add(item['id']);effects[item['effect']]+=1
    stamp=aware_time(as_of) if as_of is not None else datetime.datetime.now(datetime.timezone.utc)
    reasons=[]
    if record.get('last_checked') is not None:
        age=(stamp-aware_time(record['last_checked'])).total_seconds()
        if age<0 or age>30*86400:reasons.append('last_check_stale_or_future')
    else:reasons.append('last_check_unknown')
    for name in ('weakens','contradicts','stales'):
        if effects[name]:reasons.append(name)
    status='unsupported' if not effects['supports'] else 'needs_review' if reasons else 'supported_observations'
    return {'lesson_id':record['lesson_id'],'context':record['context'],'status':status,
            'effects':effects,'reasons':reasons,'as_of':stamp.isoformat(),'advisory_only':True,
            'warning':'Evidence is caller-described. Recheck owning sources; no automatic confidence score, instruction override or promotion.'}

