"""A strict contract still holding template text is refused at init, which then creates nothing."""
from pathlib import Path

from test_draft_in_mission import DraftFixture

ROOT = Path(__file__).resolve().parents[1]
DRAFT = '.mission/draft-contract.json'


class DecidedDrafts(DraftFixture):
    def test_template_text_is_refused_at_init_and_creates_no_state(self):
        self.repository()
        (self.work / DRAFT).write_bytes((ROOT / 'templates/small-fix-contract.json').read_bytes())
        self.ok('validate', '--contract', DRAFT)
        refused = self.call('init', '--contract', DRAFT, '--workspace', str(self.work))
        self.assertEqual(refused.returncode, 2)
        self.assertIn('template text is still in mission, fix.description, AC-1.description', refused.stderr)
        self.assertFalse((self.work / '.mission/state').exists())

    def test_a_fresh_mission_root_is_not_created_for_a_refused_draft(self):
        self.repository()
        draft = self.work / 'draft.json'
        draft.write_bytes((ROOT / 'templates/small-fix-contract.json').read_bytes())
        refused = self.call('init', '--mission', '.mission-new', '--contract', 'draft.json', '--workspace', str(self.work))
        self.assertEqual(refused.returncode, 2)
        self.assertFalse((self.work / '.mission-new').exists())
