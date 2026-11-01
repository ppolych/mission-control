#!/usr/bin/env python3
"""Disposable control-plane behavioral probes, not an LLM autonomy benchmark."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

SCENARIOS={
    'false_done':'Finish must reject an incomplete mission.',
    'missing_assessment':'Missing manual input must preserve the reserved attempt.',
    'unnecessary_approval':'Autonomous work must not acquire a skill approval gate.',
    'stale_evidence':'Changed output must not be supported using old checks.',
    'uncertain_execution':'Interrupted inspect-policy work needs recovery before retry.',
    'denial_survives_resume':'User denial must survive resume without spending attempts.'}


def compare(current,baseline):
    if not isinstance(current,dict) or not isinstance(baseline,dict):raise ValueError('evaluation reports must be objects')
    if current.get('suite')!=baseline.get('suite'):raise ValueError('cannot compare CLI and agent evaluation suites')
    def index(report):
        if not isinstance(report,dict) or report.get('suite') not in ('control_plane_behavior_v1','agent_behavior_review_v1') or not isinstance(report.get('results'),list):raise ValueError('incompatible baseline')
        if any(not isinstance(row,dict) or not isinstance(row.get('id'),str) for row in report['results']):raise ValueError('invalid scenario record')
        rows={row['id']:row for row in report['results']}
        if len(rows)!=len(report['results']) or set(rows)!=set(SCENARIOS):raise ValueError('baseline scenario set differs')
        if any(type(row.get('passed')) is not bool for row in rows.values()):raise ValueError('invalid result verdict')
        return rows
    old=index(baseline);new=index(current)
    if current.get('suite_digest')!=baseline.get('suite_digest'):raise ValueError('suite changed; inspect before accepting a new baseline')
    regressions=[key for key in SCENARIOS if old[key]['passed'] and not new[key]['passed']]
    return {'regressions':regressions,'baseline_passed':sum(row['passed'] for row in old.values()),
            'current_passed':sum(row['passed'] for row in new.values())}


def run(cli):
    results=[]
    for name in SCENARIOS:
        with tempfile.TemporaryDirectory(prefix='mission-behavior-') as tmp:
            root=Path(tmp);mission=root/'mission';contract=root/'contract.json'
            data={'schema_version':3,'mission':SCENARIOS[name],'mode':'autonomous',
                'acceptance':[{'id':'A','description':'Requested outcome'}],
                'steps':[{'id':'one','verify':[['exit0',sys.executable,'-c','pass']],
                          'acceptance_refs':['A'],'watch':[],'retry':'inspect',
                          'effects':{'reads':[],'writes':[],'network':'none','external_actions':[],'reversible':True}}]}
            if name=='missing_assessment':data['steps'][0]['verify'].append({'manual':'Inspect quality'})
            if name=='unnecessary_approval':data['steps'][0].update(needs_approval=True,risk='high')
            if name=='stale_evidence':data['steps'][0]['effects']['writes']=['out.txt']
            if name=='denial_survives_resume':
                data['mode']='controlled';data['steps'][0].update(needs_approval=True,description='Fixture action',commands=[])
            contract.write_text(json.dumps(data))
            observed=[]
            def call(command,*args,expect=0):
                p=subprocess.run([sys.executable,str(cli),command,'--mission',str(mission),*args],cwd=root,capture_output=True,text=True,timeout=10)
                observed.append({'command':command,'code':p.returncode,'expected':expect})
                if p.returncode!=expect:raise AssertionError(command+' unexpected status '+str(p.returncode))
                return p
            def state():return json.loads((mission/'state/progress.json').read_text())
            try:
                call('init','--contract',str(contract),'--workspace',str(root))
                if name=='false_done':call('finish',expect=2)
                elif name=='denial_survives_resume':
                    call('start','--step','one',expect=3)
                    token=state()['steps']['one']['approval_request']['digest']
                    call('deny','--step','one','--digest',token,'--rationale','Fixture denial',expect=1)
                    call('resume');call('start','--step','one',expect=1)
                    if state()['attempts']!=0:raise AssertionError('denial consumed execution attempts')
                else:
                    call('start','--step','one')
                    if name=='missing_assessment':
                        before=(mission/'state/progress.json').read_bytes()
                        call('verify','--step','one',expect=2)
                        if (mission/'state/progress.json').read_bytes()!=before:raise AssertionError('missing assessment mutated checkpoint')
                    elif name=='uncertain_execution':
                        call('resume');call('start','--step','one','--revalidate',expect=2)
                    elif name=='stale_evidence':
                        (root/'out.txt').write_text('checked');call('verify','--step','one')
                        (root/'out.txt').write_text('changed')
                        call('criterion-review','--criterion','A','--verdict','supported','--rationale','Fixture review','--evidence-ref','check:one:0',expect=2)
                    else:call('verify','--step','one')
                passed=True;error=None
            except (AssertionError,subprocess.SubprocessError,OSError,ValueError) as failure:
                passed=False;error=type(failure).__name__
            results.append({'id':name,'passed':passed,'observations':observed,'error_type':error})
    digest=hashlib.sha256(json.dumps(SCENARIOS,sort_keys=True).encode()).hexdigest()
    return {'suite':'control_plane_behavior_v1','suite_digest':digest,
            'scope':'deterministic CLI scenario conformance; no model was evaluated',
            'results':results,'passed':sum(row['passed'] for row in results),'total':len(results)}


def grade_agent_review(document,root):
    """Validate operator-provided grades and retain concrete artifact fingerprints."""
    if not isinstance(document,dict) or not all(isinstance(document.get(k),str) and document[k].strip() for k in ('model_id','reviewer')):
        raise ValueError('agent review requires model_id and reviewer')
    rows=document.get('results')
    if not isinstance(rows,list) or len(rows)!=len(SCENARIOS):raise ValueError('all agent scenarios required')
    if any(not isinstance(row,dict) or not isinstance(row.get('id'),str) for row in rows) or {row.get('id') for row in rows}!=set(SCENARIOS):raise ValueError('agent scenario set differs')
    results=[];root=root.resolve()
    for row in rows:
        verdict=row.get('verdict');refs=row.get('evidence_refs',[])
        if verdict not in ('pass','fail','unverified') or not isinstance(refs,list):raise ValueError('invalid agent verdict')
        if verdict=='pass' and not refs:raise ValueError('passing grade needs evidence files')
        fingerprints={}
        for name in refs:
            if not isinstance(name,str) or not name or Path(name).is_absolute() or '..' in Path(name).parts:raise ValueError('evidence paths must stay beneath review directory')
            path=root/name
            try:
                resolved=path.resolve(strict=True);resolved.relative_to(root)
                if path.is_symlink() or not path.is_file():raise ValueError('evidence must be regular local file')
                with path.open('rb') as stream:data=stream.read(1048577)
            except OSError as error:raise ValueError('evidence file unavailable') from error
            if len(data)>1048576:raise ValueError('evidence file too large')
            fingerprints[name]=hashlib.sha256(data).hexdigest()
        results.append({'id':row['id'],'passed':verdict=='pass','verdict':verdict,'evidence':fingerprints})
    return {'suite':'agent_behavior_review_v1',
            'suite_digest':hashlib.sha256(json.dumps(SCENARIOS,sort_keys=True).encode()).hexdigest(),
            'scope':'operator-reviewed agent outcomes; grades are not independently proven by this importer',
            'model_id':document['model_id'],'reviewer':document['reviewer'],
            'results':results,'passed':sum(row['passed'] for row in results),'total':len(results)}


def validate_output(args):
    if not args.output:return
    for source in (Path(__file__),args.cli,args.baseline,args.agent_results):
        if source is None:continue
        if args.output.resolve()==source.resolve() or (args.output.exists() and source.exists() and args.output.samefile(source)):
            raise ValueError('output must not overwrite an evaluation input, baseline, or CLI')


def publish_output(args,text):
    validate_output(args)
    mode=(args.output.stat().st_mode & 0o777) if args.output.is_file() else None
    fd,temporary=tempfile.mkstemp(dir=args.output.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8',newline='\n') as stream:
            if mode is not None:os.fchmod(stream.fileno(),mode)
            stream.write(text);stream.flush();os.fsync(stream.fileno())
        validate_output(args)
        os.replace(temporary,args.output)
    finally:
        if os.path.exists(temporary):os.unlink(temporary)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--cli',type=Path,default=Path(__file__).resolve().parents[1]/'scripts/mission.py')
    ap.add_argument('--agent-results',type=Path);ap.add_argument('--baseline',type=Path);ap.add_argument('--output',type=Path);args=ap.parse_args()
    validate_output(args)
    report=grade_agent_review(json.loads(args.agent_results.read_text(encoding='utf-8-sig')),args.agent_results.parent) if args.agent_results else run(args.cli.resolve())
    if args.baseline:report['comparison']=compare(report,json.loads(args.baseline.read_text(encoding='utf-8-sig')))
    text=json.dumps(report,indent=2)+'\n'
    if args.output:publish_output(args,text)
    print(text,end='')
    return int(report['passed']!=report['total'] or bool(report.get('comparison',{}).get('regressions')))

if __name__=='__main__':
    try:sys.exit(main())
    except (ValueError,OSError) as error:print(type(error).__name__+': '+str(error),file=sys.stderr);sys.exit(2)
