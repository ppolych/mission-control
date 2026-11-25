"""not_grep proves an old pattern is gone; a missing file is an error, never a pass."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CLI = str(ROOT / 'scripts/mission.py')


class NotGrep(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.work = Path(temporary.name)
        (self.work / 'client.go').write_text('q.Set("redirect_uri", uri)\n', encoding='utf-8')

    def check(self, *args):
        return subprocess.run(['python3', CLI, 'checks', '--single', *args], cwd=self.work, capture_output=True, text=True)

    def test_an_absent_pattern_passes(self):
        result = self.check('not_grep', 'redirectUri', 'client.go')
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn('PASS: not_grep', result.stdout)

    def test_a_present_pattern_fails(self):
        result = self.check('not_grep', 'redirect_uri', 'client.go')
        self.assertEqual(result.returncode, 1)
        self.assertIn('FAIL: not_grep', result.stdout)

    def test_a_missing_file_is_an_error_not_a_pass(self):
        result = self.check('not_grep', 'anything', 'missing.go')
        self.assertEqual(result.returncode, 2)

    def test_a_contract_path_outside_the_workspace_is_refused(self):
        contract = json.loads((ROOT / 'templates/small-fix-contract.json').read_text(encoding='utf-8'))
        contract['steps'][0]['verify'].append(['not_grep', 'old', '../outside.go'])
        (self.work / 'contract.json').write_text(json.dumps(contract), encoding='utf-8')
        result = subprocess.run(['python3', CLI, 'validate', '--contract', 'contract.json'], cwd=self.work,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('allowed_paths', result.stderr)


if __name__ == '__main__':
    unittest.main()
