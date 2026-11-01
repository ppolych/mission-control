"""Five-pass review regressions; no operator missions are used."""
import copy
import json
import unittest

import test_controlled as fixtures


class ControlledReview(unittest.TestCase):
    setUp = fixtures.ControlledMode.setUp
    call = fixtures.ControlledMode.call
    init = fixtures.ControlledMode.init
    state = fixtures.ControlledMode.state
    gate = fixtures.ControlledMode.gate
    decide = fixtures.ControlledMode.decide

    def checkpoint(self):
        return self.mission / 'state/progress.json'

    def test_denied_start_during_independent_active_work_is_invalid_without_writes(self):
        self.data['steps'].append({'id': 'two', 'verify': [['exit0', 'true']]})
        self.init()
        self.assertEqual(self.decide('deny').returncode, 1)
        self.assertEqual(self.call('start', '--step', 'two').returncode, 0)
        before = self.checkpoint().read_bytes()
        for flags in ([], ['--revalidate']):
            result = self.call('start', '--step', 'one', *flags)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertEqual(self.checkpoint().read_bytes(), before)

    def test_approved_start_rejects_missing_workspace_without_consuming_attempt(self):
        workspace = self.root / 'workspace'
        workspace.mkdir()
        self.init()
        state = self.state()
        state['workspace'] = str(workspace)
        self.checkpoint().write_text(json.dumps(state))
        self.assertEqual(self.decide('approve').returncode, 0)
        workspace.rmdir()
        before = self.checkpoint().read_bytes()
        self.assertEqual(self.call('start', '--step', 'one').returncode, 2)
        self.assertEqual(self.checkpoint().read_bytes(), before)

    def test_workspace_symlink_redirect_cannot_reuse_approval_or_verify(self):
        workspace = self.root / 'workspace'
        workspace.mkdir()
        outside = self.root / 'other'
        outside.mkdir()
        self.data['steps'][0]['verify'] = [['exit0', 'touch', 'unexpected']]
        self.init()
        state = self.state()
        state['workspace'] = str(workspace)
        self.checkpoint().write_text(json.dumps(state))
        self.decide('approve')
        self.assertEqual(self.call('start', '--step', 'one').returncode, 0)
        workspace.rmdir()
        workspace.symlink_to(outside, target_is_directory=True)
        before = self.checkpoint().read_bytes()
        self.assertEqual(self.call('verify', '--step', 'one').returncode, 2)
        self.assertEqual(self.checkpoint().read_bytes(), before)
        self.assertFalse((outside / 'unexpected').exists())

    def test_pending_decision_refuses_unavailable_workspace_without_writes(self):
        workspace = self.root / 'workspace'
        workspace.mkdir()
        self.init()
        state = self.state()
        state['workspace'] = str(workspace)
        self.checkpoint().write_text(json.dumps(state))
        request = self.gate()
        workspace.rmdir()
        before = self.checkpoint().read_bytes()
        self.assertEqual(self.decide('approve', request).returncode, 2)
        self.assertEqual(self.checkpoint().read_bytes(), before)

    def test_assess_refuses_missing_or_stale_approval_without_writes(self):
        self.data['steps'][0]['verify'].append({'manual': 'Inspect artifact'})
        self.init()
        self.decide('approve')
        self.call('start', '--step', 'one')
        base = self.state()
        for approvals in ({}, {'one': dict(base['approved_steps']['one'], digest='0' * 64)}):
            with self.subTest(approvals=approvals):
                state = copy.deepcopy(base)
                state['approved_steps'] = approvals
                self.checkpoint().write_text(json.dumps(state))
                before = self.checkpoint().read_bytes()
                result = self.call('assess', '--step', 'one', '--check', '1',
                                   '--verdict', 'pass', '--rationale', 'Inspected')
                self.assertEqual(result.returncode, 2)
                self.assertEqual(self.checkpoint().read_bytes(), before)

    def test_malformed_pending_snapshots_are_rejected_instead_of_repaired(self):
        self.init()
        self.gate()
        base = self.state()
        original = base['steps']['one']['approval_request']
        variants = [dict(original, status='pending'), dict(original, workspace=3),
                    dict(original, revalidate='false'), dict(original, step=[]),
                    dict(original, digest='0' * 64)]
        variants += [{key: value for key, value in original.items() if key != removed}
                     for removed in ('step', 'workspace', 'revalidate', 'status')]
        for request in variants:
            with self.subTest(request=request):
                state = copy.deepcopy(base)
                state['steps']['one']['approval_request'] = request
                self.checkpoint().write_text(json.dumps(state))
                before = self.checkpoint().read_bytes()
                result = self.call('start', '--step', 'one')
                self.assertEqual(result.returncode, 2)
                self.assertNotIn('Traceback', result.stderr)
                self.assertEqual(self.checkpoint().read_bytes(), before)

    def test_future_defaults_still_leave_autonomous_execution_ungated(self):
        self.data.pop('mode')
        self.init()
        self.assertEqual(self.call('start', '--step', 'one').returncode, 0)
        self.assertEqual(self.call('verify', '--step', 'one').returncode, 0)
        self.assertEqual(self.call('finish').returncode, 0)
