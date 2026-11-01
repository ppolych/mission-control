"""Documented commands must run unchanged in bash and zsh, including odd paths."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SHELLS = ('bash', 'zsh')
PASTED_DOCUMENTS = ('SKILL.md', 'README.md')


def bash_blocks(text):
    return re.findall(r'^```bash\n(.*?)^```$', text, flags=re.M | re.S)


def section(text, title):
    start = text.index('## ' + title)
    following = text.find('\n## ', start + 1)
    return text[start:following if following != -1 else len(text)]


def skill_commands():
    block = '\n'.join(bash_blocks(section((ROOT / 'SKILL.md').read_text(encoding='utf-8'), 'Command path')))
    block = block.replace('check:STEP:INDEX', 'check:example-001:1')
    block = block.replace('--step STEP', '--step example-001').replace('--check INDEX', '--check 1')
    return block.replace('TEXT', "'Inspected the actual artifact'")


def readme_commands():
    blocks = bash_blocks(section((ROOT / 'README.md').read_text(encoding='utf-8'), 'Quick start'))
    return '\n'.join(blocks)


class ShellBase(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.skill = self.root / 'skill copy résumé'
        self.skill.mkdir()
        shutil.copytree(ROOT / 'scripts', self.skill / 'scripts', ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copyfile(ROOT / 'VERSION', self.skill / 'VERSION')
        self.workspace = self.root / 'work space résumé'
        self.workspace.mkdir()
        shutil.copyfile(ROOT / 'templates/contract.json', self.workspace / 'contract.json')
        (self.workspace / 'report.txt').write_text('report\n', encoding='utf-8')

    def shell(self, name):
        path = shutil.which(name)
        if path:
            return path
        if os.environ.get('MISSION_REQUIRE_SHELLS'):
            self.fail(name + ' is required but not installed')
        self.skipTest(name + ' is not installed')

    def run_script(self, name, script):
        # zsh -f and bash --norc ignore user configuration, like a clean agent shell.
        flag = '-f' if name == 'zsh' else '--norc'
        strict = 'set -e\n'
        return subprocess.run([self.shell(name), flag, '-c', strict + script], cwd=self.workspace,
                              env={**os.environ, 'SKILL': str(self.skill)}, capture_output=True, text=True)

    def assert_completed(self):
        state = json.loads((self.workspace / '.mission/state/progress.json').read_text(encoding='utf-8'))
        self.assertEqual(state['stop_reason'], 'done_verified')
        self.assertEqual(state['goal_review']['verdict'], 'pass')


class DocumentedFlows(ShellBase):
    def test_readme_quick_start(self):
        for name in SHELLS:
            with self.subTest(shell=name):
                shutil.rmtree(self.workspace / '.mission', ignore_errors=True)
                result = self.run_script(name, readme_commands())
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assert_completed()

    def test_skill_command_path(self):
        for name in SHELLS:
            with self.subTest(shell=name):
                shutil.rmtree(self.workspace / '.mission', ignore_errors=True)
                result = self.run_script(name, skill_commands())
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assert_completed()


class Wrappers(ShellBase):
    def test_wrappers_run_directly_from_each_shell(self):
        for name in SHELLS:
            with self.subTest(shell=name):
                result = self.run_script(name, '"$SKILL/scripts/verify.sh" file report.txt\n'
                                               f'NO_PROGRESS_STATE={name}.json "$SKILL/scripts/no_progress.sh" record tool x\n')
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_tracked_wrappers_are_executable(self):
        for name in ('verify.sh', 'no_progress.sh'):
            self.assertTrue(os.access(ROOT / 'scripts' / name, os.X_OK), name)


class PastedBlocks(unittest.TestCase):
    def test_blocks_have_no_comments_for_interactive_zsh(self):
        # Interactive zsh treats an unquoted # as a command unless interactive_comments is set.
        for document in PASTED_DOCUMENTS:
            for block in bash_blocks((ROOT / document).read_text(encoding='utf-8')):
                for line in block.splitlines():
                    self.assertFalse(line.lstrip().startswith('#'), document + ': ' + line)


if __name__ == '__main__':
    unittest.main()
