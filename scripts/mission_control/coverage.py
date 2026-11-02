

def coverage_basis(contract, state, criterion, evidence_refs, declared_steps=None):
    from .observations import artifact_observations, observations
    if declared_steps is None:
        from .contract_index import requirement_steps
        declared_steps = requirement_steps(contract).get(criterion, [])
    steps = {step['id']: state['steps'].get(step['id'], {}) for step in declared_steps}
    names = {ref[5:] for ref in evidence_refs if ref.startswith('file:')}
    watched = set()
    for step in declared_steps:
        names.update(step['effects']['writes'])
        watched.update(step.get('watch', []))
    artifacts = artifact_observations(state['workspace'], sorted(names - watched))
    artifacts.update(observations(state['workspace'], sorted(watched)))
    return {'steps': steps, 'artifacts': artifacts}


def coverage_signature(contract, state, criterion, evidence_refs, declared_steps=None):
    from .publication import digest
    return digest(coverage_basis(contract, state, criterion, evidence_refs, declared_steps))


def verification_artifacts(step, workspace):
    from .observations import artifact_observations, observations
    watched = step.get('watch', [])
    artifacts = artifact_observations(workspace, [name for name in step['effects']['writes'] if name not in watched])
    artifacts.update(observations(workspace, watched))
    return artifacts


def verification_is_current(step, state):
    entry = state['steps'].get(step['id'], {})
    if entry.get('status') != 'completed':return False
    current = verification_artifacts(step, state['workspace'])
    # Older schema-3 checkpoints with declared files need checks-only revalidation
    # to establish a receipt. No artifact declarations require no extra receipt.
    return not current or (entry.get('verified_artifacts') == current
                           and all(v['status'] != 'unavailable' for v in current.values()))


def coverage_report(contract, state, index=None):
    if contract['schema_version'] != 3:raise ValueError('acceptance coverage requires schema 3')
    from .contract_index import requirement_steps
    if index is None:index = requirement_steps(contract)
    rows = []
    for criterion in contract['acceptance']:
        declared_steps = index[criterion['id']]
        refs = [step['id'] for step in declared_steps]
        review = state.get('acceptance_reviews', {}).get(criterion['id'])
        current = (review and not (set(criterion.get('evidence_kinds',[]))-set(review.get('evidence_kinds',[])))
                   and review['signature'] == coverage_signature(contract, state, criterion['id'], review['evidence_refs'], declared_steps)
                   and all(verification_is_current(step, state) for step in declared_steps))
        rows.append(dict(criterion, steps=refs, status=review['verdict'] if current else 'unverified',
                         review=review, stale=bool(review and not current)))
    return {'criteria': rows, 'all_supported': all(row['status'] == 'supported' for row in rows)}


def record_criterion_review(contract, state, args):
    from .contract import text_list
    from .observations import observe_artifact, readable_observations
    from .publication import digest, now
    from .quality import evidence_kinds
    if contract['schema_version'] != 3:raise ValueError('criterion-review requires schema 3')
    if state.get('stop_reason'):raise ValueError('resume mission before criterion review')
    if args.criterion not in {item['id'] for item in contract['acceptance']}:
        raise ValueError('unknown acceptance criterion')
    if not args.rationale or not args.rationale.strip():raise ValueError('criterion review needs a nonblank rationale')
    refs = args.evidence_ref or []
    text_list(refs, 'evidence references')
    kinds=evidence_kinds(getattr(args,'evidence_kind',None) or [])
    required=next(item for item in contract['acceptance'] if item['id']==args.criterion).get('evidence_kinds',[])
    if args.verdict=='supported' and set(required)-set(kinds):raise ValueError('missing required evidence kind declarations')
    mapped = {step['id'] for step in contract['steps'] if args.criterion in step.get('acceptance_refs', [])}
    if args.verdict == 'supported':
        from .discipline import require_automated_evidence
        require_automated_evidence(contract, {step['id']: step for step in contract['steps'] if step['id'] in mapped}, kinds, refs)
    if args.verdict == 'supported':
        if not refs or any(state['steps'].get(identifier, {}).get('status') != 'completed' for identifier in mapped):
            raise ValueError('supported requires completed mapped steps and evidence references')
        if any(not verification_is_current(step, state) for step in contract['steps'] if step['id'] in mapped):
            raise ValueError('verification artifact evidence is missing or stale; resume and revalidate before supporting the criterion')
    for ref in refs:
        if ref.startswith('file:'):
            value = observe_artifact(state['workspace'], ref[5:])
            if value['status'] != 'present':raise ValueError('evidence file is not readable and present')
        elif ref.startswith('check:'):
            parts = ref[6:].rsplit(':', 1)
            if len(parts) != 2 or parts[0] not in mapped or not parts[1].isdigit():raise ValueError('invalid check evidence reference')
            if not any(e.get('check') == int(parts[1]) and e.get('code') == 0
                       for e in state['steps'].get(parts[0], {}).get('evidence', [])):
                raise ValueError('evidence reference does not name a passed check')
        else:raise ValueError('evidence refs must be file:RELATIVE_PATH or check:STEP:INDEX')
    basis = coverage_basis(contract, state, args.criterion, refs)
    if args.verdict == 'supported':readable_observations(basis['artifacts'])
    state.setdefault('acceptance_reviews', {})[args.criterion] = {
        'verdict': args.verdict, 'rationale': args.rationale, 'evidence_refs': refs, 'evidence_kinds':kinds,
        'timestamp': now(), 'signature': digest(basis), 'artifacts': basis['artifacts']}

