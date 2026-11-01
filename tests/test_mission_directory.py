"""One hidden default directory for lifecycle and repeat state."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

CLI = Path(__file__).resolve().parents[1] / 'scripts/mission.py'

class MissionDirectory(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.contract = self.root / 'input.json'
        self.contract.write_text(json.dumps({'schema_version':2,'mission':'test',
            'steps':[{'id':'one','verify':[['exit0','true']]}]}))

    def call(self, *args):
        env = dict(os.environ);env.pop('NO_PROGRESS_STATE', None)
        return subprocess.run(['python3',str(CLI),*args],cwd=self.root,
                              env=env,capture_output=True,text=True)

    def test_default_lifecycle_and_repeat_share_hidden_root(self):
        self.assertEqual(self.call('init','--contract',str(self.contract)).returncode,0)
        self.assertTrue((self.root/'.mission/state/progress.json').is_file())
        self.assertEqual(self.call('repeat','record','tool','argument').returncode,0)
        self.assertTrue((self.root/'.mission/state/call_hashes.txt').is_file())
        self.assertEqual(self.call('start','--step','one').returncode,0)
        self.assertEqual(self.call('verify','--step','one').returncode,0)
        self.assertEqual(self.call('finish').returncode,0)
        self.assertFalse((self.root/'mission').exists())

    def test_explicit_legacy_directory_still_works(self):
        self.assertEqual(self.call('init','--mission','mission','--contract',str(self.contract)).returncode,0)
        self.assertEqual(self.call('status','--mission','mission').returncode,0)
        self.assertFalse((self.root/'.mission').exists())

    def test_default_does_not_modify_existing_legacy_directory(self):
        legacy = self.root/'mission';legacy.mkdir()
        marker = legacy/'keep.txt';marker.write_text('existing data')
        self.assertEqual(self.call('init','--contract',str(self.contract)).returncode,0)
        self.assertTrue((self.root/'.mission/state/progress.json').is_file())
        self.assertEqual(marker.read_text(),'existing data')
        self.assertEqual(sorted(p.name for p in legacy.iterdir()),['keep.txt'])
