"""Strict discipline: a step needs an observed change or an explicit no-change outcome."""
import copy
import json
import unittest

from strict_fixture import StrictFixture
from v3_fixture import V3Fixture

MANUAL_LABEL = 'manual_evidence_only: agent assessment, not automated verification'


class WithoutDiscipline(V3Fixture):
    def test_contract_without_the_field_keeps_old_behavior(self):
        self.data['steps'][0]['effects']['writes'] = ['out.txt']
        self.data['steps'][0]['verify'] = [['exit0', 'true'], ['exit0', 'test', '-e', str(self.root)]]
        self.init()
        self.complete()
        entry = self.state()['steps']['one']
        self.assertNotIn('discipline_outcome', entry)
        self.assertNotIn('first_effect_baseline', entry)

    def test_already_satisfied_needs_strict_discipline(self):
        self.init()
        self.assertEqual(self.call('start', '--step', 'one').returncode, 0)
        result = self.call('verify', '--step', 'one', '--already-satisfied', '--rationale', 'x')
        self.assertEqual(result.returncode, 2)
        self.assertIn('strict', result.stderr)

    def test_schema_two_draft_cannot_declare_discipline(self):
        data = {'schema_version': 2, 'mission': 'm', 'discipline': 'strict',
                'steps': [{'id': 'a', 'verify': [['exit0', 'true']]}]}
        self.contract.write_text(json.dumps(data), encoding='utf-8')
        self.assertEqual(self.call('validate', '--contract', str(self.contract)).returncode, 2)


class ChangeProof(StrictFixture):
    def start(self):
        self.init()
        self.assertEqual(self.call('start', '--step', 'one').returncode, 0)

    def test_step_without_any_change_is_refused(self):
        self.write()
        self.start()
        before = (self.mission / 'state/progress.json').read_bytes()
        result = self.call('verify', '--step', 'one')
        self.assertEqual(result.returncode, 2)
        self.assertIn('--already-satisfied', result.stderr)
        self.assertEqual((self.mission / 'state/progress.json').read_bytes(), before)

    def test_observed_change_passes_and_is_recorded(self):
        self.start()
        self.write()
        result = self.call('verify', '--step', 'one')
        self.assertEqual(result.returncode, 0, result.stderr)
        outcome = self.entry()['discipline_outcome']
        self.assertEqual(outcome['outcome'], 'changed')
        self.assertEqual(outcome['evidence_basis'], 'automated')

    def test_deleting_a_declared_file_counts_as_change(self):
        path = self.write()
        self.step['verify'] = [['not_file', 'out.txt']]
        self.start()
        path.unlink()
        self.assertEqual(self.call('verify', '--step', 'one').returncode, 0)

    def test_retry_keeps_work_of_the_first_attempt(self):
        self.step['verify'] = [['grep', 'final', 'out.txt']]
        self.step['retry'] = 'safe'
        self.start()
        self.write(text='draft')
        self.assertEqual(self.call('verify', '--step', 'one').returncode, 1)
        self.assertEqual(self.call('start', '--step', 'one').returncode, 0)
        self.write(text='final')
        self.assertEqual(self.call('verify', '--step', 'one').returncode, 0)
        self.assertEqual(self.entry()['first_effect_baseline']['out.txt']['status'], 'absent')

    def test_retry_with_no_new_change_passes_on_first_attempt_change(self):
        self.step['verify'] = [['exit0', 'test', '-e', 'flag'], ['file', 'out.txt']]
        self.step['retry'] = 'safe'
        self.start()
        self.write()
        self.assertEqual(self.call('verify', '--step', 'one').returncode, 1)
        self.assertEqual(self.call('start', '--step', 'one').returncode, 0)
        (self.root / 'flag').write_text('', encoding='utf-8')
        self.assertEqual(self.call('verify', '--step', 'one').returncode, 0)

    def test_revalidation_is_not_required_to_change_anything(self):
        self.start()
        self.write()
        self.assertEqual(self.call('verify', '--step', 'one').returncode, 0)
        self.assertEqual(self.call('stop', '--reason', 'human_paused').returncode, 0)
        self.assertEqual(self.call('resume').returncode, 0)
        self.assertEqual(self.call('start', '--step', 'one', '--revalidate').returncode, 0)
        result = self.call('verify', '--step', 'one')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.entry()['discipline_outcome']['outcome'], 'changed')


class NoChangeOutcome(StrictFixture):
    def start(self):
        self.init()
        self.assertEqual(self.call('start', '--step', 'one').returncode, 0)

    def test_existing_state_is_a_valid_recorded_outcome(self):
        self.write()
        self.start()
        result = self.call('verify', '--step', 'one', '--already-satisfied', '--rationale', 'File exists as requested')
        self.assertEqual(result.returncode, 0, result.stderr)
        outcome = self.entry()['discipline_outcome']
        self.assertEqual(outcome['outcome'], 'no_change')
        self.assertEqual(outcome['rationale'], 'File exists as requested')
        self.assertEqual(outcome['evidence_basis'], 'automated')
        report = json.loads(self.call('handoff').stdout)
        self.assertEqual(report['steps']['one']['discipline_outcome']['outcome'], 'no_change')

    def test_needs_a_rationale(self):
        self.write()
        self.start()
        self.assertEqual(self.call('verify', '--step', 'one', '--already-satisfied').returncode, 2)

    def test_refused_when_a_declared_write_changed(self):
        self.start()
        self.write()
        result = self.call('verify', '--step', 'one', '--already-satisfied', '--rationale', 'x')
        self.assertEqual(result.returncode, 2)
        self.assertIn('changed', result.stderr)

    def test_failing_checks_still_fail(self):
        self.step['verify'] = [['grep', 'absent-text', 'out.txt']]
        self.write()
        self.start()
        self.assertEqual(self.call('verify', '--step', 'one', '--already-satisfied', '--rationale', 'x').returncode, 1)
        self.assertEqual(self.entry()['status'], 'pending')

    def test_refused_during_revalidation(self):
        self.write()
        self.start()
        self.assertEqual(self.call('verify', '--step', 'one', '--already-satisfied', '--rationale', 'x').returncode, 0)
        self.assertEqual(self.call('stop', '--reason', 'human_paused').returncode, 0)
        self.assertEqual(self.call('resume').returncode, 0)
        self.assertEqual(self.call('start', '--step', 'one', '--revalidate').returncode, 0)
        self.assertEqual(self.call('verify', '--step', 'one', '--already-satisfied', '--rationale', 'x').returncode, 2)

    def test_flag_is_only_for_verify(self):
        self.write()
        self.start()
        self.assertEqual(self.call('status', '--already-satisfied').returncode, 2)


class ManualOnly(StrictFixture):
    def setUp(self):
        super().setUp()
        self.step['verify'] = [{'manual': 'Compare the output with the request'}]

    def assess(self):
        self.assertEqual(self.call('assess', '--step', 'one', '--check', '0', '--verdict', 'pass',
                                   '--rationale', 'Inspected').returncode, 0)

    def test_refused_without_the_declared_exception(self):
        code, error = self.validate_error()
        self.assertEqual(code, 2)
        self.assertIn('manual_only', error)

    def test_exception_needs_a_reason(self):
        self.step['manual_only'] = {'reason': ' '}
        self.assertEqual(self.validate_error()[0], 2)

    def test_exception_contradicts_an_automated_check(self):
        self.step['manual_only'] = {'reason': 'Judgment only'}
        self.step['verify'].append(['file', 'out.txt'])
        code, error = self.validate_error()
        self.assertEqual(code, 2)
        self.assertIn('manual_only', error)

    def test_no_change_is_labelled_as_manual_evidence(self):
        self.step['manual_only'] = {'reason': 'Only a person can judge tone'}
        self.write()
        self.init()
        self.assertEqual(self.call('start', '--step', 'one').returncode, 0)
        self.assess()
        result = self.call('verify', '--step', 'one', '--already-satisfied', '--rationale', 'Already right')
        self.assertEqual(result.returncode, 0, result.stderr)
        outcome = self.entry()['discipline_outcome']
        self.assertEqual(outcome['evidence_basis'], MANUAL_LABEL)
        self.assertEqual(outcome['manual_only_reason'], 'Only a person can judge tone')
        self.assertIn(MANUAL_LABEL, result.stderr)

    def test_changed_step_is_labelled_too(self):
        self.step['manual_only'] = {'reason': 'Only a person can judge tone'}
        self.init()
        self.assertEqual(self.call('start', '--step', 'one').returncode, 0)
        self.write()
        self.assess()
        self.assertEqual(self.call('verify', '--step', 'one').returncode, 0)
        self.assertEqual(self.entry()['discipline_outcome']['evidence_basis'], MANUAL_LABEL)

    def test_cannot_support_behavior_evidence(self):
        self.step['manual_only'] = {'reason': 'Only a person can judge tone'}
        self.data['acceptance'][0]['evidence_kinds'] = ['behavior']
        self.init()
        self.assertEqual(self.call('start', '--step', 'one').returncode, 0)
        self.write()
        self.assess()
        self.assertEqual(self.call('verify', '--step', 'one').returncode, 0)
        result = self.call('criterion-review', '--criterion', 'AC-1', '--verdict', 'supported', '--rationale', 'r',
                           '--evidence-ref', 'check:one:0', '--evidence-kind', 'behavior')
        self.assertEqual(result.returncode, 2)
        self.assertIn('automated', result.stderr)


class AutomatedEvidence(StrictFixture):
    def run_review(self, ref):
        self.data['acceptance'][0]['evidence_kinds'] = ['behavior']
        self.step['verify'] = [['file', 'out.txt'], {'manual': 'Inspect'}]
        self.init()
        self.assertEqual(self.call('start', '--step', 'one').returncode, 0)
        self.write()
        self.assertEqual(self.call('assess', '--step', 'one', '--check', '1', '--verdict', 'pass',
                                   '--rationale', 'Inspected').returncode, 0)
        self.assertEqual(self.call('verify', '--step', 'one').returncode, 0)
        return self.call('criterion-review', '--criterion', 'AC-1', '--verdict', 'supported', '--rationale', 'r',
                         '--evidence-ref', ref, '--evidence-kind', 'behavior')

    def test_behavior_can_rest_on_an_automated_check(self):
        result = self.run_review('check:one:0')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_behavior_cannot_rest_on_the_agents_assessment(self):
        self.assertEqual(self.run_review('check:one:1').returncode, 2)

    def test_behavior_cannot_rest_on_a_file_reference(self):
        self.assertEqual(self.run_review('file:out.txt').returncode, 2)


class DraftRules(StrictFixture):
    def assert_refused(self, *mention):
        code, error = self.validate_error()
        self.assertEqual(code, 2, error)
        for text in mention:
            self.assertIn(text, error)

    def test_valid_draft_passes(self):
        self.assertEqual(self.validate_error()[0], 0)

    def test_unknown_discipline_value(self):
        self.data['discipline'] = 'lenient'
        self.assert_refused('discipline')

    def test_trivially_true_checks(self):
        for check in (['exit0', 'true'], ['exit0', ':'], ['exit0', '/usr/bin/true'], ['exec', 'true'],
                      ['exec', ' exit 0 '], ['exit0', 'sh', '-c', 'true'], ['exit0', 'bash', '-c', 'exit 0'],
                      ['test', 'nonempty']):
            with self.subTest(check=check):
                self.step['verify'] = [copy.copy(check)]
                self.assert_refused('trivially')

    def test_step_with_writes_needs_a_test_first_decision(self):
        del self.step['test_first_exempt']
        self.assert_refused('test_first')

    def test_step_without_writes_needs_no_decision(self):
        del self.step['test_first_exempt']
        self.step['effects']['writes'] = []
        self.assertEqual(self.validate_error()[0], 0)

    def test_exemption_shape(self):
        for value in ({'kind': 'docs'}, {'kind': 'other', 'reason': 'x'}, {'kind': 'docs', 'reason': ' '}, 'docs',
                      {'kind': 'docs', 'reason': 'x', 'extra': 1}):
            with self.subTest(value=value):
                self.step['test_first_exempt'] = value
                self.assert_refused('test_first_exempt')

    def test_each_exemption_kind_is_accepted(self):
        for kind in ('docs', 'config', 'exploratory', 'low_impact', 'not_reproducible', 'not_applicable'):
            with self.subTest(kind=kind):
                self.step['test_first_exempt'] = {'kind': kind, 'reason': 'Because'}
                self.assertEqual(self.validate_error()[0], 0)

    def test_template_is_strict_and_valid(self):
        from pathlib import Path
        template = Path(__file__).resolve().parents[1] / 'templates/contract.json'
        self.assertEqual(json.loads(template.read_text(encoding='utf-8'))['discipline'], 'strict')
        self.assertEqual(self.call('validate', '--contract', str(template)).returncode, 0)


if __name__ == '__main__':
    unittest.main()
