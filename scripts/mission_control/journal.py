from .settings import MAX_JOURNAL_EVENTS


def state_fingerprint(state):
    from .publication import digest
    return digest({k: v for k, v in state.items() if k != 'journal'})


def validate_journal(state, contract):
    from .approvals import valid_digest
    from .publication import digest
    if contract['schema_version'] != 3:return
    if 'contract_hash' not in state and 'journal' not in state:return  # init only
    events = state.get('journal')
    if not isinstance(events, list) or not events or len(events)>MAX_JOURNAL_EVENTS:raise ValueError('missing schema-3 transition journal')
    previous = None
    for index, event in enumerate(events, 1):
        if (not isinstance(event, dict) or type(event.get('sequence')) is not int
                or event['sequence'] != index or event.get('previous') != previous
                or not isinstance(event.get('action'), str)
                or not isinstance(event.get('timestamp'), str)
                or not valid_digest(event.get('state_hash'))
                or event.get('hash') != digest({k: v for k, v in event.items() if k != 'hash'})):
            raise ValueError('invalid transition journal chain')
        previous = event['hash']
    if events[-1]['state_hash'] != state_fingerprint(state):raise ValueError('checkpoint differs from committed journal state')


def commit_state(path, state, contract, args):
    from .publication import digest, now
    from .storage import atomic
    if contract['schema_version'] == 3:
        state['last_update'] = now()
        events = state.setdefault('journal', [])
        if len(events)>=MAX_JOURNAL_EVENTS:raise ValueError('journal event limit reached; preserve this mission and create a linked revision')
        event = {'sequence': len(events) + 1, 'action': args.command, 'step': args.step,
                 'timestamp': state['last_update'], 'previous': events[-1]['hash'] if events else None,
                 'state_hash': state_fingerprint(state), 'attempts': state['attempts'],
                 'step_status': state['steps'].get(args.step, {}).get('status'),
                 'stop_reason': state.get('stop_reason')}
        for key in ('criterion', 'verdict', 'resolution', 'check'):
            if getattr(args, key, None) is not None:event[key] = getattr(args, key)
        event['hash'] = digest(event)
        events.append(event)
    atomic(path, state)

