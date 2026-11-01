"""Documentation structure: one reference level, findable sections, no release log outside its home."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
REFERENCES = sorted((ROOT / 'references').glob('*.md'))
# These two are records of history by design.
HISTORY_FILES = {'CHANGELOG.md', 'operational-validation.md', 'skill-learnings.md'}
GUIDANCE = [ROOT / name for name in ('SKILL.md', 'README.md', 'AGENTS.md')] + REFERENCES
LINK = re.compile(r'\]\(([^)\s]+)\)')


def anchors(path):
    found = set()
    for line in path.read_text(encoding='utf-8').splitlines():
        if line.startswith('#'):
            title = line.lstrip('#').strip().lower()
            found.add(re.sub(r'[^\w\- ]', '', title).replace(' ', '-'))
    return found


class Links(unittest.TestCase):
    def test_local_links_and_anchors_resolve(self):
        for path in [*GUIDANCE, ROOT / 'CHANGELOG.md', *(ROOT / 'templates').glob('*.md'), *(ROOT / 'evals').glob('*.md')]:
            for target in LINK.findall(path.read_text(encoding='utf-8')):
                if target.startswith(('http', 'mailto')):
                    continue
                name, _, anchor = target.partition('#')
                linked = (path.parent / name) if name else path
                self.assertTrue(linked.exists(), f'{path.name}: {target}')
                if anchor:
                    self.assertIn(anchor, anchors(linked), f'{path.name}: {target}')


class ReferenceDepth(unittest.TestCase):
    def test_skill_links_every_reference_directly(self):
        linked = LINK.findall((ROOT / 'SKILL.md').read_text(encoding='utf-8'))
        names = {target.partition('#')[0] for target in linked}
        for path in REFERENCES:
            self.assertIn('references/' + path.name, names, path.name)

    def test_references_do_not_chain_to_other_references(self):
        for path in REFERENCES:
            for target in LINK.findall(path.read_text(encoding='utf-8')):
                name = target.partition('#')[0]
                self.assertFalse(name.endswith('.md') and (path.parent / name).parent == path.parent,
                                 f'{path.name} links {target}')

    def test_long_references_open_with_contents(self):
        for path in REFERENCES:
            lines = path.read_text(encoding='utf-8').splitlines()
            if len(lines) > 100:
                self.assertIn('## Contents', lines[:6], path.name)


class CurrentBehaviorOnly(unittest.TestCase):
    def test_release_history_stays_in_its_files(self):
        for path in GUIDANCE:
            if path.name in HISTORY_FILES:
                continue
            for line in path.read_text(encoding='utf-8').splitlines():
                if line.startswith('#'):
                    self.assertIsNone(re.search(r'\d+\.\d+(\.\d+)?|introduced in|additions', line, re.I),
                                      f'{path.name}: {line}')

    def test_test_counts_stay_in_the_validation_record(self):
        for path in GUIDANCE:
            if path.name in HISTORY_FILES:
                continue
            self.assertIsNone(re.search(r'\b\d+ (passing )?tests\b', path.read_text(encoding='utf-8')), path.name)

    def test_project_text_has_no_greek(self):
        for path in [*GUIDANCE, ROOT / 'CHANGELOG.md']:
            self.assertIsNone(re.search(r'[Ͱ-Ͽἀ-῿]', path.read_text(encoding='utf-8')), path.name)

    def test_reference_commands_have_no_interactive_comments(self):
        for path in GUIDANCE:
            for block in re.findall(r'^```bash\n(.*?)^```$', path.read_text(encoding='utf-8'), flags=re.M | re.S):
                for line in block.splitlines():
                    self.assertFalse(line.lstrip().startswith('#'), f'{path.name}: {line}')


class KnownCorrections(unittest.TestCase):
    def all_commands(self):
        return ''.join(path.read_text(encoding='utf-8') for path in REFERENCES if path.name.startswith('commands-'))

    def test_commands_reference_is_split(self):
        self.assertFalse((ROOT / 'references/commands.md').exists())

    def test_current_behavior_is_documented(self):
        text = self.all_commands()
        for phrase in ('applied_incorrect', 'verify_timeout', 'goal_review_status', 'skipped_files'):
            self.assertIn(phrase, text)
        self.assertNotIn('Additional metadata is allowed', text)
        self.assertNotIn('Do not share compatibility history between concurrent writers', text)

    def test_recovery_reference_describes_directory_observation(self):
        text = (ROOT / 'references/evidence-recovery.md').read_text(encoding='utf-8')
        self.assertNotIn('Directory trees and large-file backup are outside', text)
        self.assertNotIn('--mission .mission-r2', text)
        self.assertIn('--mission mission-r2', text)


if __name__ == '__main__':
    unittest.main()
