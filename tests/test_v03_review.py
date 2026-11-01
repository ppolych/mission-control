"""Five corrective review passes; all artifacts and locks are synthetic."""
import json
import importlib.util
import os
import subprocess
import unittest

import test_controlled as base
import test_v03 as fixtures


class V03Review(unittest.TestCase):
    setUp = fixtures.MissionV3.setUp
    call = fixtures.MissionV3.call
    init = fixtures.MissionV3.init
    state = fixtures.MissionV3.state
    gate = fixtures.MissionV3.gate
    decide = fixtures.MissionV3.decide
    complete = fixtures.MissionV3.complete
    review = fixtures.MissionV3.review

    def checkpoint(self):
        return self.mission / 'state/progress.json'

    def test_changed_output_cannot_be_reblessed_using_old_passed_checks(self):
        self.data['steps'][0]['effects']['writes'] = ['output.txt']
        self.init()
        self.call('start', '--step', 'one')
        output = self.root / 'output.txt'
        output.write_text('checked output')
        self.call('verify', '--step', 'one')
        self.assertEqual(self.review().returncode, 0)
        output.write_text('changed without reverification')
        before = self.checkpoint().read_bytes()
        self.assertEqual(self.review().returncode, 2)
        self.assertEqual(self.checkpoint().read_bytes(), before)
        self.assertEqual(self.call('finish').returncode, 2)
        self.call('resume')
        self.call('start', '--step', 'one', '--revalidate')
        self.assertEqual(self.call('verify', '--step', 'one').returncode, 0)
        self.assertEqual(self.review().returncode, 0)

    def test_changed_input_before_first_acceptance_review_requires_reverification(self):
        self.data['steps'][0]['watch'] = ['input.txt']
        source = self.root / 'input.txt'
        source.write_text('checked input')
        self.init()
        self.complete()
        source.write_text('different input')
        self.assertEqual(self.review().returncode, 2)

    def test_recovery_decision_invalidates_previously_presented_report(self):
        self.init()
        self.call('start', '--step', 'one')
        self.call('resume')
        original = json.loads(self.call('recovery', '--step', 'one').stdout)
        args = ('--step', 'one', '--digest', original['digest'], '--rationale', 'Synthetic inspection')
        self.assertEqual(self.call('recover', *args, '--resolution', 'unknown').returncode, 1)
        before = self.checkpoint().read_bytes()
        self.assertEqual(self.call('recover', *args, '--resolution', 'completed').returncode, 2)
        self.assertEqual(self.checkpoint().read_bytes(), before)
        fresh = json.loads(self.call('recovery', '--step', 'one').stdout)
        self.assertNotEqual(fresh['digest'], original['digest'])
        self.assertEqual(self.call('recover', '--step', 'one', '--digest', fresh['digest'],
                                  '--resolution', 'completed', '--rationale', 'New explicit inspection').returncode, 0)

    def test_ungated_verification_cannot_follow_a_redirected_workspace(self):
        workspace = self.root / 'workspace'
        workspace.mkdir()
        elsewhere = self.root / 'elsewhere'
        elsewhere.mkdir()
        self.data['steps'][0]['verify'] = [['exit0', 'touch', 'unexpected']]
        self.contract.write_text(json.dumps(self.data))
        result = self.call('init', '--contract', str(self.contract), '--workspace', str(workspace))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.call('start', '--step', 'one')
        workspace.rmdir()
        workspace.symlink_to(elsewhere, target_is_directory=True)
        before = self.checkpoint().read_bytes()
        self.assertEqual(self.call('verify', '--step', 'one').returncode, 2)
        self.assertEqual(self.checkpoint().read_bytes(), before)
        self.assertFalse((elsewhere / 'unexpected').exists())

    def test_ungated_assessment_refuses_redirected_workspace(self):
        workspace = self.root / 'workspace'
        workspace.mkdir()
        elsewhere = self.root / 'elsewhere'
        elsewhere.mkdir()
        self.data['steps'][0]['verify'].append({'manual': 'Inspect actual output'})
        self.contract.write_text(json.dumps(self.data))
        self.assertEqual(self.call('init', '--contract', str(self.contract),
                                   '--workspace', str(workspace)).returncode, 0)
        self.call('start', '--step', 'one')
        workspace.rmdir()
        workspace.symlink_to(elsewhere, target_is_directory=True)
        before = self.checkpoint().read_bytes()
        self.assertEqual(self.call('assess', '--step', 'one', '--check', '1', '--verdict', 'pass',
                                   '--rationale', 'Outdated workspace').returncode, 2)
        self.assertEqual(self.checkpoint().read_bytes(), before)

    def test_symlink_lock_cannot_truncate_another_file(self):
        self.init()
        target = self.root / 'must-stay.txt'
        target.write_text('synthetic data must remain intact')
        lock = self.mission / '.lock'
        lock.unlink()
        lock.symlink_to(target)
        before = self.checkpoint().read_bytes()
        self.assertEqual(self.call('status').returncode, 2)
        self.assertEqual(target.read_text(), 'synthetic data must remain intact')
        self.assertEqual(self.checkpoint().read_bytes(), before)

    def test_regular_lock_is_never_truncated_or_replaced(self):
        self.init()
        lock = self.mission / '.lock'
        lock.write_text('persistent lock inode marker')
        inode = lock.stat().st_ino
        self.assertEqual(self.call('status').returncode, 0)
        self.assertEqual(lock.read_text(), 'persistent lock inode marker')
        self.assertEqual(lock.stat().st_ino, inode)

    def test_fifo_lock_is_refused_without_blocking(self):
        self.init()
        lock = self.mission / '.lock'
        lock.unlink()
        os.mkfifo(lock)
        result = subprocess.run(['python3', base.CLI, 'status', '--mission', str(self.mission)],
                                capture_output=True, text=True, timeout=2)
        self.assertEqual(result.returncode, 2)
        self.assertNotIn('Traceback', result.stderr)

    def test_approval_change_during_checks_cannot_complete_the_step(self):
        self.data['mode'] = 'controlled'
        source = self.root / 'input.txt'
        source.write_text('approved input')
        self.data['steps'][0].update(risk='high', watch=['input.txt'],
            verify=[['exit0', 'python3', '-c',
                     "from pathlib import Path;Path('input.txt').write_text('changed by synthetic check')"]])
        self.init()
        self.decide('approve')
        self.call('start', '--step', 'one')
        before = self.checkpoint().read_bytes()
        result = self.call('verify', '--step', 'one')
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.checkpoint().read_bytes(), before)
        self.assertEqual(self.state()['steps']['one']['status'], 'in_progress')
        self.assertEqual(source.read_text(), 'changed by synthetic check')

    def test_safe_legacy_autonomous_flow_remains_ungated(self):
        self.data['schema_version'] = 2
        self.init()
        self.complete()
        self.assertEqual(self.call('finish').returncode, 0)

    def test_previous_schema3_checkpoint_without_artifact_receipt_requires_revalidation(self):
        self.data['steps'][0]['effects']['writes'] = ['output.txt']
        (self.root / 'output.txt').write_text('synthetic existing artifact')
        self.init()
        self.complete()
        state = self.state()
        state['steps']['one'].pop('verified_artifacts')
        # Reconstruct the valid pre-fix checkpoint format, rather than testing
        # corruption rejection: the original 0.3 writer had no artifact receipt.
        spec = importlib.util.spec_from_file_location('pre_receipt_checkpoint', base.CLI)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module); __import__("core_adapter").bind(module)
        event = state['journal'][-1]
        event['state_hash'] = module.state_fingerprint(state)
        event['hash'] = module.digest({k: v for k, v in event.items() if k != 'hash'})
        self.checkpoint().write_text(json.dumps(state))
        self.assertEqual(self.call('status').returncode, 0)
        before = self.checkpoint().read_bytes()
        self.assertEqual(self.review().returncode, 2)
        self.assertEqual(self.checkpoint().read_bytes(), before)
        self.call('resume')
        self.call('start', '--step', 'one', '--revalidate')
        self.assertEqual(self.call('verify', '--step', 'one').returncode, 0)
        self.assertEqual(self.state()['attempts'], 1)
        self.assertEqual(self.review().returncode, 0)
