"""Gate behavior for commit ranges, revisions and the optional pre-push hook."""
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import unittest

from gate_fixture import GateBase

ROOT = Path(__file__).resolve().parents[1]


class Refs(GateBase):
    def test_path_outside_declared_writes(self):
        self.mission_done()
        self.write('other.txt')
        report = self.gate(self.commit(), code=1)
        self.assertEqual(self.reasons(report), {'outside_scope'})
        item = report['not_certified'][0]
        self.assertEqual(item['paths'], ['other.txt'])
        self.assertEqual(item['ownership'], 'unverified')

    def test_commit_by_someone_else_with_same_content_passes_and_states_the_limit(self):
        self.mission_done()
        self.git('add', 'out.txt')
        subprocess.run(['git', '-C', str(self.root), '-c', 'user.name=Other', '-c', 'user.email=o@example.invalid',
                        'commit', '-q', '-m', 'other author'], check=True)
        report = self.gate(self.git('rev-parse', 'HEAD'), code=0)
        self.assertTrue(report['certified'])
        self.assertIn('who wrote', ' '.join(report['does_not_certify']))

    def test_non_ancestor_base(self):
        self.mission_done()
        self.commit()
        self.git('checkout', '-q', '--orphan', 'other')
        commit = self.commit(message='unrelated')
        self.assertEqual(self.reasons(self.gate(commit, code=1)), {'base_not_ancestor'})

    def test_rebase_like_rewrite_of_the_base(self):
        self.mission_done()
        self.git('commit', '-q', '--amend', '--allow-empty', '-m', 'rewritten base')
        commit = self.commit()
        self.assertEqual(self.reasons(self.gate(commit, code=1)), {'base_not_ancestor'})

    def test_merge_bringing_other_paths(self):
        self.mission_done()
        self.commit()
        branch = self.git('rev-parse', '--abbrev-ref', 'HEAD')
        self.git('checkout', '-q', '-b', 'side', self.base)
        self.write('side.txt')
        self.commit('side.txt', message='side')
        self.git('checkout', '-q', branch)
        self.git('merge', '-q', '--no-edit', 'side')
        report = self.gate(self.git('rev-parse', 'HEAD'), code=1)
        self.assertEqual(self.reasons(report), {'outside_scope'})

    def test_merge_of_declared_content_only(self):
        self.mission_done()
        self.commit()
        branch = self.git('rev-parse', '--abbrev-ref', 'HEAD')
        self.git('checkout', '-q', '-b', 'side', self.base)
        self.git('commit', '-q', '--allow-empty', '-m', 'empty side')
        self.git('checkout', '-q', branch)
        self.git('merge', '-q', '--no-ff', '--no-edit', 'side')
        self.gate(self.git('rev-parse', 'HEAD'), code=0)

    def test_annotated_tag_resolves_to_its_commit(self):
        self.mission_done()
        self.commit()
        self.git('tag', '-a', 'v1', '-m', 'release')
        self.gate(self.git('rev-parse', 'v1'), code=0)

    def test_tag_of_a_non_commit(self):
        self.mission_done()
        self.commit()
        blob = self.git('rev-parse', 'HEAD:out.txt')
        self.assertEqual(self.reasons(self.gate(blob, code=1)), {'not_a_commit'})

    def test_unknown_or_option_like_commit_is_exit_two(self):
        self.mission_done()
        self.commit()
        self.gate('f' * 40, code=2)
        self.assertEqual(self.call('gate', '--commit=--all').returncode, 2)

    def test_missing_base_object_is_exit_two(self):
        self.mission_done()
        commit = self.commit()
        state = self.state()
        state['mission_base'] = {'status': 'commit', 'commit': 'a' * 40}
        self.rewrite(state)
        self.gate(commit, code=2)

    def test_no_recorded_base(self):
        self.mission_done()
        commit = self.commit()
        state = self.state()
        del state['mission_base']
        self.rewrite(state)
        self.assertEqual(self.reasons(self.gate(commit, code=1)), {'no_base'})

    def test_repository_without_commits_at_init(self):
        shutil.rmtree(self.root / '.git')
        self.git('init', '-q')
        self.git('config', 'commit.gpgsign', 'false')
        self.mission_done()
        self.assertEqual(self.state()['mission_base']['status'], 'empty')
        # .gitignore arrives with the same first commit, so it is outside the declared writes.
        report = self.gate(self.commit(), code=1)
        self.assertEqual(report['not_certified'][0]['paths'], ['.gitignore'])

    def test_workspace_in_a_subdirectory(self):
        nested = self.root / 'pkg'
        nested.mkdir()
        self.contract.write_text(json.dumps(self.data), encoding='utf-8')
        self.assertEqual(self.call('init', '--contract', str(self.contract), '--workspace', str(nested)).returncode, 0)
        self.assertEqual(self.call('start', '--step', 'one').returncode, 0)
        (nested / 'out.txt').write_text('x', encoding='utf-8')
        self.assertEqual(self.call('verify', '--step', 'one').returncode, 0)
        self.assertEqual(self.review().returncode, 0)
        self.assertEqual(self.call('finish').returncode, 0)
        self.assertEqual(self.call('goal-review', '--verdict', 'pass', '--rationale', 'ok').returncode, 0)
        self.gate(self.commit(), code=0)


class RevisionLineage(GateBase):
    def test_new_revision_keeps_the_base_and_open_observations(self):
        self.init()
        self.assertEqual(self.call('start', '--step', 'one').returncode, 0)
        self.write()
        self.write('other.txt')
        self.write('third.txt')
        self.assertEqual(self.call('verify', '--step', 'one').returncode, 0)
        self.git('commit', '-q', '--allow-empty', '-m', 'moved on')
        self.step['effects']['writes'] = ['out.txt', 'third.txt']
        self.contract.write_text(json.dumps(self.data), encoding='utf-8')
        destination = self.root / 'revised'
        result = self.call('revise', '--contract', str(self.contract), '--destination', str(destination), '--reason', 'Scope grew')
        self.assertEqual(result.returncode, 0, result.stderr)
        result = subprocess.run(['python3', str(ROOT / 'scripts/mission.py'), 'init', '--mission', str(destination),
                                 '--workspace', str(self.root)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        state = json.loads((destination / 'state/progress.json').read_text())
        self.assertEqual(state['mission_base']['commit'], self.base)
        self.assertEqual(list(state['scope_observations']), ['other.txt'])


class PrePushHook(GateBase):
    def setUp(self):
        super().setUp()
        self.remote = self.root / 'remote.git'
        subprocess.run(['git', 'init', '-q', '--bare', str(self.remote)], check=True)
        with (self.root / '.gitignore').open('a', encoding='utf-8') as stream:
            stream.write('remote.git/\n')
        self.git('add', '.gitignore')
        self.git('commit', '-q', '-m', 'ignore remote')
        self.git('remote', 'add', 'origin', str(self.remote))
        self.branch = self.git('rev-parse', '--abbrev-ref', 'HEAD')
        self.git('push', '-q', 'origin', self.branch)
        self.base = self.git('rev-parse', 'HEAD')
        hook = self.root / '.git/hooks/pre-push'
        shutil.copyfile(ROOT / 'templates/pre-push-gate.sh', hook)
        hook.chmod(hook.stat().st_mode | stat.S_IXUSR)
        self.environment = {'MISSION_PY': str(ROOT / 'scripts/mission.py'), 'MISSION_DIR': str(self.mission)}

    def push(self, *args, code=0):
        environment = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
        environment.update(self.environment)
        result = subprocess.run(['git', '-C', str(self.root), 'push', '-q', 'origin', *args],
                                capture_output=True, text=True, env=environment)
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        return result

    def remote_head(self, ref):
        result = subprocess.run(['git', '-C', str(self.remote), 'rev-parse', '-q', '--verify', ref],
                                capture_output=True, text=True)
        return result.stdout.strip()

    def test_certified_push_goes_through(self):
        self.mission_done()
        commit = self.commit()
        self.push(self.branch)
        self.assertEqual(self.remote_head(self.branch), commit)

    def test_uncertified_push_is_stopped(self):
        self.init()
        self.write()
        self.commit()
        self.push(self.branch, code=1)
        self.assertEqual(self.remote_head(self.branch), self.base)

    def test_no_mission_stops_the_push(self):
        self.write()
        self.commit()
        self.push(self.branch, code=1)
        self.assertEqual(self.remote_head(self.branch), self.base)

    def test_no_verify_bypasses_it_as_documented(self):
        self.write()
        commit = self.commit()
        self.push('--no-verify', self.branch)
        self.assertEqual(self.remote_head(self.branch), commit)

    def test_new_branch_is_checked(self):
        self.mission_done()
        commit = self.commit()
        self.push(self.branch + ':refs/heads/fresh')
        self.assertEqual(self.remote_head('refs/heads/fresh'), commit)

    def test_one_bad_ref_stops_all_refs(self):
        self.mission_done()
        good = self.commit()
        self.git('branch', 'good')
        self.write('other.txt')
        self.commit()
        self.push('good', self.branch, code=1)
        self.assertEqual(self.remote_head('refs/heads/good'), '')
        self.assertEqual(self.git('rev-parse', 'good'), good)

    def test_force_push_is_checked_and_warned(self):
        self.mission_done()
        commit = self.commit()
        self.git('commit', '-q', '--allow-empty', '-m', 'extra')
        self.push(self.branch)
        self.git('reset', '-q', '--hard', commit)
        result = self.push('--force', self.branch)
        self.assertIn('not a fast-forward', result.stderr)
        self.assertEqual(self.remote_head(self.branch), commit)

    def test_deleting_a_ref_is_not_certified_but_allowed(self):
        self.mission_done()
        self.commit()
        self.push(self.branch + ':refs/heads/gone')
        result = self.push(':refs/heads/gone')
        self.assertIn('nothing to certify', result.stderr)
        self.assertEqual(self.remote_head('refs/heads/gone'), '')

    def test_missing_configuration_stops_the_push(self):
        self.environment = {}
        self.write()
        self.commit()
        self.assertIn('MISSION_PY', self.push(self.branch, code=1).stderr)


class Guidance(GateBase):
    def test_next_action_names_an_open_observation_after_review(self):
        def work():
            self.write()
            self.write('other.txt')
        self.mission_done(work)
        report = json.loads(self.call('status').stdout)['next_action']
        self.assertEqual(report['action'], 'scope_note')
        self.assertEqual(report['argv'][:3], ['scope-note', '--path', 'other.txt'])

    def test_no_open_observation_reports_the_outcome(self):
        self.mission_done()
        self.assertEqual(json.loads(self.call('status').stdout)['next_action']['action'], 'report_outcome')


if __name__ == '__main__':
    unittest.main()
