"""Supported interpreter and repository-wide file limits."""
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
LINE_LIMIT = 400
TEXT_SUFFIXES = {'.py', '.md', '.sh', '.json', '.yml', '.yaml', '.toml', '.txt'}
# Temporary: the topic rewrite splits this file, then this entry must be removed.
OVERSIZED_UNTIL_DOCS_REWRITE = {'references/commands.md': 585}


def tracked_text_files():
    names = subprocess.run(['git', 'ls-files', '--cached', '--others', '--exclude-standard'], cwd=ROOT,
                           capture_output=True, text=True, check=True).stdout.splitlines()
    return [name for name in names if Path(name).suffix in TEXT_SUFFIXES and (ROOT / name).is_file()]


class InterpreterSupport(unittest.TestCase):
    def run_with_version(self, version):
        code = ('import runpy, sys\n'
                f'sys.version_info = {version!r}\n'
                f'sys.argv = ["mission.py", "--version"]\n'
                f'runpy.run_path({str(ROOT / "scripts/mission.py")!r}, run_name="__main__")\n')
        return subprocess.run([sys.executable, '-c', code], capture_output=True, text=True)

    def test_older_python_is_refused_with_a_clear_message(self):
        result = self.run_with_version((3, 10, 14))
        self.assertEqual(result.returncode, 2)
        self.assertIn('Python 3.11', result.stderr)
        self.assertNotIn('Traceback', result.stderr)

    def test_supported_python_runs(self):
        result = self.run_with_version((3, 11, 0))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Mission Control', result.stdout)


class FileSizeLimit(unittest.TestCase):
    def test_every_tracked_text_file_stays_within_the_limit(self):
        if not (ROOT / '.git').exists():
            self.skipTest('needs a git checkout to list tracked files')
        for name in tracked_text_files():
            lines = len((ROOT / name).read_text(encoding='utf-8').splitlines())
            allowed = OVERSIZED_UNTIL_DOCS_REWRITE.get(name, LINE_LIMIT)
            self.assertLessEqual(lines, allowed, name)


if __name__ == '__main__':
    unittest.main()
