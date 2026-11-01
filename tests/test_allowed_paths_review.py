"""Containment compatibility and boundary regressions."""
import json
import unittest
import v3_fixture as fixtures

class AllowedPathsReview(fixtures.V3Fixture):
    def initialize(self):
        self.contract.write_text(json.dumps(self.data))
        return self.call('init', '--contract', str(self.contract), '--workspace', str(self.root))

    def test_workspace_root_filesystem_check_with_whole_workspace_policy(self):
        self.data['allowed_paths'] = ['.']
        self.data['steps'][0]['verify'] = [['file', '.']]
        result = self.initialize()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.complete()

    def test_normalized_whole_workspace_prefix(self):
        self.data['allowed_paths'] = ['./']
        result = self.initialize()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_not_file_below_regular_file_remains_valid(self):
        (self.root / 'out').mkdir()
        (self.root / 'out/file').write_text('regular file')
        self.data['allowed_paths'] = ['out']
        self.data['steps'][0]['verify'] = [['not_file', 'out/file/child']]
        result = self.initialize()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.complete()

    def test_restricted_prefix_rejects_workspace_root(self):
        self.data['allowed_paths'] = ['out']
        self.data['steps'][0]['verify'] = [['file', '.']]
        result = self.initialize()
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn('escapes allowed_paths', result.stderr)
        self.assertFalse((self.mission / 'state/progress.json').exists())
