"""Schema-3 declared artifact containment, using disposable missions."""
import json
from pathlib import Path
import unittest
import v3_fixture as fixtures

class AllowedPaths(fixtures.V3Fixture):
    def submit(self, accepted):
        self.contract.write_text(json.dumps(self.data), encoding='utf-8')
        validation = self.call('validate', '--contract', str(self.contract))
        result = self.call('init', '--contract', str(self.contract), '--workspace', str(self.root))
        self.assertEqual(result.returncode, 0 if accepted else 2, result.stderr)
        if not accepted:
            self.assertIn('allowed_paths', result.stderr)
            self.assertFalse((self.mission / 'state/progress.json').exists())
            self.assertFalse((self.mission / 'contract.json').exists())
        return validation

    def test_absent_preserves_default_and_lifecycle(self):
        self.data['steps'][0]['effects']['writes'] = ['elsewhere/result']
        self.submit(True)
        self.complete()

    def test_inner_paths_and_whole_workspace(self):
        for allowed in (['out', 'build'], ['.']):
            with self.subTest(allowed=allowed):
                self.data['allowed_paths'] = allowed
                step = self.data['steps'][0]
                step['effects'].update(reads=['out/input'], writes=['build/result'])
                step['watch'] = ['out/input']
                step['verify'] = [['file', 'out/result'], ['not_file', 'build/missing'], ['grep', 'ok', 'out/result']]
                self.contract.write_text(json.dumps(self.data))
                result = self.call('validate', '--contract', str(self.contract))
                self.assertEqual(result.returncode, 0, result.stderr)
        self.data['allowed_paths'] = ['out', 'build']
        self.submit(True)

    def test_effects_escape_rejected(self):
        self.data['allowed_paths'] = ['out']
        for name in ('reads', 'writes'):
            with self.subTest(name=name):
                for path in ('outside/result', '../result', '/tmp/result'):
                    self.data['steps'][0]['effects'][name] = [path]
                    self.assertEqual(self.submit(False).returncode, 2)
                self.data['steps'][0]['effects'][name] = []

    def test_verify_paths_escape_rejected(self):
        self.data['allowed_paths'] = ['out']
        for check in (['file', 'outside/result'], ['not_file', 'outside/result'], ['grep', 'pattern', 'outside/result']):
            with self.subTest(check=check):
                self.data['steps'][0]['verify'] = [check]
                self.assertEqual(self.submit(False).returncode, 2)

    def test_watch_escape_rejected(self):
        self.data['allowed_paths'] = ['out']
        self.data['steps'][0]['watch'] = ['other/input']
        self.assertEqual(self.submit(False).returncode, 2)

    def test_invalid_prefixes(self):
        for value in ('out', None, [], [''], [42], ['../out'], ['/out'], ['out/../build']):
            with self.subTest(value=value):
                self.data['allowed_paths'] = value
                self.assertEqual(self.submit(False).returncode, 2)

    def test_traversal_and_absolute_checks_rejected_even_with_dot(self):
        self.data['allowed_paths'] = ['.']
        for path in ('../result', '/tmp/result', 'out/../result'):
            with self.subTest(path=path):
                self.data['steps'][0]['verify'] = [['file', path]]
                self.assertEqual(self.submit(False).returncode, 2)

    def test_symlink_escape_from_pinned_workspace_rejected(self):
        self.data['allowed_paths'] = ['out']
        (self.root / 'out').mkdir()
        (self.root / 'other').mkdir()
        (self.root / 'out/link').symlink_to(self.root / 'other', target_is_directory=True)
        self.data['steps'][0]['effects']['writes'] = ['out/link/result']
        self.submit(False)

    def test_symlink_loop_is_validation_error_and_preserves_contract(self):
        self.data['allowed_paths'] = ['out']
        (self.root / 'out').mkdir()
        (self.root / 'out/loop').symlink_to('loop')
        self.data['steps'][0]['effects']['writes'] = ['out/loop/result']
        self.contract.write_text(json.dumps(self.data))
        self.mission.mkdir()
        destination = self.mission / 'contract.json'
        destination.write_bytes(self.contract.read_bytes())
        before = destination.read_bytes()
        result = self.call('init', '--contract', str(self.contract), '--workspace', str(self.root))
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn('escapes allowed_paths', result.stderr)
        self.assertEqual(destination.read_bytes(), before)
        self.assertFalse((self.mission / 'state/progress.json').exists())
