import argparse, hashlib, json, os
from pathlib import Path
from .settings import VERSION, MAX_STATE_BYTES, MAX_JOURNAL_EVENTS


def main(argv):
    if argv==['--version'] or (len(argv)==2 and argv[0] in ('checks','repeat') and argv[1]=='--version'):
        print('Mission Control '+VERSION);return 0
    from .approvals import exhaustion_reason, has_approval, record_decision, request_approval, requires_approval, validate_approval_workspace
    from .budgets import step_budget_exhausted
    from .cache import analysis_cache
    from .checks import run_check, verify
    from .coverage import coverage_report, record_criterion_review, verification_artifacts
    from .impact import impact_report
    from .journal import commit_state
    from .lessons import lessons_search
    from .observations import observations, readable_observations, watched_inputs
    from .publication import digest, now, publish_migration
    from .quality import diagnose_report, evidence_audit, lesson_audit
    from .recovery import reconcile_recovery, recovery_report
    from .reports import handoff_report, metrics_report
    from .revisions import publish_revision, revision_diff
    from .services import service_operation
    from .storage import atomic, persistent_lock
    from .store import publish_store, read_bounded, store_snapshot
    from .validation import validate, validate_state
    timeout=float(os.environ.get('VERIFY_TIMEOUT','60'))
    if not 0 < timeout < float('inf'):raise ValueError('VERIFY_TIMEOUT must be finite and positive')
    if argv and argv[0]=='checks':
        if len(argv)>1 and argv[1]=='--single':return verify(argv[2:])
        return verify(argv[1:],split=True)
    if argv and argv[0]=='repeat':
        if len(argv)<2:raise ValueError('repeat requires a subcommand')
        cmd,*args=argv[1:]; path=Path(os.environ.get('NO_PROGRESS_STATE','.mission/state/call_hashes.txt'))
        threshold=int(os.environ.get('NO_PROGRESS_THRESHOLD','2'))
        if threshold<1:raise ValueError('threshold must be positive')
        rows=json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() and cmd!='reset' else []
        if not isinstance(rows,list):raise ValueError('invalid repeat history')
        if cmd=='reset':atomic(path,[]);return 0
        if cmd=='history':print(json.dumps(rows,indent=2));return 0
        if cmd not in ('record','check') or not args:raise ValueError('expected record/check tool args')
        key=hashlib.sha256(json.dumps(args).encode()).hexdigest()
        if cmd=='record':rows.append(key);atomic(path,rows)
        return int(rows.count(key)>=threshold)
    ap=argparse.ArgumentParser();ap.add_argument('command',choices=['validate','init','status','start','verify','block','resume','finish','migrate','assess','stop','goal-review','approve','deny','coverage','criterion-review','recovery','recover','revision-diff','revise','history','metrics','handoff','lessons-search','store-read','store-publish','service-status','service-probe','service-record','impact','evidence-audit','diagnose','lesson-audit','analysis-key','cache-save','cache-check']);ap.add_argument('--mission',default='.mission');ap.add_argument('--contract');ap.add_argument('--step');ap.add_argument('--destination');ap.add_argument('--reason');ap.add_argument('--context',default='default');ap.add_argument('--check',type=int);ap.add_argument('--verdict',choices=['pass','fail','supported','unmet','unverified']);ap.add_argument('--rationale');ap.add_argument('--revalidate',action='store_true');ap.add_argument('--workspace');ap.add_argument('--digest');ap.add_argument('--criterion');ap.add_argument('--evidence-ref',action='append');ap.add_argument('--resolution',choices=['completed','not_applied','partial','unknown']);ap.add_argument('--lessons-root');ap.add_argument('--query',action='append');ap.add_argument('--limit',type=int,default=10);ap.add_argument('--offset',type=int,default=0);ap.add_argument('--diverse',action='store_true');ap.add_argument('--store');ap.add_argument('--content');ap.add_argument('--base-hash');ap.add_argument('--health-file');ap.add_argument('--service');ap.add_argument('--outcome',choices=['success','transient','terminal']);ap.add_argument('--http-status',type=int);ap.add_argument('--retry-after',type=float);ap.add_argument('--source-root');ap.add_argument('--symbol');ap.add_argument('--evidence-kind',action='append');ap.add_argument('--record');ap.add_argument('--as-of');ap.add_argument('--policy');ap.add_argument('--input',action='append');ap.add_argument('--cache');ap.add_argument('--report');ap.add_argument('--redacted',action='store_true');ap.add_argument('--max-age',type=int,default=86400);ap.add_argument('--compact',action='store_true');a=ap.parse_args(argv)
    if a.compact and a.command!='handoff':raise ValueError('--compact is only for handoff')
    if a.digest and a.command not in ('approve','deny','recover'):raise ValueError('--digest is only for approve, deny or recover')
    if a.contract and a.command not in ('init','validate','revise','revision-diff'):raise ValueError('--contract is only for init, validate or revision commands; lifecycle uses the stored contract')
    if a.workspace and a.command not in ('init','resume'):raise ValueError('--workspace is only for init or legacy resume')
    if a.command=='assess' and a.verdict not in ('pass','fail','unverified'):raise ValueError('assess requires pass, fail or unverified')
    if a.command=='goal-review' and a.verdict not in ('pass','fail'):raise ValueError('goal-review requires pass or fail')
    if a.command=='criterion-review' and a.verdict not in ('supported','unmet','unverified'):raise ValueError('criterion-review requires supported, unmet or unverified')
    if a.command=='recover' and not a.resolution:raise ValueError('recover requires --resolution')
    root=Path(a.mission)
    if a.command=='lesson-audit':
        if not a.record:raise ValueError('--record required')
        print(json.dumps(lesson_audit(json.loads(read_bounded(Path(a.record),65536)[0].decode('utf-8-sig')),a.as_of),indent=2));return 0
    if a.command in ('analysis-key','cache-save','cache-check'):
        report,code=analysis_cache(a);print(json.dumps(report,indent=2));return code
    if a.command=='lessons-search':
        print(json.dumps(lessons_search(Path(a.lessons_root) if a.lessons_root else root,a.query,a.limit,a.offset,a.diverse)));return 0
    if a.command in ('store-read','store-publish'):
        if not a.store:raise ValueError('--store required')
        if a.command=='store-read':report=store_snapshot(Path(a.store))[0]
        else:
            if not a.content or not a.base_hash:raise ValueError('--content and --base-hash required')
            report=publish_store(Path(a.store),Path(a.content),a.base_hash)
        print(json.dumps(report));return 0
    if a.command.startswith('service-'):
        if not a.health_file or not a.service:raise ValueError('--health-file and --service required')
        if a.http_status is not None:
            if a.outcome or not 100<=a.http_status<=599:raise ValueError('use a valid HTTP status or outcome, not both')
            a.outcome='success' if 200<=a.http_status<300 else 'transient' if a.http_status==429 or a.http_status>=500 else 'terminal'
        report=service_operation(Path(a.health_file),a.service,a.command[8:],a.outcome,a.retry_after)
        print(json.dumps(report));return int(a.command=='service-probe' and not report['allowed'])
    if a.command=='impact':
        if not a.source_root:raise ValueError('--source-root required')
        print(json.dumps(impact_report(Path(a.source_root),a.symbol),indent=2));return 0
    if a.command=='migrate':
        if not a.destination:raise ValueError('migration requires separate --destination')
        dest=Path(a.destination)
        if os.path.lexists(dest):raise ValueError('destination already exists')
        c=json.loads((root/'contract.json').read_text(encoding='utf-8-sig'))
        if not isinstance(c,dict):raise ValueError('legacy contract must be object')
        if c.get('schema_version') is not None:raise ValueError('migration accepts unversioned legacy contracts only')
        if 'features' in c and 'steps' in c:raise ValueError('ambiguous legacy step collections')
        legacy_steps=c.get('features',c.get('steps'))
        if not isinstance(legacy_steps,list) or not all(isinstance(step,dict) for step in legacy_steps):raise ValueError('invalid legacy steps')
        backups={}
        for source in (root/'contract.json',root/'state/progress.json'):
            if source.exists():backups[source.name]=json.loads(source.read_text(encoding='utf-8-sig'))
        for s in legacy_steps:
            if 'verify' in s and 'steps' in s:raise ValueError('ambiguous legacy criteria')
            checks=s.get('verify',s.get('steps'))
            if not isinstance(checks,list) or not checks or not all(isinstance(item,str) and item.strip() for item in checks):raise ValueError('legacy criteria must be a nonempty string array')
            s['verify']=[{'manual':x} for x in s.get('verify',s.get('steps',[]))];s['legacy_passes']=s.pop('passes',False)
        c.pop('_usage',None)
        c['steps']=c.pop('features',c.get('steps'));c['schema_version']=2;validate(c)
        publish_migration(dest,c,backups)
        return 0
    if a.command=='validate':
        from .contract import validate_allowed_paths
        contract=json.loads(Path(a.contract or root/'contract.json').read_text(encoding='utf-8-sig'))
        validate(contract)
        validate_allowed_paths(contract, Path.cwd())
        return 0
    if a.command in ('metrics','handoff','evidence-audit','diagnose') and not root.is_dir():raise ValueError('mission directory does not exist')
    root.mkdir(parents=True,exist_ok=True)
    with persistent_lock(root/'.lock'):
        c=json.loads(Path(a.contract if a.command=='init' and a.contract else root/'contract.json').read_text(encoding='utf-8-sig'));validate(c)
        state=root/'state/progress.json'
        if a.command=='init' and os.path.lexists(state):raise ValueError('already initialized or checkpoint entry requires recovery')
        if a.command!='init' and not state.exists():raise ValueError('initialize mission first')
        s=json.loads(read_bounded(state,MAX_STATE_BYTES)[0].decode('utf-8-sig')) if state.exists() else {'steps':{},'attempts':0,'stop_reason':None}
        validate_state(s,c)
        if a.command!='init' and s.get('contract_hash')!=digest(c):raise ValueError('contract changed; create a new mission revision')
        if a.command in ('start','verify','block','assess','approve','deny','recovery','recover') and not a.step:raise ValueError('--step required')
        if a.command=='evidence-audit':
            validate_approval_workspace(s);print(json.dumps(evidence_audit(c,s),indent=2));return 0
        if a.command=='diagnose':
            report=diagnose_report(c,s);report['mission_directory']=str(root.resolve())
            print(json.dumps(report,indent=2));return 0
        if a.command=='metrics':print(json.dumps(metrics_report(c,s,root)));return 0
        if a.command=='handoff':
            report=handoff_report(c,s,root)
            if a.compact:
                from .compact_handoff import compact_handoff
                report=compact_handoff(report)
            print(json.dumps(report,indent=2));return 0
        if a.command=='status':print(json.dumps(s,indent=2));return 0
        if a.command=='history':print(json.dumps({'events':s.get('journal',[])},indent=2));return 0
        if a.command=='coverage':
            validate_approval_workspace(s)
            print(json.dumps(coverage_report(c,s),indent=2));return 0
        if a.command=='recovery':
            step=next(x for x in c['steps'] if x['id']==a.step)
            print(json.dumps(recovery_report(c,s,step),indent=2));return 0
        if a.command=='revision-diff':
            if not a.contract:raise ValueError('revision-diff requires proposed --contract')
            proposed=json.loads(Path(a.contract).read_text(encoding='utf-8-sig'));validate(proposed)
            print(json.dumps(revision_diff(c,proposed),indent=2));return 0
        if a.command=='revise':publish_revision(root,c,s,a);return 0
        if a.command=='init':
            if state.exists():raise ValueError('already initialized')
            workspace=Path(a.workspace or Path.cwd()).resolve(strict=True)
            if not workspace.is_dir():raise ValueError('workspace must be directory')
            from .contract import validate_allowed_paths
            validate_allowed_paths(c, workspace)
            destination=root/'contract.json'
            if os.path.lexists(destination):
                if destination.is_symlink():raise ValueError('destination contract must not be a symlink')
                existing=json.loads(destination.read_text(encoding='utf-8-sig'))
                if existing!=c:raise ValueError('destination contract differs; use a new mission directory')
            else:atomic(destination,c)
            s['contract_hash']=digest(c);s['workspace']=str(workspace)
            s['approved_steps']={}
        elif a.command=='criterion-review':
            validate_approval_workspace(s)
            record_criterion_review(c,s,a)
        elif a.command=='recover':
            step=next(x for x in c['steps'] if x['id']==a.step)
            reconcile_recovery(c,s,step,a)
        elif a.command=='finish':
            if s.get('stop_reason') not in (None,'done_verified'):raise ValueError('resume before finish')
            if any(s['steps'].get(x['id'],{}).get('status')!='completed' for x in c['steps']):raise ValueError('incomplete steps')
            if c['schema_version']==3:
                validate_approval_workspace(s)
                if not coverage_report(c,s)['all_supported']:raise ValueError('acceptance coverage is unmet, unverified or stale')
            if s.get('stop_reason')=='done_verified':return 0
            s['stop_reason']='done_verified'
        elif a.command=='goal-review':
            if s.get('stop_reason')!='done_verified' or any(s['steps'].get(step['id'],{}).get('status')!='completed' for step in c['steps']):
                raise ValueError('goal-review requires successful finish')
            if not a.verdict or not a.rationale or not a.rationale.strip():
                raise ValueError('goal-review requires --verdict and nonblank --rationale')
            if c['schema_version']==3 and a.verdict=='pass':
                validate_approval_workspace(s)
                if not coverage_report(c,s)['all_supported']:raise ValueError('acceptance evidence changed; cannot record a passing goal review')
            if 'goal_review' in s:s.setdefault('goal_review_history',[]).append(s['goal_review'])
            s['goal_review']={'verdict':a.verdict,'rationale':a.rationale,'timestamp':now(),
                              'goal':c['mission'],'contract_hash':s['contract_hash']}
            if a.verdict=='fail':s['stop_reason']='blocked'
        elif a.command=='stop':
            if s.get('stop_reason'):raise ValueError('resume before changing stop reason')
            if a.reason not in ('blocked','human_paused','human_abort','no_progress','budget_exhausted','max_iterations'):raise ValueError('invalid stop reason')
            s['stop_reason']=a.reason
        elif a.command=='resume':
            if 'workspace' not in s:
                if not a.workspace:raise ValueError('legacy checkpoint: resume --workspace PATH to pin workspace')
                workspace=Path(a.workspace).resolve(strict=True)
                if not workspace.is_dir():raise ValueError('workspace must be directory')
                s['workspace']=str(workspace)
            elif a.workspace:raise ValueError('workspace already pinned')
            if 'goal_review' in s:s.setdefault('goal_review_history',[]).append(s.pop('goal_review'))
            s['stop_reason']=None
            definitions={x['id']:x for x in c['steps']}
            for identifier,entry in s['steps'].items():
                if entry.get('approval_denied'):continue
                if (c['schema_version']==3 and entry.get('status')=='in_progress'
                        and not entry.get('revalidating') and definitions[identifier].get('retry','inspect')=='inspect'):
                    entry['recovery_required']=True
                entry.setdefault('history',[]).append({'evidence':entry.get('evidence',[]),'manual':entry.get('manual',{}),'timestamp':now()});entry['needs_revalidation']=entry.get('status') in ('completed','in_progress') or entry.get('needs_revalidation',False);entry['status']='pending';entry['evidence']=[];entry['manual']={}
                entry.pop('approval_request',None)
            s['resume_note']='Revalidate completed work; inspect interrupted actions before retrying.'
        else:
            step=next(x for x in c['steps'] if x['id']==a.step);entry=s['steps'].setdefault(a.step,{})
            if s.get('stop_reason'):raise ValueError('resume mission first')
            if a.command=='start':
                if c['schema_version']==3:
                    validate_approval_workspace(s)
                    if entry.get('recovery_required'):raise ValueError('inspect recovery report and reconcile before retry or revalidation')
                if entry.get('approval_denied'):
                    if any(v.get('status')=='in_progress' for v in s['steps'].values()):raise ValueError('another step active')
                    if any(s['steps'].get(d,{}).get('status')!='completed' for d in step.get('depends_on',[])):raise ValueError('dependency incomplete')
                    if step_budget_exhausted(c,s):s['stop_reason']='blocked'
                    s['last_update']=now();commit_state(state,s,c,a);return 1
                if a.revalidate and not entry.get('needs_revalidation'):raise ValueError('no interrupted or completed work to revalidate')
                if entry.get('needs_revalidation') and not a.revalidate:raise ValueError('inspect prior work and start --revalidate first')
                if s.get('stop_reason'):raise ValueError('resume mission first')
                if entry.get('status')=='completed':raise ValueError('step already completed')
                if any(v.get('status')=='in_progress' for v in s['steps'].values()):raise ValueError('another step active')
                if any(s['steps'].get(d,{}).get('status')!='completed' for d in step.get('depends_on',[])):raise ValueError('dependency incomplete')
                budget=c.get('budget',{})
                limit=budget.get('max_iterations',max(10,3*len(c['steps'])))
                if not a.revalidate and s['attempts']>=limit:
                    s['stop_reason']='max_iterations';commit_state(state,s,c,a);return 1
                if not a.revalidate and entry.get('attempts',0)>=budget.get('max_attempts_per_step',2):
                    entry['budget_exhausted']=True
                    if step_budget_exhausted(c,s):s['stop_reason']=exhaustion_reason(s)
                    s['last_update']=now();commit_state(state,s,c,a);return 1
                if c['schema_version']==3 or requires_approval(c,step):validate_approval_workspace(s)
                if requires_approval(c,step) and not has_approval(c,step,s):
                    request=request_approval(c,step,s,a.revalidate)
                    s['last_update']=now();commit_state(state,s,c,a)
                    print(json.dumps(request,indent=2));return 3
                if entry.get('manual'):
                    entry.setdefault('history',[]).append({'manual':entry['manual'],'evidence':entry.get('evidence',[]),'timestamp':now()})
                if c['schema_version']==3 and not a.revalidate:
                    entry['effect_baseline']=observations(s['workspace'],step['effects']['writes'])
                    readable_observations(entry['effect_baseline'])
                    entry['input_baseline']=watched_inputs(c,step,s['workspace'])
                    readable_observations(entry['input_baseline'])
                entry['context']=a.context;entry['manual']={};entry['status']='in_progress';entry['revalidating']=a.revalidate
                if a.revalidate:entry['revalidations']=entry.get('revalidations',0)+1
                else:entry['attempts']=entry.get('attempts',0)+1;s['attempts']+=1
            elif a.command in ('approve','deny'):
                record_decision(c,step,s,a.command,a.digest,a.rationale,now())
                if a.command=='deny' and step_budget_exhausted(c,s):s['stop_reason']='blocked'
            elif a.command=='block':
                if entry.get('status')!='in_progress':
                    raise ValueError('block requires the active step; use resume to reopen completed work')
                if not a.reason or not a.reason.strip():raise ValueError('block requires a nonempty --reason')
                entry['status']='blocked';entry['diagnosis']=a.reason
                if c['schema_version']==3 and step.get('retry','inspect')=='inspect' and not entry.get('revalidating'):
                    entry['recovery_required']=True
            elif a.command=='assess':
                if entry.get('status')!='in_progress' or a.check is None or not a.rationale or not a.rationale.strip() or not a.verdict:raise ValueError('assessment needs active step, check index, verdict and rationale')
                if a.check<0 or a.check>=len(step['verify']) or not isinstance(step['verify'][a.check],dict):raise ValueError('not a manual check')
                if requires_approval(c,step) and not has_approval(c,step,s):raise ValueError('step approval missing or stale; resume and request approval again')
                if c['schema_version']==3 or requires_approval(c,step):validate_approval_workspace(s)
                entry.setdefault('manual',{})[str(a.check)]={'verdict':a.verdict,'rationale':a.rationale,'timestamp':now()}
            else:
                if entry.get('status')!='in_progress':raise ValueError('start step first')
                if requires_approval(c,step) and not has_approval(c,step,s):raise ValueError('step approval missing or stale; resume and request approval again')
                if c['schema_version']==3 or requires_approval(c,step):validate_approval_workspace(s)
                if 'workspace' not in s:raise ValueError('legacy checkpoint: resume --workspace PATH first')
                workspace=Path(s['workspace'])
                if not workspace.is_absolute() or not workspace.is_dir():raise ValueError('pinned workspace unavailable')
                missing=[i for i,check in enumerate(step['verify']) if isinstance(check,dict) and str(i) not in entry.get('manual',{})]
                if missing:raise ValueError('missing manual assessments: '+str(missing)+'; assess then verify the active attempt')
                if any(v.get('verdict')=='unverified' for v in entry.get('manual',{}).values()):raise ValueError('manual assessment is unverified; assess the active attempt before verification')
                if c['schema_version']==3 and len(s['journal'])>=MAX_JOURNAL_EVENTS:
                    raise ValueError('journal event limit reached; refusing checks before an uncommittable verification')
                results=[]
                ordered=sorted(enumerate(step['verify']),key=lambda pair:isinstance(pair[1],dict))
                for i,check in ordered:
                    if isinstance(check,list):result=run_check(check,quiet=True,cwd=workspace)
                    else:result={'code':int(entry.get('manual',{}).get(str(i),{}).get('verdict')!='pass'),
                                 'command_exit_status':None,'signal':None,'error_type':None}
                    results.append(dict(result,check=i,identity=check,timestamp=now(),
                                        cwd=str(workspace),output_policy='discarded'))
                    if result['code']:break
                failed=any(r['code'] for r in results)
                if c['schema_version']==3 and not failed:
                    validate_approval_workspace(s)
                    if requires_approval(c,step) and not has_approval(c,step,s):
                        raise ValueError('approval inputs changed during verification; inspect and obtain current approval before revalidation')
                    receipt=verification_artifacts(step,s['workspace'])
                    readable_observations(receipt)
                entry.setdefault('history',[]).append({'evidence':entry.get('evidence',[]),'timestamp':now()})
                entry['evidence']=results;entry['status']='pending' if failed else 'completed'
                if c['schema_version']==3:
                    if failed:entry.pop('verified_artifacts',None)
                    else:entry['verified_artifacts']=receipt
                entry['needs_revalidation']=False
                if failed and c['schema_version']==3 and step.get('retry','inspect')=='inspect' and not entry.get('revalidating'):
                    entry['recovery_required']=True
                key=digest([step['verify'],entry.get('context'),[r['check'] for r in results if r['code']]])
                failures=entry.setdefault('failures',{})
                if not failed:failures.clear()
                else:failures[key]=failures.get(key,0)+1
                if failed and failures[key]>=c.get('budget',{}).get('no_progress_threshold',2):s['stop_reason']='no_progress'
        if a.command=='verify' and not s.get('stop_reason') and any(v.get('budget_exhausted') or v.get('approval_denied') for v in s['steps'].values()) and step_budget_exhausted(c,s):
            s['stop_reason']=exhaustion_reason(s)
        s['last_update']=now()
        commit_state(state,s,c,a)
        if a.command=='verify':return int(entry['status']!='completed')
        if a.command=='goal-review':return int(a.verdict=='fail')
        if a.command=='deny':return 1
        if a.command=='criterion-review':return int(a.verdict=='unmet')
        if a.command=='recover':return int(a.resolution in ('partial','unknown'))
    return 0

