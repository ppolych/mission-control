"""Regressions for the general bug hunt after 0.4.2.14: each test names the defect it pins."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from gate_fixture import GateBase
from test_acceptance_panel import PanelFixture
from test_draft_in_mission import DraftFixture
from test_stale_revalidation import Fixture, contract

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from mission_control.panel import parse_review, parse_vote  # noqa: E402
from mission_control.revisions import revision_diff  # noqa: E402
from mission_control.validation_tier import grade  # noqa: E402

DRAFT = '.mission/draft-contract.json'


class StaleRevalidationSurvives(Fixture):
    def test_a_block_keeps_a_stale_step_revalidatable_without_a_new_attempt(self):
        data = contract()
        data['budget'] = {'max_attempts_per_step': 1}
        self.contract_path.write_text(json.dumps(data), encoding='utf-8')
        self.ok('init', '--contract', str(self.contract_path), '--workspace', str(self.work))
        self.ok('start', '--step', 'base')
        (self.work / 'app.txt').write_text('one\n', encoding='utf-8')
        self.ok('verify', '--step', 'base')
        (self.work / 'app.txt').write_text('one\nchanged\n', encoding='utf-8')
        self.ok('start', '--step', 'base', '--revalidate')
        self.ok('block', '--step', 'base', '--reason', 'checking')
        self.ok('start', '--step', 'base', '--revalidate')
        self.ok('verify', '--step', 'base')
        status = json.loads(self.ok('status').stdout)
        self.assertEqual(status['steps']['base']['attempts'], 1)
        self.assertIsNone(status['stop_reason'])

    def test_after_revalidation_next_action_asks_for_a_review_not_finish(self):
        self.build_with_stale_base()
        self.ok('start', '--step', 'base', '--revalidate')
        self.ok('verify', '--step', 'base')
        advice = json.loads(self.ok('status').stdout)['next_action']
        self.assertEqual(advice['action'], 'criterion_review')
        self.assertIn('AC-1', advice['argv'])


class GateFixes(GateBase):
    def test_a_submodule_bump_hidden_by_ignore_all_is_not_certified(self):
        source = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: subprocess.run(['rm', '-rf', str(source)]))
        identity = ['-c', 'user.name=t', '-c', 'user.email=t@example.invalid', '-c', 'commit.gpgsign=false']
        subprocess.run(['git', 'init', '-q', str(source)], check=True)
        for message in ('s1', 's2'):
            subprocess.run(['git', *identity, '-C', str(source), 'commit', '-q', '--allow-empty', '-m', message], check=True)
        self.git('-c', 'protocol.file.allow=always', 'submodule', 'add', '-q', str(source), 'vendor')
        self.git('config', '-f', '.gitmodules', 'submodule.vendor.ignore', 'all')
        self.git('-C', 'vendor', 'checkout', '-q', 'HEAD~1')
        self.git('add', '-A')
        self.git('commit', '-q', '-m', 'add vendor')
        self.mission_done()
        self.git('-C', 'vendor', 'checkout', '-q', '-')
        report = self.gate(self.commit('vendor', 'out.txt'))
        self.assertFalse(report['certified'])
        self.assertIn('outside_scope', self.reasons(report))

    def test_a_file_from_the_mission_root_in_the_commit_is_not_certified(self):
        self.mission_done()
        (self.mission / 'payload.sh').write_text('echo payload\n', encoding='utf-8')
        report = self.gate(self.commit('-f', str(self.mission / 'payload.sh'), 'out.txt'))
        self.assertFalse(report['certified'])
        self.assertIn('mission_root_in_commit', self.reasons(report))


class PanelParsingFixes(unittest.TestCase):
    def test_only_the_last_non_blank_line_votes(self):
        self.assertEqual(parse_vote('VERDICT: NOT_REFUTED\n\nOn reflection AC-1 is not met.')['verdict'], 'inconclusive')
        self.assertEqual(parse_vote('Checked.\nVERDICT: NOT_REFUTED\n\n')['verdict'], 'not_refuted')

    def test_a_blocking_finding_after_the_fiftieth_still_counts(self):
        findings = [{'title': 'minor', 'priority': 3, 'confidence_score': 0.5}] * 50
        findings.append({'title': '[P0] bypass', 'priority': 0, 'confidence_score': 1.0})
        review = parse_review(json.dumps({'findings': findings, 'overall_correctness': 'patch is incorrect'}))
        self.assertEqual(review['findings'][-1]['priority'], 0)
        too_many = [{'title': 'x', 'priority': 3, 'confidence_score': 0.1}] * 201
        self.assertEqual(parse_review(json.dumps({'findings': too_many, 'overall_correctness': 'patch is correct'}))['status'],
                         'inconclusive')


class BriefWithoutWrites(PanelFixture):
    def test_no_declared_writes_sends_no_workspace_content(self):
        self.repository()
        data = json.loads((self.work / DRAFT).read_text(encoding='utf-8'))
        step = data['steps'][0]
        step['effects']['writes'] = []
        del step['test_first']
        step['test_first_exempt'] = {'kind': 'exploratory', 'reason': 'Reads only'}
        step['verify'] = [['file', 'app.py']]
        (self.work / DRAFT).write_text(json.dumps(data), encoding='utf-8')
        self.ok('init', '--contract', DRAFT, '--workspace', str(self.work))
        (self.work / 'secret.env').write_text('TOKEN=hunter2\n', encoding='utf-8')
        (self.work / 'app.py').write_text('def value():\n    return 3\n', encoding='utf-8')
        text = self.ok('brief', '--role', 'reviewer').stdout
        self.assertNotIn('hunter2', text)
        self.assertNotIn('return 3', text)
        self.assertIn('declares no files to write', text)


class SmallFixes(DraftFixture):
    def test_a_revision_does_not_copy_its_parents_lineage(self):
        parent = json.loads((ROOT / 'templates/small-fix-contract.json').read_text(encoding='utf-8'))
        parent['revision'] = {'number': 1, 'changes': [{'field': 'mission'}]}
        proposed = dict(parent, mission='Changed')
        del proposed['revision']
        fields = [change.get('field') for change in revision_diff(parent, proposed)['changes']]
        self.assertEqual(fields, ['mission'])

    def test_evidence_audit_on_schema_2_refuses_with_a_message(self):
        data = {'schema_version': 2, 'mission': 'Legacy', 'steps': [{'id': 'a', 'verify': [['file', 'x']]}]}
        (self.work / 'contract.json').write_text(json.dumps(data), encoding='utf-8')
        self.ok('init', '--contract', 'contract.json', '--workspace', str(self.work))
        refused = self.call('evidence-audit')
        self.assertEqual(refused.returncode, 2)
        self.assertIn('evidence-audit requires schema 3', refused.stderr)

    def test_more_runner_summaries(self):
        def tier(argv, output):
            return grade(['exit0', *argv], output)
        self.assertEqual(tier(['deno', 'test'], 'ok | 1 passed | 0 failed (2ms)\n')['passed'], 1)
        self.assertEqual(tier(['node', '--test'], 'ℹ tests 2\nℹ pass 2\nℹ fail 0\n')['passed'], 2)
        self.assertEqual(tier(['python3', '-m', 'unittest'], 'Ran 4 tests in 0.1s\n\nOK (skipped=1, expected failures=1)\n')['failed'], 0)
        self.assertEqual(tier(['python3', '-m', 'unittest'], 'Ran 4 tests in 0.1s\n\nFAILED (failures=1, errors=1)\n')['failed'], 2)
