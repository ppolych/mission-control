"""The behavioral runner must record failures and notice changed probe logic."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / 'evals/run_behavioral.py'
# Starts the controlled scenario but writes a checkpoint without an approval request.
STUB_CLI = """
import json, pathlib, sys
command = sys.argv[1]
mission = pathlib.Path(sys.argv[sys.argv.index('--mission') + 1])
if command == 'init':
    (mission / 'state').mkdir(parents=True)
    (mission / 'state/progress.json').write_text(json.dumps({'attempts': 0, 'steps': {'one': {}}}))
    sys.exit(0)
sys.exit(3 if command == 'start' else 1)
"""


class BehavioralRunner(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()

    def test_missing_report_field_is_recorded_not_a_traceback(self):
        stub = self.root / 'stub.py'
        stub.write_text(STUB_CLI)
        result = subprocess.run([sys.executable, str(RUNNER), '--cli', str(stub)], capture_output=True, text=True)
        self.assertNotIn('Traceback', result.stderr)
        rows = {row['id']: row for row in json.loads(result.stdout)['results']}
        self.assertFalse(rows['denial_survives_resume']['passed'])
        self.assertEqual(rows['denial_survives_resume']['error_type'], 'KeyError')

    def test_changed_probe_logic_changes_the_suite_digest(self):
        def digest(path):
            code = ('import importlib.util, sys\n'
                    f'spec = importlib.util.spec_from_file_location("runner", {str(path)!r})\n'
                    'module = importlib.util.module_from_spec(spec)\n'
                    'spec.loader.exec_module(module)\n'
                    'print(module.suite_digest())\n')
            return subprocess.check_output([sys.executable, '-c', code], text=True)
        changed = self.root / 'run_behavioral.py'
        shutil.copyfile(RUNNER, changed)
        text = changed.read_text(encoding='utf-8')
        self.assertIn("call('finish',expect=2)", text)
        changed.write_text(text.replace("call('finish',expect=2)", "call('finish',expect=0)"), encoding='utf-8')
        self.assertNotEqual(digest(RUNNER), digest(changed))


if __name__ == '__main__':
    unittest.main()
