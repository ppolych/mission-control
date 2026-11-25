"""Skeptic votes and a bug review, parsed by the controller, gate a passing goal review in enforce mode."""
import json
from pathlib import Path
import sys

from test_draft_in_mission import DraftFixture

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from mission_control.panel import evaluate, parse_review, parse_vote  # noqa: E402

DRAFT = '.mission/draft-contract.json'
CLEAN = json.dumps({'findings': [], 'overall_correctness': 'patch is correct', 'overall_explanation': 'Fine.'})
BLOCKING = json.dumps({'findings': [{'title': '[P1] value ignores input', 'body': 'x', 'priority': 1,
                                     'confidence_score': 0.9, 'location': 'app.py:2'}],
                       'overall_correctness': 'patch is incorrect', 'overall_explanation': 'One bug.'})


class Parsing(DraftFixture):
    def test_the_last_verdict_line_decides_and_anything_else_is_inconclusive(self):
        self.assertEqual(parse_vote('Looks right.\nVERDICT: NOT_REFUTED\n')['verdict'], 'not_refuted')
        refuted = parse_vote('VERDICT: NOT_REFUTED\nOn reflection:\nVERDICT: REFUTED - AC-1 returns 1')
        self.assertEqual((refuted['verdict'], refuted['gap']), ('refuted', 'AC-1 returns 1'))
        self.assertEqual(parse_vote('I think it is fine.')['verdict'], 'inconclusive')
        self.assertEqual(parse_vote('verdict: maybe')['verdict'], 'inconclusive')

    def test_a_review_needs_the_schema_and_a_fenced_reply_still_parses(self):
        self.assertEqual(parse_review('```json\n' + CLEAN + '\n```')['status'], 'parsed')
        self.assertEqual(parse_review('No bugs found.')['status'], 'inconclusive')
        self.assertEqual(parse_review('{"findings": []}')['status'], 'inconclusive')


class PanelFixture(DraftFixture):
    def finished(self, mode='enforce'):
        self.repository()
        data = json.loads((self.work / DRAFT).read_text(encoding='utf-8'))
        data['acceptance_panel'] = {'mode': mode, 'skeptics': 3}
        (self.work / DRAFT).write_text(json.dumps(data), encoding='utf-8')
        self.ok('init', '--contract', DRAFT, '--workspace', str(self.work))
        self.ok('start', '--step', 'fix')
        self.ok('red', '--step', 'fix')
        (self.work / 'app.py').write_text('def value():\n    return 2\n', encoding='utf-8')
        self.ok('verify', '--step', 'fix')
        self.ok('criterion-review', '--criterion', 'AC-1', '--verdict', 'supported', '--rationale', 'The test passes',
                '--evidence-ref', 'check:fix:0', '--evidence-kind', 'behavior')
        self.ok('finish')

    def reply(self, command, text):
        path = self.work.parent / ('reply-' + str(abs(hash(text))) + '.txt')
        path.write_text(text, encoding='utf-8')
        return self.call(command, '--content', str(path))

    def checkpoint(self):
        return (self.work / '.mission/state/progress.json').read_bytes()

    def pass_review(self):
        return self.call('goal-review', '--verdict', 'pass', '--rationale', 'Requested behavior holds')

    def votes(self, count=3):
        for index in range(count):
            self.reply('skeptic-record', 'Skeptic ' + str(index) + ' read the diff.\nVERDICT: NOT_REFUTED')


class Panel(PanelFixture):
    def test_enforce_refuses_a_pass_without_votes_and_names_the_way(self):
        self.finished()
        before = self.checkpoint()
        refused = self.pass_review()
        self.assertEqual(refused.returncode, 2)
        self.assertIn('3 more skeptic vote(s)', refused.stderr)
        self.assertIn('brief --role skeptic', refused.stderr)
        self.assertEqual(self.checkpoint(), before)
        advice = json.loads(self.ok('status').stdout)['next_action']
        self.assertEqual(advice['argv'], ['brief', '--role', 'skeptic'])

    def test_the_skeptic_brief_carries_the_work_and_changes_nothing(self):
        self.finished()
        before = self.checkpoint()
        text = self.ok('brief', '--role', 'skeptic').stdout
        self.assertIn('return 2', text)
        self.assertIn('AC-1', text)
        self.assertIn('fix:0 exit0 python3 -B -m unittest -> passed, 1 tests passed', text)
        self.assertIn('VERDICT: NOT_REFUTED', text)
        self.assertEqual(self.checkpoint(), before)
        self.assertIn('"overall_correctness"', self.ok('brief', '--role', 'reviewer').stdout)

    def test_a_majority_and_a_clean_review_allow_the_pass(self):
        self.finished()
        for text in ('A\nVERDICT: NOT_REFUTED', 'B\nVERDICT: NOT_REFUTED', 'VERDICT: REFUTED - unsure about AC-1'):
            self.assertEqual(self.reply('skeptic-record', text).returncode, 0)
        refused = self.pass_review()
        self.assertIn('a readable bug review of the current work', refused.stderr)
        self.reply('review-record', CLEAN)
        self.assertEqual(self.pass_review().returncode, 0)

    def test_inconclusive_votes_never_count_as_passing(self):
        self.finished()
        for text in ('VERDICT: NOT_REFUTED', 'Seems fine to me.', 'no verdict'):
            self.reply('skeptic-record', text)
        self.reply('review-record', CLEAN)
        refused = self.pass_review()
        self.assertIn('a majority of NOT_REFUTED votes (refuted: 0, inconclusive: 2)', refused.stderr)

    def test_a_blocking_finding_is_named(self):
        self.finished()
        self.votes()
        self.reply('review-record', BLOCKING)
        refused = self.pass_review()
        self.assertIn('1 open P0/P1 finding(s): [P1] value ignores input', refused.stderr)

    def test_votes_on_older_content_are_stale(self):
        self.finished()
        self.votes()
        root = self.work / '.mission'
        contract = json.loads((root / 'contract.json').read_text(encoding='utf-8'))
        state = json.loads((root / 'state/progress.json').read_text(encoding='utf-8'))
        self.assertEqual(evaluate(contract, state)['current_votes'], 3)
        (self.work / 'app.py').write_text('def value():\n    return 2  # changed\n', encoding='utf-8')
        self.assertEqual(evaluate(contract, state)['current_votes'], 0)

    def test_observe_reports_but_does_not_refuse(self):
        self.finished(mode='observe')
        passed = self.pass_review()
        self.assertEqual(passed.returncode, 0, passed.stderr)
        self.assertIn('acceptance panel (observe, not enforced)', passed.stdout)

    def test_votes_are_refused_before_the_steps_are_done(self):
        self.repository()
        data = json.loads((self.work / DRAFT).read_text(encoding='utf-8'))
        data['acceptance_panel'] = {'mode': 'observe'}
        (self.work / DRAFT).write_text(json.dumps(data), encoding='utf-8')
        self.ok('init', '--contract', DRAFT, '--workspace', str(self.work))
        refused = self.reply('skeptic-record', 'VERDICT: NOT_REFUTED')
        self.assertIn('complete these steps first: fix', refused.stderr)
        tester = self.ok('brief', '--role', 'tester', '--step', 'fix').stdout
        self.assertIn('Write only these test files: test_app.py', tester)
        self.assertIn('Do not open these implementation files: app.py', tester)

    def test_the_field_needs_strict_discipline_and_a_known_mode(self):
        self.repository()
        data = json.loads((self.work / DRAFT).read_text(encoding='utf-8'))
        data['acceptance_panel'] = {'mode': 'always'}
        (self.work / DRAFT).write_text(json.dumps(data), encoding='utf-8')
        self.assertIn('acceptance_panel needs mode observe or enforce', self.call('validate', '--contract', DRAFT).stderr)


class SourceEvidence(DraftFixture):
    def test_a_source_criterion_needs_a_source_url(self):
        self.repository()
        data = json.loads((self.work / DRAFT).read_text(encoding='utf-8'))
        data['acceptance'].append({'id': 'AC-2', 'description': 'Paths follow the published API specification',
                                   'evidence_kinds': ['source']})
        data['steps'][0]['acceptance_refs'].append('AC-2')
        (self.work / DRAFT).write_text(json.dumps(data), encoding='utf-8')
        self.ok('init', '--contract', DRAFT, '--workspace', str(self.work))
        self.ok('start', '--step', 'fix')
        self.ok('red', '--step', 'fix')
        (self.work / 'app.py').write_text('def value():\n    return 2\n', encoding='utf-8')
        self.ok('verify', '--step', 'fix')
        review = ['criterion-review', '--criterion', 'AC-2', '--verdict', 'supported', '--rationale', 'Matches the spec',
                  '--evidence-kind', 'source']
        self.assertIn('needs --evidence-ref source:URL', self.call(*review, '--evidence-ref', 'check:fix:0').stderr)
        self.assertIn('source:https://', self.call(*review, '--evidence-ref', 'source:somewhere').stderr)
        self.ok(*review, '--evidence-ref', 'source:https://example.org/api/openapi.yaml')
