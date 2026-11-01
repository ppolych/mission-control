"""Schema-3 workflow tests run only in disposable workspaces."""
import copy
import importlib.util
import json
from pathlib import Path
from unittest.mock import patch
import unittest

import test_controlled as fixtures


from v3_fixture import V3Fixture

class MissionV3(V3Fixture):
    def test_revision_diff_is_read_only_and_shows_changed_scope(self):
            self.init()
            before = (self.mission / 'state/progress.json').read_bytes()
            self.data['steps'][0]['effects']['writes'] = ['new.txt']
            self.contract.write_text(json.dumps(self.data))
            result = self.call('revision-diff', '--contract', str(self.contract))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('new.txt', result.stdout)
            self.assertEqual((self.mission / 'state/progress.json').read_bytes(), before)

    def test_revision_refuses_existing_destination_or_missing_reason(self):
            self.init()
            dest = self.root / 'existing'
            dest.mkdir()
            self.assertEqual(self.call('revise', '--contract', str(self.contract),
                '--destination', str(dest), '--reason', 'Change').returncode, 2)
            self.assertEqual(self.call('revise', '--contract', str(self.contract),
                '--destination', str(self.root / 'new')).returncode, 2)
            self.assertFalse((self.root / 'new').exists())

    def test_journal_is_checkpoint_atomic_and_records_real_transitions(self):
            self.init()
            self.complete()
            events = json.loads(self.call('history').stdout)['events']
            self.assertEqual([e['action'] for e in events], ['init', 'start', 'verify'])
            self.assertEqual([e['sequence'] for e in events], [1, 2, 3])
            self.assertEqual(events[1]['previous'], events[0]['hash'])
            self.assertEqual(events[1]['step_status'], 'in_progress')
            self.assertEqual(events[2]['step_status'], 'completed')
            self.assertEqual(events[2]['attempts'], 1)
            before = (self.mission / 'state/progress.json').read_bytes()
            self.call('status'); self.call('coverage'); self.call('history')
            self.assertEqual((self.mission / 'state/progress.json').read_bytes(), before)

    def test_journal_detects_corruption_before_mutation(self):
            self.init()
            path = self.mission / 'state/progress.json'
            state = self.state()
            state['journal'][0]['action'] = 'changed'
            path.write_text(json.dumps(state))
            before = path.read_bytes()
            self.assertEqual(self.call('start', '--step', 'one').returncode, 2)
            self.assertEqual(path.read_bytes(), before)

    def test_failed_checkpoint_write_publishes_neither_transition_nor_event(self):
            self.init()
            path = self.mission / 'state/progress.json'
            before = path.read_bytes()
            spec = importlib.util.spec_from_file_location('mission_v03', fixtures.CLI)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module); __import__("core_adapter").bind(module)
            with patch.object(module.os, 'replace', side_effect=OSError('simulated interruption')):
                with self.assertRaises(OSError):
                    module.main(['start', '--mission', str(self.mission), '--step', 'one'])
            self.assertEqual(path.read_bytes(), before)

    def test_safe_retry_still_preserves_budget_and_journal(self):
            self.data['steps'][0]['retry'] = 'safe'
            self.init()
            self.call('start', '--step', 'one')
            self.call('resume')
            self.assertEqual(self.call('start', '--step', 'one', '--revalidate').returncode, 0)
            self.assertEqual(self.state()['attempts'], 1)
            self.assertFalse(self.state()['steps']['one'].get('recovery_required', False))

    def test_changed_output_invalidates_coverage_and_post_finish_goal_review(self):
            self.data['steps'][0]['effects']['writes'] = ['output.txt']
            self.init()
            self.call('start', '--step', 'one')
            output = self.root / 'output.txt'
            output.write_text('verified output')
            self.call('verify', '--step', 'one')
            self.review()
            self.assertEqual(self.call('finish').returncode, 0)
            output.write_text('modified later')
            coverage = json.loads(self.call('coverage').stdout)
            self.assertTrue(coverage['criteria'][0]['stale'])
            self.assertEqual(self.call('goal-review', '--verdict', 'pass',
                '--rationale', 'Outdated evidence').returncode, 2)
            self.assertEqual(self.call('goal-review', '--verdict', 'fail',
                '--rationale', 'Output changed after finish').returncode, 1)

    def test_failed_execution_and_explicit_block_both_require_recovery(self):
            for command in ('verify', 'block'):
                with self.subTest(command=command):
                    self.mission = self.root / command
                    self.data['steps'][0]['verify'] = [['exit0', 'false']]
                    self.init()
                    self.call('start', '--step', 'one')
                    if command == 'verify': self.call('verify', '--step', 'one')
                    else: self.call('block', '--step', 'one', '--reason', 'Partial action')
                    self.assertTrue(self.state()['steps']['one']['recovery_required'])
                    self.assertEqual(self.call('start', '--step', 'one').returncode, 2)
                    self.call('resume')
                    report = json.loads(self.call('recovery', '--step', 'one').stdout)
                    if command == 'verify':self.assertEqual(report['last_verification'][0]['code'], 1)

    def test_watched_input_changes_during_work_prevent_verification_commands(self):
            self.data['mode'] = 'controlled'
            marker = self.root / 'must-not-run'
            self.data['steps'][0].update(risk='high', watch=['input.txt'],
                                        verify=[['exit0', 'touch', str(marker)]])
            source = self.root / 'input.txt'
            source.write_text('before')
            self.init()
            self.decide('approve')
            self.call('start', '--step', 'one')
            source.write_text('after')
            before = (self.mission / 'state/progress.json').read_bytes()
            self.assertEqual(self.call('verify', '--step', 'one').returncode, 2)
            self.assertEqual((self.mission / 'state/progress.json').read_bytes(), before)
            self.assertFalse(marker.exists())

    def test_snapshot_rejects_fifo_and_oversized_files_without_hanging(self):
            import os
            self.data['mode'] = 'controlled'
            self.data['steps'][0]['risk'] = 'high'
            os.mkfifo(self.root / 'pipe')
            (self.root / 'large').write_bytes(b'x' * (1024 * 1024 + 1))
            for name in ('pipe', 'large'):
                self.mission = self.root / ('mission-' + name)
                self.data['steps'][0]['watch'] = [name]
                self.init()
                self.assertEqual(self.call('start', '--step', 'one').returncode, 2)
                self.assertEqual(self.state()['attempts'], 0)

    def test_journal_detects_state_changes_and_keeps_failed_requests_read_only(self):
            self.init()
            path = self.mission / 'state/progress.json'
            before = path.read_bytes()
            self.assertEqual(self.call('verify', '--step', 'one').returncode, 2)
            self.assertEqual(path.read_bytes(), before)
            state = self.state()
            state['attempts'] += 1
            path.write_text(json.dumps(state))
            altered = path.read_bytes()
            self.assertEqual(self.call('resume').returncode, 2)
            self.assertEqual(path.read_bytes(), altered)

    def test_revision_publication_failure_leaves_parent_and_destination_intact(self):
            self.init()
            before = (self.mission / 'state/progress.json').read_bytes()
            spec = importlib.util.spec_from_file_location('mission_v03_revision', fixtures.CLI)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module); __import__("core_adapter").bind(module)
            dest = self.root / 'new-revision'
            with patch.object(module.os, 'rename', side_effect=OSError('simulated publication failure')):
                with self.assertRaises(OSError):
                    module.main(['revise', '--mission', str(self.mission), '--contract', str(self.contract),
                                 '--destination', str(dest), '--reason', 'Explicit revision'])
            self.assertFalse(dest.exists())
            self.assertEqual((self.mission / 'state/progress.json').read_bytes(), before)

    def test_revision_chain_can_be_initialized_and_extended(self):
            self.init()
            parent = self.mission
            first = self.root / 'revision-one'
            result = self.call('revise', '--contract', str(self.contract), '--destination', str(first),
                               '--reason', 'First explicit revision')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.mission = first
            result = self.call('init', '--workspace', str(self.root))
            self.assertEqual(result.returncode, 0, result.stderr)
            second = self.root / 'revision-two'
            self.assertEqual(self.call('revise', '--contract', str(self.contract), '--destination', str(second),
                                      '--reason', 'Second explicit revision').returncode, 0)
            self.assertEqual(json.loads((second / 'contract.json').read_text())['revision']['number'], 2)
            self.assertTrue((parent / 'state/progress.json').exists())

    def test_file_evidence_is_checked_and_bound_to_review(self):
            output = self.root / 'evidence.txt'
            self.init()
            self.complete()
            args = ('--criterion', 'AC-1', '--verdict', 'supported', '--rationale', 'Inspected file',
                    '--evidence-ref', 'file:evidence.txt')
            self.assertEqual(self.call('criterion-review', *args).returncode, 2)
            output.write_text('original evidence')
            self.assertEqual(self.call('criterion-review', *args).returncode, 0)
            output.write_text('changed evidence')
            self.assertEqual(self.call('finish').returncode, 2)

    def test_declaration_paths_and_booleans_are_strict(self):
            for field, value in [('watch', ['/absolute']), ('retry', 'automatic')]:
                data = copy.deepcopy(self.data)
                data['steps'][0][field] = value
                self.contract.write_text(json.dumps(data))
                self.assertEqual(self.call('validate', '--contract', str(self.contract)).returncode, 2)
            self.data['steps'][0]['effects']['reversible'] = 1
            self.contract.write_text(json.dumps(self.data))
            self.assertEqual(self.call('validate', '--contract', str(self.contract)).returncode, 2)

    def test_legacy_revision_metadata_cannot_publish_an_invalid_child(self):
            proposed = copy.deepcopy(self.data)
            self.data.update(schema_version=2, revision={'number': -2})
            self.init()
            before = (self.mission / 'state/progress.json').read_bytes()
            self.contract.write_text(json.dumps(proposed))
            dest = self.root / 'invalid-child'
            result = self.call('revise', '--contract', str(self.contract), '--destination', str(dest),
                               '--reason', 'Synthetic reviewed revision')
            self.assertEqual(result.returncode, 2)
            self.assertFalse(dest.exists())
            self.assertEqual((self.mission / 'state/progress.json').read_bytes(), before)

