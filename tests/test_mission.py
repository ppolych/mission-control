import subprocess
import unittest
import json
import os
import tempfile
from pathlib import Path
CLI=str(Path('scripts/mission.py').resolve())

class Verification(unittest.TestCase):
    def run_check(self,*args):
        return subprocess.run(['bash','scripts/verify.sh',*args],capture_output=True).returncode
    def test_empty(self):self.assertEqual(self.run_check('--'),2)
    def test_extra(self):self.assertEqual(self.run_check('file','README.md','ignored'),2)
    def test_pipeline(self):self.assertEqual(self.run_check('exec','false | true'),1)
    def test_exists(self):self.assertEqual(self.run_check('file','README.md'),0)
    def test_bad_pattern(self):self.assertEqual(self.run_check('grep','[','README.md'),2)

class Lifecycle(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.mission=self.root/'mission'
        self.contract=self.root/'contract.json'
        self.data={'schema_version':2,'mission':'test','steps':[{'id':'one','verify':[['exit0','true']]}]}
        self.save()
    def save(self):self.contract.write_text(json.dumps(self.data))
    def call(self,command,*args):
        return subprocess.run(['python3',CLI,command,'--mission',str(self.mission),*args],capture_output=True,text=True)
    def init(self):self.assertEqual(self.call('init','--contract',str(self.contract)).returncode,0)
    def test_success_and_resume(self):
        self.init();self.assertEqual(self.call('finish').returncode,2)
        self.assertEqual(self.call('start','--step','one').returncode,0)
        self.assertEqual(self.call('verify','--step','one').returncode,0)
        self.assertEqual(self.call('finish').returncode,0)
        self.assertEqual(self.call('resume').returncode,0)
        self.assertEqual(self.call('finish').returncode,2)
    def test_failure_is_not_success(self):
        self.data['steps'][0]['verify']=[['exit0','false']];self.save();self.init()
        for _ in range(2):
            self.assertEqual(self.call('start','--step','one').returncode,0)
            self.assertEqual(self.call('verify','--step','one').returncode,1)
        state=json.loads(self.call('status').stdout)
        self.assertEqual(state['stop_reason'],'no_progress')
        self.assertEqual(self.call('finish').returncode,2)
    def test_manual_cannot_override_failure(self):
        self.data['steps'][0]['verify']=[['exit0','false'],{'manual':'quality'}];self.save();self.init()
        self.call('start','--step','one')
        self.assertEqual(self.call('assess','--step','one','--check','1','--verdict','pass','--rationale','reviewed').returncode,0)
        self.assertEqual(self.call('verify','--step','one').returncode,1)
    def test_invalid_dependencies(self):
        self.data['steps'][0]['depends_on']=['one'];self.save()
        self.assertEqual(self.call('validate','--contract',str(self.contract)).returncode,2)
    def test_budget(self):
        self.data['budget']={'max_iterations':1};self.data['steps'][0]['verify']=[['exit0','false']];self.save();self.init()
        self.call('start','--step','one');self.call('verify','--step','one');self.call('resume')
        self.assertEqual(self.call('start','--step','one').returncode,1)
    def test_migration_variants(self):
        self.mission.mkdir()
        for key,checks in [('features','steps'),('steps','verify')]:
            original={'mission':'old',key:[{'id':'one',checks:['test -f artifact'],'passes':True}]}
            source=self.mission/'contract.json';source.write_text(json.dumps(original))
            dest=self.root/key
            self.assertEqual(self.call('migrate','--destination',str(dest)).returncode,0)
            self.assertEqual(json.loads(source.read_text()),original)
            migrated=json.loads((dest/'contract.json').read_text())
            self.assertTrue(migrated['steps'][0]['legacy_passes'])
            self.assertEqual(migrated['steps'][0]['verify'],[{'manual':'test -f artifact'}])
    def test_changed_contract_rejected(self):
        self.init();p=self.mission/'contract.json';c=json.loads(p.read_text());c['mission']='changed';p.write_text(json.dumps(c))
        self.assertEqual(self.call('start','--step','one').returncode,2)
    def test_repeat_boundaries(self):
        env=dict(os.environ,NO_PROGRESS_STATE=str(self.root/'repeat.json'))
        for args in (['tool','a b'],['tool','a','b']):
            result=subprocess.run(['python3',CLI,'repeat','record',*args],env=env,capture_output=True)
            self.assertEqual(result.returncode,0)
    def test_lock_contention(self):
        import fcntl
        self.init()
        with (self.mission/'.lock').open('w') as f:
            fcntl.flock(f,fcntl.LOCK_EX)
            self.assertEqual(self.call('start','--step','one').returncode,2)

class ReviewRegressions(Lifecycle):
    def test_final_attempt_revalidation(self):
        artifact=self.root/'ready'
        self.data['steps']=[{'id':'one','verify':[['file',str(artifact)]]},{'id':'two','depends_on':['one'],'verify':[['exit0','true']]}];self.save();self.init()
        self.call('start','--step','one');self.assertEqual(self.call('verify','--step','one').returncode,1)
        artifact.touch();self.call('start','--step','one');self.assertEqual(self.call('verify','--step','one').returncode,0)
        self.call('start','--step','two');self.call('stop','--reason','human_paused');self.call('resume')
        self.assertEqual(self.call('start','--step','two','--revalidate').returncode,2)
        self.assertEqual(self.call('start','--step','one','--revalidate').returncode,0)
        self.assertEqual(self.call('verify','--step','one').returncode,0)
        self.assertEqual(self.call('start','--step','two','--revalidate').returncode,0)
        self.assertEqual(self.call('verify','--step','two').returncode,0)
        self.assertEqual(self.call('finish').returncode,0)
        state=json.loads(self.call('status').stdout);self.assertEqual(state['steps']['one']['attempts'],2)
    def test_fail_fast(self):
        marker=self.root/'unexpected'
        self.data['steps'][0]['verify']=[{'manual':'review'},['exit0','false'],['exit0','touch',str(marker)]];self.save();self.init();self.call('start','--step','one')
        self.call('assess','--step','one','--check','0','--verdict','pass','--rationale','reviewed')
        self.assertEqual(self.call('verify','--step','one').returncode,1)
        self.assertFalse(marker.exists())
        evidence=json.loads(self.call('status').stdout)['steps']['one']['evidence']
        self.assertEqual([x['check'] for x in evidence],[1])
    def test_stopped_transitions(self):
        self.init();self.call('start','--step','one');self.call('verify','--step','one');self.call('stop','--reason','human_abort')
        self.assertEqual(self.call('finish').returncode,2)
        self.assertEqual(self.call('stop','--reason','blocked').returncode,2)
        self.assertEqual(json.loads(self.call('status').stdout)['stop_reason'],'human_abort')
    def test_stopped_verify(self):
        self.init();self.call('start','--step','one');self.call('stop','--reason','human_paused')
        self.assertEqual(self.call('verify','--step','one').returncode,2)
    def test_evidence_identity(self):
        self.init();self.call('start','--step','one');self.call('verify','--step','one')
        evidence=json.loads(self.call('status').stdout)['steps']['one']['evidence'][0]
        self.assertEqual(evidence['cwd'],str(Path.cwd()))
        self.assertEqual(evidence['identity'],self.data['steps'][0]['verify'][0])
        self.assertIn('timestamp',evidence)
    def test_invalid_check_preflight(self):
        marker=self.root/'executed'
        for check in (['unknown'],['file','a','b'],['exec'],['grep','x'],['exit0'],{'manual':'x','extra':True}):
            self.data['steps'][0]['verify']=[['exit0','touch',str(marker)],check];self.save()
            self.assertEqual(self.call('validate','--contract',str(self.contract)).returncode,2)
        self.assertFalse(marker.exists())
    def test_malformed_contract_types(self):
        for data in ([],{'schema_version':2,'steps':[[]]}, {'schema_version':2,'steps':[{'id':[],'verify':[['exit0','true']]}]}):
            self.data=data;self.save();r=self.call('validate','--contract',str(self.contract));self.assertEqual(r.returncode,2);self.assertNotIn('Traceback',r.stderr)
    def test_context_failure_recovery(self):
        artifact=self.root/'fixed'
        self.data['budget']={'max_attempts_per_step':6}
        self.data['steps'][0]['verify']=[['file',str(artifact)]];self.save();self.init()
        for context in ('first','changed','changed'):
            self.assertEqual(self.call('start','--step','one','--context',context).returncode,0)
            self.assertEqual(self.call('verify','--step','one').returncode,1)
        self.assertEqual(json.loads(self.call('status').stdout)['stop_reason'],'no_progress')
        self.assertEqual(self.call('start','--step','one','--context','other').returncode,2)
        artifact.touch();self.call('resume')
        self.assertEqual(self.call('start','--step','one','--context','fixed').returncode,0)
        self.assertEqual(self.call('verify','--step','one').returncode,0)
        self.assertEqual(json.loads(self.call('status').stdout)['steps']['one']['failures'],{})
    def test_output_not_persisted(self):
        self.data['steps'][0]['verify']=[['exit0','printf','private-output']];self.save();self.init();self.call('start','--step','one')
        result=self.call('verify','--step','one');self.assertEqual(result.returncode,0)
        self.assertNotIn('private-output',result.stdout)
        evidence=json.loads(self.call('status').stdout)['steps']['one']['evidence'][0]
        self.assertEqual(evidence['output_policy'],'discarded')
    def test_duplicate_and_missing_dependency(self):
        self.data['steps']*=2;self.save();self.assertEqual(self.call('validate','--contract',str(self.contract)).returncode,2)
        self.data['steps']=self.data['steps'][:1];self.data['steps'][0]['depends_on']=['missing'];self.save()
        self.assertEqual(self.call('validate','--contract',str(self.contract)).returncode,2)
    def test_shell_group_fail_fast(self):
        marker=self.root/'unexpected'
        r=subprocess.run(['bash','scripts/verify.sh','exit0','false','--','exit0','touch',str(marker)],capture_output=True)
        self.assertEqual(r.returncode,1);self.assertFalse(marker.exists())

class BlockTransitions(unittest.TestCase):
    setUp = Lifecycle.setUp
    save = Lifecycle.save
    call = Lifecycle.call
    init = Lifecycle.init

    def state_bytes(self):
        return (self.mission/'state/progress.json').read_bytes()

    def test_completed_dependency_cannot_reopen_with_stale_downstream(self):
        artifact = self.root/'downstream'
        artifact.touch()
        self.data['steps'].append({'id':'two','depends_on':['one'],
                                   'verify':[['file',str(artifact)]]})
        self.save(); self.init()
        for step in ('one','two'):
            self.assertEqual(self.call('start','--step',step).returncode,0)
            self.assertEqual(self.call('verify','--step',step).returncode,0)
        before = self.state_bytes()
        self.assertEqual(self.call('block','--step','one','--reason','redo').returncode,2)
        self.assertEqual(self.state_bytes(),before)
        self.assertEqual(self.call('start','--step','one').returncode,2)
        # Explicit resume is the supported path and invalidates downstream too.
        artifact.unlink()
        self.assertEqual(self.call('resume').returncode,0)
        self.assertEqual(self.call('start','--step','one','--revalidate').returncode,0)
        self.assertEqual(self.call('verify','--step','one').returncode,0)
        self.assertEqual(self.call('finish').returncode,2)
        self.assertEqual(self.call('start','--step','two','--revalidate').returncode,0)
        self.assertEqual(self.call('verify','--step','two').returncode,1)
        self.assertEqual(self.call('finish').returncode,2)

    def test_block_only_active_step_and_restart_with_budget(self):
        self.data['steps'].append({'id':'two','verify':[['exit0','true']]})
        self.save(); self.init()
        before = self.state_bytes()
        self.assertEqual(self.call('block','--step','one','--reason','pending').returncode,2)
        self.assertEqual(self.state_bytes(),before)
        self.assertEqual(self.call('start','--step','one').returncode,0)
        before = self.state_bytes()
        self.assertEqual(self.call('block','--step','two','--reason','other').returncode,2)
        self.assertEqual(self.state_bytes(),before)
        self.assertEqual(self.call('block','--step','one','--reason','waiting').returncode,0)
        state = json.loads(self.call('status').stdout)
        self.assertEqual(state['steps']['one']['status'],'blocked')
        self.assertEqual(state['steps']['one']['attempts'],1)
        before = self.state_bytes()
        self.assertEqual(self.call('block','--step','one','--reason','again').returncode,2)
        self.assertEqual(self.state_bytes(),before)
        self.assertEqual(self.call('start','--step','two').returncode,0)
        self.assertEqual(self.call('verify','--step','two').returncode,0)
        self.assertEqual(self.call('start','--step','one').returncode,0)
        self.assertEqual(self.call('verify','--step','one').returncode,0)
        self.assertEqual(self.call('finish').returncode,0)

    def test_block_requires_reason_and_unstopped_mission(self):
        self.init(); self.call('start','--step','one')
        before = self.state_bytes()
        for reason in ('','   '):
            self.assertEqual(self.call('block','--step','one','--reason',reason).returncode,2)
            self.assertEqual(self.state_bytes(),before)
        self.assertEqual(self.call('stop','--reason','human_paused').returncode,0)
        before = self.state_bytes()
        self.assertEqual(self.call('block','--step','one','--reason','waiting').returncode,2)
        self.assertEqual(self.state_bytes(),before)

class StartAssessmentWorkspace(unittest.TestCase):
    setUp = Lifecycle.setUp
    save = Lifecycle.save
    call = Lifecycle.call
    init = Lifecycle.init
    state_bytes = BlockTransitions.state_bytes

    def test_invalid_start_cannot_stop_active_at_iteration_limit(self):
        self.data['budget']={'max_iterations':1}
        self.data['steps'].append({'id':'two','verify':[['exit0','true']]})
        self.save();self.init();self.assertEqual(self.call('start','--step','one').returncode,0)
        before=self.state_bytes()
        self.assertEqual(self.call('start','--step','two').returncode,2)
        self.assertEqual(self.state_bytes(),before)
        self.assertEqual(self.call('verify','--step','one').returncode,0)

    def test_missing_assessment_can_complete_reserved_attempt(self):
        marker=self.root/'ran'
        self.data['budget']={'max_attempts_per_step':1}
        self.data['steps'][0]['verify']=[['exit0','touch',str(marker)],{'manual':'quality'}]
        self.save();self.init();self.call('start','--step','one')
        before=self.state_bytes()
        self.assertEqual(self.call('verify','--step','one').returncode,2)
        self.assertEqual(self.state_bytes(),before)
        self.assertFalse(marker.exists())
        self.assertEqual(self.call('assess','--step','one','--check','1','--verdict','pass','--rationale','reviewed').returncode,0)
        self.assertEqual(self.call('verify','--step','one').returncode,0)
        state=json.loads(self.call('status').stdout)
        self.assertEqual(state['steps']['one']['attempts'],1)
        self.assertEqual(self.call('finish').returncode,0)

    def test_explicit_manual_failure_uses_reserved_attempt(self):
        self.data['budget']={'max_attempts_per_step':1}
        self.data['steps'][0]['verify']=[['exit0','true'],{'manual':'quality'}]
        self.save();self.init();self.call('start','--step','one')
        self.call('assess','--step','one','--check','1','--verdict','fail','--rationale','incorrect')
        self.assertEqual(self.call('verify','--step','one').returncode,1)
        self.assertEqual(self.call('start','--step','one').returncode,1)
        self.assertEqual(json.loads(self.call('status').stdout)['stop_reason'],'budget_exhausted')

    def test_workspace_pinned_across_callers(self):
        workspace=self.root/'workspace';workspace.mkdir();(workspace/'artifact').touch()
        other=self.root/'other';other.mkdir()
        self.data['steps'][0]['verify']=[['file','artifact'],['exit0','test','-f','artifact']]
        self.save()
        result=subprocess.run(['python3',CLI,'init','--mission',str(self.mission),'--contract',str(self.contract)],cwd=workspace,capture_output=True)
        self.assertEqual(result.returncode,0)
        self.call('start','--step','one')
        result=subprocess.run(['python3',CLI,'verify','--mission',str(self.mission),'--step','one'],cwd=other,capture_output=True)
        self.assertEqual(result.returncode,0)
        evidence=json.loads(self.call('status').stdout)['steps']['one']['evidence']
        self.assertEqual({x['cwd'] for x in evidence},{str(workspace)})

    def test_explicit_workspace_and_legacy_pin(self):
        workspace=self.root/'workspace';workspace.mkdir();(workspace/'artifact').touch()
        self.data['steps'][0]['verify']=[['file','artifact']];self.save()
        self.assertEqual(self.call('init','--contract',str(self.contract),'--workspace',str(workspace)).returncode,0)
        self.call('start','--step','one');self.assertEqual(self.call('verify','--step','one').returncode,0)
        path=self.mission/'state/progress.json';state=json.loads(path.read_text());del state['workspace'];path.write_text(json.dumps(state))
        before=self.state_bytes()
        self.assertEqual(self.call('resume').returncode,2);self.assertEqual(self.state_bytes(),before)
        self.assertEqual(self.call('resume','--workspace',str(workspace)).returncode,0)
        self.assertEqual(self.call('start','--step','one','--revalidate').returncode,0)
        self.assertEqual(self.call('verify','--step','one').returncode,0)
        before=self.state_bytes()
        self.assertEqual(self.call('resume','--workspace',str(self.root)).returncode,2)
        self.assertEqual(self.state_bytes(),before)

    def test_dependency_rejection_before_budget_stop(self):
        self.data['budget']={'max_iterations':1}
        self.data['steps'].append({'id':'two','depends_on':['one'],'verify':[['exit0','true']]})
        self.data['steps'][0]['verify']=[['exit0','false']];self.save();self.init()
        self.call('start','--step','one');self.call('verify','--step','one')
        before=self.state_bytes()
        self.assertEqual(self.call('start','--step','two').returncode,2)
        self.assertEqual(self.state_bytes(),before)
