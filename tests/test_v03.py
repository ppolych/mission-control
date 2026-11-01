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
    def test_coverage_requires_explicit_evidence_review_before_finish(self):
            self.init()
            self.complete()
            coverage = json.loads(self.call('coverage').stdout)
            self.assertEqual(coverage['criteria'][0]['status'], 'unverified')
            self.assertEqual(self.call('finish').returncode, 2)
            self.assertEqual(self.review().returncode, 0)
            self.assertEqual(self.call('finish').returncode, 0)

    def test_unmet_and_unverified_are_not_supported(self):
            self.init()
            self.complete()
            for verdict in ('unmet', 'unverified'):
                self.assertEqual(self.review(verdict).returncode, int(verdict == 'unmet'))
                self.assertEqual(self.call('finish').returncode, 2)

    def test_supported_review_requires_completed_mapped_steps_and_references(self):
            self.init()
            self.assertEqual(self.review().returncode, 2)
            self.complete()
            self.assertEqual(self.call('criterion-review', '--criterion', 'AC-1',
                '--verdict', 'supported', '--rationale', 'Inspected').returncode, 2)

    def test_coverage_review_becomes_stale_after_resume_and_revalidation(self):
            self.init()
            self.complete()
            self.review()
            self.call('resume')
            self.call('start', '--step', 'one', '--revalidate')
            self.call('verify', '--step', 'one')
            coverage = json.loads(self.call('coverage').stdout)
            self.assertEqual(coverage['criteria'][0]['status'], 'unverified')
            self.assertEqual(self.call('finish').returncode, 2)

    def test_unverified_manual_assessment_does_not_execute_checks_or_spend_retry(self):
            marker = self.root / 'must-not-run'
            self.data['steps'][0]['verify'] = [['exit0', 'touch', str(marker)], {'manual': 'quality'}]
            self.init()
            self.call('start', '--step', 'one')
            self.assertEqual(self.call('assess', '--step', 'one', '--check', '1',
                '--verdict', 'unverified', '--rationale', 'No evidence yet').returncode, 0)
            before = (self.mission / 'state/progress.json').read_bytes()
            self.assertEqual(self.call('verify', '--step', 'one').returncode, 2)
            self.assertFalse(marker.exists())
            self.assertEqual((self.mission / 'state/progress.json').read_bytes(), before)

    def test_unmapped_and_unknown_criteria_fail_contract_validation(self):
            for change in ('unmapped', 'unknown', 'duplicate'):
                data = copy.deepcopy(self.data)
                if change == 'unmapped': data['steps'][0]['acceptance_refs'] = []
                elif change == 'unknown': data['steps'][0]['acceptance_refs'] = ['AC-no']
                else: data['acceptance'].append(data['acceptance'][0])
                self.contract.write_text(json.dumps(data))
                self.assertEqual(self.call('validate', '--contract', str(self.contract)).returncode, 2)

    def test_recovery_blocks_retry_until_report_is_reconciled(self):
            self.data['steps'][0]['effects']['writes'] = ['output.txt']
            self.init()
            self.call('start', '--step', 'one')
            (self.root / 'output.txt').write_text('partial output')
            self.call('resume')
            self.assertEqual(self.call('start', '--step', 'one', '--revalidate').returncode, 2)
            report = json.loads(self.call('recovery', '--step', 'one').stdout)
            self.assertEqual(report['files']['output.txt']['classification'], 'changed')
            self.assertEqual(self.call('recover', '--step', 'one', '--digest', report['digest'],
                '--resolution', 'completed', '--rationale', 'User inspected resulting artifact').returncode, 0)
            self.assertEqual(self.call('start', '--step', 'one', '--revalidate').returncode, 0)
            self.assertEqual(self.state()['attempts'], 1)

    def test_stale_recovery_report_and_partial_resolution_do_not_authorize_retry(self):
            self.data['steps'][0]['effects']['writes'] = ['output.txt']
            self.init()
            self.call('start', '--step', 'one')
            self.call('resume')
            report = json.loads(self.call('recovery', '--step', 'one').stdout)
            (self.root / 'output.txt').write_text('changed after review')
            self.assertEqual(self.call('recover', '--step', 'one', '--digest', report['digest'],
                '--resolution', 'not_applied', '--rationale', 'Inspected').returncode, 2)
            report = json.loads(self.call('recovery', '--step', 'one').stdout)
            self.assertEqual(self.call('recover', '--step', 'one', '--digest', report['digest'],
                '--resolution', 'partial', '--rationale', 'Still uncertain').returncode, 1)
            self.assertEqual(self.call('start', '--step', 'one', '--revalidate').returncode, 2)

    def test_not_applied_reconciliation_preserves_attempt_budget(self):
            self.data['budget'] = {'max_attempts_per_step': 1}
            self.init()
            self.call('start', '--step', 'one')
            self.call('resume')
            report = json.loads(self.call('recovery', '--step', 'one').stdout)
            result = self.call('recover', '--step', 'one', '--digest', report['digest'],
                '--resolution', 'not_applied', '--rationale', 'Confirmed no external effect')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(self.call('start', '--step', 'one').returncode, 1)
            self.assertEqual(self.state()['attempts'], 1)

    def test_unavailable_recovery_files_cannot_be_declared_completed(self):
            self.data['steps'][0]['effects']['writes'] = ['link']
            self.init()
            self.call('start', '--step', 'one')
            (self.root / 'target').write_text('private synthetic data')
            (self.root / 'link').symlink_to(self.root / 'target')
            self.call('resume')
            report = json.loads(self.call('recovery', '--step', 'one').stdout)
            self.assertEqual(report['files']['link']['classification'], 'unavailable')
            self.assertNotIn('private synthetic data', json.dumps(report))
            self.assertEqual(self.call('recover', '--step', 'one', '--digest', report['digest'],
                '--resolution', 'completed', '--rationale', 'Guess').returncode, 2)

    def test_changed_watched_input_invalidates_controlled_approval(self):
            self.data['mode'] = 'controlled'
            self.data['steps'][0].update(risk='high', watch=['input.txt'])
            source = self.root / 'input.txt'
            source.write_text('before')
            self.init()
            first = self.gate()
            self.assertEqual(self.decide('approve', first).returncode, 0)
            source.write_text('after')
            second = self.gate()
            self.assertNotEqual(first['digest'], second['digest'])
            self.assertEqual(self.state()['attempts'], 0)

    def test_stale_pending_input_snapshot_refuses_decision_without_state_changes(self):
            self.data['mode'] = 'controlled'
            self.data['steps'][0].update(risk='high', watch=['input.txt'])
            source = self.root / 'input.txt'
            source.write_text('before')
            self.init()
            request = self.gate()
            source.write_text('after')
            before = (self.mission / 'state/progress.json').read_bytes()
            self.assertEqual(self.decide('approve', request).returncode, 2)
            self.assertEqual((self.mission / 'state/progress.json').read_bytes(), before)

    def test_watch_refuses_symlink_and_parent_escape(self):
            self.data['steps'][0]['watch'] = ['../outside']
            self.contract.write_text(json.dumps(self.data))
            self.assertEqual(self.call('validate', '--contract', str(self.contract)).returncode, 2)
            self.data['mode'] = 'controlled'
            self.data['steps'][0].update(risk='high', watch=['link'])
            (self.root / 'target').write_text('synthetic secret')
            (self.root / 'link').symlink_to(self.root / 'target')
            self.init()
            self.assertEqual(self.call('start', '--step', 'one').returncode, 2)

    def test_effects_are_disclosed_verbatim_and_not_executed(self):
            self.data['mode'] = 'controlled'
            self.data['steps'][0]['risk'] = 'high'
            self.data['steps'][0]['effects'].update(network='external', external_actions=['Publish release'])
            self.init()
            self.assertEqual(self.gate()['step']['effects'], self.data['steps'][0]['effects'])

    def test_effect_validation_rejects_unknowns_invalid_types_and_safe_external_retry(self):
            for field, value in [('network', 'maybe'), ('reversible', 'true'),
                                 ('writes', ['/outside']), ('external_actions', 'deploy'),
                                 ('unknown', False)]:
                data = copy.deepcopy(self.data)
                data['steps'][0]['effects'][field] = value
                self.contract.write_text(json.dumps(data))
                self.assertEqual(self.call('validate', '--contract', str(self.contract)).returncode, 2)
            self.data['steps'][0].update(retry='safe')
            self.data['steps'][0]['effects']['external_actions'] = ['Deploy']
            self.contract.write_text(json.dumps(self.data))
            self.assertEqual(self.call('validate', '--contract', str(self.contract)).returncode, 2)

    def test_revision_is_separate_links_parent_and_never_copies_approval(self):
            self.init()
            before = (self.mission / 'state/progress.json').read_bytes()
            self.data['mission'] = 'Revised reviewed goal'
            self.contract.write_text(json.dumps(self.data))
            dest = self.root / 'revision'
            result = self.call('revise', '--contract', str(self.contract), '--destination', str(dest),
                               '--reason', 'User requested the new goal')
            self.assertEqual(result.returncode, 0, result.stderr)
            child = json.loads((dest / 'contract.json').read_text())
            self.assertEqual(child['revision']['parent_contract_hash'], self.state()['contract_hash'])
            self.assertEqual(child['revision']['number'], 1)
            self.assertFalse((dest / 'state/progress.json').exists())
            self.assertTrue((dest / 'lineage/parent-progress.json').exists())
            self.assertEqual((self.mission / 'state/progress.json').read_bytes(), before)

