"""The commit gate says what evidence covers a commit, and refuses to claim more."""
import json
import shutil
import unittest

from gate_fixture import GateBase


class MissionState(GateBase):
    def test_no_mission_is_not_certified(self):
        report = self.gate(self.base, code=1)
        self.assertEqual(self.reasons(report), {'no_mission'})
        self.assertFalse(report['certified'])

    def test_unfinished_mission(self):
        self.init()
        self.assertIn('not_done_verified', self.reasons(self.gate(self.base, code=1)))

    def test_goal_review_is_required(self):
        self.init()
        self.assertEqual(self.call('start', '--step', 'one').returncode, 0)
        self.write()
        self.assertEqual(self.call('verify', '--step', 'one').returncode, 0)
        self.assertEqual(self.review().returncode, 0)
        self.assertEqual(self.call('finish').returncode, 0)
        self.assertIn('goal_review_not_passed', self.reasons(self.gate(self.commit(), code=1)))

    def test_contract_without_discipline_is_not_certified(self):
        del self.data['discipline']
        del self.step['test_first_exempt']
        self.init()
        self.assertEqual(self.reasons(self.gate(self.base, code=1)), {'discipline_not_strict'})

    def test_corrupt_checkpoint_is_exit_two(self):
        self.mission_done()
        (self.mission / 'state/progress.json').write_text('{', encoding='utf-8')
        self.gate(self.commit(), code=2)

    def test_stale_coverage(self):
        self.mission_done()
        commit = self.commit()
        self.write(text='changed after review\n')
        self.assertIn('coverage_not_current', self.reasons(self.gate(commit, code=1)))

    def test_open_scope_observation_blocks_until_a_statement(self):
        def work():
            self.write()
            self.write('other.txt')
        self.mission_done(work)
        commit = self.commit('out.txt')
        report = self.gate(commit, code=1)
        self.assertIn('open_scope_observation', self.reasons(report))
        for disposition, code in (('unknown', 1), ('not_mine', None)):
            self.assertEqual(self.call('scope-note', '--path', 'other.txt', '--disposition', disposition,
                                       '--rationale', 'Inspected').returncode, 0)
            report = self.gate(commit)
            if code:
                self.assertIn('open_scope_observation', self.reasons(report))
        self.assertNotIn('open_scope_observation', self.reasons(report))

    def test_gate_changes_no_bytes(self):
        self.mission_done()
        commit = self.commit()
        path = self.mission / 'state/progress.json'
        before = path.read_bytes()
        index = (self.root / '.git/index').read_bytes()
        self.gate(commit, code=0)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual((self.root / '.git/index').read_bytes(), index)


class ScopeUnavailable(GateBase):
    def test_commit_gate_does_not_pass_or_claim_a_completed_check(self):
        self.mission_done()
        commit = self.commit()
        state = self.state()
        state['steps']['one']['scope_check'] = {'status': 'unavailable', 'reason': 'git failed', 'observed': []}
        self.rewrite(state)
        report = self.gate(commit, code=1)
        self.assertEqual(report['scope_check']['status'], 'not_performed')
        self.assertEqual(report['scope_check']['steps']['one'], 'git failed')
        self.assertIn('scope_check_not_performed', self.reasons(report))
        self.assertFalse(report['certified'])

    def test_without_git_says_only_mission_state_was_checked(self):
        shutil.rmtree(self.root / '.git')
        self.mission_done()
        report = self.gate(code=0)
        self.assertFalse(report['certified'])
        self.assertEqual(report['result'], 'mission_state_only')
        self.assertEqual(report['scope_check']['status'], 'not_performed')
        self.assertNotIn('passed', json.dumps(report['scope_check']))
        self.assertIn('commit_content', report['not_evaluated'])

    def test_commit_outside_git_is_exit_two(self):
        shutil.rmtree(self.root / '.git')
        self.mission_done()
        self.gate(self.base, code=2)


class Artifacts(GateBase):
    def test_same_content_committed_after_finish_passes(self):
        self.mission_done()
        report = self.gate(self.commit(), code=0)
        self.assertTrue(report['certified'])
        self.assertEqual(self.artifact(report)['result'], 'content_match')
        self.assertEqual(report['scope_check']['status'], 'performed')
        self.assertIn('who wrote', ' '.join(report['does_not_certify']))

    def test_changed_after_evidence_is_not_silently_certified(self):
        self.mission_done()
        first = self.commit()
        self.write(text='later\n')
        second = self.commit()
        self.write(text='content\n')
        self.gate(first, code=0)
        report = self.gate(second, code=1)
        self.assertEqual(self.artifact(report)['result'], 'content_mismatch')
        self.assertIn('filter', self.artifact(report)['detail'])

    def test_executable_bit_differs(self):
        self.mission_done()
        (self.root / 'out.txt').chmod(0o755)
        self.git('add', 'out.txt')
        self.git('commit', '-q', '-m', 'mode')
        commit = self.git('rev-parse', 'HEAD')
        (self.root / 'out.txt').chmod(0o644)
        self.assertEqual(self.artifact(self.gate(commit, code=1))['result'], 'content_mismatch')

    def test_oversized_blob_for_a_hash_receipt(self):
        self.mission_done()
        self.commit()
        self.write(text='x' * (1024 * 1024 + 1))
        big = self.commit(message='big')
        self.write(text='content\n')
        self.assertEqual(self.artifact(self.gate(big, code=1))['result'], 'unverified_oversized')

    def test_metadata_only_receipt_cannot_prove_content(self):
        self.step['verify'] = [['file', 'out.txt']]
        self.mission_done(lambda: self.write(text='x' * (1024 * 1024 + 1)))
        self.assertEqual(self.artifact(self.gate(self.commit(), code=1))['result'], 'unverified_metadata_only')

    def test_directory_receipt_cannot_prove_content(self):
        self.step['effects']['writes'] = ['out']
        self.step['verify'] = [['file', 'out/a.txt']]
        self.mission_done(lambda: self.write('out/a.txt'))
        report = self.gate(self.commit(), code=1)
        self.assertEqual(self.artifact(report, 'out')['result'], 'unverified_directory')

    def test_deletion_matches(self):
        path = self.write()
        self.commit()
        self.base = self.git('rev-parse', 'HEAD')
        self.step['verify'] = [['not_file', 'out.txt']]
        self.mission_done(path.unlink)
        report = self.gate(self.commit(), code=0)
        self.assertEqual(self.artifact(report)['result'], 'deletion_match')

    def test_recorded_absence_but_present_in_commit(self):
        path = self.write()
        self.commit()
        self.step['verify'] = [['not_file', 'out.txt']]
        self.mission_done(path.unlink)
        self.assertEqual(self.artifact(self.gate(self.git('rev-parse', 'HEAD'), code=1))['result'], 'content_mismatch')

    def test_untracked_artifact(self):
        self.mission_done()
        (self.root / 'x').write_text('x', encoding='utf-8')
        self.git('add', 'x')
        self.git('commit', '-q', '-m', 'not it')
        self.assertEqual(self.artifact(self.gate(self.git('rev-parse', 'HEAD'), code=1))['result'], 'not_in_commit')

    def test_ignored_artifact(self):
        with (self.root / '.gitignore').open('a', encoding='utf-8') as stream:
            stream.write('out.txt\n')
        self.git('add', '.gitignore')
        self.git('commit', '-q', '-m', 'ignore')
        self.mission_done()
        self.assertEqual(self.artifact(self.gate(self.git('rev-parse', 'HEAD'), code=1))['result'], 'ignored_not_in_commit')

    def test_symlink_in_commit_is_not_followed(self):
        self.mission_done()
        path = self.root / 'out.txt'
        path.unlink()
        path.symlink_to('elsewhere')
        commit = self.commit()
        path.unlink()
        self.write()
        self.assertEqual(self.artifact(self.gate(commit, code=1))['result'], 'unverified_symlink')

    def test_symlink_in_a_parent_path(self):
        self.step['effects']['writes'] = ['dir/out.txt']
        self.step['verify'] = [['file', 'dir/out.txt']]
        self.mission_done(lambda: self.write('dir/out.txt'))
        directory = self.root / 'dir'
        shutil.move(directory, self.root / 'real')
        directory.symlink_to('real')
        commit = self.commit()
        directory.unlink()
        shutil.move(self.root / 'real', directory)
        self.assertEqual(self.artifact(self.gate(commit, code=1), 'dir/out.txt')['result'], 'unverified_symlink')

    def test_gitlink_in_commit(self):
        self.mission_done()
        self.git('update-index', '--add', '--cacheinfo', '160000,' + self.base + ',out.txt')
        self.git('commit', '-q', '-m', 'gitlink')
        commit = self.git('rev-parse', 'HEAD')
        self.git('reset', '-q', '--hard', self.base)
        self.write()
        self.assertEqual(self.artifact(self.gate(commit, code=1))['result'], 'unverified_gitlink')

    def test_missing_receipt(self):
        self.mission_done()
        commit = self.commit()
        state = self.state()
        state['steps']['one'].pop('verified_artifacts')
        self.rewrite(state)
        self.assertEqual(self.artifact(self.gate(commit, code=1))['result'], 'missing_receipt')

    def test_declared_uncommitted_is_reported_not_certified(self):
        self.step['effects']['uncommitted'] = ['out.txt']
        with (self.root / '.gitignore').open('a', encoding='utf-8') as stream:
            stream.write('out.txt\n')
        self.git('add', '.gitignore')
        self.git('commit', '-q', '-m', 'ignore')
        self.mission_done()
        report = self.gate(self.git('rev-parse', 'HEAD'), code=0)
        self.assertEqual(self.artifact(report)['result'], 'out_of_commit_not_certified')
        self.assertIn('out.txt', report['out_of_commit_not_certified'])

    def test_declared_uncommitted_present_in_commit(self):
        self.step['effects']['uncommitted'] = ['out.txt']
        self.mission_done()
        self.assertEqual(self.artifact(self.gate(self.commit(), code=1))['result'], 'unexpected_in_commit')

    def test_uncommitted_must_be_a_declared_write(self):
        self.step['effects']['uncommitted'] = ['other.txt']
        self.assertEqual(self.validate_error()[0], 2)
        self.step['effects']['uncommitted'] = ['out.txt']
        del self.data['discipline']
        del self.step['test_first_exempt']
        self.assertEqual(self.validate_error()[0], 2)

    def test_latest_receipt_wins_across_steps(self):
        second = dict(self.step, id='two', depends_on=['one'], acceptance_refs=['AC-1'], verify=[['grep', 'second', 'out.txt']])
        self.data['steps'].append(second)
        self.init()
        for identifier, text in (('one', 'first\n'), ('two', 'second\n')):
            self.assertEqual(self.call('start', '--step', identifier).returncode, 0)
            self.write(text=text)
            self.assertEqual(self.call('verify', '--step', identifier).returncode, 0)
        commit = self.commit()
        report = self.gate(commit)
        self.assertEqual(self.artifact(report)['result'], 'content_match')


if __name__ == '__main__':
    unittest.main()
