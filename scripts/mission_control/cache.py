import datetime, hashlib, json, os
from pathlib import Path
from .settings import VERSION, MAX_CACHE_BYTES


def analysis_binding(args):
    from .contract import text_list
    from .observations import observations, readable_observations
    from .publication import digest
    from .store import read_bounded
    if not args.source_root or not args.policy or not args.policy.strip() or len(args.policy)>256:
        raise ValueError('source-root and bounded nonblank policy required')
    queries=args.query or []
    if not queries or len(queries)>16 or not all(q.strip() and len(q)<=256 for q in queries):raise ValueError('bounded nonblank query required')
    names=args.input or []
    text_list(names,'analysis inputs',paths=True)
    if not names:raise ValueError('declare at least one input; implicit whole-workspace cache is unsafe')
    workspace=Path(args.source_root).resolve(strict=True)
    if not workspace.is_dir():raise ValueError('analysis workspace must be directory')
    observed=observations(str(workspace),sorted(names));readable_observations(observed)
    payload={'workspace':str(workspace),'query':queries,'policy':args.policy,
             'inputs':observed,'release':VERSION,
             'engine':engine_fingerprint()}
    return {'digest':digest(payload),'scope':payload}


def safe_derived_report(value):
    if not isinstance(value,dict):raise ValueError('derived report must be object')
    forbidden={'raw_logs','raw_payload','raw_chain_of_thought','approved_steps','approval_request','verified_artifacts','acceptance_reviews'}
    pending=[value];count=0
    while pending:
        item=pending.pop();count+=1
        if count>4096:raise ValueError('derived report structure too large')
        if isinstance(item,dict):
            if forbidden & set(item):raise ValueError('raw payload or lifecycle authority cannot be cached')
            pending.extend(item.values())
        elif isinstance(item,list):pending.extend(item)
    return value


def analysis_cache(args):
    from .publication import digest, now
    from .quality import aware_time
    from .storage import atomic, persistent_lock
    from .store import read_bounded
    if not 1<=args.max_age<=604800:raise ValueError('max-age must be 1..604800 seconds')
    binding=analysis_binding(args)
    if args.command=='analysis-key':return binding,0
    if not args.cache:raise ValueError('--cache required')
    target=Path(args.cache)
    if args.command=='cache-save':
        if any(value['status']!='present' for value in binding['scope']['inputs'].values()):raise ValueError('cache-save requires present declared inputs')
        if not args.report or not args.redacted:raise ValueError('cache-save requires a derived --report and explicit --redacted assertion')
        report=safe_derived_report(json.loads(read_bounded(Path(args.report),65536)[0].decode('utf-8-sig')))
        record={'format':1,'binding':binding,'report':report,'report_digest':digest(report),
                'created_at':now(),'advisory_only':True}
        if len(json.dumps(record,indent=2).encode('utf-8'))>MAX_CACHE_BYTES:raise ValueError('cache record too large')
        protect_cache_sources(target, args, binding)
        target.parent.mkdir(parents=True,exist_ok=True)
        with persistent_lock(target.with_name(target.name+'.lock')):
            if analysis_binding(args)!=binding:raise ValueError('analysis inputs changed while preparing cache; refresh from current sources')
            protect_cache_sources(target, args, binding)
            atomic(target,record)
        return {'decision':'saved','binding':binding['digest'],'advisory_only':True},0
    if not os.path.lexists(target):return {'decision':'refresh_required','reason':'missing_cache','advisory_only':True},1
    record=json.loads(read_bounded(target,MAX_CACHE_BYTES)[0].decode('utf-8-sig'))
    if not isinstance(record,dict) or record.get('format')!=1 or record.get('advisory_only') is not True:raise ValueError('invalid cache record')
    safe_derived_report(record.get('report'))
    if record.get('report_digest')!=digest(record['report']):raise ValueError('cached report digest mismatch')
    if not isinstance(record.get('binding'),dict) or record['binding'].get('digest')!=digest(record['binding'].get('scope')):
        raise ValueError('invalid cached binding')
    if not 1<=args.max_age<=604800:raise ValueError('max-age must be 1..604800 seconds')
    age=(datetime.datetime.now(datetime.timezone.utc)-aware_time(record.get('created_at'))).total_seconds()
    current_binding=analysis_binding(args)
    reusable=(current_binding==binding and record['binding']==binding and 0<=age<=args.max_age
              and all(value['status']=='present' for value in binding['scope']['inputs'].values()))
    result={'decision':'reuse_allowed' if reusable else 'refresh_required','advisory_only':True,
            'reason':'matching_scope_and_sources' if reusable else 'scope_sources_policy_engine_or_age_changed',
            'binding':binding['digest'],'approval_granted':False,'execution_enabled':False}
    if reusable:result['report']=record['report']
    return result,int(not reusable)


def engine_fingerprint():
    from .store import read_bounded
    root = Path(__file__).resolve().parent
    paths = [root.parent / 'mission.py', *sorted(root.glob('*.py'))]
    engine = hashlib.sha256()
    for path in paths:
        engine.update(path.relative_to(root.parent).as_posix().encode())
        engine.update(b'\0')
        engine.update(read_bounded(path, 1048576)[0])
        engine.update(b'\0')
    return engine.hexdigest()

def protect_cache_sources(target, args, binding):
    """Reject output aliases of inputs, reports, or installed implementation."""
    package = Path(__file__).resolve().parent
    protected = [Path(args.report), package.parent / 'mission.py',
                 package.parent.parent / 'VERSION', *package.glob('*.py')]
    workspace = Path(binding['scope']['workspace'])
    protected.extend(workspace / name for name in binding['scope']['inputs'])
    for output in (target, target.with_name(target.name + '.lock')):
        for source in protected:
            if output.resolve() == source.resolve():
                raise ValueError('cache output or lock aliases a protected source')
            if output.exists() and source.exists() and output.samefile(source):
                raise ValueError('cache output or lock aliases a protected source')
