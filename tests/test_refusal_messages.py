"""Refusals name what is missing, so an agent need not read the controller to recover."""
import json

from gate_fixture import GateBase
from test_stale_revalidation import Fixture, contract


class RefusalsNameTheFix(Fixture):
    def started(self, data):
        self.contract_path.write_text(json.dumps(data), encoding='utf-8')
        self.ok('init', '--contract', str(self.contract_path), '--workspace', str(self.work))

    def test_an_invalid_network_value_lists_the_allowed_values(self):
        data = contract()
        data['steps'][0]['effects']['network'] = 'module-proxy'
        self.contract_path.write_text(json.dumps(data), encoding='utf-8')
        refused = self.call('validate', '--contract', str(self.contract_path))
        self.assertEqual(refused.returncode, 2)
        self.assertIn('step base: network must be one of none, self_hosted, external', refused.stderr)

    def test_a_non_boolean_reversible_value_says_so(self):
        data = contract()
        data['steps'][0]['effects']['reversible'] = 'yes'
        self.contract_path.write_text(json.dumps(data), encoding='utf-8')
        refused = self.call('validate', '--contract', str(self.contract_path))
        self.assertEqual(refused.returncode, 2)
        self.assertIn('step base: reversible must be true or false', refused.stderr)

    def test_a_missing_evidence_kind_is_named(self):
        data = contract()
        data['acceptance'][0]['evidence_kinds'] = ['behavior', 'content']
        self.started(data)
        self.ok('start', '--step', 'base')
        (self.work / 'app.txt').write_text('one\n', encoding='utf-8')
        self.ok('verify', '--step', 'base')
        refused = self.call('criterion-review', '--criterion', 'AC-1', '--verdict', 'supported', '--rationale', 'r',
                            '--evidence-ref', 'check:base:0', '--evidence-kind', 'content')
        self.assertEqual(refused.returncode, 2)
        self.assertIn('AC-1 requires --evidence-kind behavior', refused.stderr)

    def test_an_incomplete_mapped_step_is_named(self):
        self.started(contract())
        refused = self.review('AC-2', 'extend')
        self.assertEqual(refused.returncode, 2)
        self.assertIn('mapped steps not completed: extend', refused.stderr)

    def test_missing_evidence_references_are_named(self):
        self.started(contract())
        self.ok('start', '--step', 'base')
        (self.work / 'app.txt').write_text('one\n', encoding='utf-8')
        self.ok('verify', '--step', 'base')
        refused = self.call('criterion-review', '--criterion', 'AC-1', '--verdict', 'supported', '--rationale', 'r')
        self.assertEqual(refused.returncode, 2)
        self.assertIn('supported needs --evidence-ref', refused.stderr)


class GateOutsideScope(GateBase):
    def test_the_refusal_says_to_keep_the_file_and_how_to_certify_it(self):
        self.mission_done()
        self.write('.gitignore')
        report = self.gate(self.commit(), code=1)
        detail = report['not_certified'][0]['detail']
        self.assertIn('Do not drop a needed file to pass', detail)
        self.assertIn('revise', detail)
