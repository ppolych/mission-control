import subprocess
import unittest
import json
import os
import tempfile
from pathlib import Path
CLI=str(Path('scripts/mission.py').resolve())

import test_mission as original_fixtures

class VerificationAndPublicationReview(unittest.TestCase):
    setUp = original_fixtures.Lifecycle.setUp
    save = original_fixtures.Lifecycle.save
    call = original_fixtures.Lifecycle.call
    init = original_fixtures.Lifecycle.init

    def test_empty_filesystem_path_is_not_current_directory(self):
        for check in (['file',''],['not_file',''],['grep','pattern','']):
            with self.subTest(check=check):
                self.data['steps'][0]['verify']=[check];self.save()
                self.assertEqual(self.call('validate','--contract',str(self.contract)).returncode,2)
                result=subprocess.run(['bash','scripts/verify.sh',*check],capture_output=True)
                self.assertEqual(result.returncode,2)

    def test_malformed_test_expression_is_execution_error(self):
        check=['test','1','-eq','not-a-number']
        result=subprocess.run(['bash','scripts/verify.sh',*check],capture_output=True)
        self.assertEqual(result.returncode,2)
        self.data['steps'][0]['verify']=[check];self.save();self.init();self.call('start','--step','one')
        self.assertEqual(self.call('verify','--step','one').returncode,1)
        evidence=json.loads(self.call('status').stdout)['steps']['one']['evidence'][0]
        self.assertEqual(evidence['code'],2)
        self.assertEqual(evidence['command_exit_status'],2)
        self.assertEqual(evidence['error_type'],'test_error')

    def test_migration_write_failure_does_not_publish_partial_mission(self):
        import importlib.util
        from unittest.mock import patch
        spec=importlib.util.spec_from_file_location('mission_publication_test',CLI)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module); __import__("core_adapter").bind(module)
        self.mission.mkdir();source=self.mission/'contract.json'
        source.write_text(json.dumps({'mission':'legacy','features':[{'id':'one','steps':['review']}]}))
        before=source.read_bytes();destination=self.root/'migrated'
        original_atomic=module.atomic
        def fail_backup(path,data):
            if path.parent.name=='legacy':raise OSError('simulated backup write failure')
            return original_atomic(path,data)
        with patch.object(module,'atomic',side_effect=fail_backup):
            with self.assertRaises(OSError):module.main(['migrate','--mission',str(self.mission),'--destination',str(destination)])
        self.assertFalse(destination.exists())
        self.assertEqual(source.read_bytes(),before)
        self.assertEqual(self.call('migrate','--destination',str(destination)).returncode,0)
        self.assertTrue((destination/'legacy/contract.json').exists())

class MigrationCrashRecovery(unittest.TestCase):
    setUp = original_fixtures.Lifecycle.setUp
    save = original_fixtures.Lifecycle.save
    call = original_fixtures.Lifecycle.call
    init = original_fixtures.Lifecycle.init

    def prepare_legacy(self):
        self.mission.mkdir()
        source=self.mission/'contract.json'
        source.write_text(json.dumps({'mission':'legacy','features':[{'id':'one','steps':['review']}]}))
        return source

    def test_retry_recovers_staging_after_abrupt_exit(self):
        source=self.prepare_legacy();before=source.read_bytes();dest=self.root/'migrated'
        # Exit inside a staged write, bypassing finally/context-manager cleanup.
        script='''import importlib.util,os,sys
from pathlib import Path
spec=importlib.util.spec_from_file_location('crash_test',sys.argv[1])
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module); sys.path.insert(0,str(Path(sys.argv[1]).parent.parent/"tests")); __import__("core_adapter").bind(module)
original=module.atomic
def crash(path,data):
    original(path,data)
    os._exit(73)
module.atomic=crash
module.main(['migrate','--mission',sys.argv[2],'--destination',sys.argv[3]])
'''
        result=subprocess.run(['python3','-c',script,CLI,str(self.mission),str(dest)],capture_output=True)
        self.assertEqual(result.returncode,73)
        self.assertFalse(dest.exists())
        self.assertTrue(any(p.is_dir() for p in self.root.glob('.mission-migration-*')))
        import fcntl
        lock_path=next(self.root.glob('.mission-migration-*.lock'))
        stage=next(self.root.glob('.mission-migration-*.stage'))
        staged_bytes=(stage/'contract.json').read_bytes()
        with lock_path.open('a+') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            self.assertEqual(self.call('migrate','--destination',str(dest)).returncode,2)
            self.assertEqual((stage/'contract.json').read_bytes(),staged_bytes)
        unrelated=self.root/'.mission-migration-unrelated';unrelated.mkdir();(unrelated/'keep').touch()
        self.assertEqual(self.call('migrate','--destination',str(dest)).returncode,0)
        leftovers=[p for p in self.root.glob('.mission-migration-*') if p.is_dir() and p!=unrelated]
        self.assertEqual(leftovers,[])
        self.assertTrue((unrelated/'keep').exists())
        self.assertEqual(source.read_bytes(),before)
        self.assertTrue((dest/'legacy/contract.json').exists())

class WslReleaseCompatibility(unittest.TestCase):
    setUp = original_fixtures.Lifecycle.setUp
    save = original_fixtures.Lifecycle.save
    call = original_fixtures.Lifecycle.call
    init = original_fixtures.Lifecycle.init

    def test_windows_edited_bom_crlf_contract_and_checkpoint(self):
        self.data['mission']='Report for résumé'
        raw=json.dumps(self.data,ensure_ascii=False,indent=2).replace('\n','\r\n')
        self.contract.write_bytes(b'\xef\xbb\xbf'+raw.encode('utf-8'))
        self.assertEqual(self.call('validate','--contract',str(self.contract)).returncode,0)
        self.init()
        checkpoint=self.mission/'state/progress.json'
        checkpoint.write_bytes(b'\xef\xbb\xbf'+checkpoint.read_bytes().replace(b'\n',b'\r\n'))
        self.assertEqual(self.call('start','--step','one').returncode,0)
        self.assertEqual(self.call('verify','--step','one').returncode,0)
        self.assertEqual(self.call('finish').returncode,0)

    def test_utf8_contract_independent_of_process_locale(self):
        self.data['mission']='Résumé'
        self.contract.write_text(json.dumps(self.data,ensure_ascii=False),encoding='utf-8')
        env=dict(os.environ,LC_ALL='C',PYTHONUTF8='0',PYTHONCOERCECLOCALE='0')
        result=subprocess.run(['python3',CLI,'validate','--contract',str(self.contract)],env=env,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_wrappers_and_workspace_with_spaces_and_unicode(self):
        import shutil
        skill=self.root/'skill copy résumé';(skill/'scripts').mkdir(parents=True)
        repo=Path(CLI).parent.parent
        for name in ('mission.py','verify.sh','no_progress.sh'):
            shutil.copyfile(repo/'scripts'/name,skill/'scripts'/name)
        shutil.copytree(repo/'scripts/mission_control',skill/'scripts/mission_control')
        # VERSION is part of a complete skill installation.
        if (repo/'VERSION').exists():shutil.copyfile(repo/'VERSION',skill/'VERSION')
        workspace=self.root/'workspace with spaces résumé';workspace.mkdir()
        (workspace/'result résumé.txt').touch()
        self.data['steps'][0]['verify']=[['file','result résumé.txt']];self.save()
        self.assertEqual(self.call('init','--contract',str(self.contract),'--workspace',str(workspace)).returncode,0)
        self.call('start','--step','one');self.assertEqual(self.call('verify','--step','one').returncode,0)
        result=subprocess.run(['bash',str(skill/'scripts/verify.sh'),'file','result résumé.txt'],cwd=workspace,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_version_without_mission_or_valid_timeout(self):
        env=dict(os.environ,VERIFY_TIMEOUT='invalid')
        for command in (['python3',CLI,'--version'],['bash','scripts/verify.sh','--version'],['bash','scripts/no_progress.sh','--version']):
            result=subprocess.run(command,cwd=Path(CLI).parent.parent,env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(result.stdout.strip(),'Mission Control 0.4.2.9')

class GoalReviewLifecycle(unittest.TestCase):
    setUp = original_fixtures.Lifecycle.setUp
    save = original_fixtures.Lifecycle.save
    call = original_fixtures.Lifecycle.call
    init = original_fixtures.Lifecycle.init
    state_bytes = original_fixtures.BlockTransitions.state_bytes

    def complete(self):
        self.init();self.call('start','--step','one')
        self.assertEqual(self.call('verify','--step','one').returncode,0)
        self.assertEqual(self.call('finish').returncode,0)

    def test_goal_review_pass_records_rationale_and_preserves_evidence(self):
        self.complete();before=json.loads(self.call('status').stdout)
        self.assertEqual(self.call('goal-review','--verdict','pass','--rationale','Artifacts jointly meet original goal and constraints').returncode,0)
        state=json.loads(self.call('status').stdout)
        self.assertEqual(state['stop_reason'],'done_verified')
        self.assertEqual(state['steps'],before['steps'])
        self.assertEqual(state['attempts'],before['attempts'])
        self.assertEqual(state['goal_review']['verdict'],'pass')
        self.assertEqual(state['goal_review']['goal'],self.data['mission'])
        self.assertEqual(state['goal_review']['contract_hash'],state['contract_hash'])
        self.assertIn('timestamp',state['goal_review'])

    def test_failed_review_blocks_false_done_without_losing_steps(self):
        self.complete();before=json.loads(self.call('status').stdout)
        self.assertEqual(self.call('goal-review','--verdict','fail','--rationale','Steps passed but requested integration is missing').returncode,1)
        state=json.loads(self.call('status').stdout)
        self.assertEqual(state['stop_reason'],'blocked')
        self.assertEqual(state['steps'],before['steps'])
        self.assertEqual(self.call('finish').returncode,2)
        blocked=self.state_bytes()
        self.assertEqual(self.call('goal-review','--verdict','pass','--rationale','ignore gap').returncode,2)
        self.assertEqual(self.state_bytes(),blocked)
        self.assertEqual(self.call('resume').returncode,0)
        state=json.loads(self.call('status').stdout)
        self.assertNotIn('goal_review',state)
        self.assertEqual(state['goal_review_history'][-1]['verdict'],'fail')
        self.assertEqual(self.call('finish').returncode,2)

    def test_review_requires_finish_and_nonblank_rationale(self):
        self.init();before=self.state_bytes()
        self.assertEqual(self.call('goal-review','--verdict','pass','--rationale','too early').returncode,2)
        self.assertEqual(self.state_bytes(),before)
        self.call('start','--step','one');self.call('verify','--step','one');self.call('finish')
        before=self.state_bytes()
        for args in ([],['--verdict','pass'],['--verdict','pass','--rationale','   ']):
            self.assertEqual(self.call('goal-review',*args).returncode,2)
            self.assertEqual(self.state_bytes(),before)

    def test_repeated_review_preserves_history_and_resume_invalidates_pass(self):
        self.complete()
        self.call('goal-review','--verdict','pass','--rationale','first inspection')
        self.call('goal-review','--verdict','pass','--rationale','second inspection')
        state=json.loads(self.call('status').stdout)
        self.assertEqual(state['goal_review_history'][-1]['rationale'],'first inspection')
        self.call('resume');state=json.loads(self.call('status').stdout)
        self.assertNotIn('goal_review',state)
        self.assertEqual(state['goal_review_history'][-1]['rationale'],'second inspection')

    def test_repeated_finish_preserves_reported_exit_identity(self):
        self.complete()
        self.call('goal-review','--verdict','pass','--rationale','combined result meets original goal')
        before=self.state_bytes()
        self.assertEqual(self.call('finish').returncode,0)
        self.assertEqual(self.state_bytes(),before)

    def test_review_rejects_other_stop_reasons_without_mutation(self):
        self.complete();self.call('resume');self.call('stop','--reason','human_abort')
        before=self.state_bytes()
        self.assertEqual(self.call('goal-review','--verdict','fail','--rationale','cannot override abort').returncode,2)
        self.assertEqual(self.state_bytes(),before)
