"""Packaging invariants for the modular CLI."""
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import shutil
import unittest

ROOT = Path(__file__).resolve().parents[1]

class PackageStructure(unittest.TestCase):
    def test_python_files_stay_within_400_lines(self):
        for directory in ('scripts', 'tests', 'evals'):
            for path in (ROOT / directory).rglob('*.py'):
                self.assertLessEqual(len(path.read_text().splitlines()), 400, str(path))

    def test_engine_fingerprint_changes_with_module(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)
            shutil.copytree(ROOT / 'scripts', target / 'scripts')
            shutil.copyfile(ROOT / 'VERSION', target / 'VERSION')
            code = 'from mission_control.cache import engine_fingerprint; print(engine_fingerprint())'
            def fingerprint():
                return subprocess.check_output([sys.executable, '-c', code], cwd=target / 'scripts')
            before = fingerprint()
            with (target / 'scripts/mission_control/budgets.py').open('a') as stream:
                stream.write('\n# changed implementation\n')
            self.assertNotEqual(before, fingerprint())
