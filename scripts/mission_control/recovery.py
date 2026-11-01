

def recovery_report(contract, state, step):
    from .approvals import validate_approval_workspace
    from .observations import artifact_observations
    from .publication import digest
    if contract['schema_version'] != 3:raise ValueError('recovery reports require schema 3')
    validate_approval_workspace(state)
    entry = state['steps'].get(step['id'], {})
    baseline = entry.get('effect_baseline', {})
    current = artifact_observations(state['workspace'], step['effects']['writes'])
    files = {}
    for name, observed in current.items():
        old = baseline.get(name)
        classification = ('unavailable' if observed['status'] == 'unavailable' or old is None
                          or old.get('status') == 'unavailable' else
                          'unchanged' if old == observed else 'changed')
        files[name] = {'before': old, 'current': observed, 'classification': classification}
    last_verification = entry.get('evidence', []) or next(
        (record['evidence'] for record in reversed(entry.get('history', [])) if record.get('evidence')), [])
    report = {'step': step['id'], 'workspace': state['workspace'],
              'contract_hash': state['contract_hash'], 'attempts': entry.get('attempts', 0),
              'step_status': entry.get('status', 'pending'),
              'needs_revalidation': entry.get('needs_revalidation', False),
              'reconciliation_sequence': len(entry.get('recovery_history', [])),
              'recovery_required': entry.get('recovery_required', False), 'files': files,
              'external_actions': step['effects']['external_actions'],
              'external_result': 'unknown' if step['effects']['external_actions'] or step['effects']['network'] != 'none' else 'not_declared',
              'last_verification': last_verification,
              'notice': 'File hashes do not prove external actions occurred or succeeded; operator reconciliation is required.'}
    report['digest'] = digest(report)
    return report


def reconcile_recovery(contract, state, step, args):
    from .publication import now
    entry = state['steps'].get(step['id'], {})
    if state.get('stop_reason'):raise ValueError('resume mission before recovery reconciliation')
    if not entry.get('recovery_required') or entry.get('status') == 'in_progress':
        raise ValueError('recover requires interrupted work awaiting reconciliation')
    if any(e.get('status') == 'in_progress' for e in state['steps'].values()):raise ValueError('another step active')
    report = recovery_report(contract, state, step)
    if args.digest != report['digest']:raise ValueError('recovery report changed; inspect and use the current digest')
    if not args.rationale or not args.rationale.strip():raise ValueError('recovery needs an evidence-linked rationale')
    if args.resolution == 'applied_incorrect':
        # Only a failure of the latest attempt counts; older failures describe older work.
        if not entry.get('failed_verification'):
            raise ValueError('applied_incorrect requires a failed verification; inspect interrupted work and use another resolution')
        effects = step['effects']
        if effects['external_actions'] or not effects['reversible']:
            raise ValueError('applied_incorrect refuses external or irreversible effects; a corrective attempt could repeat them')
    resolved = args.resolution in ('completed', 'not_applied', 'applied_incorrect')
    if resolved and any(f['classification'] == 'unavailable' for f in report['files'].values()):
        raise ValueError('unavailable files require inspection; recovery cannot be declared resolved')
    entry.setdefault('recovery_history', []).append({
        'resolution': args.resolution, 'rationale': args.rationale, 'timestamp': now(),
        'report_digest': args.digest, 'report': report})
    entry['recovery_required'] = not resolved
    entry['status'] = 'pending' if resolved else 'blocked'
    if resolved:entry['needs_revalidation'] = args.resolution == 'completed'

