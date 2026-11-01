import subprocess
import unittest
import json
import os
import tempfile
from pathlib import Path
CLI=str(Path('scripts/mission.py').resolve())

import test_mission as original_fixtures

class ArgvAndSymlinks(unittest.TestCase):
    setUp = original_fixtures.Lifecycle.setUp
    save = original_fixtures.Lifecycle.save
    call = original_fixtures.Lifecycle.call
    init = original_fixtures.Lifecycle.init

    def test_contract_preserves_literal_separator_arguments(self):
        check=['exit0','python3','-c',
               'import sys; assert sys.argv[1:] == ["--", "hello"]','--','hello']
        self.data['steps'][0]['verify']=[check];self.save()
        self.assertEqual(self.call('validate','--contract',str(self.contract)).returncode,0)
        self.init();self.call('start','--step','one')
        self.assertEqual(self.call('verify','--step','one').returncode,0)
        evidence=json.loads(self.call('status').stdout)['steps']['one']['evidence']
        self.assertEqual(evidence[0]['identity'],check)

    def test_wrapper_single_mode_preserves_separator(self):
        check=['exit0','python3','-c',
               'import sys; assert sys.argv[1:] == ["--", "hello"]','--','hello']
        result=subprocess.run(['bash','scripts/verify.sh','--single',*check],capture_output=True)
        self.assertEqual(result.returncode,0)
        result=subprocess.run(['bash','scripts/verify.sh','--single','file','a','--','file','b'],capture_output=True)
        self.assertEqual(result.returncode,2)

    def test_not_file_directory_entry_semantics(self):
        regular=self.root/'file';regular.touch()
        directory=self.root/'directory';directory.mkdir()
        valid=self.root/'valid';valid.symlink_to(regular)
        dangling=self.root/'dangling';dangling.symlink_to(self.root/'missing-target')
        for path,expected in [(regular,1),(directory,1),(valid,1),(dangling,1),(self.root/'absent',0)]:
            with self.subTest(path=path.name):
                result=subprocess.run(['bash','scripts/verify.sh','not_file',str(path)],capture_output=True)
                self.assertEqual(result.returncode,expected)
        self.data['steps'][0]['verify']=[['not_file',str(dangling)]];self.save();self.init()
        self.call('start','--step','one')
        self.assertEqual(self.call('verify','--step','one').returncode,1)

class InitBudgetEvidence(unittest.TestCase):
    setUp = original_fixtures.Lifecycle.setUp
    save = original_fixtures.Lifecycle.save
    call = original_fixtures.Lifecycle.call
    init = original_fixtures.Lifecycle.init
    state_bytes = original_fixtures.BlockTransitions.state_bytes

    def test_init_rejects_different_destination_without_data_loss(self):
        self.mission.mkdir();destination=self.mission/'contract.json'
        existing=dict(self.data,mission='existing mission')
        destination.write_text(json.dumps(existing)+'\n')
        before=destination.read_bytes()
        self.assertEqual(self.call('init','--contract',str(self.contract)).returncode,2)
        self.assertEqual(destination.read_bytes(),before)
        self.assertFalse((self.mission/'state/progress.json').exists())
        self.assertEqual(self.contract.read_text(),json.dumps(self.data))

    def test_init_from_destination_preserves_original_bytes(self):
        self.mission.mkdir();destination=self.mission/'contract.json'
        destination.write_text(json.dumps(self.data,indent=4)+'\n')
        before=destination.read_bytes()
        self.assertEqual(self.call('init','--contract',str(destination)).returncode,0)
        self.assertEqual(destination.read_bytes(),before)
        state=self.state_bytes()
        self.assertEqual(self.call('init','--contract',str(destination)).returncode,2)
        self.assertEqual(destination.read_bytes(),before);self.assertEqual(self.state_bytes(),state)

    def test_exhausted_step_does_not_stop_independent_work(self):
        self.data['budget']={'max_attempts_per_step':1}
        self.data['steps'][0]['verify']=[['exit0','false']]
        self.data['steps'] += [{'id':'two','verify':[['exit0','true']]},
                               {'id':'dependent','depends_on':['one'],'verify':[['exit0','true']]}]
        self.save();self.init();self.call('start','--step','one');self.call('verify','--step','one')
        self.assertEqual(self.call('start','--step','one').returncode,1)
        state=json.loads(self.call('status').stdout);self.assertIsNone(state['stop_reason'])
        before=self.state_bytes()
        self.assertEqual(self.call('start','--step','dependent').returncode,2)
        self.assertEqual(self.state_bytes(),before)
        self.assertEqual(self.call('start','--step','two').returncode,0)
        self.assertEqual(self.call('verify','--step','two').returncode,0)
        state=json.loads(self.call('status').stdout)
        self.assertEqual(state['stop_reason'],'budget_exhausted')
        self.assertEqual(state['steps']['two']['status'],'completed')
        self.assertEqual(self.call('finish').returncode,2)

    def test_command_evidence_preserves_actual_exit(self):
        self.data['steps'][0]['verify']=[['exec','exit 2']];self.save();self.init()
        self.call('start','--step','one');self.assertEqual(self.call('verify','--step','one').returncode,1)
        evidence=json.loads(self.call('status').stdout)['steps']['one']['evidence'][0]
        self.assertEqual(evidence['code'],1)
        self.assertEqual(evidence['command_exit_status'],2)
        self.assertIsNone(evidence['signal'])
        self.assertIsNone(evidence['error_type'])

    def test_signal_timeout_and_start_error_evidence(self):
        cases=[(['exit0','python3','-c','import os,signal;os.kill(os.getpid(),signal.SIGTERM)'],'signal',-15,15),
               (['exit0','/does-not-exist/private-command'],'FileNotFoundError',None,None),
               (['exit0','python3','-c','import time;time.sleep(2)'],'timeout',None,None)]
        for index,(check,error,exit_status,signal_number) in enumerate(cases):
            with self.subTest(check=check):
                self.mission=self.root/str(index)
                self.data['steps'][0]['verify']=[check];self.save();self.init();self.call('start','--step','one')
                env=dict(os.environ,VERIFY_TIMEOUT='0.1')
                result=subprocess.run(['python3',CLI,'verify','--mission',str(self.mission),'--step','one'],env=env,capture_output=True,text=True)
                self.assertEqual(result.returncode,1)
                evidence=json.loads(self.call('status').stdout)['steps']['one']['evidence'][0]
                self.assertEqual(evidence['error_type'],error)
                self.assertEqual(evidence['command_exit_status'],exit_status)
                self.assertEqual(evidence['signal'],signal_number)
                self.assertNotIn('private-command',result.stderr)

    def test_interrupted_init_recovers_without_replacing_contract(self):
        import importlib.util
        from unittest.mock import patch
        spec=importlib.util.spec_from_file_location('mission_under_test',CLI)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module); __import__("core_adapter").bind(module)
        real_atomic=module.atomic
        def interrupt(path,data):
            if path.name=='progress.json':raise OSError('simulated checkpoint failure')
            return real_atomic(path,data)
        with patch.object(module,'atomic',side_effect=interrupt):
            with self.assertRaises(OSError):
                module.main(['init','--mission',str(self.mission),'--contract',str(self.contract)])
        destination=self.mission/'contract.json';before=destination.read_bytes()
        self.assertFalse((self.mission/'state/progress.json').exists())
        self.assertEqual(self.call('init','--contract',str(self.contract)).returncode,0)
        self.assertEqual(destination.read_bytes(),before)
        self.assertEqual(json.loads(self.call('status').stdout)['steps'],{})

    def test_exhausted_parent_blocks_descendants_final_reason(self):
        self.data['budget']={'max_attempts_per_step':1}
        self.data['steps'][0]['verify']=[['exit0','false']]
        self.data['steps'].append({'id':'child','depends_on':['one'],'verify':[['exit0','true']]})
        self.save();self.init();self.call('start','--step','one');self.call('verify','--step','one')
        self.assertEqual(self.call('start','--step','one').returncode,1)
        state=json.loads(self.call('status').stdout)
        self.assertEqual(state['stop_reason'],'budget_exhausted')
        self.assertEqual(self.call('start','--step','child').returncode,2)

class AdditionalBugReview(unittest.TestCase):
    setUp = original_fixtures.Lifecycle.setUp
    save = original_fixtures.Lifecycle.save
    call = original_fixtures.Lifecycle.call
    init = original_fixtures.Lifecycle.init
    state_bytes = original_fixtures.BlockTransitions.state_bytes

    def test_corrupt_checkpoint_rejected_without_traceback_or_mutation(self):
        self.init();path=self.mission/'state/progress.json'
        original=json.loads(path.read_text())
        for state in ([], dict(original,steps={'one':None}),dict(original,attempts=-1),
                      dict(original,steps={'one':{'status':'pending','attempts':-1}})):
            with self.subTest(state=state):
                path.write_text(json.dumps(state));before=path.read_bytes()
                result=self.call('start','--step','one')
                self.assertEqual(result.returncode,2)
                self.assertNotIn('Traceback',result.stderr)
                self.assertEqual(path.read_bytes(),before)

    def test_migration_invalid_backup_leaves_no_partial_destination(self):
        self.mission.mkdir();(self.mission/'state').mkdir()
        original={'mission':'legacy','features':[{'id':'one','steps':['review']} ]}
        source=self.mission/'contract.json';source.write_text(json.dumps(original))
        (self.mission/'state/progress.json').write_text('{broken')
        dest=self.root/'migrated'
        result=self.call('migrate','--destination',str(dest))
        self.assertEqual(result.returncode,2)
        self.assertFalse(dest.exists())
        self.assertEqual(json.loads(source.read_text()),original)

    def test_malformed_legacy_input_has_clean_error(self):
        self.mission.mkdir();source=self.mission/'contract.json'
        for original in ([],{'mission':'legacy','features':[None]}):
            source.write_text(json.dumps(original))
            result=self.call('migrate','--destination',str(self.root/'dest'))
            self.assertEqual(result.returncode,2)
            self.assertNotIn('Traceback',result.stderr)

    def test_nul_argument_rejected_during_validation(self):
        self.data['steps'][0]['verify']=[['exit0','printf','bad\x00argument']];self.save()
        self.assertEqual(self.call('validate','--contract',str(self.contract)).returncode,2)

    def test_blank_manual_rationale_rejected(self):
        self.data['steps'][0]['verify']=[{'manual':'quality'}];self.save();self.init()
        self.call('start','--step','one');before=self.state_bytes()
        result=self.call('assess','--step','one','--check','0','--verdict','pass','--rationale','   ')
        self.assertEqual(result.returncode,2);self.assertEqual(self.state_bytes(),before)

class ContractAndHistoryReview(unittest.TestCase):
    setUp = original_fixtures.Lifecycle.setUp
    save = original_fixtures.Lifecycle.save
    call = original_fixtures.Lifecycle.call
    init = original_fixtures.Lifecycle.init
    state_bytes = original_fixtures.BlockTransitions.state_bytes

    def test_external_contract_cannot_bypass_frozen_destination(self):
        self.init()
        destination=self.mission/'contract.json'
        changed=dict(self.data,mission='changed destination')
        destination.write_text(json.dumps(changed))
        before=self.state_bytes()
        result=self.call('start','--step','one','--contract',str(self.contract))
        self.assertEqual(result.returncode,2)
        self.assertEqual(self.state_bytes(),before)

    def test_legacy_check_string_not_split_into_character_criteria(self):
        self.mission.mkdir()
        source=self.mission/'contract.json'
        source.write_text(json.dumps({'mission':'legacy','features':[{'id':'one','steps':'check'}]}))
        before=source.read_bytes();destination=self.root/'migrated'
        self.assertEqual(self.call('migrate','--destination',str(destination)).returncode,2)
        self.assertFalse(destination.exists());self.assertEqual(source.read_bytes(),before)

    def test_failed_manual_judgment_survives_retry(self):
        self.data['steps'][0]['verify']=[{'manual':'quality'}];self.save();self.init()
        self.call('start','--step','one')
        self.call('assess','--step','one','--check','0','--verdict','fail','--rationale','first version omitted source')
        self.assertEqual(self.call('verify','--step','one').returncode,1)
        self.assertEqual(self.call('start','--step','one').returncode,0)
        state=json.loads(self.call('status').stdout)
        history=state['steps']['one']['history']
        self.assertTrue(any(item.get('manual',{}).get('0',{}).get('rationale')=='first version omitted source' for item in history))
        self.assertEqual(state['steps']['one']['manual'],{})

    def test_deep_dependency_chain_validates_without_recursion_failure(self):
        self.data['steps']=[{'id':str(i),'depends_on':[str(i+1)] if i<1199 else [],'verify':[['exit0','true']]} for i in range(1200)]
        self.save();result=self.call('validate','--contract',str(self.contract))
        self.assertEqual(result.returncode,0,result.stderr)
