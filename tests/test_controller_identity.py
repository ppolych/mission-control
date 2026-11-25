"""A controller edited mid-mission refuses mutating commands until the change is acknowledged."""
import json
import shutil
import subprocess
from pathlib import Path

from test_draft_in_mission import DraftFixture

ROOT = Path(__file__).resolve().parents[1]
DRAFT = '.mission/draft-contract.json'


class ChangedController(DraftFixture):
    def setUp(self):
        super().setUp()
        self.install = self.work.parent / 'skill'
        shutil.copytree(ROOT / 'scripts', self.install / 'scripts', ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copy(ROOT / 'VERSION', self.install / 'VERSION')
        self.repository()
        self.ok('init', '--contract', DRAFT, '--workspace', str(self.work))

    def call(self, *args):
        return subprocess.run(['python3', str(self.install / 'scripts/mission.py'), *args], cwd=self.work,
                              capture_output=True, text=True, env=self.environment)

    def edit_controller(self):
        module = self.install / 'scripts/mission_control/test_first.py'
        module.write_text(module.read_text(encoding='utf-8') + '\n# edited\n', encoding='utf-8')

    def checkpoint(self):
        return (self.work / '.mission/state/progress.json').read_bytes()

    def test_an_edited_controller_refuses_and_leaves_the_checkpoint_unchanged(self):
        self.edit_controller()
        before = self.checkpoint()
        refused = self.call('start', '--step', 'fix')
        self.assertEqual(refused.returncode, 2)
        self.assertIn('controller changed since this mission began', refused.stderr)
        self.assertIn('controller-adopt --rationale', refused.stderr)
        self.assertEqual(self.checkpoint(), before)
        self.ok('status')

    def test_an_acknowledged_change_is_recorded_and_work_continues(self):
        self.edit_controller()
        self.assertEqual(self.call('controller-adopt', '--rationale', '').returncode, 2)
        self.ok('controller-adopt', '--rationale', 'The user installed a newer release on purpose')
        self.ok('start', '--step', 'fix')
        status = json.loads(self.ok('status').stdout)
        self.assertEqual(len(status['controller_history']), 1)
        self.assertIn('on purpose', status['controller_history'][0]['rationale'])

    def test_adopting_an_unchanged_controller_is_refused(self):
        refused = self.call('controller-adopt', '--rationale', 'Nothing changed')
        self.assertEqual(refused.returncode, 2)
        self.assertIn('controller is unchanged', refused.stderr)
