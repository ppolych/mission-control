"""Controlled-mode policy regressions; all mission state is temporary."""
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

CLI = str(Path(__file__).resolve().parents[1] / 'scripts/mission.py')


class ControlledMode(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.mission = self.root / 'mission'
        self.contract = self.root / 'input.json'
        self.data = {'schema_version': 2, 'mission': 'reviewed work',
                     'mode': 'controlled', 'steps': [
                         {'id': 'one', 'description': 'Create the reviewed artifact',
                          'risk': 'high', 'needs_approval': False,
                          'commands': [['printf', '%s', 'a b', '--']],
                          'verify': [['exit0', 'true']]}]}

    def call(self, command, *args):
        return subprocess.run(['python3', CLI, command, '--mission', str(self.mission),
                               *args], capture_output=True, text=True)

    def init(self):
        self.contract.write_text(json.dumps(self.data), encoding='utf-8')
        result = self.call('init', '--contract', str(self.contract), '--workspace', str(self.root))
        self.assertEqual(result.returncode, 0, result.stderr)

    def state(self):
        return json.loads((self.mission / 'state/progress.json').read_text())

    def gate(self):
        result = self.call('start', '--step', 'one')
        self.assertEqual(result.returncode, 3, result.stderr)
        return json.loads(result.stdout)

    def decide(self, verdict, request=None):
        request = request or self.gate()
        return self.call(verdict, '--step', 'one', '--digest', request['digest'],
                         '--rationale', 'User explicitly chose ' + verdict)

    def test_high_risk_gate_discloses_exact_plan_without_execution(self):
        marker = self.root / 'must-not-exist'
        self.data['steps'][0]['commands'] = [['touch', str(marker)]]
        self.data['steps'][0]['verify'] = [['exit0', 'touch', str(marker)]]
        self.init()
        request = self.gate()
        self.assertEqual(request['step'], self.data['steps'][0])
        self.assertEqual(request['workspace'], str(self.root))
        self.assertEqual(request['status'], 'awaiting_approval')
        self.assertFalse(marker.exists())
        self.assertEqual(self.state()['attempts'], 0)
        self.assertEqual(self.state()['steps']['one']['attempts'], 0)
        self.assertEqual(self.call('verify', '--step', 'one').returncode, 2)

    def test_low_and_medium_explicit_approval_also_gate(self):
        for risk in ('low', 'medium'):
            with self.subTest(risk=risk):
                self.mission = self.root / risk
                self.data['steps'][0].update(risk=risk, needs_approval=True)
                self.init()
                self.gate()

    def test_low_and_medium_without_explicit_approval_run(self):
        for risk in ('low', 'medium'):
            with self.subTest(risk=risk):
                self.mission = self.root / risk
                self.data['steps'][0].update(risk=risk, needs_approval=False)
                self.init()
                self.assertEqual(self.call('start', '--step', 'one').returncode, 0)
                self.assertEqual(self.call('verify', '--step', 'one').returncode, 0)

    def test_omitted_mode_and_explicit_autonomous_keep_existing_behavior(self):
        for mode in (None, 'autonomous'):
            with self.subTest(mode=mode):
                self.mission = self.root / str(mode)
                self.data.pop('mode', None)
                if mode:
                    self.data['mode'] = mode
                self.data['steps'][0]['needs_approval'] = True
                self.data['steps'][0].pop('commands', None)
                self.init()
                self.assertEqual(self.call('start', '--step', 'one').returncode, 0)
                self.assertEqual(self.call('verify', '--step', 'one').returncode, 0)
                self.assertEqual(self.state()['attempts'], 1)

    def test_approval_is_explicit_then_persists_through_resume(self):
        self.init()
        request = self.gate()
        self.assertEqual(self.decide('approve', request).returncode, 0)
        approved = copy.deepcopy(self.state()['approved_steps'])
        self.assertEqual(approved['one']['digest'], request['digest'])
        self.assertEqual(self.state()['attempts'], 0)
        self.assertEqual(self.call('start', '--step', 'one').returncode, 0)
        self.assertEqual(self.call('verify', '--step', 'one').returncode, 0)
        self.assertEqual(self.call('resume').returncode, 0)
        self.assertEqual(self.state()['approved_steps'], approved)
        self.assertEqual(self.call('start', '--step', 'one', '--revalidate').returncode, 0)
        self.assertEqual(self.call('verify', '--step', 'one').returncode, 0)
        self.assertEqual(self.state()['attempts'], 1)

    def test_wrong_digest_and_blank_rationale_do_not_change_state(self):
        self.init()
        request = self.gate()
        path = self.mission / 'state/progress.json'
        before = path.read_bytes()
        for command in ('approve', 'deny'):
            for digest, rationale in (('0' * 64, 'yes'), (request['digest'], '  ')):
                result = self.call(command, '--step', 'one', '--digest', digest,
                                   '--rationale', rationale)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(path.read_bytes(), before)

    def test_decision_without_presented_request_is_rejected(self):
        self.init()
        self.assertEqual(self.call('approve', '--step', 'one', '--digest', '0' * 64,
                                   '--rationale', 'yes').returncode, 2)

    def test_repeated_gate_does_not_spend_attempts(self):
        self.init()
        first = self.gate()
        second = self.gate()
        self.assertEqual(first['digest'], second['digest'])
        self.assertEqual(self.state()['attempts'], 0)

    def test_denial_blocks_without_retry_or_budget_reset_on_resume(self):
        self.init()
        self.assertEqual(self.decide('deny').returncode, 1)
        state = self.state()
        self.assertEqual(state['steps']['one']['status'], 'blocked')
        self.assertTrue(state['steps']['one']['approval_denied'])
        self.assertEqual(state['stop_reason'], 'blocked')
        self.assertEqual(state['attempts'], 0)
        self.assertEqual(self.call('resume').returncode, 0)
        self.assertEqual(self.state()['steps']['one']['status'], 'blocked')
        self.assertEqual(self.call('start', '--step', 'one').returncode, 1)
        self.assertEqual(self.call('resume').returncode, 0)
        self.assertEqual(self.call('start', '--step', 'one', '--revalidate').returncode, 1)
        self.assertEqual(self.state()['attempts'], 0)

    def test_denial_preserves_independent_work_but_not_dependents(self):
        self.data['steps'] += [
            {'id': 'two', 'verify': [['exit0', 'true']]},
            {'id': 'child', 'depends_on': ['one'], 'verify': [['exit0', 'true']]}]
        self.init()
        self.assertEqual(self.decide('deny').returncode, 1)
        self.assertIsNone(self.state()['stop_reason'])
        self.assertEqual(self.call('start', '--step', 'child').returncode, 2)
        self.assertEqual(self.call('start', '--step', 'two').returncode, 0)
        self.assertEqual(self.call('verify', '--step', 'two').returncode, 0)
        self.assertEqual(self.state()['stop_reason'], 'blocked')

    def test_pending_request_allows_independent_work(self):
        self.data['steps'].append({'id': 'two', 'verify': [['exit0', 'true']]})
        self.init()
        request = self.gate()
        self.assertEqual(self.call('start', '--step', 'two').returncode, 0)
        self.assertEqual(self.call('verify', '--step', 'two').returncode, 0)
        self.assertEqual(self.decide('approve', request).returncode, 0)
        self.assertEqual(self.call('start', '--step', 'one').returncode, 0)

    def test_dependencies_and_active_step_checked_before_gate(self):
        self.data['steps'].append({'id': 'two', 'verify': [['exit0', 'true']]})
        self.data['steps'][0]['depends_on'] = ['two']
        self.init()
        before = self.state()
        self.assertEqual(self.call('start', '--step', 'one').returncode, 2)
        self.assertEqual(self.state(), before)
        self.call('start', '--step', 'two')
        self.assertEqual(self.call('start', '--step', 'one').returncode, 2)

    def test_invalid_contract_policy_values_fail_before_init(self):
        base = copy.deepcopy(self.data)
        cases = [('mode', value) for value in ('CONTROLLED', '', None, 1, [], {})]
        cases += [('risk', value) for value in ('critical', '', None, True, [], {})]
        cases += [('needs_approval', value) for value in ('false', 0, 1, None, [])]
        for field, value in cases:
            with self.subTest(field=field, value=value):
                self.data = copy.deepcopy(base)
                target = self.data if field == 'mode' else self.data['steps'][0]
                target[field] = value
                self.contract.write_text(json.dumps(self.data))
                result = self.call('init', '--contract', str(self.contract))
                self.assertEqual(result.returncode, 2)
                self.assertFalse((self.mission / 'state/progress.json').exists())

    def test_gated_step_requires_explicit_commands_and_summary(self):
        for field in ('commands', 'description'):
            with self.subTest(field=field):
                data = copy.deepcopy(self.data)
                data['steps'][0].pop(field)
                self.contract.write_text(json.dumps(data))
                self.assertEqual(self.call('validate', '--contract', str(self.contract)).returncode, 2)

    def test_invalid_command_argv_rejected(self):
        for commands in (None, 'echo x', [['']], [[]], [['echo', 1]], [['echo', '\x00']]):
            self.data['steps'][0]['commands'] = commands
            self.contract.write_text(json.dumps(self.data))
            self.assertEqual(self.call('validate', '--contract', str(self.contract)).returncode, 2)

    def test_explicit_empty_command_list_is_valid_manual_work(self):
        self.data['steps'][0]['commands'] = []
        self.init()
        self.assertEqual(self.gate()['step']['commands'], [])

    def test_stale_approved_digest_reopens_gate(self):
        self.init()
        self.decide('approve')
        path = self.mission / 'state/progress.json'
        state = self.state()
        state['approved_steps']['one']['digest'] = '0' * 64
        path.write_text(json.dumps(state))
        self.gate()
        self.assertNotIn('one', self.state()['approved_steps'])

    def test_frozen_contract_edits_cannot_reuse_approval(self):
        self.init()
        self.decide('approve')
        path = self.mission / 'contract.json'
        data = json.loads(path.read_text())
        data['steps'][0]['commands'].append(['echo', 'changed'])
        path.write_text(json.dumps(data))
        self.assertEqual(self.call('start', '--step', 'one').returncode, 2)

    def test_corrupt_approval_records_rejected_without_writes(self):
        self.init()
        self.decide('approve')
        path = self.mission / 'state/progress.json'
        base = self.state()
        for approvals in ([], {'unknown': {}}, {'one': {'digest': 3}},
                          {'one': {'digest': '0' * 64, 'timestamp': '', 'rationale': ''}}):
            state = copy.deepcopy(base)
            state['approved_steps'] = approvals
            path.write_text(json.dumps(state))
            before = path.read_bytes()
            self.assertEqual(self.call('start', '--step', 'one').returncode, 2)
            self.assertEqual(path.read_bytes(), before)

    def test_legacy_checkpoint_without_approval_map_still_works(self):
        self.data.pop('mode')
        self.init()
        path = self.mission / 'state/progress.json'
        state = self.state()
        state.pop('approved_steps', None)
        path.write_text(json.dumps(state))
        self.assertEqual(self.call('start', '--step', 'one').returncode, 0)

    def test_changed_workspace_invalidates_recorded_approval(self):
        self.init()
        self.decide('approve')
        path = self.mission / 'state/progress.json'
        state = self.state()
        different = self.root / 'different'
        different.mkdir()
        state['workspace'] = str(different)
        path.write_text(json.dumps(state))
        self.assertEqual(self.gate()['workspace'], str(different))

    def test_verify_rechecks_approval_before_running_commands(self):
        marker = self.root / 'verified'
        self.data['steps'][0]['verify'] = [['exit0', 'touch', str(marker)]]
        self.init()
        self.decide('approve')
        self.call('start', '--step', 'one')
        path = self.mission / 'state/progress.json'
        state = self.state()
        state['approved_steps'].clear()
        path.write_text(json.dumps(state))
        self.assertEqual(self.call('verify', '--step', 'one').returncode, 2)
        self.assertFalse(marker.exists())

    def test_approval_for_one_step_does_not_approve_another(self):
        other = copy.deepcopy(self.data['steps'][0])
        other['id'] = 'two'
        self.data['steps'].append(other)
        self.init()
        self.decide('approve')
        self.call('start', '--step', 'one')
        self.call('verify', '--step', 'one')
        self.assertEqual(self.call('start', '--step', 'two').returncode, 3)

    def test_resume_while_waiting_requires_a_fresh_presented_request(self):
        self.init()
        request = self.gate()
        self.assertEqual(self.call('resume').returncode, 0)
        self.assertEqual(self.decide('approve', request).returncode, 2)
        self.assertEqual(self.state()['attempts'], 0)
        self.assertEqual(self.decide('approve').returncode, 0)

    def test_approved_retry_obeys_original_execution_budget(self):
        self.data['budget'] = {'max_attempts_per_step': 1}
        self.data['steps'][0]['verify'] = [['exit0', 'false']]
        self.init()
        self.decide('approve')
        self.call('start', '--step', 'one')
        self.assertEqual(self.call('verify', '--step', 'one').returncode, 1)
        self.assertEqual(self.call('start', '--step', 'one').returncode, 1)
        self.assertEqual(self.state()['stop_reason'], 'budget_exhausted')
        self.assertEqual(self.state()['attempts'], 1)

    def test_unclassified_controlled_step_defaults_to_low_ungated(self):
        self.data['steps'][0] = {'id': 'one', 'verify': [['exit0', 'true']]}
        self.init()
        self.assertEqual(self.call('start', '--step', 'one').returncode, 0)

    def test_decisions_reject_changed_presented_snapshot(self):
        self.init()
        request = self.gate()
        path = self.mission / 'state/progress.json'
        state = self.state()
        state['steps']['one']['approval_request']['step']['commands'] = [['echo', 'different']]
        path.write_text(json.dumps(state))
        before = path.read_bytes()
        self.assertEqual(self.decide('approve', request).returncode, 2)
        self.assertEqual(path.read_bytes(), before)

    def test_denial_is_not_an_execution_failure_or_no_progress(self):
        self.data['steps'].append({'id': 'two', 'verify': [['exit0', 'true']]})
        self.init()
        self.decide('deny')
        denied = self.state()['steps']['one']
        self.assertEqual(denied['approval_denial']['rationale'], 'User explicitly chose deny')
        self.assertEqual(denied.get('failures', {}), {})
        self.assertFalse(denied.get('budget_exhausted', False))
        self.assertEqual(denied['attempts'], 0)
