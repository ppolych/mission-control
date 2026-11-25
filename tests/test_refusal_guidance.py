"""Refusals seen in a real trial name the path, the next command and the accepted spelling."""
import json
from pathlib import Path
import re
import subprocess

from test_draft_in_mission import DraftFixture

ROOT = Path(__file__).resolve().parents[1]
CLI = str(ROOT / 'scripts/mission.py')
DRAFT = '.mission/draft-contract.json'


class Guidance(DraftFixture):
    def misnamed(self):
        """The OPNsense trial: the contract declares config.example, the agent wrote examples/config.env.example."""
        self.repository()
        data = json.loads((self.work / DRAFT).read_text(encoding='utf-8'))
        step = data['steps'][0]
        step['effects']['writes'].append('config.example')
        step['verify'].append(['file', 'config.example'])
        (self.work / DRAFT).write_text(json.dumps(data), encoding='utf-8')
        self.ok('init', '--contract', DRAFT, '--workspace', str(self.work))
        self.ok('start', '--step', 'fix')
        self.ok('red', '--step', 'fix')
        (self.work / 'app.py').write_text('def value():\n    return 2\n', encoding='utf-8')
        (self.work / 'examples').mkdir()
        (self.work / 'examples/config.env.example').write_text('KEY=\n', encoding='utf-8')
        return self.call('verify', '--step', 'fix')

    def test_a_missing_file_is_named_with_the_similar_undeclared_one(self):
        failed = self.misnamed()
        self.assertEqual(failed.returncode, 1)
        self.assertIn('FAIL: file (check 1, config.example missing)', failed.stdout)
        self.assertIn('hint: config.example is declared but missing, and examples/config.env.example appeared', failed.stdout)

    def test_verify_after_a_failure_names_the_recovery_commands(self):
        self.misnamed()
        refused = self.call('verify', '--step', 'fix')
        self.assertEqual(refused.returncode, 2)
        self.assertIn('recovery --step fix shows the report and its digest, then recover --step fix --digest DIGEST', refused.stderr)
        refused = self.call('start', '--step', 'fix')
        self.assertIn('recovery --step fix', refused.stderr)

    def test_a_stale_recovery_digest_prints_the_current_one(self):
        self.misnamed()
        current = json.loads(self.ok('recovery', '--step', 'fix').stdout)['digest']
        refused = self.call('recover', '--step', 'fix', '--digest', '0' * 64, '--resolution', 'not_applied',
                            '--rationale', 'Nothing was applied')
        self.assertEqual(refused.returncode, 2)
        self.assertIn('use its current digest: ' + current, refused.stderr)

    def test_test_first_note_accepts_rationale_and_scope_note_accepts_reason(self):
        self.repository()
        self.ok('init', '--contract', DRAFT, '--workspace', str(self.work))
        self.ok('start', '--step', 'fix')
        (self.work / 'app.py').write_text('def value():\n    return 2\n', encoding='utf-8')
        self.ok('test-first-note', '--step', 'fix', '--rationale', 'Written before the test ran')
        (self.work / 'notes.txt').write_text('scratch\n', encoding='utf-8')
        self.ok('verify', '--step', 'fix')
        self.ok('scope-note', '--path', 'notes.txt', '--disposition', 'mine', '--reason', 'My scratch notes')
        status = json.loads(self.ok('status').stdout)
        self.assertEqual(status['steps']['fix']['test_first_notes'][0]['reason'], 'Written before the test ran')
        self.assertEqual(status['scope_observations']['notes.txt']['notes'][0]['rationale'], 'My scratch notes')

    def test_a_supported_review_without_evidence_shows_an_example(self):
        self.repository()
        self.ok('init', '--contract', DRAFT, '--workspace', str(self.work))
        self.ok('start', '--step', 'fix')
        self.ok('red', '--step', 'fix')
        (self.work / 'app.py').write_text('def value():\n    return 2\n', encoding='utf-8')
        self.ok('verify', '--step', 'fix')
        refused = self.call('criterion-review', '--criterion', 'AC-1', '--verdict', 'supported', '--rationale', 'Passes',
                            '--evidence-kind', 'behavior')
        self.assertIn('for example --evidence-ref check:fix:0', refused.stderr)
        refused = self.call('criterion-review', '--criterion', 'AC-1', '--verdict', 'unverified', '--rationale', 'Unsure',
                            '--evidence-ref', 'check:other:0')
        self.assertIn('with a step mapped to AC-1 (fix)', refused.stderr)

    def test_no_mission_yet_names_the_template_and_the_draft_path(self):
        self.work.joinpath('x').write_text('', encoding='utf-8')
        refused = self.call('status')
        self.assertIn('templates/contract.json', refused.stderr)
        self.assertIn('draft-contract.json', refused.stderr)

    def test_a_contract_without_schema_names_the_template(self):
        (self.work / 'contract.json').write_text(json.dumps({'id': 'x', 'acceptance': []}), encoding='utf-8')
        refused = subprocess.run(['python3', CLI, 'validate', '--contract', 'contract.json'], cwd=self.work,
                                 capture_output=True, text=True)
        self.assertEqual(refused.returncode, 2)
        self.assertTrue(re.search(r"templates/contract\.json.*mission-guide\.md", refused.stderr))

    def test_research_guidance_forbids_a_whole_filesystem_search(self):
        """Three real sessions lost time to hung commands; the last was a subagent's find / crawling /mnt/c."""
        self.repository()
        self.ok('init', '--contract', DRAFT, '--workspace', str(self.work))
        brief = self.ok('brief', '--role', 'researcher', '--query', 'the auth crate').stdout
        self.assertIn('Never search the whole filesystem with find /', brief)
        self.assertIn('~/.cargo/registry/src', brief)
        skill = (ROOT / 'SKILL.md').read_text(encoding='utf-8')
        self.assertIn('Never search the whole filesystem with `find /`, and tell subagents so', skill)
