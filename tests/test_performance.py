"""Cheap commands must not load modules only other commands need. Counts imports, not time."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / 'scripts/mission.py'
HEAVY = ('subprocess', 'traceback', 'tempfile', 'shutil', 'ast', 'random', 'zipfile')
PROBE = """
import json, runpy, sys
sys.argv = ['mission.py'] + json.loads(sys.argv[1])
already = set(sys.modules)
try:
    runpy.run_path({cli!r}, run_name='__main__')
except SystemExit as stop:
    code = stop.code
print(json.dumps({{'code': code, 'loaded': sorted(set(sys.modules) - already)}}), file=sys.__stderr__)
"""


class ImportBudget(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        step = {'id': 's1', 'description': 'd', 'verify': [['exit0', 'true']], 'acceptance_refs': ['A'],
                'effects': {'reads': [], 'writes': [], 'network': 'none', 'external_actions': [], 'reversible': True}}
        (self.root / 'contract.json').write_text(json.dumps({
            'schema_version': 3, 'mission': 'probe', 'steps': [step], 'acceptance': [{'id': 'A', 'description': 'x'}]}))
        subprocess.run([sys.executable, str(CLI), 'init', '--contract', 'contract.json'], cwd=self.root, check=True)

    def own_heavy(self, loaded):
        # argparse itself loads some of these on newer Python versions; that cost is not ours.
        code = ('import argparse, json, sys\n'
                'argparse.ArgumentParser().add_argument("--x")\n'
                'print(json.dumps(sorted(sys.modules)))\n')
        stdlib = set(json.loads(subprocess.check_output([sys.executable, '-c', code], text=True)))
        return (loaded & set(HEAVY)) - stdlib

    def loaded(self, *args):
        code = PROBE.format(cli=str(CLI))
        result = subprocess.run([sys.executable, '-c', code, json.dumps(list(args))], cwd=self.root,
                                capture_output=True, text=True)
        report = json.loads(result.stderr.strip().splitlines()[-1])
        self.assertEqual(report['code'], 0, result.stderr)
        return set(report['loaded'])

    def test_status_loads_no_heavy_modules(self):
        self.assertEqual(self.own_heavy(self.loaded('status')), set())

    def test_mutating_command_loads_no_checks_or_analysis_modules(self):
        self.assertEqual(self.own_heavy(self.loaded('stop', '--reason', 'human_paused')) & {'subprocess', 'traceback', 'ast', 'zipfile'}, set())

    def test_version_loads_no_package_logic(self):
        loaded = self.loaded('--version')
        self.assertEqual(loaded & set(HEAVY), set())
        self.assertFalse({name for name in loaded if name.startswith('mission_control.')} - {'mission_control.cli', 'mission_control.settings'})

    def test_helpers_load_only_their_own_module(self):
        loaded = self.loaded('status')
        self.assertFalse({'mission_control.impact', 'mission_control.services', 'mission_control.cache'} & loaded)


class BenchmarkTool(unittest.TestCase):
    def test_small_run_reports_every_measured_command(self):
        result = subprocess.run([sys.executable, str(ROOT / 'evals/benchmark.py'), '--events', '1', '--bytes', '16', '--repeat', '1'],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr[-400:])
        row = json.loads(result.stdout)['rows'][0]
        for name in ('version', 'status', 'handoff', 'coverage', 'finish', 'criterion_review'):
            self.assertGreater(row[name], 0, name)


class SubprocessFailures(unittest.TestCase):
    def test_subprocess_error_still_exits_2_with_its_message(self):
        code = ('import runpy, subprocess, sys\n'
                'sys.argv = ["mission.py", "--version"]\n'
                'import builtins\n'
                f'source = open({str(CLI)!r}).read().replace("sys.exit(main(sys.argv[1:]))", '
                '"raise subprocess.SubprocessError(\'probe\')")\n'
                'sys.path.insert(0, ' + repr(str(CLI.parent)) + ')\n'
                'exec(compile(source, "mission.py", "exec"), {"__name__": "__main__", "__file__": ' + repr(str(CLI)) + ', "subprocess": subprocess})\n')
        result = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn('probe', result.stderr)
        self.assertNotIn('internal error', result.stderr)


if __name__ == '__main__':
    unittest.main()
