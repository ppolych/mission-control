import datetime


def goal_review_status(state):
    """Report whether the required combined-outcome review exists."""
    review = state.get('goal_review')
    if review:return review.get('verdict')
    return 'missing' if state.get('stop_reason') == 'done_verified' else 'not_applicable'


def metrics_report(contract, state, root):
    """Deterministic projection; never invent host usage or human interventions."""
    from .publication import digest
    events=state.get('journal') if contract['schema_version']==3 else None
    counts=None
    transitions=[]
    if events is not None:
        counts={}
        previous=None
        for event in events:
            action=event['action'];counts[action]=counts.get(action,0)+1
            reason=event.get('stop_reason')
            if reason and reason!=previous:
                transitions.append({'sequence':event['sequence'],'exit_label':reason})
            previous=reason
    duration=None
    if events:
        try:duration=max(0,(datetime.datetime.fromisoformat(state['last_update'])-datetime.datetime.fromisoformat(events[0]['timestamp'])).total_seconds())
        except (ValueError,KeyError,TypeError):pass
    identity=events[-1]['hash'] if events else digest(state)
    return {'mission_id':str(root.resolve()),'exit_id':identity,
            'ended_at':state.get('last_update'),'exit_label':state.get('stop_reason'),
            'attempts_used':state['attempts'],
            'revalidations':sum(e.get('revalidations',0) for e in state['steps'].values()),
            'event_counts':counts,'terminal_transitions':transitions,
            'goal_review_passed':state.get('goal_review',{}).get('verdict')=='pass',
            'duration_seconds':duration,'tokens_used':None,'interventions':None,'source':'checkpoint_and_journal'}


def handoff_report(contract, state, root):
    from .guidance import installation_identity, step_guidance
    active_step_present=any(entry.get('status')=='in_progress' for entry in state['steps'].values())
    steps={}
    for step in contract['steps']:
        entry=state['steps'].get(step['id'],{})
        steps[step['id']]={key:entry.get(key) for key in
            ('status','attempts','needs_revalidation','recovery_required','approval_denied')}
        steps[step['id']]['status']=entry.get('status','pending')
        steps[step['id']]['depends_on']=step.get('depends_on',[])
        steps[step['id']].update(step_guidance(contract, state, step, active_step_present))
    return {'installation': installation_identity(), 'mission_directory': str(root.resolve()),
            'goal':contract['mission'],'constraints':contract.get('constraints',[]),
            'workspace':state.get('workspace'),'contract_hash':state['contract_hash'],
            'checkpoint':str((root/'state/progress.json').resolve()),
            'decision_log':str((root/'decision-log.md').resolve()),
            'lessons':str((root/'lessons.md').resolve()),
            'journal_head':(state.get('journal') or [{}])[-1].get('hash'),
            'active_steps':[key for key,value in steps.items() if value['status']=='in_progress'],
            'steps':steps,'stop_reason':state.get('stop_reason'),'goal_review_status':goal_review_status(state),
            'pending_approvals':{key:entry['approval_request'] for key,entry in state['steps'].items() if entry.get('status')=='awaiting_approval'},
            'approved_digests':{key:record['digest'] for key,record in state.get('approved_steps',{}).items()},
            'evidence_refs':{key:[{'check':e.get('check'),'code':e.get('code')} for e in entry.get('evidence',[])] for key,entry in state['steps'].items()},
            'reminder':'Reinspect current workspace and evidence; use recovery for uncertain work. This summary grants no approval and starts no work.'}

